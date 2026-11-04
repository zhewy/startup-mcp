# Authentication Approach

## Decision

zmcp authenticates to Google Drive with its **own** OAuth 2.0 client, independent of
either desktop app's built-in Drive connector. See `01-feasibility.md` §2 for why: no evidence
either client exposes connector credentials to a local MCP process, and the working
precedent among existing Google Drive MCP servers is a dedicated client.

This is **not implemented yet** in this repo (Phase 2 uses a local fixture source, not live
Drive — see `02-architecture.md`). This document specifies the approach for Phase 3.

## Client setup (one-time, by the user, in Google Cloud Console)

1. Create (or reuse) a Google Cloud project.
2. Enable the Google Drive API.
3. Create an OAuth 2.0 **Desktop app** client ID (not "Web application" — Desktop app clients
   support the installed-app / loopback redirect flow with no client secret exposure risk
   appropriate for a local process).
4. Request the **narrowest workable scope**: `drive.readonly`
   (`https://www.googleapis.com/auth/drive.readonly`). If the Brain folder can be scoped further
   (e.g. `drive.file` restricted to files the app has been explicitly granted), prefer that; this
   needs confirmation against which scope actually lets a read-only service enumerate an existing
   shared folder it did not create. **Decision required from the user**: confirm whether
   `drive.readonly` (broad, read-only, sees all of the user's Drive) or a narrower, per-file grant
   is acceptable — see `07-decisions-needed.md`.
5. The user supplies the resulting `client_id`/`client_secret` to zmcp via local
   configuration (e.g. `~/.config/zmcp/oauth_client.json` or environment variables) — never
   committed to this repository.

## Runtime flow

1. On first use, the server starts a local loopback HTTP listener on an ephemeral port, opens the
   user's default browser to Google's consent screen, and receives the authorization code via the
   loopback redirect (standard "installed application" OAuth flow — no secret embedded in a
   public client, no copy-pasted codes).
2. The resulting refresh token is cached locally (e.g. `~/.config/zmcp/token.json`,
   file mode `0600`, never logged, never included in any tool output).
3. On subsequent runs, the server uses the cached refresh token silently; if it has been revoked
   or expired, the server returns `BLOCKED` with an `unresolved` entry telling the user re-auth is
   needed, rather than hanging on an interactive prompt that may not be visible to the model.
4. Read-only access only. The server will not request, accept, or use any scope that permits
   writes, consistent with brief §8/§12 ("No canonical writes", "Do not modify Brain canonicals
   ... without explicit approval").

## What the server will never do

- Read or depend on Claude Desktop's or ChatGPT Desktop's own connector session/cookies/tokens.
- Request write, delete, or sharing-management scopes.
- Log or echo the client secret, access token, or refresh token in any tool output, error
  message, or log line.
- Fall back to an unauthenticated or cached-only mode and report `READY` if live Drive
  authentication fails for a mandatory source (that's a `BLOCKED`, per brief §6).
