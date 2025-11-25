import bisect
import os


class MultiFileReader:
    """Provide a file-like object that concatenates multiple binary files."""

    def __init__(self, paths):
        if not paths:
            raise ValueError("paths must not be empty")
        self._paths = list(paths)
        self._files = []
        self._sizes = []
        self._offsets = []
        offset = 0
        for path in self._paths:
            fh = open(path, 'rb')
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(0, os.SEEK_SET)
            self._files.append(fh)
            self._sizes.append(size)
            self._offsets.append(offset)
            offset += size
        self._length = offset
        self._pos = 0
        self._current_index = 0
        self.name = "+".join(self._paths)

    def close(self):
        for fh in self._files:
            fh.close()

    def tell(self):
        return self._pos

    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            new_pos = offset
        elif whence == os.SEEK_CUR:
            new_pos = self._pos + offset
        elif whence == os.SEEK_END:
            new_pos = self._length + offset
        else:
            raise ValueError("invalid whence value: {}".format(whence))

        if new_pos < 0:
            raise ValueError("seek before start of file")
        if new_pos > self._length:
            new_pos = self._length

        self._pos = new_pos
        self._current_index = self._locate_index(self._pos)
        self._sync_current_handle()
        return self._pos

    def read(self, size=-1):
        if size is None or size < 0:
            size = self._length - self._pos
        if size == 0 or self._pos >= self._length:
            return b''

        remaining = size
        chunks = []
        while remaining > 0 and self._pos < self._length:
            fh = self._files[self._current_index]
            start = self._pos - self._offsets[self._current_index]
            fh.seek(start, os.SEEK_SET)
            available = self._sizes[self._current_index] - start
            to_read = min(remaining, available)
            data = fh.read(to_read)
            if not data:
                break
            chunks.append(data)
            read_len = len(data)
            self._pos += read_len
            remaining -= read_len
            if self._pos == self._offsets[self._current_index] + self._sizes[self._current_index]:
                if self._current_index < len(self._files) - 1:
                    self._current_index += 1
        return b''.join(chunks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _locate_index(self, position):
        if position >= self._length:
            return len(self._offsets) - 1
        idx = bisect.bisect_right(self._offsets, position) - 1
        if idx < 0:
            idx = 0
        return idx

    def _sync_current_handle(self):
        within = self._pos - self._offsets[self._current_index]
        within = max(0, min(within, self._sizes[self._current_index]))
        self._files[self._current_index].seek(within, os.SEEK_SET)


def open_binary(source):
    """Return a binary file handle for path string or multipart list."""
    if isinstance(source, MultiFileReader):
        return source
    if isinstance(source, (list, tuple)):
        return MultiFileReader(source)
    if hasattr(os, 'PathLike') and isinstance(source, os.PathLike):
        return open(os.fspath(source), 'rb')
    if isinstance(source, (str, bytes)):
        return open(source, 'rb')
    raise TypeError("unsupported source type: {}".format(type(source)))
