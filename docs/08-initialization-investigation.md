# MCP Initialization & Automatic Discovery — Findings and Recommendation

Responds to the 31 Oct 2026 handover on whether MCP connection initialization can reliably lead
to automatic conversation/task startup. Per that handover's own instruction ("record actual
behaviour, rather than treating model statements about having initialized as evidence"), this
document distinguishes **protocol-architecture facts** (true regardless of which client you run)
from **empirical client behavior** (true only if observed in a real client). **This session has
no GUI and no Claude Desktop or ChatGPT Desktop binary available to it** — the empirical items
below are explicitly marked UNTESTED and describe what a human needs to run locally, not a result.

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
   process start (pid, fixture root, budget), each `startup` tool invocation (topic, role hint),
   and each tool return (status, counts of unresolved/warnings). stdout is left untouched since
   it's reserved for the MCP JSON-RPC stream over stdio. This exists purely so a human running
   the handover §4 experiment has a timestamped, inspectable record of exactly when the process
   started and when (if ever) the tool was actually called — rather than relying on the model's
   own narrated account.
4. No renaming, caching, or `prompts` implementation was added — those remain open decisions
   (see §6-7 below and `docs/07-decisions-needed.md`), per "avoid unnecessary redesign."

## 1. Answers to Q1-Q7

**Q1. Does Claude Desktop expose MCP server initialization instructions to the model?**
UNTESTED. Cannot be determined without a running Claude Desktop instance. What's confirmed at
the protocol level: the `instructions` field exists in the `InitializeResult` and is now
populated (§0.2). Whether Claude Desktop reads it and folds it into the model's context, versus
just logging or displaying it, is unverified — see `docs/01-feasibility.md` and
`docs/05-invocation-reliability.md`, which already flagged this as an open gap before this
handover.

**Q2. Can those instructions cause the model to invoke `startup` automatically in a new
conversation?**
UNTESTED, for the same reason, and logically downstream of Q1 — if the client doesn't surface
`instructions` to the model at all, this can't be true regardless of wording quality. The server
now advertises the capability per handover §3's illustrative text; whether that advertisement
*causes* invocation is exactly what the local experiment in handover §4 needs to establish. This
implementation cannot be marked complete until that test runs.

**Q3. What happens when multiple conversations share an already-established MCP connection?**
Mostly UNTESTED, with one protocol-level fact available: the MCP spec itself does not mandate
any particular mapping between "connection" and "conversation" — a client is free to reuse one
long-lived connection across many conversations, or open a fresh connection per conversation.
Nothing in the spec requires a new `initialize` handshake per conversation. Whether Claude
Desktop or ChatGPT Desktop spawn one server process per app session (shared across chats) or one
per conversation is implementation-specific and not something this session can observe. The
added process-start log line (§0.3) gives a human a concrete signal: if the pid and start
timestamp stay constant across several new chats, the connection/process is shared; if a fresh
log line appears per chat, it isn't.

**Q4. Can the client distinguish a new conversation from a new task for startup purposes?**
This one has a confident, protocol-grounded (not empirical) answer: **no, not from MCP protocol
signals alone.** MCP has no message type that signals "a new conversation has begun" or "a new
task has begun" within an existing connection — the server only ever sees `initialize` (once per
connection), `tools/list`, and individual tool-call requests, none of which carry a
conversation- or task-boundary flag. The only way the server can know is if the caller's tool
call itself conveys it (e.g. a fresh `topic`/`role` argument on each call). This is precisely why
the tool contract puts `topic` and `role` as **call-time arguments** rather than something
resolved once from connection-level state (see `docs/03-tool-contract.md`) — the architecture
already assumes the server cannot infer task boundaries and requires the caller to state them
every time.

**Q5. Can the surface provide role context, and how should that context be validated?**
Already implemented, not just designed: `startup(topic, role)` accepts a caller-supplied role
value; `procedure.py` treats it purely as an advisory hint, resolves the actual applicable role
from the manifest's canonical `role_for_topic` mapping, and emits a `warnings` entry (without
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
Already available today, with no further implementation needed: a short, literal user phrase
("Startup MCP — initialise devotions," or the handover's own example) leaves the model little
room to skip the call, because it only depends on the tool's `description`/schema being visible
at `tools/list` time — a channel that, unlike `instructions`, the client must expose for
tool-calling to function at all (see the earlier distinction drawn in
`docs/05-invocation-reliability.md`). This remains the one invocation path with no open
"is this surfaced at all" question attached to it.

## 2. Recommendation

Keep the explicit user-triggered call (Q7) as the dependable baseline now. Treat automatic
invocation via `instructions` (Q1/Q2) as a hypothesis the implementation now supports testing,
not a shipped feature — don't represent it to the user as working until a human runs the
handover §4 steps against a real Claude Desktop (and, separately, ChatGPT Desktop) install and
reports what the stderr log and the client's own MCP logs actually show. Do not treat a model's
own claim of having "initialized" or "checked startup" as evidence either way, per the
handover's own caution.

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
7. Within one conversation, introduce a second, different topic partway through; check whether a
   second `startup tool invoked` line appears for it (tests whether the model independently
   re-grounds on task change, which Q4 already establishes the *server* cannot force on its own).
8. Repeat all of the above in ChatGPT Desktop, separately noting whether it accepts this stdio
   server at all (per `docs/01-feasibility.md` §1, this is itself unconfirmed).

Report the raw log lines, not a summary of what the model said it did.
