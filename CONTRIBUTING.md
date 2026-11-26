# Contributing

Pull requests are welcome from anyone with access. Keep them small and say what changed for a person using the skills.

## Change a skill, a script or the hook

These files are mirrored from agent-plugins#595 and must stay byte-identical to it: `skills/ios-orchestration-*`, `scripts/` and `hooks/hooks.json`.

1. Make the change in the PR branch of `gdncomm/agent-plugins` (folder `plugins/mobileapps/ios/`), with its tests, and push it there.
2. Run `tools/sync_from_pr.sh` here to copy it in. Set `SRC_DIR` to a local checkout to skip the clone.
3. Run `tools/sync_from_pr.sh --check`. It must print `identical`.
4. If a skill was added, renamed or removed, or its dependencies changed, update its row in `tools/build_diagram.py`, then run `python3 tools/build_diagram.py` and `python3 tools/build_flow_diagram.py`. CI fails if the committed SVGs are out of date. The PNG of the flow diagram is rendered from the SVG with a headless browser.
5. Update the README table and `docs/` if the behavior changed.
6. Run the tests.

```bash
python3 -m unittest discover -s scripts/tests
python3 -m unittest discover -s tests
```

After agent-plugins#595 merges, set `SRC_BRANCH=main` (or change the default in `tools/sync_from_pr.sh`).

## Rules for what goes in the repo

- No credentials, tokens, passwords or personal account IDs. Anything personal belongs in `~/.claude/ios-ticket-flow/` on the user's machine. CI scans for the usual patterns.
- Skills should read the current user from the tool, for example `currentUser()` in JQL, and never hard-code a name.
- Changes to the entry skill change what the agent does on every ticket. Test one real ticket before the PR merges.

## Writing

Docs are plain prose. Use sentence-case headings and short paragraphs. Skip em dashes, bold labels on list items and closing summaries. CI checks the docs for em dashes.

## Commits and releases

Commit messages follow Conventional Commits, for example `docs: explain the mirror`. Bump `VERSION` and `.claude-plugin/plugin.json` and add a line to `CHANGELOG.md` for anything users will notice.
