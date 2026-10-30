from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import SourceRecord


class FixtureSourceProvider:
    """Phase 2 stand-in for live Brain retrieval.

    Reads a manifest.json plus one JSON file per source from a local directory tree, structured
    identically in shape to what Phase 3's GoogleDriveSourceProvider will expose (manifest +
    per-source id lookup) so swapping providers doesn't require changing `procedure.py`.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._manifest = json.loads((self._root / "manifest.json").read_text())

    def get_manifest(self) -> dict[str, Any]:
        return self._manifest

    def get_source(self, source_id: str) -> SourceRecord | None:
        path = self._root / "sources" / f"{source_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return SourceRecord(
            source_id=data["id"],
            title=data["title"],
            version=data["version"],
            fetched_at=data["fetched_at"],
            content=data["content"],
            mandatory=bool(data.get("mandatory", False)),
            conflicts_with=tuple(data.get("conflicts_with", [])),
        )
