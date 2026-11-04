from __future__ import annotations

from dataclasses import dataclass, field

from .sources.base import SourceProvider, SourceRecord


@dataclass
class StartupResult:
    status: str  # READY | DEGRADED | BLOCKED
    canonical_version: str
    bootstrap: SourceRecord | None
    base_contract: SourceRecord | None
    role_contract: SourceRecord | None
    resolved_role: str | None
    purpose_context: list[SourceRecord]
    decisions: list[SourceRecord]
    continuity: list[SourceRecord]
    sources_consulted: list[SourceRecord]
    warnings: list[str]
    unresolved: list[str]
    write_authority: bool


def run_startup(provider: SourceProvider, purpose: str, role_hint: str | None) -> StartupResult:
    """The deterministic startup procedure (brief §4, steps 1-9), executed against whatever
    SourceProvider is supplied (fixture in Phase 2, live Drive in Phase 3)."""
    manifest = provider.get_manifest()
    mandatory_ids = set(manifest.get("mandatory_source_ids", []))
    optional_ids = set(manifest.get("optional_source_ids", []))

    warnings: list[str] = []
    unresolved: list[str] = []
    sources_consulted: list[SourceRecord] = []
    degraded = False

    def fetch(source_id: str) -> SourceRecord | None:
        nonlocal degraded
        record = provider.get_source(source_id)
        if record is None:
            if source_id in mandatory_ids:
                unresolved.append(f"missing mandatory source: {source_id}")
            elif source_id in optional_ids:
                warnings.append(f"optional source unavailable: {source_id}")
                degraded = True
            return None
        sources_consulted.append(record)
        return record

    # 1. Retrieve the current live bootstrap.
    bootstrap = fetch(manifest["bootstrap_source_id"])

    # 2. Resolve the current canonical designations.
    canonical_version = manifest.get("canonical_version", "")

    # 3. Identify applicable Base and role contracts.
    base_contract = fetch(manifest["base_contract_source_id"])

    resolved_role = manifest.get("role_for_purpose", {}).get(purpose)
    if role_hint and resolved_role and role_hint != resolved_role:
        warnings.append(
            f"role hint '{role_hint}' does not match canonically resolved role "
            f"'{resolved_role}' for purpose '{purpose}'; using the resolved role, not the hint"
        )
    elif not resolved_role:
        warnings.append(f"no canonical role mapping found for purpose '{purpose}'")
        degraded = True

    role_contract = None
    if resolved_role:
        role_contract_id = manifest.get("role_contract_source_ids", {}).get(resolved_role)
        if role_contract_id:
            role_contract = fetch(role_contract_id)
        else:
            unresolved.append(f"no role contract mapped for resolved role '{resolved_role}'")

    # 4. Retrieve all mandatory grounding — anything mandatory not already resolved above
    # (bootstrap/base/role contracts) is still required, even if no other step named it.
    fetched_ids = {r.source_id for r in sources_consulted}
    reported_missing_ids = {item.rsplit(": ", 1)[-1] for item in unresolved}
    for source_id in sorted(mandatory_ids):
        if source_id not in fetched_ids and source_id not in reported_missing_ids:
            fetch(source_id)

    # 5. Validate required sources and designation consistency.
    consulted_ids = {r.source_id for r in sources_consulted}
    for record in sources_consulted:
        for other_id in record.conflicts_with:
            if other_id in consulted_ids:
                unresolved.append(
                    f"conflicting mandatory sources: '{record.source_id}' conflicts with "
                    f"'{other_id}'"
                )

    # 6. Retrieve purpose-specific Brain knowledge.
    purpose_source_ids = manifest.get("purpose_source_ids", {}).get(purpose, [])
    if not purpose_source_ids:
        warnings.append(f"no purpose-specific knowledge indexed for purpose '{purpose}'")
        degraded = True
    purpose_context = [r for sid in purpose_source_ids if (r := fetch(sid)) is not None]

    # 7. Include relevant decisions, history and continuity.
    decisions = [r for sid in manifest.get("decision_source_ids", []) if (r := fetch(sid)) is not None]
    continuity = [r for sid in manifest.get("continuity_source_ids", []) if (r := fetch(sid)) is not None]

    # Defensive floor: this tool never reports write authority, regardless of manifest content
    # (brief §8: "No canonical writes" for the current implementation scope).
    if manifest.get("write_authority", False):
        warnings.append(
            "source data declares write_authority=true; overridden to false by this tool's "
            "hardcoded safety floor (write capability is out of scope for this implementation)"
        )
    write_authority = False

    # 9. Explicit readiness status.
    if unresolved:
        status = "BLOCKED"
    elif degraded:
        status = "DEGRADED"
    else:
        status = "READY"

    return StartupResult(
        status=status,
        canonical_version=canonical_version,
        bootstrap=bootstrap,
        base_contract=base_contract,
        role_contract=role_contract,
        resolved_role=resolved_role,
        purpose_context=purpose_context,
        decisions=decisions,
        continuity=continuity,
        sources_consulted=sources_consulted,
        warnings=warnings,
        unresolved=unresolved,
        write_authority=write_authority,
    )
