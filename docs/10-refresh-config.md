# Manual Brain configuration refresh

`refresh-config()` is explicitly invoked. It does not run at process startup, on
`startup()` or on `ground()`. `startup()` remains a placeholder; `ground()` reads
bundled fixtures. Neither consumes the configuration cache or delivers live roles.

## First use on a local host

1. In Google Cloud Console, create or select a project, enable Google Drive API,
   configure the OAuth consent screen, and create a **Desktop app** OAuth client.
   If the app is in Testing, add the intended account as a test user. Testing-mode
   grants may expire and require consent again. The app requests only
   `https://www.googleapis.com/auth/drive.readonly`, which grants read access to
   the user's Drive; consent should be given only if that scope is acceptable.
2. Install `pip install -e '.[drive]'`. Save the downloaded Desktop client JSON
   locally as `~/.config/zmcp/oauth_client.json` (or set `ZMCP_OAUTH_CLIENT`).
   Do not commit it. Run `zmcp-auth` in an interactive local terminal once to
   complete browser consent. It writes `~/.config/zmcp/token.json` with mode 0600
   (or `ZMCP_OAUTH_TOKEN`). Keep this file private. Access tokens are renewed
   from its refresh token. If renewal fails, repeat `zmcp-auth` locally.
3. Invoke `refresh-config` when you want a new comparison. No source-ID JSON is
   needed. It starts at Brain initialization ID
   `1bGVXeMqG899ScKLdADsyYtPP4tWOLyuA`, follows its explicit routing guide,
   checks that Base's designation agrees between initialization and routing,
   and reads those three configuration sources. Missing, ambiguous or conflicting
   links fail closed. This is a bounded configuration snapshot, not an inventory
   of all role or task-specific materials.

The older `ZMCP_CONFIG_SOURCES` JSON file remains an advanced compatibility
option. It overrides discovery and should only be used with intentionally
specified source IDs. `ZMCP_CONFIG_CACHE` sets the cache location (default
`~/.zmcp/config-cache.json`).

## Transaction and evidence

Every source is read with metadata before and after retrieval. A changed revision,
missing item, invalid identity, empty content, or failed validation aborts the
refresh. Before replacement the existing cache is checked for schema version,
required fields, unique names and IDs, timestamps, and content hashes. A corrupt
cache is left in place as evidence. A replacement is written and checked in the
same directory, then activated with `os.replace`. Retrieval, staging or activation
failure preserves the previous cache. Unchanged content is not rewritten.

Receipts include status (`CURRENT`, `REFRESHED`, `FAILED`), source identities and
hashes, changes and missing sources, and whether activation happened. No source
content or credential is returned. `live_brain_verified` requires a successful
read by the built-in Drive reader; fixture and mocked tests cannot assert it.
This has not been verified against a live host OAuth session or MCP desktop client.
No Brain canonical is edited and no host is deployed by this command.
