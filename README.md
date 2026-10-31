# Startup MCP

A lightweight, platform-neutral MCP server that moves the mechanical work of AI conversation
startup — canonical retrieval, role grounding, topic-context assembly — into a deterministic
service, so a calling AI doesn't have to independently discover and interpret a chain of startup
documents.

See `docs/` for the full design record:

1. [`01-feasibility.md`](docs/01-feasibility.md) — what's actually confirmed vs. unconfirmed about
   MCP support in Claude Desktop / ChatGPT Desktop, Google Drive auth, invocation reliability, and
   Desktop→Web continuity.
2. [`02-architecture.md`](docs/02-architecture.md) — component map and the hardcoded-vs-retrieved
   split.
3. [`03-tool-contract.md`](docs/03-tool-contract.md) — the `startup(topic, role?)` tool's input/
   output schema and status semantics.
4. [`04-authentication.md`](docs/04-authentication.md) — the proposed (not yet implemented) Google
   Drive OAuth approach for Phase 3.
5. [`05-invocation-reliability.md`](docs/05-invocation-reliability.md) — what can and can't be done
   to make a model actually call this tool.
6. [`06-test-plan.md`](docs/06-test-plan.md) — automated test coverage plus the manual checks a
   human needs to run against real desktop clients.
7. [`07-decisions-needed.md`](docs/07-decisions-needed.md) — open items that need explicit user
   sign-off before Phase 3 (live Brain integration) proceeds.
8. [`08-initialization-investigation.md`](docs/08-initialization-investigation.md) — findings on
   whether MCP connection initialization can drive automatic conversation/task startup, what's a
   protocol fact vs. an untested client behavior, and the diagnostic logging added to make the
   untested parts testable by a human with a real desktop client.

## Current status: Phase 2 — minimal prototype

This repo implements a single `startup` tool over MCP stdio, backed by a **local fixture** that
stands in for live Brain retrieval (no Google Drive access yet — see decision 1 in
`docs/07-decisions-needed.md`). It exists to let Phase 1/Phase 2 client-behavior questions
(does Claude Desktop actually invoke this tool reliably? does Claude Desktop ↔ Web continuity
work? per `docs/06-test-plan.md`) get answered before any live-data risk is taken on.

```
startup(topic="devotions")
  -> { "status": "READY", "grounding": {...}, "sources": [...], ... }
```

## Project layout

```
src/startup_mcp/
  server.py       MCP entrypoint (stdio), registers the `startup` tool
  procedure.py     The deterministic startup procedure (brief steps 1-9)
  bundle.py        Assembles the final response bundle, applies the context budget
  config.py        Fixture path / context-budget configuration
  sources/
    base.py        SourceProvider protocol (fixture today, live Drive in Phase 3)
    fixture.py      FixtureSourceProvider — reads the local JSON fixture tree
  fixtures/default/ Fixture data standing in for the live Brain (manifest + per-source files)
tests/
  test_server.py   Unit tests: determinism, READY/DEGRADED/BLOCKED, provenance, budget, conflicts
examples/
  claude_desktop_config.json  Example local MCP server registration for Claude Desktop
```

## Running locally

```bash
cd startup-mcp
pip install -e ".[dev]"
pytest
```

On Windows, the default pytest temp directory can hit a `PermissionError` depending on the
machine — if so, use `pytest --basetemp=.pytest-tmp` instead.

Run the server directly over stdio (for manual MCP client testing):

```bash
python3 -m startup_mcp.server
```

## Wiring into Claude Desktop

Add an entry like `examples/claude_desktop_config.json` to your `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: **not
reliably `%APPDATA%\Claude\claude_desktop_config.json`** — on a Windows 10/11 machine tested 31
Oct 2026 (Claude Desktop 4.4212.0) the real path was
`%LOCALAPPDATA%\Claude-Data\claude_<per-install-id>\claude_desktop_config.json`, a randomly
per-install-suffixed directory under `Local\Claude-Data`. Search under `%LOCALAPPDATA%` for
`claude_desktop_config.json` rather than assuming the path on Windows), pointing
`STARTUP_MCP_FIXTURE_ROOT` at an absolute path if you don't want the bundled default fixture,
then restart Claude Desktop. The `STARTUP_MCP_*` environment variables are optional — omit them
to use the bundled fixture and a 20,000-character context budget. On Windows, `"command":
"python3"` in the example config may need to be `"python"` instead — check which resolves on
your machine.

MCP server logs on Windows land in `%LOCALAPPDATA%\Claude\logs\` — this server's own stderr
diagnostics appear in `mcp-server-startup-mcp.log`, while the client's own connection-level log
(showing the actual `initialize`/`tools/list`/`tools/call` traffic) is `main.log`.

**ChatGPT Desktop wiring is not yet validated** — see `docs/01-feasibility.md` §1 and
`docs/06-test-plan.md` §B2. Confirm stdio support there before assuming this config pattern
transfers.

## Explicitly not yet done

- No live Google Drive retrieval (Phase 3 — gated on the decisions in
  `docs/07-decisions-needed.md`).
- No OAuth flow (`docs/04-authentication.md` describes the intended design, unimplemented).
- No MCP `prompts` entry for explicit, non-model-mediated invocation (proposed, not yet built —
  decision 6 in `docs/07-decisions-needed.md`).
- No hands-on verification against a running Claude Desktop or ChatGPT Desktop install — the
  server has only been exercised via direct Python calls and the SDK's in-process `list_tools()`
  in this environment, which has no desktop client available to test against.
