# Decisions Requiring User Approval

These are the choices made provisionally in this repo that the brief flags as needing explicit
sign-off before Phase 3 (live Brain integration) proceeds. Nothing below has been acted on against
live Brain infrastructure — Phase 2 uses only a local fixture.

1. **Google Drive OAuth scope.** Proposed: a dedicated OAuth client with `drive.readonly` scope
   (see `04-authentication.md`). This scope can see *all* of the user's Drive, read-only, not just
   the Brain folder — Google does not offer a "read-only, this-folder-only, but I didn't create
   these files" scope without either (a) the broader `drive.readonly`, or (b) `drive.file`
   combined with the user individually picking the Brain folder through a Google file-picker
   consent flow. **Needs a decision**: accept broad `drive.readonly`, or require the narrower
   picker-based flow (more setup friction, smaller blast radius if the token is ever compromised).

2. **Where OAuth credentials and tokens live.** Proposed: user-local config directory
   (`~/.config/startup-mcp/`), never committed to this repository, never logged. Confirm this
   location/approach is acceptable, and confirm the repository's `.gitignore` should explicitly
   exclude any such path if the server is ever run from inside a clone of this repo.

3. **Context-size budget default.** Not yet set to a specific number — `config.py` exposes it as
   configurable but Phase 2 ships an illustrative default. Needs a number (or a formula, e.g. "N
   tokens, leaving headroom for M turns of conversation") from the user, since this directly
   trades off completeness of grounding against context consumed.

4. **Mandatory vs optional source designation.** This repo's validator trusts Brain's own data for
   which sources are mandatory (brief §7: this must come from Brain, not be hardcoded). Phase 3
   integration needs the user (or Brain's own canonical data, once retrieval is built) to confirm
   the actual mandatory-reading list format so `validation.py`'s parsing logic matches it exactly
   — guessing the shape of that list risks misclassifying a mandatory source as optional.

5. **ChatGPT Desktop viability for this project at all.** Per `01-feasibility.md` §1, stdio
   support in ChatGPT Desktop is unconfirmed and possibly absent for the consumer app. If Phase 1
   manual testing (`06-test-plan.md` §B2) shows it's not supported, decide whether to (a) scope
   this project to Claude Desktop only for now, (b) build a Streamable-HTTP transport binding for
   ChatGPT (more infrastructure: needs a running local HTTP endpoint, not just a spawned stdio
   process), or (c) wait on OpenAI's Developer Mode maturing.

6. **MCP `prompts` capability.** Proposed addition (see `05-invocation-reliability.md`) of a
   server-defined prompt for explicit, non-model-mediated invocation. Not yet implemented in
   Phase 2's code — confirm this is wanted before adding it, since it changes the tool surface
   beyond the single `startup` tool the brief scopes for the initial version (brief §8: "One
   primary startup tool" — a `prompts` entry that simply invokes the same tool is arguably still
   within that scope, but flagging the distinction for approval rather than assuming it; note the
   tool surface already grew to two tools, `startup`/`ground`, for a different reason — see
   decision 8 below — so this one needs re-evaluating against the current surface, not the
   original single-tool one).

7. **Permanent local service vs on-demand process.** Brief §8 says "No permanent local service
   unless required." Current design: the client (Claude Desktop) spawns the server process
   on-demand per its own MCP lifecycle, and the process exits when the client closes it — nothing
   here runs as a standing background service/daemon. Confirm this matches intent before any
   future work considers caching Drive content across process restarts for performance (which
   would start to resemble a stateful local service and deserves its own review).

8. **Should `startup()` ever take arguments?** Currently fully argument-free by design, per the
   "even that might be more than necessary initially" framing from the proposal that motivated
   the two-tool split (see `02-architecture.md`'s "Tool surface" section). The alternative — a
   light hint argument (e.g. an anticipated purpose) that tailors `startup()`'s `guidance` text —
   was considered and set aside for now, since any per-call tailoring risks pulling this tool back
   toward doing retrieval, which is exactly the responsibility kept on `ground`'s side of the
   split. Default is argument-free unless this is explicitly revisited.
