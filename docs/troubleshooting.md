# Troubleshooting

## Team version

Start with `/ios-orchestration-flow-doctor`. The other skills also run a quiet preflight first.

| What you see | Likely cause | What to do |
|---|---|---|
| The skill prints `BLOCKER: gh NOT LOGGED IN` or a missing tool | The preflight found a tool the skill needs is missing | Follow the fix printed on the same line, then run the skill again. `flow-doctor` ignores the 24-hour cache |
| The preflight still reports a problem you fixed | Tool results are cached for 24 hours | Run `/ios-orchestration-flow-doctor`, which checks fresh |
| `git commit` is denied with `run ios-orchestration-verify-ticket first` | The gate is armed for this ticket and it is not verified | Run `/ios-orchestration-verify-ticket <KEY>`. Do not look for a way around the hook |
| `git commit` is denied after verify with `files changed since verification` | You edited files after the verified marker was written | Run verify again, or `ticket_gate.py mark-verified <KEY>` if the change is intended |
| `git merge` or `rebase` is denied during a ticket | The command does not name a remote branch | Use `git merge origin/<base>` or `git rebase origin/<base>` to sync, or `--continue` and `--abort` |
| The gate stays armed for an abandoned ticket | The marker was never cleared | `ticket_gate.py clear <KEY>`. A marker also expires by itself after seven days |
| The Jira ticket was not moved | No transition to `In Development` or `In Progress` was available, or the move failed twice | Read the `not moved` line. Move it by hand, the run does not stop for this |
| `ticket_slots.py` exits with code 3 | Every slot of this repo is busy | `/ios-orchestration-ticket-status`, then finish or release a ticket |
| `ticket_slots.py` exits with code 4 | A slot has uncommitted changes, or the repo layout is unknown | Read the reason on stderr. For an unknown layout run `/ios-orchestration-flow-config` and set the profile. Never discard changes without checking them |
| A crashed session still holds a slot | The slot lock is only freed by `release` | `ticket_slots.py --repo <owner/repo> release <KEY or slot letter>` |
| The skill stops at login | The test-account file is missing or has placeholders | Fill in `~/.claude/ios-ticket-flow/uatb-account.json` |
| Click tests are marked `needs manual run` | You are in the terminal, which has no simulator tool | Use the desktop app, or run the cases by hand |

The scripts are in the `scripts` folder of the `mobileapps-ios` plugin. Your branch prefix, default repo and slot counts are in `~/.claude/ios-ticket-flow/config.json`.

## Original version

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

### Getting back to a clean state

Every file the installer changes is copied to `~/.claude/adit-workflow/backups/<timestamp>/` first. To undo an install, run `python3 install.py uninstall`. To restore an older `settings.json` or `CLAUDE.md`, copy it back from the newest backup folder.
