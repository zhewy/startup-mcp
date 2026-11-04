# Invocation Reliability Strategy

> Current behaviour (4 Nov 2026): `startup()` is a placeholder returning
> `"to be defined"`; no startup invocation is required. `ground` is retained as a
> local fixture prototype. Earlier invocation strategies and startup payload
> descriptions below are design history, not the current startup contract.


Per brief §9, there are two separate reliability concerns. This document addresses the first
(does the client call the tool at all); execution reliability (does the call then work
correctly) is addressed by `validation.py` and the BLOCKED/DEGRADED/READY status machine described
in `03-tool-contract.md`.

**Naming note:** everything below was written against a single `startup(purpose, role?)` tool,
since renamed to `ground` after the tool surface was split in two (see `02-architecture.md`'s
"Tool surface" section and `03-tool-contract.md`'s naming note). Where this document says
`startup` below and means "the tool that performs full deterministic retrieval," read that as
`ground` — preserved as originally written rather than silently edited, same discipline as the
`topic`→`purpose` rename. The new, separate `startup()` entrypoint has its own, not-yet-answered
invocation question, addressed in the new section near the end of this document.

## What cannot be guaranteed

A client that lets the model decide which tools to call, when to call them, cannot be forced by
server-side configuration to call a specific tool. No MCP server capability changes this. Treat
any claim otherwise as false.

## Layered mitigations (in decreasing reliability)

1. **Explicit user action**, in order of reliability:
   - A client-level slash command or MCP *prompt* the user invokes directly (e.g. typing
     `/startup devotions` if the client surfaces server-defined prompts as slash commands). This
     bypasses model judgement entirely — the user's explicit action calls the tool.
   - A user typing a direct instruction ("call the startup tool with purpose devotions") that
     leaves the model little room to skip the call.
   - **Action for this repo**: expose an MCP `prompts/list` entry (e.g. `startup_devotions` or a
     parameterized `startup` prompt) alongside the tool, so clients that support prompt-based
     invocation give the user a direct, non-model-mediated path. Needs confirmation of what
     Claude Desktop's and ChatGPT Desktop's UI actually does with MCP prompts (see test plan).

2. **Tool metadata engineered for selection**: tool name (`startup`, not e.g. `get_context` or
   something more generic competing clients might shadow), and a description that explicitly says
   *when* to call it ("at the start of a new conversation for this purpose, before independent
   reasoning") and *why not to substitute for it* ("do not attempt to independently discover
   grounding documents"). This raises the odds the model selects it unprompted, but is advisory,
   not enforced.

3. **Client-level startup instructions** (a system prompt / custom instructions configured once
   in the client, outside this repo, e.g. "for any Brain-dependent conversation, always call the
   `startup` MCP tool first") — out of scope to configure from the server itself, but worth
   documenting as a recommended user-side setup step, since it's the only lever between "tool
   exists" and "tool gets called" that sits above the model's per-turn judgement and below
   requiring an explicit command every time.

4. **Fail loud, not silent, on a skipped call.** Because invocation can't be guaranteed, the
   design assumes it sometimes won't happen, and treats that as the normal case to design for, not
   an edge case:
   - The tool's own description and the bundle's `receipt` field make the *absence* of a startup
     call conspicuous: any Brain-dependent answer given without it is visibly ungrounded to a
     careful reader, because there is no READY/DEGRADED/BLOCKED receipt to point to.
   - This repo does not attempt any technical means of detecting "the model should have called
     this but didn't" from inside the server — the server only knows about calls that happen.
     That detection, if ever wanted, lives in the client/user layer (e.g. a user habit of checking
     for a startup receipt before trusting Brain-dependent output), not in the MCP.

## What this repo does NOT attempt

- No polling, no "did you call startup yet" nagging via side channels — there is no side channel;
  MCP servers can't inject unsolicited messages into a conversation.
- No attempt to detect and route around a skipped call by inferring purpose from conversation
  history — that's exactly the kind of model-dependent discovery/interpretation brief §1 says this
  project exists to eliminate, not reintroduce inside the server.

## Open item requiring direct testing (see `06-test-plan.md`)

Confirm, for each client:
- Does the client surface MCP `prompts` to the user as an explicit, user-triggerable action
  (slash command or menu item)?
- Does a well-written tool description measurably change whether the model calls `startup`
  unprompted at the start of a fresh conversation, versus needing an explicit user instruction?

These are empirical questions this document cannot answer from investigation alone.

## New open question, 1 Nov 2026: chained invocation across the two-tool split

Splitting one tool into `startup()` (lightweight) and `ground()` (full retrieval, what this
document calls `startup` above) doesn't make the reliability problem go away — it potentially
doubles it:

1. Does a model call `startup()` unprompted at all? Untested. All existing evidence (0/5 trials
   across Claude Desktop and Codex CLI, per `08-initialization-investigation.md`) is for the
   *old*, now-`ground`-named tool, and does not transfer automatically to this new, differently
   named, differently described, argument-free tool.
2. *If* a model does call `startup()` (prompted or not) and receives its `guidance` text — does
   that returned content then cause it to call `ground()` on its own, without a further explicit
   instruction? This is the one genuinely new mechanism the split introduces: per the handshake
   analysis in this conversation's chat record, a tool's *return value* is a real message the
   model reads directly, unlike the `instructions`/`description` fields whose exposure to the
   model is an unproven, client-dependent black box. If `startup()`'s guidance reliably triggers
   an unprompted `ground()` call even when nothing else does, that would be a materially stronger
   result than anything found so far — but it is a hypothesis, not yet a finding.

Both need their own live-client rounds (same discipline as before: don't ask the model directly
whether it would call the tool, give it an ordinary task and observe). Tracked as new rows in
`06-test-plan.md`.

## Update, 31 Oct 2026

The three lifecycle events this document was conflating — connection initialization, conversation
startup, and task startup — are now disentangled explicitly, with answers to Q1-Q7 from the
follow-up handover, in `08-initialization-investigation.md`. Notably: MCP has no protocol
primitive for "new conversation" or "new task" at all, so the server can never detect either on
its own — this is a confident architectural finding, not an open question, and it's why `purpose`/
`role` are call-time tool arguments rather than connection-level state. (The parameter was named
`topic` at the time this finding was first written; see `docs/03-tool-contract.md`'s naming note
for the later rename to `purpose`.)
