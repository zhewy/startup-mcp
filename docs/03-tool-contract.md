# MCP Tool Contract

**Naming note (topic → purpose):** the handover brief's illustrative signature uses `topic` (e.g.
`startup(topic: string, role?: string)`). This implementation uses `purpose` instead — same
concept, renamed deliberately after the Phase 2 prototype was already live and tested (see
`docs/08-initialization-investigation.md`, which preserves pre-rename log quotes verbatim and
notes the rename explicitly).

**Naming note (single tool → two tools):** the brief's own illustrative signature, and this
implementation up to this point, described a single `startup(purpose, role?)` tool that always
performs full deterministic retrieval. This has since been split into two tools, `startup` and
`ground`, to separate a lightweight entrypoint from the (renamed) full retrieval call — see
`02-architecture.md`'s "Tool surface" section for the rationale. Everything the brief and earlier
docs called "the `startup` tool" is now `ground`; the name `startup` now refers to the new,
argument-free, Brain-content-free entrypoint described first below.

## Tool: `startup`

### Description (as exposed to the calling model)

> Lightweight entrypoint, takes no arguments. Returns short, stable, versioned guidance on when
> this server's full grounding call (`ground`) is necessary — it does not itself retrieve any
> canonical content. Call this at the start of a new conversation, or whenever unsure whether a
> task depends on Brain-backed grounding, before deciding whether to call `ground`.

### Input schema

```json
{ "type": "object", "properties": {} }
```

No arguments. This is deliberate — anything resembling a `purpose`/`role` parameter here would
blur this tool back into performing retrieval, which is exactly the responsibility `ground` keeps.

### Output schema

```json
{
  "version": "v1",
  "guidance": "string — explains what \"Brain\" means, that receiving this response is not grounding, and when to call `ground`",
  "next_action": "ground(purpose, role?)"
}
```

### Properties

- **Static and versioned.** The payload is a fixed constant in `server.py`
  (`STARTUP_PAYLOAD`), not computed per-call and not read from any source file — two calls in the
  same process return identical results, structurally guaranteed by the tool having no
  `SourceProvider` dependency at all, not just observed to be so.
- **Never a substitute for `ground`.** This tool's `guidance` text must stay generic routing
  advice — it must never grow into something Brain-authoritative (e.g. it must not enumerate
  specific purpose/role names, per the data-driven-purposes discipline `procedure.py` already
  follows). If it starts answering questions `ground` should answer, it has become a competing
  canonical source, which is the one thing this split was designed to avoid.
- **Invocation reliability is a separate, untested question from `ground`'s.** Empirical findings
  for the (renamed) full-retrieval tool — zero unprompted invocations across every trial run so
  far (1 Claude Desktop round, 3 Codex CLI runs) — do not automatically transfer to this tool.
  Whether a model calls `startup()` unprompted, and whether receiving its guidance then causes an
  unprompted `ground` call, are each their own open questions. See `05-invocation-reliability.md`.

## Tool: `ground`

### Description (as exposed to the calling model)

> Retrieve and validate the mandatory grounding (bootstrap, canonical designations, Base and role
> contracts, purpose knowledge, decisions, continuity) required to begin a Brain-grounded
> conversation for the given purpose. This is the full, deterministic retrieval step — call
> `startup` first for short guidance on whether this is necessary for the task at hand. Call this
> with the current purpose (and, if known, a role hint) at the start of a new conversation, AND
> again at the start of any substantive new task within an existing conversation — a prior call
> does not cover a later, different purpose. Do not attempt to independently discover or
> reconstruct grounding documents yourself — this tool performs that retrieval deterministically.
> Returns a structured bundle with an explicit `status` of READY, DEGRADED, or BLOCKED; never
> treat ungrounded reasoning as equivalent to a READY result.

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
    "operation": "ground",
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
    "refresh_hint": "Call `ground` again with the same purpose if this conversation is continued elsewhere or after significant truncation/compaction."
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
  stale and whether to re-call `ground`.
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
