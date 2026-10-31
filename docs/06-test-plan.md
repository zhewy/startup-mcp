# Prototype Test Plan

Maps to the acceptance tests in brief §11. Split into what this repo's automated tests cover now
(fixture-based, no live client/Drive needed) versus what needs a human running a real desktop
client (manual, one-time per phase).

## A. Automated (covered by `tests/test_server.py`, runs now, no client needed)

| # | Brief §11 item | Test |
|---|---|---|
| 6 | Identical inputs + source versions → equivalent results | `test_determinism_across_identical_calls`: two calls with the same purpose against the fixture source produce identical `grounding`/`sources`/`versions`/`status`, differing only in `receipt.generated_at`. |
| 7 | Missing mandatory sources → BLOCKED, not false success | `test_missing_mandatory_source_blocks`: fixture with a mandatory source deleted → `status == "BLOCKED"` and the missing id appears in `unresolved`. |
| 8 | Source identities and provenance retained | `test_sources_retain_provenance`: every entry in `sources[]` has non-empty `source_id`, `version`, `fetched_at`. |
| 5 | `devotions` produces relevant purpose grounding | `test_devotions_purpose_produces_relevant_grounding`: `startup(purpose="devotions")` against the fixture returns a `purpose_context` entry sourced from the devotions fixture file, not from an unrelated purpose. |
| — | Optional material missing → DEGRADED, not BLOCKED | `test_optional_missing_degrades`: fixture with only a non-mandatory continuity entry removed → `status == "DEGRADED"`, mandatory grounding still present, `warnings` names it. |
| — | Context-size budget enforcement | `test_budget_truncation`: a fixture engineered to exceed a small configured budget → bundle stays within budget, `sources[]` still lists every *consulted* source (budget affects what's inlined under `grounding`, not the provenance ledger), and this is recorded in `warnings`. |
| — | `role` input is advisory only | `test_role_hint_does_not_grant_authority`: calling with a `role` hint that doesn't match the canonical-resolved role still resolves the role from canonical data, not from the hint, and emits a mismatch warning. |

Run with:
```bash
cd startup-mcp
pip install -e ".[dev]"
pytest
```

## B. Manual — Phase 1 feasibility checks (do before/alongside Phase 2 client wiring)

1. **Claude Desktop stdio launch.** Add this server to `claude_desktop_config.json` per
   `examples/claude_desktop_config.json`, restart Claude Desktop, confirm the `startup` tool
   appears in its tool picker and a direct call succeeds end-to-end.
2. **ChatGPT Desktop stdio launch.** Attempt the equivalent in ChatGPT Desktop's MCP/Developer
   Mode settings. Record whether it accepts a local stdio server at all (per
   `01-feasibility.md` §1, sources disagree). If it only accepts Streamable HTTP, note as a
   blocker for that client in this phase, not a bug in this server.
3. **MCP prompts surfacing.** In each client, check whether a server-defined `prompts/list` entry
   becomes a user-visible slash command or menu action (feeds into `05-invocation-reliability.md`).

## C. Manual — invocation behavior (per client)

4. Start a fresh conversation in each client with no explicit instruction beyond a task that
   implies needing Brain grounding (e.g. "let's do devotions today"). Record whether the model
   calls `startup` unprompted, and compare against the same scenario with an explicit instruction
   ("call the startup tool for purpose devotions first").

## D. Manual — Desktop → Web continuity (per provider, after Phase 3 Drive integration exists)

5. Start a conversation in Desktop, call `startup`, receive a READY bundle. Continue the *same*
   conversation in that provider's Web app. Ask a question that depends on bundle content (e.g.
   "what does the role contract say about X"). Confirm the Web session can answer from the
   returned grounding without re-calling `startup`, and separately confirm that after heavy
   scrollback/compaction, the model (or user) can use the `receipt` to decide a re-call is needed.

## E. Manual — negative/safety checks

6. Confirm no writes occur: inspect Drive activity/audit log (if available) after a full test
   run and confirm zero write/modify/share events attributable to the server's service account or
   OAuth client.
7. Simulate an unreachable mandatory source (e.g. revoke the OAuth token, or point config at a
   nonexistent fixture) and confirm the tool returns `BLOCKED`, never a silently-degraded `READY`.

## F. Automatic invocation via MCP initialization (see `08-initialization-investigation.md`)

8. Run the instrumented experiment in `08-initialization-investigation.md` §3 against a real
   Claude Desktop (and, separately, ChatGPT Desktop) install: confirm the process-start log line
   appears, then confirm whether a `startup tool invoked` line appears in an unprompted new
   conversation. This supersedes §C above with actual log evidence rather than relying on the
   model's own account of whether it called the tool.

   **Run 1 (31 Oct 2026, Windows, Claude Desktop 4.4212.0): done — result was no automatic
   invocation across 3 fresh conversations.** See `08-initialization-investigation.md` §0.5 for
   the full evidence.

   **Run 2 (31 Oct 2026, same machine/install): done — explicit user instruction did get
   `startup` called, twice, both READY.** See `08-initialization-investigation.md` §0.6. This
   confirms the Q7 fallback actually works on this client, in direct contrast to Run 1's result
   on the same install.

   **Run 3 (31 Oct 2026, same machine): done — purpose routing (`devotionals`, `librarian`, an
   unmapped purpose) confirmed live via explicit calls, all three statuses matched expectation.**
   See `08-initialization-investigation.md` §0.7. Content itself was only verified by a local
   check against the same fixture, not captured through the Desktop path directly — that
   distinction is preserved in §0.7 rather than blurred.

   Still outstanding: a ChatGPT Desktop run of all three rounds, a repeat Claude Desktop run with
   a controlled instructions-present-vs-removed comparison (to separate Q1 from Q2), and a run
   that captures the actual chat text (none of the three runs used GUI control, so what the
   model said is unknown in all three).

## G. CLI agent clients — new scope, beyond the brief's two named clients

The handover brief named exactly two targets: ChatGPT Desktop and Claude Desktop — consumer chat
GUI apps. This section tracks a deliberate scope addition: testing Startup MCP against **CLI
coding-agent tools** instead, which are separate products from their respective companies'
consumer chat apps, not alternate skins on the same one. Two parallel, independently-tracked
streams:

- **Claude Code CLI** — already running on every Remote Control bridge session used so far (it's
  the host of those sessions). Its own MCP config mechanism (`.mcp.json` / `claude mcp add`) is
  separate from `claude_desktop_config.json`. No new install needed to test this — it's already
  present on kofimule.
- **Codex CLI** (OpenAI) — **confirmed installed on kofimule** (31 Oct 2026): `codex-cli 0.166.0`
  at `/home/arty/.local/bin/codex`, installed globally via npm (`@openai/codex@0.166.0`). No
  install step needed on that machine.

  **Its own MCP config mechanism, confirmed (31 Oct 2026):** separate from both Claude's and
  from ChatGPT Desktop's Developer Mode settings. `codex mcp` subcommand (`list`/`get`/`add`/
  `remove`/`login`/`logout`); config lives at `~/.codex/config.toml`, servers under
  `[mcp_servers.<name>]`. Both stdio and streamable-HTTP transports supported — stdio via
  `command`/`args`/`env` (plus `startup_timeout_sec`, `tool_timeout_sec`,
  `default_tools_approval_mode`), HTTP via `url`/`http_headers`. Stdio add syntax:
  `codex mcp add <NAME> [--env KEY=VAL] -- <COMMAND>...`.

  That config file already has three servers configured on kofimule: `iqbible` and
  `brain-recall` (both HTTP), and `hub` (stdio, a Python `mcphub.cli` server). Startup MCP is
  **not wired in yet** — recon only, as instructed.

  **Security note, not acted on (out of scope for this project):** the reporting session found
  `brain-recall`'s config has a plaintext bearer token under `http_headers` in `config.toml`, and
  deliberately withheld the value from its report rather than relaying a secret. It suggested
  moving it to `--bearer-token-env-var` instead. That's a different, unrelated MCP server's
  credential storage — flagged here for the user's awareness, not something to fix from this
  project.

**The same non-equivalence applies to both, for the same reason:** a CLI coding agent is a
different host application from its vendor's consumer chat app — different system prompt,
different default disposition toward calling available tools (a tool-execution agent is
plausibly *more* eager to call tools than a conversational chat surface), different permission
machinery (Claude Code CLI's own "auto mode classifier," seen blocking actions in earlier bridge
sessions, has no equivalent in Desktop chat). A result from Claude Code CLI or Codex CLI answers
"does *this CLI tool's* host behavior invoke `startup` automatically" — a real, useful, distinct
data point — but does **not** stand in for, or get averaged with, the Claude Desktop / ChatGPT
Desktop findings already in `08-initialization-investigation.md`. Each gets its own row in that
doc's results, clearly labeled by which specific tool produced it.

**Bias risk specific to CLI testing, same discipline as the Desktop tests:** don't ask a bridge
session "would you call startup" directly — that primes it. Give it an ordinary task and observe
whether it reaches for the tool unprompted, same as the "let's do devotions today" framing used
for Desktop.

**Codex CLI stream: run (31 Oct 2026).** Wired in via `codex mcp add`, tested on kofimule via a
Remote Control bridge session. Explicit invocation (`"Call the startup tool with purpose
devotions"`) worked end-to-end, READY, role resolved to chaplain. Unprompted invocation
(`"let's do devotions today"`, 3 runs) did **not** happen — the model answered directly from its
own knowledge each time instead of calling `startup`. Codex does not persist this server's stderr
anywhere discoverable (`~/.codex`, including `logs_2.sqlite`, searched directly) — only its own
`mcp_tool_call` event stream via `codex exec --json` is usable as evidence, which is what both
tests above relied on. Full raw evidence: `08-initialization-investigation.md` §0.9. The
`startup-mcp` entry is still live in `~/.codex/config.toml` on kofimule, not yet removed.

**Claude Code CLI stream: not yet run.** Still open.

## Exit criteria for each phase

- **Phase 1 closed** when A1–A3 (manual) are each answered with evidence (a screenshot/log, not
  an assumption) for both target clients.
- **Phase 2 closed** when section A (automated) passes and C has been run at least once per
  client.
- **Phase 3 closed** when D and E have been run at least once against live Drive content.
