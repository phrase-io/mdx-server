import json
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup, NavigableString
except ImportError:  # pragma: no cover - optional dependency
    BeautifulSoup = None
    NavigableString = None


def _text(tag):
    if not tag:
        return ''
    return ' '.join(tag.stripped_strings)


def _text_excluding(tag, excluded=None):
    if not tag:
        return ''
    excluded = excluded or {'chn', 'chnsep'}
    parts = []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            parent = node.parent
            if parent and parent.name in excluded:
                continue
            value = str(node).strip()
            if value:
                parts.append(value)
    return ' '.join(parts).strip()


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


def _collect_pronunciations(root):
    pronunciations = []
    if not root:
        return pronunciations
    pron_tag = root.find('pron-gs') or root.find('pron')
    if not pron_tag:
        return pronunciations
    for block in pron_tag.find_all('pron-g-blk', recursive=False):
        label = block.find('brelabel') or block.find('namelabel') or block.find('label')
        region = _text(label) or None
        phon = block.find('phon')
        audio_link = None
        link = block.find('a', href=True)
        if link and '/sound/' in link['href']:
            audio_link = _normalize_media_url(link['href'])
        entry = {
            'region': region,
            'ipa': _text(phon) or None,
            'audio': audio_link
        }
        entry = {k: v for k, v in entry.items() if v}
        if entry:
            pronunciations.append(entry)
    return pronunciations


def _extract_use_notes(sn_tag):
    notes = []
    for use_blk in sn_tag.find_all('use-blk', recursive=False):
        payload = use_blk.find('use') or use_blk
        text = _text_excluding(payload)
        translation = _text(payload.find('chn')) if payload else None
        entry = {}
        if text:
            entry['text'] = text
        if translation:
            entry['translation'] = translation
        if entry:
            notes.append(entry)
    return notes


def _extract_patterns(sn_tag):
    patterns = []
    for cf_blk in sn_tag.find_all('cf-blk', recursive=False):
        cf = cf_blk.find('cf')
        if not cf:
            continue
        entry = {'pattern': _text_excluding(cf)}
        translation = _text(cf.find('chn'))
        if translation:
            entry['translation'] = translation
        if entry.get('pattern'):
            patterns.append(entry)
    return patterns


def _block_in_sense(block, sn_tag):
    parent = block
    while parent:
        if parent is sn_tag:
            return True
        if parent.name == 'unbox':
            return False
        parent = parent.parent
    return False


def _extract_examples(sn_tag):
    examples = []
    for blk in sn_tag.find_all('x-g-blk'):
        if not _block_in_sense(blk, sn_tag):
            continue
        x_tag = blk.find('x')
        if not x_tag:
            continue
        example = {'text': _text_excluding(x_tag)}
        translation = _text(x_tag.find('chn'))
        if translation:
            example['translation'] = translation
        audio_links = []
        audio_wrapper = blk.find('audio-wr')
        if audio_wrapper:
            for anchor in audio_wrapper.find_all('a', href=True):
                normalized = _normalize_media_url(anchor['href'])
                if normalized:
                    audio_links.append(normalized)
        if audio_links:
            example['audio'] = audio_links
        cf = blk.find('cf')
        if cf:
            example['pattern'] = _text_excluding(cf)
        example = {k: v for k, v in example.items() if v}
        if example:
            examples.append(example)
    return examples


def _extract_labels(sn_tag):
    labels = []
    gram = sn_tag.find('gram-g')
    if gram:
        labels.append({'type': 'grammar', 'text': _text_excluding(gram)})
    for label in sn_tag.find_all('label-g-blk', recursive=False):
        labels.append({'type': 'label', 'text': _text_excluding(label)})
    for reg in sn_tag.find_all('reg', recursive=False):
        labels.append({'type': 'register', 'text': _text_excluding(reg)})
    return [label for label in labels if label.get('text')]


def _extract_topics(sn_tag):
    topics = []
    for topic in sn_tag.find_all('topic', recursive=False):
        level = [topic.get('l1'), topic.get('l2'), topic.get('l3')]
        values = [item for item in level if item]
        if values:
            topics.append(values)
    return topics


def _extract_help_entries(sn_tag):
    entries = []
    for helper in sn_tag.find_all('un', {'un': 'help'}):
        entry = {'label': 'HELP', 'text': _text_excluding(helper, excluded={'chn', 'chnsep', 'boxtag'})}
        translation = _text(helper.find('chn'))
        if translation:
            entry['translation'] = translation
        entry = {k: v for k, v in entry.items() if v}
        if entry:
            entries.append(entry)
    return entries


def _parse_collocation_items(unbox):
    items = []
    if not unbox:
        return items
    for li in unbox.find_all('li'):
        und = li.find('und') or li
        pattern = _text_excluding(und)
        translation = _text(und.find('chn'))
        entry = {}
        if pattern:
            entry['pattern'] = pattern
        if translation:
            entry['translation'] = translation
        if entry:
            items.append(entry)
    return items


def _extract_collocations(sn_tag):
    collocations = []
    for box in sn_tag.find_all('unbox', {'type': 'colloc'}):
        base_entry = {}
        label = box.find('utitle')
        title = _text_excluding(label)
        if title:
            base_entry['title'] = title
        translation = _text(label.find('chn')) if label else None
        if translation:
            base_entry['translation'] = translation
        sections = []
        section_map = {}
        default_key = object()

        def ensure_section(heading):
            key = heading if heading is not None else default_key
            entry = section_map.get(key)
            if entry:
                return entry
            entry = dict(base_entry)
            if heading is not None:
                subtitle = _text_excluding(heading)
                if subtitle:
                    entry['subtitle'] = subtitle
                subtitle_tr = _text(heading.find('chn'))
                if subtitle_tr:
                    entry['subtitle_translation'] = subtitle_tr
            section_map[key] = entry
            sections.append(entry)
            return entry

        for ul in box.find_all('ul'):
            if ul.find_parent('unbox', {'type': 'colloc'}) is not box:
                continue
            heading = ul.find_previous('h2')
            while heading and heading.find_parent('unbox', {'type': 'colloc'}) is not box:
                heading = heading.find_previous('h2')
            entry = ensure_section(heading)
            items = _parse_collocation_items(ul)
            if items:
                entry.setdefault('items', []).extend(items)

        if sections:
            for entry in sections:
                entry = {k: v for k, v in entry.items() if v}
                if entry.get('items'):
                    collocations.append(entry)
            continue

        entry = dict(base_entry)
        heading = box.find('h2')
        if heading:
            subtitle = _text_excluding(heading)
            if subtitle:
                entry['subtitle'] = subtitle
            subtitle_tr = _text(heading.find('chn'))
            if subtitle_tr:
                entry['subtitle_translation'] = subtitle_tr
        items = _parse_collocation_items(box)
        if items:
            entry['items'] = items
        entry = {k: v for k, v in entry.items() if v}
        if entry.get('items'):
            collocations.append(entry)
    return collocations


def _normalize_image_src(img):
    if not img:
        return None
    return _normalize_media_url(img.get('src'))


def _extract_illustrations(sn_tag):
    illustrations = []
    for ill in sn_tag.find_all('ill-g', recursive=False):
        caption_tag = ill.find('ill-txt')
        caption = _text_excluding(caption_tag) if caption_tag else None
        figures = []
        for pic in ill.find_all('div', class_='pic'):
            thumb_div = pic.find('div', class_='pic_thumb')
            big_div = pic.find('div', class_='big_pic')
            entry = {}
            thumb_img = thumb_div.find('img') if thumb_div else None
            big_img = big_div.find('img') if big_div else None
            if thumb_img:
                entry['thumbnail'] = _normalize_image_src(thumb_img)
            if big_img:
                entry['image'] = _normalize_image_src(big_img)
            if not entry:
                img = pic.find('img')
                if img:
                    entry['image'] = _normalize_image_src(img)
            if entry:
                figures.append(entry)
        if not figures:
            for img in ill.find_all('img'):
                path = _normalize_image_src(img)
                if path:
                    entry = {'image': path}
                    if img.get('alt'):
                        entry['alt'] = img.get('alt')
                    figures.append(entry)
        if figures:
            if caption:
                for entry in figures:
                    entry.setdefault('caption', caption)
            illustrations.extend(figures)
    return illustrations


def _parse_sense(sn_tag):
    definition_tag = sn_tag.find('def')
    if not definition_tag:
        return None
    sense = {}
    if sn_tag.get('eid'):
        sense['id'] = sn_tag.get('eid')
    sense['definition'] = _text_excluding(definition_tag)
    translation = _text(definition_tag.find('chn'))
    if translation:
        sense['translation'] = translation
    notes = _extract_use_notes(sn_tag)
    if notes:
        sense['notes'] = notes
    patterns = _extract_patterns(sn_tag)
    if patterns:
        sense['patterns'] = patterns
    labels = _extract_labels(sn_tag)
    if labels:
        sense['labels'] = labels
    topics = _extract_topics(sn_tag)
    if topics:
        sense['topics'] = topics
    examples = _extract_examples(sn_tag)
    if examples:
        sense['examples'] = examples
    help_entries = _extract_help_entries(sn_tag)
    if help_entries:
        sense['helps'] = help_entries
    collocations = _extract_collocations(sn_tag)
    if collocations:
        sense['collocations'] = collocations
    images = _extract_illustrations(sn_tag)
    if images:
        sense['images'] = images
    return sense


def _parse_usage_boxes(sn_group):
    notes = []
    for box in sn_group.find_all('unbox'):
        if box.get('type') == 'colloc':
            continue
        data = {}
        label = _text_excluding(box.find('utitle'))
        if label:
            data['label'] = label
        header = box.find('h2') or box.find('h1')
        title = _text_excluding(header)
        if title:
            data['title'] = title
        translation = _text(header.find('chn')) if header else None
        if translation:
            data['translation'] = translation
        entries = []
        for x_block in box.find_all('x'):
            entry = {'text': _text_excluding(x_block)}
            translation = _text(x_block.find('chn'))
            if translation:
                entry['translation'] = translation
            entry = {k: v for k, v in entry.items() if v}
            if entry:
                entries.append(entry)
        if entries:
            data['entries'] = entries
        data = {k: v for k, v in data.items() if v}
        if data:
            notes.append(data)
    return notes


def _parse_highlight_lists(sn_group):
    lists = []
    for body in sn_group.find_all('span', class_='body'):
        entry = {}
        title_tag = body.find(class_='h1') or body.find('h1')
        title = _text_excluding(title_tag)
        if title:
            entry['title'] = title
        translation = _text(title_tag.find('chn')) if title_tag else None
        if translation:
            entry['translation'] = translation
        items = []
        inline = body.find(class_='inline') or body
        for item in inline.find_all('span', class_='li'):
            value = _text(item)
            if value:
                items.append(value)
        if items:
            entry['items'] = items
        entry = {k: v for k, v in entry.items() if v}
        if entry:
            lists.append(entry)
    return lists


def _parse_sn_group(sn_group):
    result = {}
    guide = sn_group.find('shcut')
    if guide:
        guideword = _text_excluding(guide)
        if guideword:
            result['guideword'] = guideword
        translation = _text(guide.find('chn'))
        if translation:
            result['translation'] = translation
    senses = []
    for sn_tag in sn_group.find_all('sn-g'):
        if sn_tag.find_parent('idm-g'):
            continue
        sense = _parse_sense(sn_tag)
        if sense:
            senses.append(sense)
    if senses:
        result['senses'] = senses
    usage_notes = _parse_usage_boxes(sn_group)
    if usage_notes:
        result['usage_notes'] = usage_notes
    highlight_lists = _parse_highlight_lists(sn_group)
    if highlight_lists:
        result['highlight_lists'] = highlight_lists
    return result


def _parse_forms(section):
    forms = []
    resg = section.find('res-g')
    if resg:
        vpforms = resg.find_all('vpform')
        vpgs = resg.find_all('vp-g')
        for label_tag, value_tag in zip(vpforms, vpgs):
            label = _text(label_tag)
            vp = value_tag.find('vp')
            value = _text(vp)
            if label and value:
                forms.append({'label': label, 'value': value})
    comp_block = section.find('if-gs-blk')
    if comp_block:
        items = []
        for if_tag in comp_block.find_all('if'):
            value = _text(if_tag)
            if value:
                items.append(value)
        if items:
            forms.append({'label': 'comparison', 'value': items})
    return forms


def _parse_idioms(block):
    idioms = []
    if not block:
        return idioms
    for idm in block.find_all('idm-g'):
        entry = {'text': _text_excluding(idm.find('idm'))}
        sn_tag = idm.find('sn-g')
        if sn_tag:
            sense = _parse_sense(sn_tag)
            if sense:
                definition = sense.get('definition')
                if definition:
                    entry['definition'] = definition
                translation = sense.get('translation')
                if translation:
                    entry['translation'] = translation
                if sense.get('examples'):
                    entry['examples'] = sense['examples']
                if sense.get('helps'):
                    entry['helps'] = sense['helps']
        entry = {k: v for k, v in entry.items() if v}
        if entry:
            idioms.append(entry)
    return idioms


def _parse_pos_section(section):
    entry = {}
    pos_value = section.get('id')
    if not pos_value:
        pos_tag = section.find('pos')
        pos_value = _text(pos_tag) if pos_tag else None
    if pos_value:
        entry['pos'] = pos_value
    forms = _parse_forms(section)
    if forms:
        entry['forms'] = forms
    group_nodes = section.select('subentry-g > sn-gs')
    if not group_nodes:
        group_nodes = [
            node for node in section.find_all('sn-gs')
            if not node.find_parent('idm-g')
        ]
    groups = []
    for sn_group in group_nodes:
        data = _parse_sn_group(sn_group)
        if data:
            groups.append(data)
    if groups:
        entry['groups'] = groups
    idioms = _parse_idioms(section.find('idm-gs-blk'))
    if idioms:
        entry['idioms'] = idioms
    entry = {k: v for k, v in entry.items() if v}
    if len(entry) > 1:
        return entry
    return None


def parse_entry(html, resolved_word=None):
    if BeautifulSoup is None:
        raise RuntimeError('beautifulsoup4 is required for JSON parsing. Please install bs4.')
    soup = BeautifulSoup(html, 'html.parser')
    headword = soup.find('h')
    sections = soup.select('div.cixing_part')
    if not sections:
        sections = soup.find_all('h-g')
    if not sections:
        sections = [soup]
    entries = []
    for section in sections:
        data = _parse_pos_section(section)
        if data:
            entries.append(data)
    pronunciations = _collect_pronunciations(soup.select_one('div.cixing_part') or soup)
    result = {
        'word': resolved_word or (headword.get_text(strip=True) if headword else None),
        'pronunciations': pronunciations,
        'entries': entries
    }
    return {k: v for k, v in result.items() if v}


def to_json_bytes(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
