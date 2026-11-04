# zmcp

A lightweight MCP server for Brain context and AI startup guidance. Connection
initialization supplies Brain's description, folder link, and initialization link.
The `startup` tool is currently reserved and returns only `"to be defined"`; there
is no need to call it. A separate `role` call for `architect` or `librarian` is
under consideration, not implemented.

See `docs/` for the full design record:

1. [`01-feasibility.md`](docs/01-feasibility.md) — what's actually confirmed vs. unconfirmed about
   MCP support in Claude Desktop / ChatGPT Desktop, Google Drive auth, invocation reliability, and
   Desktop→Web continuity.
2. [`02-architecture.md`](docs/02-architecture.md) — component map and the hardcoded-vs-retrieved
   split.
3. [`03-tool-contract.md`](docs/03-tool-contract.md) — the `startup(purpose, role?)` tool's input/
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
9. [`09-dev-workflow.md`](docs/09-dev-workflow.md) — the cloud-edit → local-pull → live-test loop
   this project actually uses, and why the Windows machine is a pull-only test target, never an
   edit target.

## Current status: initialization guidance and a startup placeholder

The server exposes two tools over MCP stdio:

```text
startup() -> "to be defined"
ground(purpose, role?) -> legacy fixture grounding bundle
```

The previous optional arguments `purpose` and `role` are accepted for compatibility
and ignored. The tool performs no retrieval and reports no grounding status.
Existing fixture retrieval code and its tests are retained as a prototype, but
are exposed only by the legacy `ground` tool, not `startup`.
The `ground` tool was added in a parallel remote update and is retained as a
fixture prototype; its READY status does not establish live Brain grounding. The older design documents describe that prototype;
they do not require callers to invoke the current placeholder.

## Project layout

```
src/zmcp/
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
cd zmcp
pip install -e ".[dev]"
pytest
```

On Windows, the default pytest temp directory can hit a `PermissionError` depending on the
machine — if so, use `pytest --basetemp=.pytest-tmp` instead.

Run the server directly over stdio (for manual MCP client testing):

```bash
python3 -m zmcp.server
```

## Wiring into Claude Desktop

Add an entry like `examples/claude_desktop_config.json` to your `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: **not
reliably `%APPDATA%\Claude\claude_desktop_config.json`** — on a Windows 10/11 machine tested 31
Oct 2026 (Claude Desktop 4.4212.0) the real path was
`%LOCALAPPDATA%\Claude-Data\claude_<per-install-id>\claude_desktop_config.json`, a randomly
per-install-suffixed directory under `Local\Claude-Data`. Search under `%LOCALAPPDATA%` for
`claude_desktop_config.json` rather than assuming the path on Windows), pointing
`ZMCP_FIXTURE_ROOT` at an absolute path if you don't want the bundled default fixture,
then restart Claude Desktop. The `ZMCP_*` environment variables are optional — omit them
to use the bundled fixture and a 20,000-character context budget. On Windows, `"command":
"python3"` in the example config may need to be `"python"` instead — check which resolves on
your machine.

MCP server logs on Windows land in `%LOCALAPPDATA%\Claude\logs\` — this server's own stderr
diagnostics appear in `mcp-server-zmcp.log`, while the client's own connection-level log
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

## Renamed from Startup MCP

The project, Python package, MCP server, CLI command, and desktop plugin are now
`zmcp`. Settings use `ZMCP_FIXTURE_ROOT`, `ZMCP_CONTEXT_BUDGET_CHARS`, and
`ZMCP_LOG_LEVEL`; the desktop launcher also accepts `ZMCP_PYTHON`. The tool remains
`startup(purpose, role?)`. Update existing client configurations and reinstall the
Python package after pulling this rename. Historical logs retain their old names.

Build the private ChatGPT desktop plugin ZIP with:

```bash
python packaging/build_chatgpt_plugin.py
```

The output is `dist/zmcp-chatgpt-0.1.0.zip`. Extract it and follow `INSTALL.txt`.
On Windows the installer registers `zmcp` at `%USERPROFILE%\.codex\plugins\zmcp`
and stores its runtime at `%USERPROFILE%\.zmcp\runtime-0.1.0`. An existing
`startup-mcp` installation is separate; remove its old marketplace entry using
the earlier uninstall instructions. This rename does not modify installations
on other computers.
