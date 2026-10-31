# Prototype Test Plan

Maps to the acceptance tests in brief §11. Split into what this repo's automated tests cover now
(fixture-based, no live client/Drive needed) versus what needs a human running a real desktop
client (manual, one-time per phase).

## A. Automated (covered by `tests/test_server.py`, runs now, no client needed)

| # | Brief §11 item | Test |
|---|---|---|
| 6 | Identical inputs + source versions → equivalent results | `test_determinism`: two calls with the same topic against the fixture source produce identical `grounding`/`sources`/`versions`/`status`, differing only in `receipt.generated_at`. |
| 7 | Missing mandatory sources → BLOCKED, not false success | `test_missing_mandatory_source_blocks`: fixture with a mandatory source deleted → `status == "BLOCKED"` and the missing id appears in `unresolved`. |
| 8 | Source identities and provenance retained | `test_sources_have_provenance`: every entry in `sources[]` has non-empty `source_id`, `version`, `fetched_at`. |
| 5 | `devotions` produces relevant topic grounding | `test_devotions_topic`: `startup(topic="devotions")` against the fixture returns a `topic_context` entry sourced from the devotions fixture file, not from an unrelated topic. |
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
   ("call the startup tool for topic devotions first").

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
   the full evidence. Still outstanding: a ChatGPT Desktop run, a repeat run on Claude Desktop
   with a controlled instructions-present-vs-removed comparison (to separate Q1 from Q2), and a
   run that captures the actual chat text (this run used no GUI control, so what the model said
   in those 3 chats is unknown).

## Exit criteria for each phase

- **Phase 1 closed** when A1–A3 (manual) are each answered with evidence (a screenshot/log, not
  an assumption) for both target clients.
- **Phase 2 closed** when section A (automated) passes and C has been run at least once per
  client.
- **Phase 3 closed** when D and E have been run at least once against live Drive content.
