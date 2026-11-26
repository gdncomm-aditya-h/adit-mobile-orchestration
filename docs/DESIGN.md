# Design notes

These notes record why the repo looks the way it does, so the next person can change it without guessing.

## Why this repo is a mirror

The flow is being reviewed and will ship inside `mobileapps-ios` (agent-plugins#595). Keeping a second, different copy here meant two versions that drifted apart. In 0.2.0 the repo was made to mirror the PR, and the PR is the source of truth.

- Mirrored, byte for byte: `skills/ios-orchestration-*`, `scripts/` (with their tests) and `hooks/hooks.json`. Only these, because the plugin folder also holds unrelated skills (`swift-codegen`, `run-tests` and others) that do not belong in this repo.
- `tools/sync_from_pr.sh` copies them in and `--check` fails on any difference. The check needs read access to the private repo, so CI does not run it and the contributor does.
- Owned by this repo: the README, the docs, both diagrams and their builders in `tools/`, `.claude-plugin/plugin.json`, the CI workflow and `tests/test_mirror.py`.
- `.claude-plugin/plugin.json` is the one addition that is not in the PR. It lets `claude --plugin-dir` load the mirror before the plugin is released. It must not be enabled next to `mobileapps-ios` 1.11.0 or newer.

### Calls made without asking

- The installer, `deps.json`, `skills.json`, the rules block, the old hooks and the nine `adit-workflow-*` skills were deleted, as asked. `graphify` went with them: it was not moved to the plugin, and it is a renamed upstream skill, so it was not carried over. It is in the git history.
- The earlier parity edits to the installer version (retry, `packages` command, sub-agent rules, `adit-workflow-setup`) were not kept, as asked. The same behavior now comes from the PR.
- The diagram builders moved from `scripts/` to `tools/`, so `scripts/` can be an exact copy of the PR's folder.
- The plugin README of `mobileapps-ios` is not mirrored. It also documents the plugin's other skills. This repo's README covers the flow.
- The version went from 0.1.0 to 0.2.0 because removing the installer breaks anyone who used it.

## The flow as a plugin

The first version of this repo was an installer (nine `adit-workflow-*` skills, two hooks, a rules block in `CLAUDE.md` and `install.py`). It only worked for one person's machine layout, and its flow started from prose in `CLAUDE.md`. In October `jira-implement` was removed from `mobileapps-ios` in agent-plugins#493, and `jira-plan` and `jira-develop` are no longer in the marketplace either, so the original ticket flow stopped running end to end. The team asked for the harness to become a plugin, and the work is in review as agent-plugins#595.

### What changed from the installer design

- The trigger is an entry skill, `ios-orchestration-ticket-to-pr`, plus plugin hooks. A plugin cannot ship `CLAUDE.md` text, so the rules moved into the skill and the gate hook moved into the plugin's `hooks.json`. Nothing is written into a global file any more.
- Every skill is named `ios-orchestration-<name>`. Skills call each other by that full name, so the plugin can move without edits.
- The entry skill now owns the steps `jira-implement`, `jira-plan` and `jira-develop` used to do. The drafting step that `jira-plan` provided is now `plan-from-ticket`, reworked so it explores the code, writes only the first part of the plan in the flow and never implements, and `enrich-plan` adds the rest.
- Settings live in `~/.claude/ios-ticket-flow/config.json`, which is the source of truth. It is named for the feature, not for the plugin, so a later move does not break it.

### Decisions

- The flow targets the iOS team only, and any iOS repo they use. The default is `gdncomm/BlibliIOSApp`, and any `owner/repo` is accepted and checked.
- Slots are per repo and only for app repos. A package repo gets one plain worktree per ticket.
- If nothing can be built, the gate waits for a written override reason, and the PR is labeled `build-unverified`.
- An SDK change can optionally be tested inside the latest `develop` of `BlibliIOSApp`. The tool only reports compile errors and never fixes app code.
- The terminal is the baseline and the desktop app is the enhancement. The flow detects which one it is in and records a manual run where a tool is missing.
- The plugin lives inside `mobileapps-ios`. The team asked for a plugin and did not say which one, so a later move to its own plugin is meant to be mechanical.

### Calls made without asking

- `review-open-prs` comments only by default and needs `--approve` to approve, because a bot approval can count as a human review.
- `reply-pr-comments` writes plain English. The terse caveman style made the replies hard for teammates to read.
- `audit-changes` fixes only must-fix and should-fix findings, so the diff does not grow.
- `graphify` was not moved, because it is a renamed upstream skill unrelated to the iOS flow.
- The branch prefix is a setting asked on first run, and defaults to the engineer's `gh` login instead of the author's prefix.
- The design check in `verify-ticket` is advisory, because it is a visual comparison and not a pixel diff.

### Added after the first run and the team meeting

- The flow always asks which repo first, before anything else runs, and then which version. The team works on release branches, so the base is the ticket's `release/v<Fix Version>` when it exists, not always `develop`. This adds two one-click stops, and the recommended answers keep each to a click.
- The gate closes the draft gaps: `--draft` is required, `--draft=false` and the GraphQL ready mutation are denied.
- A test target that does not compile is a failed check with its own override (`tests-unverified`), and the `uatb` environment is confirmed from the screen before login.
- `pr-watch` babysits the draft PR with a background shell script, because polling with `gh` costs no model tokens. It was written from the documented behaviour of the jira-implement-v2 watcher, not copied.
- `wrap-up` handles the post-merge Jira move and cleanup. `publish-doc` puts context, plan and test cases into Confluence, and runs only with `--doc` so the flow gets no extra question.
- The context file for new sessions is not built yet. It stays on the machine under `~/.claude/ios-ticket-flow/`, and the Confluence page is the copy teammates can read.
- The jira-implement-v2 prompt hook can fire next to this flow, so it should be off for engineers who use this one.

### Open items

- The team version has not been run in the terminal, and its gate has not been smoke-tested there.
- Of the first run's gaps, the unsigned simulator build and the missing screenshots in the Jira comment are still open.
- `pr-watch`, `wrap-up` and `publish-doc` have not run on a real ticket. The watcher has unit tests against a fake `gh`.
