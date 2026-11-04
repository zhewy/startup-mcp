# MCP Tool Contract

> Current public surface (4 Nov 2026): `startup()` returns only `"to be defined"`
> and need not be called. `ground(purpose, role?)`, retained from the parallel
> prototype update, returns local fixture data only. Neither tool reads live Brain.
> The proposed `role` tool is not implemented. Older architecture and bundle
> descriptions below concern the fixture prototype.


## Current public contract (4 Nov 2026)

`startup(purpose: string | null = null, role: string | null = null) -> string`
returns exactly `"to be defined"`. Arguments are accepted for compatibility and
ignored. No retrieval or grounding validation occurs; callers need not invoke it.
Connection initialization continues to provide Brain location and initialization
links. A `role` tool for `architect` and `librarian` is being considered, not yet
implemented.

## Historical fixture prototype contract

The remaining sections describe the retained fixture pipeline, not the current
public startup response.

**Naming note:** the handover brief's illustrative signature uses `topic` (e.g.
`startup(topic: string, role?: string)`). This implementation uses `purpose` instead — same
concept, renamed deliberately after the Phase 2 prototype was already live and tested (see
`docs/08-initialization-investigation.md`, which preserves pre-rename log quotes verbatim and
notes the rename explicitly). Everything below reflects the prototype contract after that parameter rename.

## Tool: `startup`

### Description (as exposed to the calling model)

> Retrieve and validate the mandatory grounding (bootstrap, canonical designations, Base and role
> contracts, purpose knowledge, decisions, continuity) required to begin a Brain-grounded
> conversation for the given purpose. Call this once, before any other reasoning about the
> purpose, at the start of a new conversation. Do not attempt to independently discover or
> reconstruct grounding documents — this tool performs that retrieval deterministically. Returns
> a structured bundle with an explicit `status` of READY, DEGRADED, or BLOCKED; never treat
> ungrounded reasoning as equivalent to a READY result.

(Rationale for the directive tone: per brief §9, invocation reliability is improved, not
guaranteed, by making the tool description itself tell the model when and why to call it.)

### Input schema

```json
{
  "type": "object",
  "properties": {
    "purpose": {
      "type": "string",
      "description": "The subject of the conversation to ground, e.g. \"devotions\". Required."
    },
    "role": {
      "type": "string",
      "description": "Optional hint for which role context the caller believes applies. This is advisory only: it does not grant authority and does not bypass role-selection rules. The server resolves the actual applicable role contract(s) from current canonical designations, independent of this value, and will report in `warnings` if the hint conflicts with the resolved role."
    }
  },
  "required": ["purpose"]
}
```

### Output schema

Matches brief §5, with field semantics pinned down:

```json
{
  "status": "READY | DEGRADED | BLOCKED",
  "request": {
    "operation": "startup",
    "purpose": "string, echoed verbatim",
    "role_hint": "string or null, echoed verbatim (renamed from input `role` to make clear it's a hint)"
  },
  "grounding": {
    "bootstrap": { "content": "...", "source_id": "...", "version": "...", "fetched_at": "ISO-8601" },
    "base_contract": { "content": "...", "source_id": "...", "version": "...", "fetched_at": "ISO-8601" },
    "role_contract": { "content": "...", "source_id": "...", "version": "...", "fetched_at": "ISO-8601", "resolved_role": "string" },
    "purpose_context": [ { "content": "...", "source_id": "...", "version": "...", "fetched_at": "ISO-8601" } ],
    "decisions": [ { "content": "...", "source_id": "...", "version": "...", "fetched_at": "ISO-8601" } ],
    "continuity": [ { "content": "...", "source_id": "...", "version": "...", "fetched_at": "ISO-8601" } ]
  },
  "sources": [
    { "source_id": "...", "title": "...", "url": "...", "version": "...", "fetched_at": "ISO-8601", "mandatory": true }
  ],
  "versions": { "canonical_designation_version": "...", "bootstrap_version": "..." },
  "warnings": [ "string, present when status is DEGRADED or when a role hint mismatch occurred" ],
  "unresolved": [ "string, mandatory items that could not be retrieved/validated — present only when status is BLOCKED" ],
  "permissions": { "write_authority": false },
  "receipt": {
    "generated_at": "ISO-8601",
    "source_versions": { "...": "..." },
    "refresh_hint": "Call `startup` again with the same purpose if this conversation is continued elsewhere or after significant truncation/compaction."
  }
}
```

Notes:
- `grounding.*` fields contain **actual content**, not links (brief §5: "should include the
  actual required content, not merely file links").
- `sources[]` is the full provenance ledger — every source consulted, mandatory or not, with
  enough identity (id/title/url/version/fetched_at) to support later refresh or audit, independent
  of whether its content made it into the bundle (e.g. a source that was checked but excluded for
  budget reasons is still listed here, see `06-test-plan.md` budget test).
- `receipt` is the mechanism for brief §10 (Desktop→Web continuity): a model picking the
  conversation back up, in Web or after compaction, has enough to decide whether grounding is
  stale and whether to re-call `startup`.
- `permissions.write_authority` is always `false` from this tool in the current scope (brief §8:
  "No canonical writes"). It is still retrieved from Brain's governance data (not hardcoded to
  `false` as a business rule) but the server additionally hardcodes a defensive floor: it will
  never report `write_authority: true` regardless of what Brain's data says, until a future
  version explicitly adds write capability. This is documented as a deliberate asymmetry.

### Status semantics

- **READY**: every mandatory source resolved, parsed, and internally consistent (no conflicting
  canonical designations). `warnings` may be non-empty for optional-material notices only.
- **DEGRADED**: all mandatory grounding satisfied; one or more *optional* sources (e.g. a "nice to
  have" continuity entry) were unavailable. `warnings` enumerates exactly what's missing and why
  it's non-mandatory.
- **BLOCKED**: any mandatory source missing, stale beyond its validity rule, conflicting with
  another mandatory source, or unverifiable (e.g. checksum/version mismatch). `unresolved`
  enumerates each failing item with the specific reason. The server must not guess a resolution or
  silently proceed — this is a hard requirement from brief §6.

A `BLOCKED` response is a **successful tool call** (no MCP error) carrying a status that tells the
model not to proceed as if grounded — the brief is explicit that false `READY` is the failure mode
to avoid, not a non-zero exit code.

### Determinism

For a fixed `(purpose, role)` input and a fixed set of underlying source versions, the tool must
return byte-identical `grounding`/`sources`/`versions`/`status` content. `receipt.generated_at` is
the only field allowed to vary between otherwise-identical calls.
