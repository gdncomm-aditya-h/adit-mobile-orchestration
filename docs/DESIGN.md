# Design notes

These notes record why the repo looks the way it does, so the next person can change it without guessing.

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
- Packaging as a Claude Code plugin. Plugin skills get a namespace prefix, which would break the bare names the skills use to call each other, and a plugin cannot edit the global `CLAUDE.md`.
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
- Several skills name `gdncomm/BlibliIOSApp` and the IOS Jira project. Widening means pulling those into settings.
- Codex support has never been run end to end.
