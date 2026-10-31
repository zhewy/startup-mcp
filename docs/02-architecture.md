# Proposed Minimal Architecture

## Scope of this document

This describes the architecture actually implemented in this repo at the current phase
(Phase 2 — minimal prototype with a fixed test bundle), plus the seams left for Phase 3 (live
Brain integration). It intentionally does not implement live Google Drive retrieval yet — see
`01-feasibility.md` §2 and `07-decisions-needed.md` for why that's gated on an explicit decision.

## Component map

```
startup_mcp/
  server.py       MCP server entrypoint (stdio transport, FastMCP), registers the `startup` tool
  bundle.py        Grounding bundle schema (dataclasses) + bundle assembly logic
  procedure.py     The deterministic startup procedure (steps 1-9 from the brief), currently
                   operating against a fixed/local test source set
  sources/
    base.py        SourceProvider protocol: retrieve(id) -> (content, version, fetched_at)
    fixture.py     Phase 2: FixtureSourceProvider — reads a local JSON/YAML fixture tree,
                   standing in for live Brain retrieval
    drive.py       Phase 3 (not yet implemented): GoogleDriveSourceProvider
  validation.py    Mandatory-source / designation-consistency checks -> READY/DEGRADED/BLOCKED
  config.py        Context-size budget, fixture path, (future) Drive OAuth config
```

`procedure.py` depends only on the `SourceProvider` protocol, not on Drive specifically. Swapping
`FixtureSourceProvider` for `GoogleDriveSourceProvider` in Phase 3 should not require changing the
startup procedure, validator, or bundle assembler — only the source layer and its credentials.

## What's hardcoded vs retrieved (per brief §7)

Hardcoded in this implementation now:
- The 9-step startup sequence order (`procedure.py`).
- Retrieval mechanics (the `SourceProvider` interface and its call pattern).
- Validation rules for what counts as "mandatory grounding satisfied" (`validation.py`) — note
  this is *mechanical* validation (is the source present, parseable, versioned, non-conflicting),
  not a reinterpretation of Brain's governance rules.
- The grounding bundle's JSON schema (matches the brief's §5 illustrative structure).
- Failure handling / status derivation (READY / DEGRADED / BLOCKED).
- Context-size budgeting (truncation order when a budget is exceeded).
- Structured logging of each resolved source (id, version, fetched_at) for diagnostics.

Retrieved from Brain (fixture in Phase 2, live Drive in Phase 3) — never hardcoded:
- Current bootstrap content.
- Canonical designations (which Base/role contracts currently apply).
- Base and role contract text.
- Mandatory reading list itself (which sources are mandatory is *data*, not code).
- Purpose knowledge for the requested purpose.
- Decisions / continuity entries.
- Permissions / governance rules (e.g. `write_authority`).

This split is the core design invariant: the MCP enforces *process* (did we check everything we
were told to check, is it internally consistent), but Brain content supplies *what* must be
checked. The server must never fall back to a locally hardcoded "default" bootstrap or canonical
designation if Brain's own live source is unreachable — that would silently violate brief §6
("Missing or conflicting canonical designations must not be silently resolved by guessing"). An
unreachable mandatory source is a `BLOCKED` result, full stop.

## Tool surface

Phase 2 ships exactly one tool: `startup`. See `03-tool-contract.md` for the full contract. No
other tools (no Brain search, no write operations, no admin) are exposed, per brief §8/§12.

## Transport

`stdio`, via the official `mcp` Python SDK (`FastMCP`). This is the one transport confirmed to
work with Claude Desktop (see feasibility doc). A Streamable-HTTP transport for ChatGPT Desktop,
if that client turns out to need it, would be an additive transport binding over the same
`procedure.py`/`bundle.py` core — not a rewrite.

## Determinism

Given the same purpose/role request and the same underlying source versions, `procedure.py` produces
byte-identical bundle content (modulo a `generated_at` timestamp field, which is explicitly
excluded from any equality/determinism check). This is testable without live Drive access using
the fixture provider, and `tests/test_server.py` asserts it.
