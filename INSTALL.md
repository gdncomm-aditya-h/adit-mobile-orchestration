# Install guide for agents

This file is written for Claude Code. A person who wants to install by hand should follow the README instead.

This repo is a mirror of the `ios-orchestration-*` skills of the `mobileapps-ios` plugin (agent-plugins#595, in review, not released). Once that plugin version is released, the user should install `mobileapps-ios` 1.11.0 or newer from the `agent-plugins` marketplace and not use this repo. Until then, this repo can be loaded as a plugin directory. There is no installer: nothing is written into the user's `~/.claude` files.

## Before you start

1. Confirm `python3 --version` is 3.8 or newer and `gh auth status` succeeds. If `gh` is not signed in, stop and tell the user to run `gh auth login`.
2. Check that the user does not already have `mobileapps-ios` 1.11.0 or newer enabled. Two copies mean two gate hooks on the same ticket. If they do, stop and tell them to use that plugin.

## Install

1. Clone the repo anywhere that is not a temp folder, because updates are a `git pull` away:

   ```bash
   git clone git@github.com:gdncomm-aditya-h/adit-mobile-orchestration.git ~/.local/share/adit-mobile-orchestration
   ```

   If SSH fails, try `gh repo clone gdncomm-aditya-h/adit-mobile-orchestration`. If both fail, the user lacks access: tell them to ask the repo owner to add them, then stop.

2. Tell the user to start Claude Code with the repo as a plugin directory:

   ```bash
   claude --plugin-dir ~/.local/share/adit-mobile-orchestration
   ```

3. In that session, run `/ios-orchestration-setup`. It checks the plugins the flow needs, asks per plugin and installs the ones the user approves. Never install a plugin on your own.

4. Run `/ios-orchestration-flow-doctor` and report every blocker and warning as it is. Do not hide them.

## What you must not do

- Do not edit `settings.json`, `CLAUDE.md` or `AGENTS.md` by hand. The gate hook comes from `hooks/hooks.json` in the plugin.
- Do not edit the mirrored files (`skills/ios-orchestration-*`, `scripts/`, `hooks/hooks.json`). They are copies of the PR.
- Do not commit or push anything in this repo while installing.
- Do not run the ticket flow to test the install.
- The simulator test account is the user's to fill in: `~/.claude/ios-ticket-flow/uatb-account.json`. Never ask for the values in chat and never type them in.

## Finish

Say in two or three lines what was set up, what the doctor flagged, and what the user still needs to do.
