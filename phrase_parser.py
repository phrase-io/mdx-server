"""短语（习语 / 短语动词）查询：给短语页用。

牛津 mdx 里每个习语、短语动词都有自己的词头（take care、give up、kick the bucket），
内容是一个 <idm-g> / <pv-g> 块，或者一条 @@@LINK= 跳转。这里把同一个短语的所有块找齐，
解析出义项、语体标签（口语、俚语、英式……）和例句，再从所属词条里取同族短语当「相关短语」。
"""
import re

from json_parser import BeautifulSoup, _parse_sense, _text_excluding, normalize_html

_LINK = re.compile(r"@@@LINK=(.+)")
_STRESS = re.compile(r"[ˈˌ]")
_SPACES = re.compile(r"\s+")
_MAX_LINK_HOPS = 3
_MAX_RELATED = 12
_BLOCK_TAGS = {"idm-g": ("idiom", "idm"), "pv-g": ("phrasal_verb", "pv")}


def normalize_phrase(value):
    """小写、去重读符号、合并空白、统一撇号，用来比对「同一个短语」。"""
    text = _STRESS.sub("", value or "").replace("’", "'").lower()
    return _SPACES.sub(" ", text).strip(" !?.")


def _tidy(text):
    """牛津原文按词拆开，标点前会多一个空格：「Bye ! Take care !」→「Bye! Take care!」。"""
    text = re.sub(r"\s+([,.!?;:)…’'])", r"\1", text or "")
    return re.sub(r"([(‘])\s+", r"\1", text).strip()


def _tidy_sense(sense):
    for key in ("definition", "translation"):
        if sense.get(key):
            sense[key] = _tidy(sense[key])
    for ex in sense.get("examples") or []:
        ex["text"] = _tidy(ex.get("text"))
    return sense


def _display(tag):
    text = _STRESS.sub("", _text_excluding(tag)).replace("↔", " ")
    text = re.sub(r"\s+([,.!?)…])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    return _SPACES.sub(" ", text).strip()


def _structured_labels(blocks):
    labels = []
    for blk in blocks:
        for reg in blk.find_all("reg"):
            labels.append({"type": "register", "text": _text_excluding(reg)})
        for geo in blk.find_all("geo"):
            labels.append({"type": "geo", "text": _text_excluding(geo)})
    seen, unique = set(), []
    for label in labels:
        key = (label["type"], label["text"])
        if label["text"] and key not in seen:
            seen.add(key)
            unique.append(label)
    return unique


def _own(block, tags):
    """只要属于这个块自己的元素：短语动词里常嵌着别的习语（grow up 里嵌着 great oaks from little acorns grow），
    嵌套块的义项和标签不能算到外层头上。"""
    return [tag for tag in block.find_all(tags) if tag.find_parent(list(_BLOCK_TAGS)) is block]


def _block_labels(block):
    """块级标签：习语 / 短语动词本身的语体（reg）和地区（geo），不含义项内的。"""
    top = block.find("top-g") or block
    return _structured_labels(blk for blk in _own(top, "label-g-blk") if not blk.find_parent("sn-g"))


def _sense_labels(sn):
    """义项自己的语体和地区（牛津常把 informal 写在义项上，而不是习语头上）。"""
    return _structured_labels(sn.find_all("label-g-blk", recursive=False))


def _parse_block(block):
    kind, head_tag = _BLOCK_TAGS[block.name]
    head = block.find(head_tag)
    if not head:
        return None
    senses = []
    for sn in _own(block, "sn-g"):
        sense = _parse_sense(sn)
        if sense:
            sense.pop("id", None)
            sense["register"] = _sense_labels(sn)
            senses.append(_tidy_sense(sense))
    if not senses:
        return None
    eid = block.get("eid") or ""
    return {
        "kind": kind,
        "display": _display(head),
        "headword": eid.split("_")[0] if "_" in eid else None,
        "labels": _block_labels(block),
        "senses": senses,
    }


def _collect_html(word, builder, hops=0):
    """查词头，跟随所有 @@@LINK=（一个短语常常一条是正文、一条是跳转）。"""
    pages = []
    for content in builder.mdx_lookup(word):
        link = _LINK.match(content.strip())
        if link:
            if hops < _MAX_LINK_HOPS:
                pages.extend(_collect_html(link.group(1).strip(), builder, hops + 1))
        else:
            pages.append(normalize_html(content))
    return pages


def _blocks_in(html):
    soup = BeautifulSoup(html, "html.parser")
    return [block for block in soup.find_all(list(_BLOCK_TAGS)) if block.find(_BLOCK_TAGS[block.name][1])]


def _related(headword, builder, exclude):
    """同一词条下的其他习语和短语动词，作为站内「相关短语」。"""
    related, seen = [], set(exclude)
    for html in _collect_html(headword, builder):
        for block in _blocks_in(html):
            head = block.find(_BLOCK_TAGS[block.name][1])
            display = _display(head)
            key = normalize_phrase(display)
            if not key or key in seen or " " not in key:
                continue
            seen.add(key)
            related.append({"kind": _BLOCK_TAGS[block.name][0], "display": display})
            if len(related) >= _MAX_RELATED:
                return related
    return related


def lookup_phrase(phrase, builder):
    """返回 {phrase, found, blocks, related}。blocks 按词典顺序，同一短语的多个义项块都在。"""
    query = normalize_phrase(phrase)
    if not query or builder is None or BeautifulSoup is None:
        return {"phrase": query, "found": False, "blocks": [], "related": []}
    blocks, seen = [], set()
    wanted = set(query.split())
    for html in _collect_html(query, builder):
        for block in _blocks_in(html):
            parsed = _parse_block(block)
            if not parsed:
                continue
            # 同一页里还会有别的短语（grow up 页里嵌着 great oaks … grow）：写法里要包含查询的全部单词
            if not wanted <= set(re.findall(r"[a-z']+", normalize_phrase(parsed["display"]))):
                continue
            key = (parsed["display"], tuple(s.get("definition") for s in parsed["senses"]))
            if key in seen:
                continue
            seen.add(key)
            blocks.append(parsed)
    headwords = []
    for block in blocks:
        if block["headword"] and block["headword"] not in headwords:
            headwords.append(block["headword"])
    exclude = {query} | {normalize_phrase(block["display"]) for block in blocks}
    related = _related(headwords[0], builder, exclude) if headwords else []
    return {"phrase": query, "found": bool(blocks), "blocks": blocks, "related": related}
