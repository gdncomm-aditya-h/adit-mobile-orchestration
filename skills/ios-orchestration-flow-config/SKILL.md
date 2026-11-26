---
name: ios-orchestration-flow-config
description: Show or change the saved settings of the iOS ticket-flow skills: default repo, branch prefix, Jira project, slot counts, and repo profile (app or package). Offers to save the repo so the engineer is not asked again. Use for "set my repo", "which repo am I on", "change branch prefix", or /ios-orchestration-flow-config.
argument-hint: [show | repo <owner/repo> | prefix <name> | jira <KEY> | slots <owner/repo> <n> | profile <owner/repo> <app|package>]
---

# config

Settings live in `~/.claude/ios-ticket-flow/config.json`. That file is the source of truth: skills read it with `python3 <skill_dir>/../../scripts/flowconfig.py` and never rely on memory for these values. No file means defaults: repo `gdncomm/BlibliIOSApp`, Jira project `IOS`, no branch prefix, 4 slots for `BlibliIOSApp` and 1 for other app repos.

## Show
`python3 <scripts>/flowconfig.py get` and print it as a short list. Say which values are defaults because nothing is saved.

## Change
Map the request to one command and run it. Do not edit the JSON by hand.
- default repo: `flowconfig.py set defaultRepo <owner/repo>`. Check the repo first with `gh repo view <owner/repo>`. Any valid GitHub repo is accepted, not only the ones the team usually uses. A name that does not resolve: tell the user and do not save.
- branch prefix: `flowconfig.py set branchPrefix <name>` (letters, digits, dot, dash, underscore). Suggest the user's `gh api user -q .login`, never anyone else's.
- Jira project: `flowconfig.py set jiraProject <KEY>`.
- slots for an app repo: `flowconfig.py set slots.<owner/repo> <1-8>`. Each slot keeps its own DerivedData and packages, so more slots cost disk.
- profile: `flowconfig.py set profile.<owner/repo> app|package` after the user confirms what `python3 <scripts>/repo_profile.py detect` found.

## First run
When a flow skill asks "which repo are you working on?" and the user answers, offer once to save it. State the default you would use if they say nothing: `gdncomm/BlibliIOSApp`. On a yes, run the command above. If memory is available in this client, also save one memory line that points at the config file (for example "iOS ticket-flow settings: ~/.claude/ios-ticket-flow/config.json") so you can explain the setting in other sessions. The config file stays the source of truth.

To work on a different repo for one run, pass `--repo owner/repo` to the flow skill. That never changes the saved default.
