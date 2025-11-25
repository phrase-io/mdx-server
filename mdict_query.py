# -*- coding: utf-8 -*-
# version: python 3.5


from readmdict import MDX, MDD
from struct import pack, unpack
from io import BytesIO
import re
import sys
import os
import glob
import sqlite3
import json

# zlib compression is used for engine version >=2.0
import zlib
# LZO compression is used for engine version < 2.0
try:
    import lzo
except ImportError:
    lzo = None
    #print("LZO compression support is not available")

from multi_file_reader import open_binary

# 2x3 compatible
if sys.hexversion >= 0x03000000:
    unicode = str

version = '1.1'


class IndexBuilder(object):
    #todo: enable history
    def __init__(self, fname, encoding = "", passcode = None, force_rebuild = False, enable_history = False, sql_index = True, check = False):
        self._mdx_file = fname
        self._mdd_file = ""
        self._encoding = ''
        self._stylesheet = {}
        self._title = ''
        self._version = ''
        self._description = ''
        self._sql_index = sql_index
        self._check = check
        _filename, _file_extension = os.path.splitext(fname)
        assert(_file_extension == '.mdx')
        assert(os.path.isfile(fname))
        self._mdx_db = _filename + ".mdx.db"
        # make index anyway
        if force_rebuild:
            self._make_mdx_index(self._mdx_db)

        self._mdd_infos = []

        if os.path.isfile(self._mdx_db):
            #read from META table
            conn = sqlite3.connect(self._mdx_db)
            #cursor = conn.execute("SELECT * FROM META")
            cursor = conn.execute("SELECT * FROM META WHERE key = \"version\"")
            #判断有无版本号
            for cc in cursor:
                self._version = cc[1]
            ################# if not version in fo #############
            if not self._version:
                print("version info not found")
                conn.close()
                self._make_mdx_index(self._mdx_db)
                print("mdx.db rebuilt!")
                self._setup_mdd_indices(_filename, force_rebuild=True)
                self._finalize_mdd_attributes()
                if self._mdd_infos:
                    print("mdd db rebuilt!")
                return None
            cursor = conn.execute("SELECT * FROM META WHERE key = \"encoding\"")
            for cc in cursor:
                self._encoding = cc[1]
            cursor = conn.execute("SELECT * FROM META WHERE key = \"stylesheet\"")
            for cc in cursor:
                self._stylesheet = json.loads(cc[1])

            cursor = conn.execute("SELECT * FROM META WHERE key = \"title\"")
            for cc in cursor:
                self._title = cc[1]

            cursor = conn.execute("SELECT * FROM META WHERE key = \"description\"")
            for cc in cursor:
                self._description = cc[1]

            #for cc in cursor:
            #    if cc[0] == 'encoding':
            #        self._encoding = cc[1]
            #        continue
            #    if cc[0] == 'stylesheet':
            #        self._stylesheet = json.loads(cc[1])
            #        continue
            #    if cc[0] == 'title':
            #        self._title = cc[1]
            #        continue
            #    if cc[0] == 'title':
            #        self._description = cc[1]
        else:
            self._make_mdx_index(self._mdx_db)

        self._setup_mdd_indices(_filename, force_rebuild=force_rebuild)
        self._finalize_mdd_attributes()
        pass
    
    def _find_multipart_files(self, base_path):
        base_dir = os.path.dirname(base_path)
        base_name = os.path.basename(base_path)
        name_without_ext, _ = os.path.splitext(base_name)
        pattern_suffix = re.compile(re.escape(base_path) + r'\.(\d+)$')
        pattern_prefix = re.compile(re.escape(os.path.join(base_dir, name_without_ext)) + r'\.(\d+)\.mdd$')
        candidates = glob.glob(base_path + '.*') + glob.glob(os.path.join(base_dir, name_without_ext + '.*.mdd'))
        parts = []
        for path in candidates:
            match = pattern_suffix.match(path) or pattern_prefix.match(path)
            if match:
                parts.append((int(match.group(1)), path))
        parts.sort(key=lambda item: item[0])
        return [path for _, path in parts]

    def _setup_mdd_indices(self, filename, force_rebuild=False):
        base_mdd_path = filename + ".mdd"
        mdd_paths = []
        if os.path.isfile(base_mdd_path):
            mdd_paths.append(base_mdd_path)
        extra = self._find_multipart_files(base_mdd_path)
        for path in extra:
            if path not in mdd_paths:
                mdd_paths.append(path)
        for path in mdd_paths:
            db_path = path + ".db"
            if force_rebuild and os.path.isfile(db_path):
                os.remove(db_path)
            if not os.path.isfile(db_path):
                self._make_mdd_index(path, db_path)
            self._mdd_infos.append({'file': path, 'db': db_path})

    def _finalize_mdd_attributes(self):
        if self._mdd_infos:
            self._mdd_file = [info['file'] for info in self._mdd_infos]
            self._mdd_db = self._mdd_infos[0]['db']
        else:
            self._mdd_file = ""
            self._mdd_db = ""
    

    def _replace_stylesheet(self, txt):
        # substitute stylesheet definition
        txt_list = re.split('`\d+`', txt)
        txt_tag = re.findall('`\d+`', txt)
        txt_styled = txt_list[0]
        for j, p in enumerate(txt_list[1:]):
            style = self._stylesheet[txt_tag[j][1:-1]]
            if p and p[-1] == '\n':
                txt_styled = txt_styled + style[0] + p.rstrip() + style[1] + '\r\n'
            else:
                txt_styled = txt_styled + style[0] + p + style[1]
        return txt_styled

    def _make_mdx_index(self, db_name):
        if os.path.exists(db_name):
            os.remove(db_name)
        mdx = MDX(self._mdx_file)
        self._mdx_db = db_name
        returned_index = mdx.get_index(check_block = self._check)
        index_list = returned_index['index_dict_list']
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute(
            ''' CREATE TABLE MDX_INDEX
               (key_text text not null,
                file_pos integer,
                compressed_size integer,
                decompressed_size integer,
                record_block_type integer,
                record_start integer,
                record_end integer,
                offset integer
                )'''
        )

        tuple_list = [
            (item['key_text'],
                     item['file_pos'],
                     item['compressed_size'],
                     item['decompressed_size'],
                     item['record_block_type'],
                     item['record_start'],
                     item['record_end'],
                     item['offset']
                     )
            for item in index_list
            ]
        c.executemany('INSERT INTO MDX_INDEX VALUES (?,?,?,?,?,?,?,?)',
                      tuple_list)
        # build the metadata table
        meta = returned_index['meta']
        c.execute(
            '''CREATE TABLE META
               (key text,
                value text
                )''')

        #for k,v in meta:
        #    c.execute(
        #    'INSERT INTO META VALUES (?,?)', 
        #    (k, v)
        #    )
        
        c.executemany(
            'INSERT INTO META VALUES (?,?)', 
            [('encoding', meta['encoding']),
             ('stylesheet', meta['stylesheet']),
             ('title', meta['title']),
             ('description', meta['description']),
             ('version', version)
             ]
            )
        
        if self._sql_index:
            c.execute(
                '''
                CREATE INDEX key_index ON MDX_INDEX (key_text)
                '''
                )

        conn.commit()
        conn.close()
        #set class member
        self._encoding = meta['encoding']
        self._stylesheet = json.loads(meta['stylesheet'])
        self._title = meta['title']
        self._description = meta['description']

    def _make_mdd_index(self, mdd_path, db_name):
        if os.path.exists(db_name):
            os.remove(db_name)
        mdd = MDD(mdd_path)
        index_list = mdd.get_index(check_block = self._check)
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute(
            ''' CREATE TABLE MDX_INDEX
               (key_text text not null unique,
                file_pos integer,
                compressed_size integer,
                decompressed_size integer,
                record_block_type integer,
                record_start integer,
                record_end integer,
                offset integer
                )'''
        )

        tuple_list = [
            (item['key_text'],
                     item['file_pos'],
                     item['compressed_size'],
                     item['decompressed_size'],
                     item['record_block_type'],
                     item['record_start'],
                     item['record_end'],
                     item['offset']
                     )
            for item in index_list
            ]
        c.executemany('INSERT INTO MDX_INDEX VALUES (?,?,?,?,?,?,?,?)',
                      tuple_list)
        if self._sql_index:
            c.execute(
                '''
                CREATE UNIQUE INDEX key_index ON MDX_INDEX (key_text)
                '''
                )

        conn.commit()
        conn.close()

    def get_mdx_by_index(self, fmdx, index):
        fmdx.seek(index['file_pos'])
        record_block_compressed = fmdx.read(index['compressed_size'])
        record_block_type = record_block_compressed[:4]
        record_block_type = index['record_block_type']
        decompressed_size = index['decompressed_size']
        #adler32 = unpack('>I', record_block_compressed[4:8])[0]
        if record_block_type == 0:
            _record_block = record_block_compressed[8:]
            # lzo compression
        elif record_block_type == 1:
            if lzo is None:
                print("LZO compression is not supported")
                # decompress
            header = b'\xf0' + pack('>I', index['decompressed_size'])
            _record_block = lzo.decompress(record_block_compressed[8:], initSize = decompressed_size, blockSize=1308672)
                # zlib compression
        elif record_block_type == 2:
            # decompress
            _record_block = zlib.decompress(record_block_compressed[8:])
        record = _record_block[index['record_start'] - index['offset']:index['record_end'] - index['offset']]
        record = record = record.decode(self._encoding, errors='ignore').strip(u'\x00').encode('utf-8')
        if self._stylesheet:
            record = self._replace_stylesheet(record)
        record = record.decode('utf-8')
        return record

    def get_mdd_by_index(self, fmdx, index):
        fmdx.seek(index['file_pos'])
        record_block_compressed = fmdx.read(index['compressed_size'])
        record_block_type = record_block_compressed[:4]
        record_block_type = index['record_block_type']
        decompressed_size = index['decompressed_size']
        #adler32 = unpack('>I', record_block_compressed[4:8])[0]
        if record_block_type == 0:
            _record_block = record_block_compressed[8:]
            # lzo compression
        elif record_block_type == 1:
            if lzo is None:
                print("LZO compression is not supported")
                # decompress
            header = b'\xf0' + pack('>I', index['decompressed_size'])
            _record_block = lzo.decompress(record_block_compressed[8:], initSize = decompressed_size, blockSize=1308672)
                # zlib compression
        elif record_block_type == 2:
            # decompress
            _record_block = zlib.decompress(record_block_compressed[8:])
        data = _record_block[index['record_start'] - index['offset']:index['record_end'] - index['offset']]        
        return data

    def _rows_to_lookup(self, cursor, data_file, fetcher):
        lookup_result_list = []
        for result in cursor:
            index = {}
            index['file_pos'] = result[1]
            index['compressed_size'] = result[2]
            index['decompressed_size'] = result[3]
            index['record_block_type'] = result[4]
            index['record_start'] = result[5]
            index['record_end'] = result[6]
            index['offset'] = result[7]
            lookup_result_list.append(fetcher(data_file, index))
        return lookup_result_list

    def mdx_lookup(self, keyword):
        conn = sqlite3.connect(self._mdx_db)
        mdx_file = open(self._mdx_file,'rb')
        try:
            cursor = conn.execute("SELECT * FROM MDX_INDEX WHERE key_text = ?", (keyword,))
            lookup_result_list = self._rows_to_lookup(cursor, mdx_file, self.get_mdx_by_index)
        finally:
            mdx_file.close()
            conn.close()
        return lookup_result_list
	
    def mdd_lookup(self, keyword):
        if not self._mdd_infos:
            return []
        for info in self._mdd_infos:
            conn = sqlite3.connect(info['db'])
            mdd_file = open_binary(info['file'])
            try:
                for candidate in self._candidate_mdd_keys(keyword):
                    cursor = conn.execute("SELECT * FROM MDX_INDEX WHERE key_text = ? COLLATE NOCASE", (candidate,))
                    lookup_result_list = self._rows_to_lookup(cursor, mdd_file, self.get_mdd_by_index)
                    if lookup_result_list:
                        return lookup_result_list
                suffix = self._mdd_suffix(keyword)
                if suffix:
                    cursor = conn.execute("SELECT * FROM MDX_INDEX WHERE key_text LIKE ? COLLATE NOCASE", ('%' + suffix,))
                    lookup_result_list = self._rows_to_lookup(cursor, mdd_file, self.get_mdd_by_index)
                    if lookup_result_list:
                        return lookup_result_list
            finally:
                mdd_file.close()
                conn.close()
        return []

    def _candidate_mdd_keys(self, keyword):
        text = (keyword or '').strip()
        if not text:
            return []
        if text.lower().startswith('sound://'):
            text = text[8:]
        text = text.strip('/\\')
        normalized = text.replace('\\', '/')
        candidates = set()

        def add(path):
            if not path:
                return
            path = path.strip()
            if not path:
                return
            candidates.add(path)
            candidates.add(path.replace('/', '\\'))

        add(normalized)
        add('/' + normalized)
        add('\\' + normalized)

        def add_sound_variants(target):
            add('sound/' + target)
            add('\\sound\\' + target)
            add('/sound/' + target)

        if normalized.lower().startswith('sound/'):
            remainder = normalized[6:]
            add(remainder)
            add_sound_variants(remainder)
        else:
            add_sound_variants(normalized)

        filename = normalized.split('/')[-1]
        add(filename)
        add('/' + filename)
        add('\\' + filename)
        add_sound_variants(filename)

        return [c for c in candidates if c]

    def _mdd_suffix(self, keyword):
        normalized = (keyword or '').replace('\\', '/').strip('/')
        if not normalized:
            return ''
        return normalized.split('/')[-1]

    def get_mdd_keys(self, query = ''):
        if not self._mdd_infos:
            return []
        results = []
        for info in self._mdd_infos:
            conn = sqlite3.connect(info['db'])
            if query:
                local_query = query
                if '*' in local_query:
                    local_query = local_query.replace('*','%')
                else:
                    local_query = local_query + '%'
                cursor = conn.execute('SELECT key_text FROM MDX_INDEX WHERE key_text LIKE ?', (local_query,))
            else:
                cursor = conn.execute('SELECT key_text FROM MDX_INDEX')
            results.extend([item[0] for item in cursor])
            conn.close()
        return results

    def get_mdx_keys(self, query = ''):
        conn = sqlite3.connect(self._mdx_db)
        if query:
            if '*' in query:
                query = query.replace('*','%')
            else:
                query = query + '%'
            cursor = conn.execute('SELECT key_text FROM MDX_INDEX WHERE key_text LIKE \"' + query + '\"')
            keys = [item[0] for item in cursor]
        else:
            cursor = conn.execute('SELECT key_text FROM MDX_INDEX')
            keys = [item[0] for item in cursor]
        conn.close()
        return keys



# mdx_builder = IndexBuilder("oald.mdx")
# text = mdx_builder.mdx_lookup('dedication')
# keys = mdx_builder.get_mdx_keys()
# keys1 = mdx_builder.get_mdx_keys('abstrac')
# keys2 = mdx_builder.get_mdx_keys('*tion')
# for key in keys2:
    # text = mdx_builder.mdx_lookup(key)[0]
# pass
