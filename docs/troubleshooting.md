# Troubleshooting


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
| A plugin is reported missing | `mobileapps-foundation` is not installed | Run `/ios-orchestration-setup`. It asks per plugin and installs after a yes |
| Click tests are marked `needs manual run` | You are in the terminal, which has no simulator tool | Use the desktop app, or run the cases by hand |

The scripts are in the `scripts` folder of this repo and of the `mobileapps-ios` plugin. Your branch prefix, default repo and slot counts are in `~/.claude/ios-ticket-flow/config.json`.
