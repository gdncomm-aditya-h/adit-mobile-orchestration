# Changelog

## Unreleased

- Swift packages need no manual step. `ticket-slots.py` retries a failed download once and has a new `packages <KEY>` command that re-checks the slot. A download that still fails is a blocker.
- The ticket flow rules and `verify-before-pr` run implementation and verification in sub-agents that return short reports and never ask the user.
- New `adit-workflow-setup` skill and `install.py deps --only <names>`: check the plugins the flow needs, ask per missing plugin, install the approved ones. The install manifest now records the repo path.
- Docs and diagrams follow agent-plugins#595: sixteen skills, the new `ios-orchestration-setup` skill, sub-agents for implement and verify, and automatic Swift packages.
- Docs and diagrams follow agent-plugins#595 as it stands now: fifteen skills, the repo and version questions, release branches as the base, draft-only PRs enforced by the gate, the tests-must-compile override, `uatb` confirmed before login, and the new `pr-watch`, `wrap-up` and `publish-doc` skills.
- The worktree slot pool grew from three to four slots.
- Added the target-design diagram of the team version, `scripts/build_flow_diagram.py`, and rebuilt the dependency graph.
- README and docs now describe the team version first: the twelve `ios-orchestration-*` skills in the `mobileapps-ios` plugin (agent-plugins#595, in review), the flow, repo profiles, settings, and the first real run with its gaps.
- The original version is marked as such. Its ticket flow can no longer run end to end, because `jira-implement`, `jira-plan` and `jira-develop` were removed from `mobileapps-ios`.
- Design notes record the move from the installer to the plugin and the calls made on the way.
- Diagrams show `plan-from-ticket` as the drafting step of the flow, `ticket-to-pr` calling its five steps, and every skill as Claude Code only.

## 0.1.0

First release.

- Nine skills: plan-enrich, verify-before-pr, audit-review-code, generate-plan-from-ticket, pr-reply, review-pr-blibli-mobile-ios, check-slot-bliblimobileios, low-hanging-fruit and graphify.
- Two hooks: `ticket-flow-gate.py` and `ticket-slots.py`.
- The ticket-flow rules as a block the installer writes into `CLAUDE.md`, with a configurable branch prefix.
- `install.py` with install, uninstall, doctor and dry-run, for Claude Code and Codex (experimental).
- Dependency graph, ticket-flow walkthrough and troubleshooting guide.

Changed from the author's private setup:

- The shared simulator test account moved out of `verify-before-pr` into `~/.claude/adit-workflow/uatb-account.json`.
- `low-hanging-fruit` uses `currentUser()` instead of a fixed Jira account ID.
