# Install guide for agents

This file is written for Claude Code or Codex. A person who wants to install by hand should follow the README instead.

This guide installs the original version in this repo. The team version is a plugin and is not installed by `install.py`. It is part of `mobileapps-ios` 1.11.0 or newer from `gdncomm/agent-plugins`, which is in review as agent-plugins#595 and not released yet. The original ticket flow also calls skills that were removed from `mobileapps-ios`, so tell the user that before you install it. If the user wants the ticket flow, stop here and point them to the README section "Try the team version before it is released".

You are installing a set of skills, two hooks and a rules block. The installer does the work. Your job is to run it with the right options, show the user what it will change, and report the result honestly.

## Before you start

1. Confirm `python3 --version` is 3.8 or newer and `gh auth status` succeeds. If `gh` is not signed in, stop and tell the user to run `gh auth login`.
2. Work out the target. Use `claude` if the user is in Claude Code, `codex` if they are in Codex, and `both` if they said so. If unsure, use `auto`, which picks every agent that has a home folder on this machine.
3. Ask the user for a branch prefix, such as their first name in lowercase. If they have no preference, omit `--prefix` and the installer uses their `git config user.name`.

## Install

1. Clone the repo anywhere that is not a temp folder, because updates are a `git pull` away:

   ```bash
   git clone git@github.com:gdncomm-aditya-h/adit-mobile-orchestration.git ~/.local/share/adit-mobile-orchestration
   cd ~/.local/share/adit-mobile-orchestration
   ```

   If SSH fails, try `gh repo clone gdncomm-aditya-h/adit-mobile-orchestration`. If both fail, the user lacks access: tell them to ask the repo owner to add them, then stop.

2. Show the user the plan before changing anything:

   ```bash
   python3 install.py install --target auto --prefix <prefix> --dry-run
   ```

   Summarize it in a few lines: which skills, which files in `~/.claude` or `~/.codex` change, and which plugins would be added. Wait for a yes.

3. Run it for real, without `--dry-run`. Add `--skip-deps` only if the user asked to skip plugins.

4. Verify:

   ```bash
   python3 install.py doctor
   ```

   Report every `FAIL` and `WARN` line as it is. Do not hide them.

## Reading the doctor output

- A missing plugin from `agent-plugins` means the user has no access to that private marketplace. The skills that need it will not fully work. Tell the user which ones, using `skills.json`.
- A plugin version that differs from the tested one is only a warning.
- The `uatb test account file` warning matters only if the user will run `adit-workflow-verify-before-pr`. Tell them to fill in `~/.claude/adit-workflow/uatb-account.json` themselves. Never ask for the values in chat and never type them in.
- When the `claude` CLI is not on the PATH, the installer prints the `/plugin` commands to run inside a Claude Code session. Pass those on to the user.

## What you must not do

- Do not edit `settings.json`, `CLAUDE.md` or `AGENTS.md` by hand. The installer owns the marked block and the one hook entry.
- Do not commit or push anything in this repo while installing.
- Do not run the ticket flow to test the install.

## Finish

Tell the user to restart Claude Code or Codex so the new skills load. Then say in two or three lines what was installed, what the doctor flagged, and what they still need to do.

For Codex, add that support is experimental and the full ticket flow works only in Claude Code. See `docs/compatibility.md`.
