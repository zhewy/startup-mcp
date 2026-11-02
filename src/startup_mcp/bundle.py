from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .procedure import StartupResult
from .sources.base import SourceRecord


def _grounding_entry(record: SourceRecord, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "content": record.content,
        "source_id": record.source_id,
        "version": record.version,
        "fetched_at": record.fetched_at,
    }
    if extra:
        entry.update(extra)
    return entry


def _ledger_entry(record: SourceRecord, mandatory_ids: set[str]) -> dict[str, Any]:
    return {
        "source_id": record.source_id,
        "title": record.title,
        "version": record.version,
        "fetched_at": record.fetched_at,
        "mandatory": record.source_id in mandatory_ids,
    }


def _total_chars(result: StartupResult, purpose_context: list, decisions: list, continuity: list) -> int:
    total = 0
    for record in (result.bootstrap, result.base_contract, result.role_contract):
        if record is not None:
            total += len(record.content)
    total += sum(len(r.content) for r in purpose_context)
    total += sum(len(r.content) for r in decisions)
    total += sum(len(r.content) for r in continuity)
    return total


def build_bundle(
    result: StartupResult,
    manifest: dict[str, Any],
    purpose: str,
    role_hint: str | None,
    budget_chars: int,
) -> dict[str, Any]:
    mandatory_ids = set(manifest.get("mandatory_source_ids", []))
    warnings = list(result.warnings)

    purpose_context = list(result.purpose_context)
    decisions = list(result.decisions)
    continuity = list(result.continuity)

    # Context-size budget: drop lowest-priority, least-mandatory content first. Dropped entries
    # stay in the provenance ledger (sources[]) — only their inlined content is removed from the
    # bundle, consistent with "sources consulted" being distinct from "content inlined".
    while _total_chars(result, purpose_context, decisions, continuity) > budget_chars and continuity:
        dropped = continuity.pop()
        warnings.append(
            f"dropped continuity entry '{dropped.source_id}' to stay within the context budget"
        )
    while _total_chars(result, purpose_context, decisions, continuity) > budget_chars and decisions:
        dropped = decisions.pop()
        warnings.append(
            f"dropped decision entry '{dropped.source_id}' to stay within the context budget"
        )
    while _total_chars(result, purpose_context, decisions, continuity) > budget_chars and purpose_context:
        dropped = purpose_context.pop()
        warnings.append(
            f"dropped purpose-context entry '{dropped.source_id}' to stay within the context budget"
        )

    grounding: dict[str, Any] = {
        "bootstrap": _grounding_entry(result.bootstrap) if result.bootstrap else None,
        "base_contract": _grounding_entry(result.base_contract) if result.base_contract else None,
        "role_contract": (
            _grounding_entry(result.role_contract, {"resolved_role": result.resolved_role})
            if result.role_contract
            else None
        ),
        "purpose_context": [_grounding_entry(r) for r in purpose_context],
        "decisions": [_grounding_entry(r) for r in decisions],
        "continuity": [_grounding_entry(r) for r in continuity],
    }

    return {
        "status": result.status,
        "request": {"operation": "ground", "purpose": purpose, "role_hint": role_hint},
        "grounding": grounding,
        "sources": [_ledger_entry(r, mandatory_ids) for r in result.sources_consulted],
        "versions": {"canonical_designation_version": result.canonical_version},
        "warnings": warnings,
        "unresolved": result.unresolved,
        "permissions": {"write_authority": result.write_authority},
        "receipt": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_versions": {r.source_id: r.version for r in result.sources_consulted},
            "refresh_hint": (
                "Call ground again with the same purpose if this conversation is continued "
                "elsewhere or after significant truncation/compaction."
            ),
        },
    }
