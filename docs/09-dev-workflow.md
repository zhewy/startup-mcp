# Development Workflow: Cloud Edit → Local Pull → Live Test

The split in one line: **the cloud (this session, or Cursor pointed at the same repo) is where
code changes happen. The Windows machine — where Claude Desktop actually runs — is a pull-and-
test target only.** Never edit code directly on that machine; if something needs fixing, fix it
in the cloud and pull again. Otherwise the two environments drift and "pull = known state" stops
being true, which is exactly the problem that caused the Windows clone to end up four commits
behind and still running the old `topic=` parameter (see `docs/08-initialization-investigation.md`).

## Multiple AI tools, one branch

This repo may be edited by more than one AI coding tool (Cursor, Claude Code, Codex CLI) pointed
at the same branch, but all from a single computer, under a fixed rule: **strict serialization,
one tool editing at a time.** Concretely:

- Only one tool gets an edit task at a time. Wait for it to commit *and push* before handing
  anything to the next one.
- Every tool pulls fresh immediately before starting new work, not just after finishing — a tool
  working from a stale checkout can confidently redo or contradict something another tool already
  changed (exactly how the Windows clone ended up four commits behind and still on `topic=`).
- Git's push rejection on a stale branch is the last-resort safety net here, not the plan — the
  plan is that two tools are never mid-edit at the same time in the first place.

This is deliberately simpler than giving each tool its own branch: with one computer and strict
turn-taking, there's no real concurrency to design around, so a single shared branch with a pull
→ edit → test → commit → push → next-tool-pulls cycle is sufficient.

## Why bridge sessions can't message the cloud coordinator back by session ID

Recurring friction worth fixing at the instruction level, not re-discovering each time: a Remote
Control bridge session (e.g. on kofimule) and this cloud coordinator session use two different
messaging tools that don't share an addressing scheme.

- This session reaches a bridge session with a session-ID-addressed tool
  (`mcp__claude-code-remote__send_message`, taking the full `session_...` ID).
- A bridge session only has a generic `SendMessage` tool that addresses by **name**, taken from
  its own `ListAgents` peer list — it has no concept of the `session_...` ID format at all, and
  `ListAgents` doesn't surface IDs either, only names/refs.

So telling a bridge session "send your findings back to `session_017SNSNRSrouifawxmQQHMk3`"
always fails (`No agent named '...' is reachable`), regardless of which bridge session it is —
that's not a one-off bug, it's a structural mismatch between the two tools.

**Fix:** in any handover/follow-up message to a bridge session, tell it the coordinator's current
*name* (call `ListAgents` from this session, or note the title shown in this session's own
header) instead of the session ID — e.g. "when done, use `SendMessage` with `to` set to the name
matching this project's cloud coordinator session (currently titled `startupmcp coordinator`,
but call `ListAgents` and confirm, since titles can change)." If it still can't find a match,
don't have it guess — the fallback is the same as always: it reports findings in its own final
response, and the human relays them here manually.

## The loop

**1. Edit and validate in the cloud.**
- Make the change here, or in Cursor against the same repo/branch — the workflow doesn't care
  which tool authored the diff, only that it lands in git.
- Run `pytest` before pushing anything. This catches most mistakes for free, without spending a
  live-client round trip on something `pytest` would have caught in a second.
- Commit, push to `claude/cool-franklin-81hsgd`.
- Note, for yourself and whoever pulls next, which *kind* of change this was — it decides step 3:
  - **Content-only** (editing an existing source file's `content` field, nothing else added or
    restructured): no restart needed on the other end.
  - **Structural** (new/changed `manifest.json` keys, new `.py` code, a parameter rename, a new
    fixture file referenced by the manifest, a new dependency): needs a restart on the other end.

**2. Pull on the Windows machine (via the bridge session), don't reclone.**
- `git pull` in the existing clone.
- Sanity-check it actually moved: `git log -1 --oneline`, and compare the short SHA against what
  you just pushed. This is the single step that was skipped last time and caused a stale-clone
  test. Don't skip it.
- Only re-run `pip install -e ".[dev]"` if `pyproject.toml` or its dependencies changed — plain
  `.py`/`.json` edits don't need it, because it's an editable install (see
  `docs/08-initialization-investigation.md`'s discussion of this).

**3. Decide whether Claude Desktop needs restarting.**
- Content-only change → no restart. `FixtureSourceProvider.get_source()` reads each source file
  fresh from disk on every call — proven live, not assumed (see the chat transcript where this
  was demonstrated by editing a fixture file mid-process).
- Anything structural → restart Claude Desktop. `manifest.json` is read once and cached per
  process (`FixtureSourceProvider.__init__`), and Python code is loaded into memory at process
  start — neither picks up changes without a fresh process.

**4. Test with the one dependable invocation path.**
- An explicit instruction naming the tool/purpose directly — the only invocation path confirmed
  to work so far (automatic invocation tested negative; see `docs/08-initialization-investigation.md`
  §0.5/§1 Q2). Don't spend a round re-testing automatic invocation unless that's specifically
  what changed.
- Check `mcp-server-zmcp.log` for the `invoked`/`returned` lines. That's the evidence —
  not the model's own account of what it did.

**5. Report back with raw log lines, not narration.**
- Same rule as every round so far: quote the actual log, don't summarize what the model claimed.
- If something's wrong, the fix happens back in the cloud (step 1) — never by patching the
  Windows clone directly.

## Pre-flight checklist before asking for a live test round

- [ ] `pytest` passes in the cloud clone
- [ ] Pushed to `claude/cool-franklin-81hsgd`
- [ ] Noted whether this change needs a Desktop restart or not
- [ ] Know the exact commit SHA the other end should see after pulling, so it can self-verify
      (`git log -1 --oneline`) instead of assuming it's current

## ChatGPT Windows plugin package: repeatable build and delivery

This package is separate from the pull-and-test Claude Desktop loop above.
It is a local ChatGPT desktop test plugin; a hosted/web/mobile install and
automatic invocation are not established. Build it from the intended commit on
`claude/cool-franklin-81hsgd` with a clean working tree. The source templates
are under `packaging/chatgpt/`; `packaging/build_chatgpt_plugin.py` reads the
version from `plugin.json` and includes the template plus `src/zmcp` Python and
fixture JSON files. It excludes caches and local credentials.

```bash
git fetch origin claude/cool-franklin-81hsgd
git status --short --branch
python -m pytest -q
git diff --check
python packaging/build_chatgpt_plugin.py
unzip -t dist/zmcp-chatgpt-0.1.1.zip
sha256sum dist/zmcp-chatgpt-0.1.1.zip
```

The current package filename is `zmcp-chatgpt-0.1.1.zip`; use the actual version
from `packaging/chatgpt/plugin.json` after a future version change. For a direct
GitHub download, copy the validated ZIP to a versioned filename under
`packaging/downloads/`, commit that binary, push the same Franklin branch, and
verify that a download from the resulting commit's `raw.githubusercontent.com`
URL has the same SHA-256. Keep the source commit ID in the binary filename so
users can identify which code was packaged. For example, after the source
changes have been committed and pushed:

```bash
SOURCE_SHA=$(git rev-parse --short HEAD)
PACKAGE=zmcp-chatgpt-0.1.1-${SOURCE_SHA}.zip
cp dist/zmcp-chatgpt-0.1.1.zip "packaging/downloads/$PACKAGE"
git add "packaging/downloads/$PACKAGE"
git commit -m "Publish Windows plugin test package"
git push origin HEAD:refs/heads/claude/cool-franklin-81hsgd
PACKAGE_COMMIT=$(git rev-parse HEAD)
curl -L --fail --silent --show-error \
  "https://raw.githubusercontent.com/zhewy/zmcp/$PACKAGE_COMMIT/packaging/downloads/$PACKAGE" \
  -o "/tmp/$PACKAGE"
sha256sum "dist/zmcp-chatgpt-0.1.1.zip" "/tmp/$PACKAGE"
```

The two hashes must match. Do not publish if the branch has moved since the
source commit; fetch and review first. Never include OAuth client JSON, tokens,
local caches or environment files in the ZIP or download commit.

On Windows, extract the ZIP and run `install-windows.cmd` from the extracted
folder. It invokes `install.py` through `py -3` or `python`; the installer creates
or reuses `%USERPROFILE%\.zmcp\runtime-0.1.0`, installs Python dependencies,
overwrites an already registered `%USERPROFILE%\.codex\plugins\zmcp` folder,
backs up and updates the personal marketplace entry, and preserves other
entries. `launch.py` remains the working stdio loader; `install.py` does not
replace it with a new loader design. Fully quit and restart ChatGPT Desktop,
then install/enable zmcp from the personal marketplace (disable and reinstall
if the old tool text remains). Installation requires network access for pip;
startup itself does not perform a package download or Drive read. OAuth is
optional for the separate explicit `refresh-config` operation and is never
provisioned by this installer.

Verify a live host separately: confirm plugin discovery, invoke `startup`
explicitly, inspect the actual response and MCP log, and confirm the calling
session follows Brain routing through its own authorized Drive connection.
Check that no cache refresh occurs. The repository's automated tests and ZIP
integrity check are mocked/local checks, not proof of ChatGPT Desktop support,
its model's automatic invocation, the user's Drive connector access, or a
successful Windows installation.
