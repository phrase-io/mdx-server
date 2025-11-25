import json
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency
    BeautifulSoup = None


def _text(tag):
    if not tag:
        return ''
    return ' '.join(tag.stripped_strings)


def _normalize_media_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme in ('http', 'https'):
        return parsed.path or '/'
    value = value.strip()
    if value.startswith('./'):
        value = value[1:]
    if not value.startswith('/'):
        value = '/' + value
    return value


def _extract_pronunciations(soup):
    pronunciations = []
    pron_tag = soup.find('pron')
    if not pron_tag:
        return pronunciations
    for block in pron_tag.find_all('pron-g-blk', recursive=False):
        region = None
        label = block.find('brelabel') or block.find('namelabel') or block.find('label-g')
        region = _text(label)
        phon = block.find('phon')
        audio_link = None
        link = block.find('a', href=True)
        if link and '/sound/' in link['href']:
            audio_link = _normalize_media_url(link['href'])
        pronunciations.append({
            'region': region or None,
            'ipa': _text(phon) or None,
            'audio': audio_link
        })
    return [p for p in pronunciations if p.get('ipa') or p.get('audio')]


def _extract_examples(sn):
    examples = []
    for xgs in sn.find_all('x-gs', recursive=False):
        for blk in xgs.find_all('x-g-blk', recursive=False):
            x_tag = blk.find('x')
            if not x_tag:
                continue
            example = {'text': _text(x_tag)}
            chn = x_tag.find('chn')
            if chn:
                example['translation'] = _text(chn)
            audios = []
            audio_wrapper = blk.find('audio-wr')
            if audio_wrapper:
                for a in audio_wrapper.find_all('a', href=True):
                    path = _normalize_media_url(a['href'])
                    if path:
                        audios.append(path)
            if audios:
                example['audio'] = audios
            examples.append(example)
    return examples


def _extract_topics(sn):
    topics = []
    for topic in sn.find_all('topic', recursive=False):
        level = [topic.get('l1'), topic.get('l2'), topic.get('l3')]
        topics.append([t for t in level if t])
    return [t for t in topics if t]


def _extract_labels(sn):
    labels = []
    for gram in sn.find_all('gram', recursive=False):
        labels.append(_text(gram))
    for label in sn.find_all('label-g', recursive=False):
        labels.append(_text(label))
    return [l for l in labels if l]


def _parse_sense(sn):
    definition_tag = sn.find('def')
    if not definition_tag:
        return None
    definition = _text(definition_tag)
    translation = None
    chn = definition_tag.find('chn')
    if chn:
        translation = _text(chn)
    sense = {
        'definition': definition,
        'translation': translation,
        'labels': _extract_labels(sn),
        'topics': _extract_topics(sn),
        'examples': _extract_examples(sn)
    }
    sense = {k: v for k, v in sense.items() if v}
    return sense


def _extract_parts(soup):
    parts = []
    for sub in soup.find_all('subentry-g'):
        pos_tag = sub.find('pos')
        part = {'pos': _text(pos_tag)} if pos_tag else {}
        senses = []
        for sngs in sub.find_all('sn-gs', recursive=False):
            for sn in sngs.find_all('sn-g'):
                sense = _parse_sense(sn)
                if sense:
                    senses.append(sense)
        if senses:
            part['senses'] = senses
            parts.append(part)
    return parts


def _extract_idioms(soup):
    idioms = []
    for idm_g in soup.find_all('idm-g'):
        name = _text(idm_g.find('idm'))
        def_tag = idm_g.find('def')
        definition = _text(def_tag)
        translation = None
        if def_tag:
            chn = def_tag.find('chn')
            if chn:
                translation = _text(chn)
        if name:
            entry = {'text': name, 'definition': definition}
            if translation:
                entry['translation'] = translation
            idioms.append(entry)
    return idioms


def _extract_phrasal_verbs(soup):
    phrases = []
    for pv in soup.find_all('pv'):
        text = _text(pv)
        if not text:
            continue
        parent = pv.find_parent('pv-g') or pv.find_parent('pv-blk')
        def_tag = parent.find('def') if parent else None
        entry = {'text': text}
        if def_tag:
            entry['definition'] = _text(def_tag)
            chn = def_tag.find('chn')
            if chn:
                entry['translation'] = _text(chn)
        phrases.append(entry)
    return phrases


def _extract_images(soup):
    images = []
    for img in soup.find_all('img'):
        src = _normalize_media_url(img.get('src'))
        if src:
            images.append({'src': src, 'alt': img.get('alt')})
    return images


def _extract_related(soup):
    related = []
    for xr in soup.find_all('xr-g'):
        link = xr.find('a', href=True)
        if not link:
            continue
        related.append({'title': _text(link), 'href': link['href']})
    return related


def parse_entry(html, resolved_word=None):
    if BeautifulSoup is None:
        raise RuntimeError('beautifulsoup4 is required for JSON parsing. Please install bs4.')
    soup = BeautifulSoup(html, 'html.parser')
    top_heading = soup.find('h')
    result = {
        'word': resolved_word or (top_heading.get_text(strip=True) if top_heading else None),
        'pronunciations': _extract_pronunciations(soup),
        'parts': _extract_parts(soup),
        'phrasal_verbs': _extract_phrasal_verbs(soup),
        'idioms': _extract_idioms(soup),
        'images': _extract_images(soup),
        'related': _extract_related(soup)
    }
    return {k: v for k, v in result.items() if v}


def to_json_bytes(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
