# Troubleshooting

Start with `python3 install.py doctor`. It names most of these problems directly.

| What you see | Likely cause | What to do |
|---|---|---|
| New skills do not appear | The agent was open during install | Restart Claude Code or Codex |
| `doctor` shows `FAIL skills installed` | Install did not finish, or the links were removed | Run `python3 install.py install` again |
| `WARN mobileapps-ios@agent-plugins not installed` | You have no access to `gdncomm/agent-plugins` | Ask the plugin owners for access, then run `/plugin marketplace add git@github.com:gdncomm/agent-plugins.git` |
| `settings.json is not valid JSON` during install | A hand edit left the file broken | Fix the file, then re-run. The installer never overwrites a file it cannot parse |
| The installer prints `/plugin` commands instead of installing | The `claude` CLI is not on your PATH | Paste those commands into a Claude Code session |
| `git commit` is denied with a message about verification | The gate is on for this ticket and it is not verified | Run `adit-workflow-verify-before-pr <KEY>`. Do not look for a way around the hook |
| The gate stays on after you abandoned a ticket | The marker for that ticket was never cleared | Run `python3 ~/.claude/hooks/ticket-flow-gate.py clear <KEY>` inside that ticket's checkout |
| `ticket-slots.py` exits with code 3 | All four slots are in use | Run `python3 ~/.claude/hooks/ticket-slots.py status`, finish or release a ticket, then retry |
| `ticket-slots.py` exits with code 4 | A slot has uncommitted changes, or setup failed | Read the reason on stderr. Do not discard the changes without checking them |
| A crashed session still holds a slot | The slot lock is only freed by `release` | `python3 ~/.claude/hooks/ticket-slots.py release <KEY or slot letter>` |
| `verify-before-pr` stops at login | The test-account file is missing or still has placeholders | Fill in `~/.claude/adit-workflow/uatb-account.json` |
| A skill says a plugin skill does not exist | That plugin is not installed for this agent | Check `doctor`. On Codex this is expected for the experimental skills |

## Getting back to a clean state

Every file the installer changes is copied to `~/.claude/adit-workflow/backups/<timestamp>/` first. To undo an install, run `python3 install.py uninstall`. To restore an older `settings.json` or `CLAUDE.md`, copy it back from the newest backup folder.
