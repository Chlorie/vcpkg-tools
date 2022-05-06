from pathlib import Path
from .logging import error


class Portfile:
    def __init__(self, path: Path):
        self._path: Path = path
        self._content: str = path.read_text()
        self._repo: slice = slice(0, 0)
        self._ref: slice = slice(0, 0)
        self._sha512: slice = slice(0, 0)
        self._head_ref: slice = slice(0, 0)
        self._extract_values()

    @property
    def repo(self) -> str: return self._content[self._repo]

    @property
    def ref(self) -> str: return self._content[self._ref]

    @property
    def sha512(self) -> str: return self._content[self._sha512]

    @property
    def head_ref(self) -> str: return self._content[self._head_ref]

    @property
    def path(self) -> Path: return self._path

    @ref.setter
    def ref(self, value: str) -> None: self._replace_slice(self._ref, value)

    @sha512.setter
    def sha512(self, value: str) -> None: self._replace_slice(self._sha512, value)

    def save(self): self._path.write_text(self._content)

    def _replace_slice(self, slc: slice, value: str) -> None:
        self._content = "".join([
            self._content[:slc.start],
            value,
            self._content[slc.stop:]
        ])

    def _extract_values(self):
        func_start = self._content.find("vcpkg_from_github")
        if func_start == -1:
            error("The port is not from github")

        kv_begin = self._content.find('(', func_start)
        kv_end = self._content.find(')', kv_begin)
        if kv_begin == -1 or kv_end == -1:
            error("Syntax error in portfile")

        kvs = str.split(self._content[kv_begin + 1:kv_end])
        repo = kvs[kvs.index("REPO") + 1]
        ref = kvs[kvs.index("REF") + 1]
        sha512 = kvs[kvs.index("SHA512") + 1]
        head_ref = kvs[kvs.index("HEAD_REF") + 1]

        def find_slice(s: str) -> slice:
            return slice(
                self._content.find(s, kv_begin),
                self._content.find(s, kv_begin) + len(s)
            )

        self._repo = find_slice(repo)
        self._ref = find_slice(ref)
        self._sha512 = find_slice(sha512)
        self._head_ref = find_slice(head_ref)
