import json
from pathlib import Path
from typing import Any


class Manifest:
    def __init__(self, manifest_json: Any):
        self._manifest_json: Any = manifest_json
        version_keys = ["version", "version-semver", "version-date", "version-string"]
        self._port_version: int = 0
        for k, v in self._manifest_json.items():
            if k in version_keys:
                self._version_type: str = k
                self._version: str = v
            if k == "port-version":
                self._port_version = v

    @property
    def version_type(self) -> str: return self._version_type

    @property
    def version(self) -> str: return self._version

    @property
    def port_version(self) -> int: return self._port_version

    @property
    def version_repr(self) -> str:
        if self._port_version != 0:
            return f"{self._version}#{self._port_version}"
        return self._version

    def write(self, path: Path):
        path.write_text(json.dumps(self._manifest_json, indent=4))
