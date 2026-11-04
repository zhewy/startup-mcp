from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent
DEFAULT_FIXTURE_ROOT = _PACKAGE_ROOT / "fixtures" / "default"
DEFAULT_CONTEXT_BUDGET_CHARS = 20_000


@dataclass(frozen=True)
class Config:
    fixture_root: Path = DEFAULT_FIXTURE_ROOT
    context_budget_chars: int = DEFAULT_CONTEXT_BUDGET_CHARS
    config_sources: Path | None = None
    config_cache: Path = Path.home() / ".zmcp" / "config-cache.json"

    @classmethod
    def from_env(cls) -> "Config":
        root = os.environ.get("ZMCP_FIXTURE_ROOT")
        budget = os.environ.get("ZMCP_CONTEXT_BUDGET_CHARS")
        return cls(
            fixture_root=Path(root) if root else DEFAULT_FIXTURE_ROOT,
            context_budget_chars=int(budget) if budget else DEFAULT_CONTEXT_BUDGET_CHARS,
            config_sources=Path(os.environ["ZMCP_CONFIG_SOURCES"]) if os.environ.get("ZMCP_CONFIG_SOURCES") else None,
            config_cache=Path(os.environ.get("ZMCP_CONFIG_CACHE", str(cls.config_cache))),
        )
