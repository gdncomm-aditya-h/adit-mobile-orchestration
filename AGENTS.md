# Agent instructions

To install this repo for a user, follow [INSTALL.md](INSTALL.md).

To change this repo, read [CONTRIBUTING.md](CONTRIBUTING.md) first. Keep these rules:

- Never commit credentials, tokens or personal Jira IDs. The test account lives in `~/.claude/ios-ticket-flow/uatb-account.json`, outside the repo.
- `skills/ios-orchestration-*`, `scripts/` and `hooks/hooks.json` are mirrored from agent-plugins#595. Never edit them here. Change the PR, then run `tools/sync_from_pr.sh` and `tools/sync_from_pr.sh --check`.
- When a skill is added, renamed or removed in the PR, update `tools/build_diagram.py`, then run `python3 tools/build_diagram.py` and `python3 tools/build_flow_diagram.py`.
- Run `python3 -m unittest discover -s scripts/tests` and `python3 -m unittest discover -s tests` before committing.
- Write docs in plain sentences. No em dashes, no bold labels on list items, sentence-case headings.
