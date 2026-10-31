# MCP Initialization & Automatic Discovery — Findings and Recommendation

Responds to the 31 Oct 2026 handover on whether MCP connection initialization can reliably lead
to automatic conversation/task startup. Per that handover's own instruction ("record actual
behaviour, rather than treating model statements about having initialized as evidence"), this
document distinguishes **protocol-architecture facts** (true regardless of which client you run)
from **empirical client behavior** (true only if observed in a real client). **This session has
no GUI and no Claude Desktop or ChatGPT Desktop binary available to it** — the empirical items
below are explicitly marked UNTESTED and describe what a human needs to run locally, not a result.

**Naming note (added after Round 4):** the tool's `topic` parameter was renamed to `purpose`
(field name, log messages, fixture keys, and the `topic_context`/`grounding.topic_context`
bundle field, now `purpose_context`). Everything below written since the rename uses `purpose`.
The raw log-line quotes from Rounds 2–4, and the quoted local-check output in §0.7, are
reproduced verbatim as they were actually captured — they still say `topic=` / `topic_context`
because that was the field name in effect at the time, not a transcription inconsistency.

## 0. Implementation changes made (bounded, per handover §10 steps 1-4)

1. Inspected `src/startup_mcp/server.py`: server-level `instructions` were already present
   (added during the Phase 2 prototype) — step 10.2's answer is **yes, already supplied**, not
   absent.
2. Refined the wording of both `instructions` (server-level) and the `startup` tool's
   `description` to explicitly state the handover §3 distinction: *a successful connection does
   not by itself constitute grounding*, and a prior `startup` call doesn't cover a later,
   different task within the same conversation. No canonical authority, role designation, or
   governance logic was touched — this is wording only.
3. Added stderr logging (`logging` module, `STARTUP_MCP_LOG_LEVEL` env var, default `INFO`) at:
   process start (pid, fixture root, budget), each `startup` tool invocation (purpose, role hint),
   and each tool return (status, counts of unresolved/warnings). stdout is left untouched since
   it's reserved for the MCP JSON-RPC stream over stdio. This exists purely so a human running
   the handover §4 experiment has a timestamped, inspectable record of exactly when the process
   started and when (if ever) the tool was actually called — rather than relying on the model's
   own narrated account.
4. No renaming, caching, or `prompts` implementation was added — those remain open decisions
   (see §6-7 below and `docs/07-decisions-needed.md`), per "avoid unnecessary redesign."

## 0.5. Round 1 empirical results — Windows, Claude Desktop 4.4212.0 (31 Oct 2026)

A human ran the handover §4 / this doc's §3 experiment for real, via a Remote Control bridge
session on the machine where Claude Desktop actually runs. Raw findings, not narration:

**Setup notes, worth keeping for future runs:**
- Repo cloned to `D:\z\Downloads\mcptest\startup-mcp`; `pip install -e ".[dev]"` succeeded as-is.
- Plain `pytest` failed with a `PermissionError` on `%TEMP%` on this machine; passing `--basetemp`
  pointed at a writable folder fixed it (all 9 tests passed). Not a bug in this repo — a Windows
  temp-directory permission quirk on that machine — but worth doing by default on Windows:
  `pytest --basetemp=.pytest-tmp`.
- **The real `claude_desktop_config.json` location was not the documented path.** It was at
  `C:\Users\<user>\AppData\Local\Claude-Data\claude_<install-id>\claude_desktop_config.json` — a
  per-install, randomly-suffixed directory under `Local\Claude-Data`, not
  `%APPDATA%\Claude\claude_desktop_config.json` as `README.md` and
  `examples/claude_desktop_config.json` currently say. **The documented path should be treated as
  unreliable on Windows; search for `claude_desktop_config.json` under `%LOCALAPPDATA%` rather
  than assuming the path.**
- MCP server logs land in `C:\Users\<user>\AppData\Local\Claude\logs\`, split across
  `mcp-server-startup-mcp.log` (this server's own stdout/stderr, i.e. our diagnostic logging) and
  `main.log` (the client's own connection-level log, which is where the actual MCP protocol
  method calls are visible).

**What `main.log` shows about the handshake (this is the first real evidence of what the client
actually does, not just what the spec allows):** on connecting, Claude Desktop called
`initialize`, `notifications/initialized`, `tools/list`, `prompts/list`, and `resources/list` —
confirming it probes for prompts and resources capabilities even though this server registers
neither. Logged as "Connected to startup-mcp (1 tools); negotiated protocol 2025-11-25."

**What `mcp-server-startup-mcp.log` (our own log) shows:** two `startup-mcp process starting`
lines ~1 second apart (pid 24404, then pid 25692), both under the same parent process (pid 3016)
— read as two connections/handshakes at launch, not one. **No `startup tool invoked` line, and
no `tools/call` of any kind, appears anywhere in the log** — checked ~5 minutes after the last
process-start line, after the user had run 3 ordinary new conversations using a devotions-style
prompt ("let's do devotions today" or similar) without mentioning Startup MCP.

**Answer, as far as this round goes:**
- **Q2 is answered, empirically, for this client/version/test: NO — Claude Desktop 4.4212.0 did
  not call `startup` automatically across 3 fresh conversations in this test.** This isn't
  narration-dependent: the log would show a `tools/call` line if it had happened, and it doesn't,
  regardless of what the model said in the chats (which wasn't observed — no GUI control was
  used, so the chats' text is unknown).
- **Q1 is still not fully separable from Q2 by this test.** A "no" on Q2 is consistent with
  either "the client never surfaced `instructions` to the model" or "it surfaced them and the
  model still chose not to call the tool" — this test can't distinguish those. Confirming Q1
  specifically would need inspecting what context the client actually sends the model (not
  available from server-side logs), or a controlled comparison with `instructions` present vs.
  removed.
- **Q3 (shared connection across conversations) has supporting evidence, not full proof:** no new
  process-start line appeared after the initial one across the 3 subsequent conversations,
  consistent with one shared connection/process serving all of them. Exact timestamp correlation
  between each of the 3 chats and the connection log wasn't established (the log was checked once,
  after the fact, not per-chat).
- **Q4, Q5, Q7 are unaffected** by this round — they were answered from protocol architecture
  and existing implementation already (see below), not from this test.
- **Q6 got one new, useful data point:** `main.log` confirms Claude Desktop calls `prompts/list`
  on connect — so if this server implements the proposed MCP `prompts` capability
  (`docs/07-decisions-needed.md` item 6), the client is at least enumerating prompts at connection
  time, which is a necessary (not sufficient) precondition for it to surface one as a
  user-triggerable action. This doesn't confirm the UI surfaces it as a slash command — only that
  the client isn't ignoring the capability outright.

## 0.6. Round 2 empirical results — explicit user-triggered call (31 Oct 2026)

Same machine/install as §0.5, same log file. The user opened a new conversation and typed an
explicit instruction naming the tool/action directly (e.g. "call the startup tool with purpose
devotions", or a question-phrased variant — which exact phrasing produced which call line below
wasn't separately recorded).

```
2026-10-31 20:38:52,984 startup-mcp INFO startup tool invoked: topic='devotions' role_hint=None
2026-10-31 20:38:53,022 startup-mcp INFO startup tool returned: topic='devotions' status=READY unresolved=0 warnings=0
2026-10-31 20:39:05,355 startup-mcp INFO startup tool invoked: topic='devotions' role_hint=None
2026-10-31 20:39:05,356 startup-mcp INFO startup tool returned: topic='devotions' status=READY unresolved=0 warnings=0
```

**Q7 is now confirmed empirically, not just by design: an explicit, literal user instruction does
get Claude Desktop 4.4212.0 to call `startup`, twice in a row, both returning READY.** This is the
one invocation path tested so far, on this client, that actually produced a `tools/call`. It
stands in direct contrast to Round 1 (§0.5), where the same client, same install, same server,
produced zero calls across 3 unprompted conversations — the only variable that changed was the
explicitness of the user's instruction.

One correction to §0.5's assumption: **`main.log` does not log individual `tools/call` entries at
all** — it only recorded the connection-level handshake and had nothing new since the initial
connection, even though two real tool calls happened in between. The server's own log
(`mcp-server-startup-mcp.log`) is the only place these calls are actually visible; don't rely on
`main.log` for call-level evidence.

Still not established from this round: whether both calls came from the same chat or two
different ones, which exact phrasing (command vs. question) produced which call (the reporting
session noted that if the question-phrased variant was used at all, it also succeeded — so
phrasing doesn't appear to block it, but this wasn't controlled rigorously), and what the model
said back to the user in either case.

## 0.7. Round 3 empirical results — purpose routing through the real Desktop path (31 Oct 2026)

After adding the `devotionals` and `librarian` purposes (see the fixture changes in this branch's
later commits), a different Remote Control session on the same Windows machine re-ran the test
with three explicit calls, each naming a different purpose:

```
22:22:21,666 startup tool invoked: topic='devotionals' role_hint=None
22:22:21,667 startup tool returned: topic='devotionals' status=READY unresolved=0 warnings=0
22:23:09,924 startup tool invoked: topic='librarian' role_hint=None
22:23:09,926 startup tool returned: topic='librarian' status=READY unresolved=0 warnings=0
22:23:50,671 startup tool invoked: topic='some-made-up-topic' role_hint=None
22:23:50,674 startup tool returned: topic='some-made-up-topic' status=DEGRADED unresolved=0 warnings=2
```

**Directly observed through the real Desktop path:** all three statuses matched expectation —
`devotionals` and `librarian` both READY, the made-up purpose DEGRADED with 2 warnings (no
purpose mapping, no role mapping). Purpose-based routing to the correct status is confirmed live,
not just in `pytest`.

**Not directly observed through the Desktop path, only inferred:** the server's own log records
status and counts, not the actual returned content. The reporting session separately ran
`startup()` locally, against the same fixture, and got the expected content (`devotionals` →
"this is devotional topic" / role `chaplain`; `librarian` → "this is librarian" / role
`librarian`; the made-up purpose → `role_contract: null`, empty `topic_context`) — quoted
verbatim as captured at the time, before the `topic`→`purpose` rename (now `purpose_context` /
"this is devotional purpose") — but that's a local check standing in for the Desktop-path
content, not a capture of what Desktop itself
returned to the model. It's a reasonable inference (same server binary, same fixture, and
`test_determinism_across_identical_calls` already proves identical inputs produce identical
content) rather than a leap, but it's still an inference, not a direct observation — logged here
as that distinction, not blurred into "confirmed."

Also noted, unexplained: two server processes started at launch (two pids, ~seconds apart) —
consistent with the same pattern seen in Round 1 (§0.5), so not a new anomaly, just corroborating
evidence for the existing "two connections at launch" observation. Investigated further in §0.8.

## 0.8. Investigation — the two-process-at-launch anomaly (31 Oct 2026)

Ruled out, with direct evidence (read-only checks, no config or code changes made on the remote
machine for this part):

- **Not a duplicate config entry.** The real `claude_desktop_config.json`'s `mcpServers` object
  has exactly one `startup-mcp` key. Only one server is configured.
- **Not two separate logical connections from the client's own point of view.** `main.log` shows
  exactly one `Launching MCP Server: startup-mcp` and one `Connected to startup-mcp (1 tools)`
  line for this launch (an `[localMcpBridge] announcing startup-mcp` line appeared twice, cause
  unknown — not necessarily related).
- **Not a probe-then-retry pattern.** Neither process exited. Both `python -m startup_mcp.server`
  processes (pids 23960 and 4672 in this run, ~4 seconds apart — 22:21:22 and 22:21:26) stayed
  alive indefinitely under the same parent, confirmed to be the single running `Claude.exe`
  instance (`Claude_4.4212.0.0_x64__pzs8sxrjxfjjc`), not a helper, updater, or second window.

**What the evidence suggests, without yet being conclusive:** only one `initialize` request was
logged server-side, and its timing lines up closely with the *second* process (pid 4672)
entering its serve loop (22:21:29,144) and the reply going out (22:21:29,245) — while the first
process (pid 23960) entered its own serve loop earlier (22:21:26,796) and logged no further
activity afterward. This is suggestive that the client spawns a process, abandons it without
ever writing to its stdin (so it just sits blocked in its stdio read loop forever, which matches
"never exits"), and spawns a second one that it actually talks to — but this is inference from
timing, not confirmed, because **the `startup tool invoked`/`returned` log lines didn't originally
record which process handled them.**

**Fix applied:** `server.py` now includes `pid=%s` (via `os.getpid()`) in the `startup tool
invoked` and `startup tool returned` log lines (previously only the process-start line had it).
The next live test that triggers a `startup` call will show, definitively, which of the two pids
actually serves requests — closing this open question with direct evidence instead of timing
inference.

**Round 4 result (1 Nov 2026), after the pid-logging fix — definitive, and corrects the earlier
guess:**

```
00:11:58,520 startup-mcp process starting: pid=23000 ...
00:11:58,526 startup-mcp entering stdio serve loop: pid=23000
00:12:00,157 startup-mcp process starting: pid=6100 ...
00:12:00,159 startup-mcp entering stdio serve loop: pid=6100
00:12:13,876 startup tool invoked: pid=23000 topic='devotions' role_hint=None
00:12:13,878 startup tool returned: pid=23000 topic='devotions' status=READY unresolved=0 warnings=0
```

The call went to **pid 23000, the first-spawned process** — not the second one, contradicting
this doc's earlier timing-based guess (which pointed at the later-spawned pid in Round 3). That
earlier guess is now known to be wrong, not just unconfirmed; recorded here rather than quietly
corrected, since the point of this doc is to distinguish inference from evidence.

**Status of this thread: behaviorally closed, root cause still open.** Across all observed runs:
a second, idle `python -m startup_mcp.server` process is spawned a second or two after the first,
under the same Claude Desktop parent, and never does anything — this doesn't affect correctness
(the three READY/DEGRADED results in Round 3 were unaffected) and isn't a bug in this server (the
server does nothing to cause its own duplication; it's spawned, once each, by the client). The
*cause* — why Claude Desktop launches a second instance it never talks to — remains unexplained
and is not pursued further here: it looks like Claude Desktop's own behavior, not something
fixable or diagnosable from this project's side. Worth a one-line mention if ever filing feedback
with Anthropic about Claude Desktop's MCP process management, but out of scope for this repo.

## 1. Answers to Q1-Q7

**Q1. Does Claude Desktop expose MCP server initialization instructions to the model?**
Still not directly confirmed — see §0.5's caveat: the Round 1 result (no automatic call) is
consistent with "not surfaced" but doesn't rule out "surfaced but the model didn't act on it."
What's confirmed at the protocol level: the `instructions` field exists in the `InitializeResult`
and is now populated (§0.2), and `main.log` from Round 1 confirms the real client completes the
handshake (`initialize`, `tools/list`, `prompts/list`, `resources/list`) — but server-side logs
can't show what the client does with the `instructions` string after reading it. Still open.

**Q2. Can those instructions cause the model to invoke `startup` automatically in a new
conversation?**
**Tested once, on Windows / Claude Desktop 4.4212.0(§0.5): no.** Across 3 fresh conversations
using a devotions-style prompt, with no mention of Startup MCP, no `tools/call` to `startup`
appeared in the log. This is one data point on one client version, not a general proof for every
client/version — but it's a real negative result, not an absence of testing. Worth re-running on
ChatGPT Desktop and on a later Claude Desktop version before generalizing.

**Q3. What happens when multiple conversations share an already-established MCP connection?**
Partially tested (§0.5): no new server-process-start line appeared across the 3 conversations
after the initial connection, consistent with one shared connection serving all of them — but
exact per-chat timestamp correlation wasn't captured, so this is supporting evidence, not proof.
Protocol-level fact underneath it: the MCP spec itself does not mandate any particular mapping
between "connection" and "conversation" — nothing requires a new `initialize` handshake per
conversation, so a client is free to do either.

**Q4. Can the client distinguish a new conversation from a new task for startup purposes?**
This one has a confident, protocol-grounded (not empirical) answer: **no, not from MCP protocol
signals alone.** MCP has no message type that signals "a new conversation has begun" or "a new
task has begun" within an existing connection — the server only ever sees `initialize` (once per
connection), `tools/list`, and individual tool-call requests, none of which carry a
conversation- or task-boundary flag. The only way the server can know is if the caller's tool
call itself conveys it (e.g. a fresh `purpose`/`role` argument on each call). This is precisely
why the tool contract puts `purpose` and `role` as **call-time arguments** rather than something
resolved once from connection-level state (see `docs/03-tool-contract.md`) — the architecture
already assumes the server cannot infer task boundaries and requires the caller to state them
every time.

**Q5. Can the surface provide role context, and how should that context be validated?**
Already implemented, not just designed: `startup(purpose, role)` accepts a caller-supplied role
value; `procedure.py` treats it purely as an advisory hint, resolves the actual applicable role
from the manifest's canonical `role_for_purpose` mapping, and emits a `warnings` entry (without
blocking) if the hint and the resolved role disagree — see
`test_role_hint_is_advisory_only` in `tests/test_server.py`. `permissions.write_authority` is
hardcoded to `false` regardless of what any source or caller claims (the "defensive floor"
described in `docs/03-tool-contract.md`). Naming note: the handover's illustrative signature uses
`role_context`; this implementation kept the existing `role` parameter name rather than renaming
it, since the semantics already match and renaming a working parameter isn't needed to answer
this question — flag if you'd prefer the rename for clarity anyway.

**Q6. Is there a more reliable client-supported startup mechanism than model-directed
invocation?**
Two protocol-native candidates, both still UNTESTED for actual client support:
- **MCP `prompts` capability** — a server can define prompts that the spec allows clients to
  surface as a direct, user-triggerable action (e.g. a slash command), which would bypass model
  judgment entirely. Not yet implemented here (`docs/07-decisions-needed.md` item 6) — building
  it is cheap, but whether Claude Desktop or ChatGPT Desktop actually turn a server-defined
  prompt into a UI-level slash command is exactly as unverified as instructions/invocation.
- **Host-level mechanisms outside MCP** (e.g. a client's own "custom instructions" or "project
  instructions" feature, if it has one) — these aren't part of the MCP spec at all, so the MCP
  server can't configure them; a human would need to check each client's own settings
  documentation.
Neither is confirmed more reliable than model-directed invocation yet — only MCP `prompts` is
something *this server* could add and still remain in scope.

**Q7. If automatic startup is unavailable, what is the smallest dependable user-triggered
alternative?**
**Confirmed empirically (§0.6), not just by design.** A short, literal user phrase ("Startup
MCP — initialise devotions," or the handover's own example) actually produced two `tools/call`
hits on the real client, both returning READY — in direct contrast to Round 1's zero hits across
3 unprompted conversations on the same install. It works because it only depends on the tool's
`description`/schema being visible at `tools/list` time — a channel that, unlike `instructions`,
the client must expose for tool-calling to function at all (see the earlier distinction drawn in
`docs/05-invocation-reliability.md`). This is now the one invocation path with both a design
rationale and a real log showing it worked.

## 2. Recommendation

**Updated after Rounds 1 and 2:** keep the explicit user-triggered call (Q7) as the dependable
path — it's no longer just a design assumption, it's now the only invocation path with a real
log showing it worked, twice, on a real client. Continue to treat automatic invocation via
`instructions` (Q1/Q2) as not working, on the one client/version tested so far — represent that to
the user as a tested negative, not an open hypothesis. Do not treat a model's own claim of having
"initialized" or "checked startup" as evidence either way, per the handover's own caution; the
server log remains the only trustworthy evidence, and `main.log` turned out not to log call-level
detail at all (§0.6), so don't rely on it for that purpose either.

Next worth testing, in priority order: (1) a ChatGPT Desktop run of both rounds, since nothing
here generalizes across clients; (2) the MCP `prompts` capability (`docs/07-decisions-needed.md`
item 6), now that §0.5 confirmed Claude Desktop at least calls `prompts/list` on connect; (3) a
controlled instructions-present-vs-removed comparison, to finally separate Q1 from Q2 rather than
leaving Q1 open by default.

## 3. What a human needs to do next (mirrors handover §4, now instrumented)

1. Set `STARTUP_MCP_LOG_LEVEL=INFO` (default) and wire this server into Claude Desktop per
   `examples/claude_desktop_config.json`.
2. Locate where that client stores captured stderr for MCP server subprocesses (client-specific;
   check its own MCP/logs settings).
3. Restart/reconnect the client; confirm a `startup-mcp process starting: pid=...` line appears.
4. Open a brand-new conversation, say nothing about Startup MCP, and ask something that implies
   needing grounded content (e.g. "let's do devotions today").
5. Check the log for a `startup tool invoked...` line. Its presence/absence, with a timestamp,
   is the actual answer to Q2 — not the model's own narration.
6. Open several more new conversations without restarting the client; compare pids in the log to
   answer Q3.
7. Within one conversation, introduce a second, different purpose partway through; check whether a
   second `startup tool invoked` line appears for it (tests whether the model independently
   re-grounds on task change, which Q4 already establishes the *server* cannot force on its own).
8. Repeat all of the above in ChatGPT Desktop, separately noting whether it accepts this stdio
   server at all (per `docs/01-feasibility.md` §1, this is itself unconfirmed).

Report the raw log lines, not a summary of what the model said it did.
