# Manual configuration refresh

`refresh-config()` is an explicit MCP tool. No process initialization, connection,
`startup`, or `ground` call triggers a freshness check. Startup remains the existing
placeholder. This operation does not retire bootstrap, change canonical Brain
documents, or deploy/reconfigure a desktop host.

The previous branch had no configuration cache or live reader. This operation adds
a persistent snapshot of explicitly designated configuration documents. It does
not execute their contents or change startup instructions dynamically. `ground`
continues to use fixtures and cannot establish live Brain grounding.

## Configuration

Set `ZMCP_CONFIG_SOURCES` to an administrator-controlled local JSON designation
file, containing the exact Brain Drive file IDs to check. No discovery, guessed
canonical IDs, or fixture fallback is used. All designated sources are required.
For example (replace the illustrative ID before use):

```json
{"sources": [{"name": "initialization", "source_id": "YOUR_BRAIN_FILE_ID"}]}
```

Set `ZMCP_DRIVE_ACCESS_TOKEN` to an existing read-only Google Drive access token.
The tool does not provision OAuth credentials, refresh tokens, or request write
access. Missing/expired credentials yield a failed receipt. Tokens are never
included in receipts. Only the designated file IDs are retrieved, from the fixed
Google Drive API endpoint. Native Google Docs are exported as plain text; plain
text, Markdown and JSON files are supported. JSON files must parse successfully.
Other file types fail closed.

`ZMCP_CONFIG_CACHE` optionally selects the snapshot path (default
`~/.zmcp/config-cache.json`). Do not point it at a Brain source or the designation
file. Only the cache and a temporary staging file are written. Use a single server
process per cache path; calls within that process are serialized.

## Transaction and receipt

Each invocation reads the designation file afresh, retrieves every designated
source and checks metadata both before and after retrieval to reject a revision
that changed mid-read. Validation requires exact source identity, nonempty title,
version and content, a parseable modification timestamp, supported source types,
and unique designation names and IDs. This validates the snapshot's integrity,
not the semantic truth of arbitrary Brain prose. It cannot provide a global
transaction across separate Drive documents.

The receipt reports `CURRENT`, `REFRESHED` or `FAILED`, whether the *previous*
snapshot was `current` (`null` if comparison could not complete), `checked_at`,
`refreshed_at`, source IDs/titles/versions/modification times/content hashes,
added/changed/removed entries, `missing`, `errors`, and `cache_activated`.
Source content and revision metadata both participate in comparison. Removing a
designation is reported as a removal; an unavailable designated source instead
fails the entire refresh and is listed as missing.

Changed content is staged in the cache's directory, flushed, parsed back and
compared to the validated candidate, then activated with `os.replace`. Retrieval,
validation, staging or replacement failures preserve the previous cache bytes.
A corrupt existing cache fails closed rather than silently overwriting evidence.
An unchanged cache is not rewritten; its last activation timestamp is retained.
No cache exists until the first successful explicit refresh.

`live_brain_verified` means all designated material was successfully retrieved by
the built-in live Drive reader during this call. `verification=fixture-or-test`
never establishes live verification, even on a successful fixture transaction.
Missing configuration/credentials is `unverified`. A failed activation may still
have successful retrieval evidence; always check `status` and `cache_activated`.

## Verification scope

Automated tests use local temporary caches and mocked readers/HTTP responses.
They cover current/changed content, missing material, invalid replacements,
transport/staging/replacement failure, provenance, revision races and the MCP
registration. They do **not** verify live Brain contents, OAuth setup, desktop
client behavior or host deployment. A live receipt requires a separately invoked
tool call with actual designated sources and valid credentials.
