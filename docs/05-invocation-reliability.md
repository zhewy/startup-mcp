# Invocation Reliability Strategy

Per brief §9, there are two separate reliability concerns. This document addresses the first
(does the client call `startup` at all); execution reliability (does the call then work
correctly) is addressed by `validation.py` and the BLOCKED/DEGRADED/READY status machine described
in `03-tool-contract.md`.

## What cannot be guaranteed

A client that lets the model decide which tools to call, when to call them, cannot be forced by
server-side configuration to call a specific tool. No MCP server capability changes this. Treat
any claim otherwise as false.

## Layered mitigations (in decreasing reliability)

1. **Explicit user action**, in order of reliability:
   - A client-level slash command or MCP *prompt* the user invokes directly (e.g. typing
     `/startup devotions` if the client surfaces server-defined prompts as slash commands). This
     bypasses model judgement entirely — the user's explicit action calls the tool.
   - A user typing a direct instruction ("call the startup tool with topic devotions") that
     leaves the model little room to skip the call.
   - **Action for this repo**: expose an MCP `prompts/list` entry (e.g. `startup_devotions` or a
     parameterized `startup` prompt) alongside the tool, so clients that support prompt-based
     invocation give the user a direct, non-model-mediated path. Needs confirmation of what
     Claude Desktop's and ChatGPT Desktop's UI actually does with MCP prompts (see test plan).

2. **Tool metadata engineered for selection**: tool name (`startup`, not e.g. `get_context` or
   something more generic competing clients might shadow), and a description that explicitly says
   *when* to call it ("at the start of a new conversation on this topic, before independent
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
- No attempt to detect and route around a skipped call by inferring topic from conversation
  history — that's exactly the kind of model-dependent discovery/interpretation brief §1 says this
  project exists to eliminate, not reintroduce inside the server.

## Open item requiring direct testing (see `06-test-plan.md`)

Confirm, for each client:
- Does the client surface MCP `prompts` to the user as an explicit, user-triggerable action
  (slash command or menu item)?
- Does a well-written tool description measurably change whether the model calls `startup`
  unprompted at the start of a fresh conversation, versus needing an explicit user instruction?

These are empirical questions this document cannot answer from investigation alone.
