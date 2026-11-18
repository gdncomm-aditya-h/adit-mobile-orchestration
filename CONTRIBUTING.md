# Contributing

Pull requests are welcome from anyone with access. Keep them small and say what changed for a person using the skills.

## Add or change a skill

1. Put the skill in `skills/adit-workflow-<name>/SKILL.md`. Bundled scripts and references go in the same folder.
2. Add or update its entry in `skills.json`: the summary, whether it works on Codex, whether it names Blibli-specific things, and which other skills it calls.
3. Add or update its row in `scripts/build_diagram.py`, then run `python3 scripts/build_diagram.py`. CI fails if the committed SVG is out of date.
4. Add the skill to the table in `README.md` and, if it needs a new plugin, to `deps.json`.
5. Run the tests.

```bash
python3 -m unittest discover -s tests
python3 -m unittest discover -s skills/adit-workflow-check-slot-bliblimobileios
```

## Rules for what goes in the repo

- No credentials, tokens, passwords or personal account IDs. Anything personal belongs in `~/.claude/adit-workflow/` on the user's machine. CI scans for the usual patterns.
- Skills should read the current user from the tool, for example `currentUser()` in JQL, and never hard-code a name.
- Changes to `claude-md/ticket-flow.md` change what the agent does on every ticket. Test one real ticket before merging.
- If a skill needs a new plugin, say so in `deps.json` and the README table.

## Writing

Docs are plain prose. Use sentence-case headings and short paragraphs. Skip em dashes, bold labels on list items and closing summaries. CI checks the docs for em dashes.

## Commits and releases

Commit messages follow Conventional Commits, for example `feat(skills): add low-hanging-fruit`. Bump `VERSION` and add a line to `CHANGELOG.md` for anything users will notice.
