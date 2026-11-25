# Claude Code and Codex

## Team version

The team version is part of `mobileapps-ios`, which is a Claude Code only plugin. It has no Codex support and none is planned.

It runs in Claude Code in the terminal and in the desktop app. The terminal is the baseline and the desktop app adds tools.

| Need | Terminal | Desktop app | What the flow does |
|---|---|---|---|
| Skills, plan mode, hooks, plugin scripts | yes | yes | works in both |
| Switch to auto mode by itself | no | yes | in the terminal you press Shift+Tab |
| Simulator tool for click tests | no | yes | in the terminal, click tests become `needs manual run` |
| Session and PR tools | no | yes | optional extras, never required |

The hook has been smoke-tested in the desktop app only. The terminal has not been tried yet.

## Original version

The skills are plain `SKILL.md` folders, so both agents can load them. What differs is the tooling around them.

### How the install works for each agent

The installer keeps one real copy of every skill in `~/.agents/skills` and links it into `~/.claude/skills` and `~/.codex/skills`. Rules go into `~/.claude/CLAUDE.md` for Claude Code and a shorter note into `~/.codex/AGENTS.md` for Codex.

### Support matrix

| Skill | Claude Code | Codex | Why |
|---|---|---|---|
| plan-enrich | yes | no | Needs plan mode, `ExitPlanMode` and the gate hook |
| verify-before-pr | yes | no | Needs the gate hook, the iOS Simulator tool and session tools |
| audit-review-code | yes | experimental | Calls ponytail skills |
| generate-plan-from-ticket | yes | yes | Reads a ticket and writes a plan |
| pr-reply | yes | experimental | Calls superpowers, caveman and mobileapps-ios skills |
| review-pr-blibli-mobile-ios | yes | experimental | Calls ecc agents and the code-review skill |
| check-slot-bliblimobileios | yes | yes | Runs one bundled script |
| low-hanging-fruit | yes | yes | Needs a Jira connector, nothing else |
| graphify | yes | yes | Uses its own CLI. It uses subagents when the host has them |

"Experimental" means the skill loads in Codex but calls a skill from a plugin that may not exist there. When that skill is missing the agent should say so and continue by hand.

The hook `ticket-flow-gate.py` reads Claude Code's hook input. It is not registered for Codex.

### What has been tested

- The installer, with a throwaway home folder, for both targets. See `tests/test_install.py`.
- The skills in Claude Code, in daily use.

Not tested: any skill inside Codex. The author had the Codex desktop app but not the `codex` CLI when this was written. If you try it, please open an issue with what worked and what did not.

### Going further later

A full Codex port would need three pieces: an adapter for Codex's hook payload so the gate can run, a replacement for the plan-approval step, and plugin equivalents for the skills listed as experimental. None of that is started.
