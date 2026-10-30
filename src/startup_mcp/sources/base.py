from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    version: str
    fetched_at: str
    content: str
    mandatory: bool
    conflicts_with: tuple[str, ...] = field(default_factory=tuple)


class SourceProvider(Protocol):
    """A retrieval backend for Brain content.

    Phase 2 implements this against a local fixture tree (`FixtureSourceProvider`). Phase 3's
    live Google Drive backend implements the same protocol so `procedure.py` and `bundle.py`
    never need to change when the retrieval mechanism does.
    """

    def get_manifest(self) -> dict[str, Any]:
        """Return the current manifest: canonical version, mandatory source ids, topic index,
        role mapping, decision/continuity indexes, and governance data (e.g. write_authority)."""
        ...

    def get_source(self, source_id: str) -> SourceRecord | None:
        """Retrieve a single source by id, or None if it cannot currently be retrieved."""
        ...
