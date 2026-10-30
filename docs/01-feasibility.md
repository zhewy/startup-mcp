# Feasibility Assessment

Status: investigation only. Nothing described here as "confirmed" has been verified against a
running ChatGPT Desktop or Claude Desktop instance — it is based on current public documentation
and community reporting, gathered 2026-10-30. **Re-verify against each client's live settings
before relying on it.**

## 1. Local stdio MCP support

| Client | stdio (local process) support | Confidence |
|---|---|---|
| **Claude Desktop** | Yes. Local MCP servers are configured directly in `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: `%APPDATA%\Claude\claude_desktop_config.json`) and launched by the app as a child process over stdio. This is Anthropic's original, primary MCP transport and is well established. | High |
| **ChatGPT Desktop** | Unclear / contested. OpenAI's documented, supported MCP transports for ChatGPT are remote (Streamable HTTP, SSE) via "Developer Mode" (beta, plan-gated — at least one source says Team plans are excluded). Reference stdio servers (filesystem, Figma Dev Mode, local Stripe MCP) are reported **not** to load. A more recent (Oct 2026) community guide claims the desktop app's MCP settings can run local stdio servers, but this conflicts with OpenAI's own Developer Mode docs from earlier in 2026. | Low — contradictory sources |

**Consequence for architecture:** Startup MCP cannot assume it will be launched the same way by
both clients. It must work as a standard stdio MCP server (satisfies Claude Desktop today), and
the implementation should not hard-wire stdio-only assumptions into business logic, so that a thin
Streamable-HTTP transport wrapper could be added later for ChatGPT Desktop without touching the
grounding/retrieval logic. **This needs a hands-on test against a real ChatGPT Desktop
installation before Phase 1 is considered closed for that client** (see test plan, §6).

## 2. Google Drive authentication

Both clients' *built-in* Google Drive connectors (Claude's "Connectors" settings, ChatGPT's
consumer Drive connector) are separate, consumer-oriented integrations. No source found indicates
either client exposes those connector credentials to a locally-launched MCP server process. The
practical, confirmed pattern used by third-party Google Drive MCP servers is:

- Register your own OAuth 2.0 **Desktop app** client in Google Cloud Console (not "Web
  application" — that's for server-side redirect flows).
- Run a one-time local OAuth consent flow from the MCP server itself the first time it starts.
- Cache the resulting refresh token locally (e.g. `~/.config/startup-mcp/token.json`, file
  permissions `0600`), and refresh it silently on subsequent runs.

**Decision required (see `07-decisions-needed.md`):** Startup MCP will run its own Google OAuth
client and maintain its own token cache. It will *not* attempt to read or depend on either
desktop app's connector session. This is the only pattern with public, working precedent.

## 3. Invocation reliability

Neither client guarantees that a model will call a given tool just because a system prompt or
tool description asks it to — this is a known, structural limitation of model-initiated tool use,
not a bug to "fix" in the MCP server. What *can* be hardened:

- **Tool description** can be written to make `startup` the unambiguous, low-cost first move for
  any Brain-dependent conversation (name, description, and input schema all signal "call this
  first").
- **Explicit user-issued commands** (e.g. the user typing `startup devotions` or a client-level
  slash command/prompt template, where the client supports MCP "prompts") are far more reliable
  than hoping the model infers it should call the tool.
- **MCP `prompts` capability**: both the spec and (per public docs) Claude Desktop support
  server-defined prompts that a user can invoke explicitly (e.g. via a `/` command in Claude
  Desktop). ChatGPT Desktop's prompt-invocation UI is unconfirmed.
- Nothing short of the user (or a client-specific slash command) explicitly invoking the tool can
  be treated as a *guarantee*. Design the server so a skipped `startup` call fails loud later
  (e.g. any Brain-dependent follow-up the model attempts without grounding should be visibly
  unverified) rather than failing silently.

## 4. Desktop → Web continuity

No source confirms that MCP tool-call results from a Desktop session are available to the *same
conversation* when continued in a browser tab against the provider's web app — this depends on
whether the provider's backend treats Desktop-originated tool results as durable conversation
history synced to the web client, which is a product behavior, not an MCP protocol guarantee.
**This must be tested directly** (§6) rather than assumed. Our mitigating design choice: the
grounding bundle is returned as an explicit, self-contained message in the tool result (not just
retained in local MCP process memory), and includes a "startup receipt" with enough source/version
identifiers that a model picking the conversation back up on Web — or after compaction — can
detect staleness and re-call `startup` if needed.

## 5. Summary

| Question | Status |
|---|---|
| Claude Desktop launches local stdio MCP servers | Confirmed by documented, standard mechanism |
| ChatGPT Desktop launches local stdio MCP servers | **Unconfirmed, contradictory sources — must test directly** |
| Either client exposes its own Drive connector credentials to a local MCP server | No evidence this is possible — assume no, build independent OAuth |
| Tool invocation can be guaranteed by prompt/description alone | No — mitigate via explicit user commands / MCP prompts, not guarantees |
| Desktop-originated grounding survives a switch to the Web client | Unconfirmed — must test directly; design bundle to be self-contained regardless |

Sources consulted: OpenAI Developer Mode / MCP docs (as reported secondhand), Anthropic Claude
Desktop MCP configuration docs (as reported secondhand), and community write-ups on Google Drive
MCP servers (piotr-agier/google-drive-mcp, fast.io guides, lobehub/glama listings). None of these
were fetched directly in this pass — treat every claim above as needing a direct check against the
primary source or a live client before Phase 1 is signed off.
