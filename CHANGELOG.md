# Changelog

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
