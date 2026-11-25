# Design notes

These notes record why the repo looks the way it does, so the next person can change it without guessing. The first part covers the original installer version. The last part covers the move to the `mobileapps-ios` plugin, which supersedes some of those decisions.

## Why this exists

Aditya's ticket workflow was spread across nine skills in `~/.claude/skills`, two hooks, an edited `settings.json` and a long block in the global `CLAUDE.md`. None of it could be shared without copying files by hand. The goal is that a teammate can point their agent at this repo and get the same setup.

## Goals

- One command, or one sentence to an agent, installs everything.
- The installer is safe to run twice and easy to reverse.
- The people who install it can see the whole workflow in one picture.
- It works for Claude Code now and leaves room for Codex.
- It can be widened beyond the team later without a rewrite.

## Non-goals

- A full Codex port of the plan-mode and hook-gate parts.
- Packaging as a Claude Code plugin. This was a non-goal for the installer version, because a plugin cannot edit the global `CLAUDE.md` and plugin skills get a namespace prefix. The team version later solved both, see "Moving to the plugin" below.
- Vendoring the plugins this repo depends on.

## Approaches considered

1. Installer script. Chosen. It keeps bare skill names, can edit `settings.json` and the rules file, and works the same whether a person or an agent runs it.
2. Plugin marketplace. Clean updates and removal, but the namespace and `CLAUDE.md` problems above remain, so a manual step would still be needed.
3. Plugin plus a setup command. Has both problems and two install paths to maintain.

## Decisions

- One real copy of each skill in `~/.agents/skills`, linked into each agent's folder. This matches how the author's machine was already laid out.
- Standard-library Python for the installer. The hooks already need `python3`, so no new requirement.
- A marked block in `CLAUDE.md`, replaced on each install, so the user's own text is never touched.
- The branch prefix is a parameter. The original rules hard-coded the author's prefix.
- `deps.json` pins tested versions and `doctor` only warns on drift. A hard pin would break installs every time a plugin updates.
- `INSTALL.md` is written for an agent, with explicit steps, a dry run first and a list of things not to do.

## Calls made without asking

- The shared test-account login was removed from `verify-before-pr` and moved to a local file outside the repo. A password does not belong in git history even for a private repo, and it would leak the day the repo is widened.
- The author's Jira account ID in `low-hanging-fruit` became `currentUser()`, so it works for anyone.
- A colleague's email address in a skill was dropped with the login.
- The repo was switched from public to private before the first push.

## Open items

- The repo lives under a personal account. Teammates need to be added as collaborators, or the repo should move into the organization.
- No licence yet. `graphify` is a renamed copy of an upstream skill and its licence has not been checked. See [NOTICE.md](../NOTICE.md).
- Several original skills name `gdncomm/BlibliIOSApp` and the IOS Jira project. The team version pulls those into settings, the original skills keep them.
- Codex support has never been run end to end.

## Moving to the plugin

The installer version only worked for one person's machine layout, and its flow started from prose in `CLAUDE.md`. In October `jira-implement` was removed from `mobileapps-ios` in agent-plugins#493, and `jira-plan` and `jira-develop` are no longer in the marketplace either, so the original ticket flow stopped running end to end. The team asked for the harness to become a plugin, and the work is in review as agent-plugins#595.

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
- This repo keeps the original skills and installer unchanged. Decide whether to archive them once the plugin is released.
