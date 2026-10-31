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
- Check `mcp-server-startup-mcp.log` for the `invoked`/`returned` lines. That's the evidence —
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
