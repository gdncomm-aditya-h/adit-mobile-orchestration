# Agent instructions

To install this repo for a user, follow [INSTALL.md](INSTALL.md).

To change this repo, read [CONTRIBUTING.md](CONTRIBUTING.md) first. Keep these rules:

- Never commit credentials, tokens or personal Jira IDs. The test account lives in `~/.claude/adit-workflow/uatb-account.json`, outside the repo.
- When a skill is added, renamed or removed, update `skills.json` and `scripts/build_diagram.py`, then run `python3 scripts/build_diagram.py`.
- Run `python3 -m unittest discover -s tests` before committing.
- Write docs in plain sentences. No em dashes, no bold labels on list items, sentence-case headings.
