# -*- coding: utf-8 -*-
# version: python 3.5

import sys
import re
import threading
import os
from collections import OrderedDict
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


class LRUCacheBytes(object):
    def __init__(self, max_bytes=1024 * 1024 * 512):  # default 512 MB
        self.max_bytes = max_bytes
        self.current_bytes = 0
        self.data = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key not in self.data:
                return None
            value = self.data.pop(key)
            self.data[key] = value
            return value

    def set(self, key, value):
        size = len(value)
        if size > self.max_bytes:
            return
        with self.lock:
            if key in self.data:
                old = self.data.pop(key)
                self.current_bytes -= len(old)
            self.data[key] = value
            self.current_bytes += size
            while self.current_bytes > self.max_bytes and self.data:
                _, evicted = self.data.popitem(last=False)
                self.current_bytes -= len(evicted)


CACHE_VERSION = 'json-v3'
json_cache = LRUCacheBytes(max_bytes=1024 * 1024 * 1024)  # 1GB

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


def _rewrite_media_urls(data, base):
    if not base:
        return data
    b = base.rstrip('/')
    def ra(v):
        if not v:
            return v
        if v.startswith(b + '/'):
            return v
        if v.startswith('/sound/'):
            return b + v
        fn = v.split('/')[-1]
        return b + '/sound/' + fn
    def ri(v):
        if not v:
            return v
        if v.startswith(b + '/'):
            return v
        fn = v.split('/')[-1]
        return b + '/img/' + fn
    prs = data.get('pronunciations') or []
    for p in prs:
        a = p.get('audio')
        if a:
            p['audio'] = ra(a)
    entries = data.get('entries') or []
    for e in entries:
        groups = e.get('groups') or []
        for g in groups:
            senses = g.get('senses') or []
            for s in senses:
                examples = s.get('examples') or []
                for ex in examples:
                    aud = ex.get('audio')
                    if aud:
                        ex['audio'] = [ra(x) for x in aud]
                imgs = s.get('images') or []
                for im in imgs:
                    th = im.get('thumbnail')
                    if th:
                        im['thumbnail'] = ri(th)
                    ig = im.get('image')
                    if ig:
                        im['image'] = ri(ig)
    return data

def get_definition_json(word, builder, media_prefix=None):
    cache_key = "{}:{}:{}".format(CACHE_VERSION, (media_prefix or 'none'), word.lower())
    cached = json_cache.get(cache_key)
    if cached is not None:
        return [cached]
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
    if media_prefix:
        data = _rewrite_media_urls(data, media_prefix)
    result = to_json_bytes(data)
    json_cache.set(cache_key, result)
    return [result]

def get_definition_mdd(word, builder):
    """根据关键字得到MDX词典的媒体"""
    if builder is None:
        return []
    content = builder.mdd_lookup(word)
    if len(content) > 0:
        return [content[0]]
    else:
        return []
