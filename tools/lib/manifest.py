"""The deployment manifest: everything this repo created, for safe reruns and guarded cleanup."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / ".state" / "manifest.json"


class ManifestError(RuntimeError):
    pass


class Manifest:
    def __init__(self, path: Path, data: dict[str, Any]):
        self.path, self.data = Path(path), data

    @classmethod
    def load(cls, path: Path = DEFAULT_MANIFEST) -> "Manifest":
        path = Path(path)
        if not path.exists():
            return cls(path, {"version": 1, "runs": []})
        data = json.loads(path.read_text())
        if data.get("version") != 1:
            raise ManifestError(f"{path}: unsupported manifest version {data.get('version')!r}")
        return cls(path, data)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".manifest-", suffix=".json")
        with os.fdopen(fd, "w") as handle:
            json.dump(self.data, handle, indent=2, sort_keys=True, default=str)
            handle.write("\n")
        os.replace(tmp, self.path)

    def bind(self, target: str, profile: str, host: str) -> None:
        """Pin the manifest to one target, profile, and workspace; refuse to mix deployments."""
        for key, value in (("target", target), ("profile", profile), ("host", host)):
            recorded = self.data.get(key)
            if recorded is not None and recorded != value:
                raise ManifestError(f"{self.path} records {key}={recorded!r}, not {value!r}; use a separate --state file")
            self.data[key] = value

    def record_run(self, **fields: Any) -> None:
        self.data.setdefault("runs", []).append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields})
