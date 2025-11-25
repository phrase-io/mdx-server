# -*- coding: utf-8 -*-
# version: python 3.5

import sys
import re
from file_util import *
from json_parser import parse_entry, to_json_bytes


def _normalize_html(html):
    html = html.replace("\r\n", "").replace("entry:/", "")
    html = re.sub(r'(?i)sound://', '/sound/', html)
    return html


def _lookup_entry_html(word, builder):
    if builder is None:
        return "", word
    search_word = word
    content = builder.mdx_lookup(search_word)
    if len(content) < 1:
        fp = os.popen('python lemma.py ' + word)
        lemma_word = fp.read().strip()
        fp.close()
        if lemma_word:
            print("lemma: " + lemma_word)
            search_word = lemma_word
            content = builder.mdx_lookup(search_word)
    pattern = re.compile(r"@@@LINK=([\\w\\s]*)")
    if content:
        rst = pattern.match(content[0])
        if rst is not None:
            link = rst.group(1).strip()
            search_word = link
            content = builder.mdx_lookup(link)
    str_content = ""
    if len(content) > 0:
        for c in content:
            str_content += _normalize_html(c)
    return str_content, search_word

def get_definition_mdx(word, builder):
    """根据关键字得到MDX词典的解释"""
    str_content, _ = _lookup_entry_html(word, builder)
    if not str_content:
        str_content = "<p>No entry found.</p>"
    injection = []
    injection_html = ''
    output_html = ''

    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # base_path = sys._MEIPASS
        base_path = os.path.dirname(sys.executable)
    except Exception:
        base_path = os.path.abspath(".")
            
    resource_path = os.path.join(base_path, 'mdx')

    file_util_get_files(resource_path, injection)

    for p in injection:
        if file_util_is_ext(p, 'html'):
            injection_html += file_util_read_text(p)

    output_html = str_content + injection_html
    return [output_html.encode('utf-8')]


def get_definition_json(word, builder):
    html_content, resolved = _lookup_entry_html(word, builder)
    active_word = resolved or word
    if not html_content:
        data = {'word': active_word, 'found': False}
    else:
        try:
            data = parse_entry(html_content, resolved_word=active_word)
            data.setdefault('word', active_word)
        except RuntimeError as exc:
            data = {'word': active_word, 'error': str(exc)}
    return [to_json_bytes(data)]

def get_definition_mdd(word, builder):
    """根据关键字得到MDX词典的媒体"""
    if builder is None:
        return []
    content = builder.mdd_lookup(word)
    if len(content) > 0:
        return [content[0]]
    else:
        return []
