---
name: ios-orchestration-flow-doctor
description: Check that this machine and client can run the iOS ticket-flow skills: tools, gh login, Xcode and simulator runtime, saved settings, stale gates, and which optional tools this client has (Atlassian MCP, simulator control, permission-mode switching). Read-only. Use before a first ticket, when a flow step fails for a missing tool, or for /ios-orchestration-flow-doctor.
argument-hint: [checkout dir]
---

# doctor

Read-only. Fix nothing; report and say what to do.

The other ios-orchestration skills already run a quiet, cached preflight of the machine checks themselves (`doctor.py --preflight`), so nobody has to run this first. Run it when you want the full picture, including the client checks below, or after fixing something (it ignores the 24-hour cache).

1. Machine checks: run `python3 <skill_dir>/../../scripts/doctor.py [dir]` and print its table. It covers `git`, `gh` and its login, `python3`, `xcodebuild`, `xcrun`, the saved settings, stale gate markers, the repo profile, SwiftLint, an iOS simulator runtime and the plugins the flow calls (`mobileapps-foundation` is required; `superpowers`, `ponytail` and `ecc` are optional). Missing plugins are installed by `ios-orchestration-setup`, not here.
2. Client checks (the script cannot see these): search the tool list, loading deferred tools with ToolSearch, for:
   - Atlassian MCP (`getJiraIssue`, `transitionJiraIssue`): needed to read tickets and move status. Missing: tell the user to connect it; the flow cannot read tickets without it.
   - `mcp__Claude_Code_iOS_Simulator__control`: needed for click tests. Missing: that is the CLI case, click tests become `needs manual run`.
   - `mcp__ccd_session_mgmt__set_session_permission_mode`: needed to switch to auto mode by itself. Missing: the engineer presses Shift+Tab.
   - GitHub tools `mcp__github__create_pull_request`: optional; `gh` is used when absent.
3. Print one verdict line: `app mode` (simulator tool and mode switch present), `cli mode` (neither), or the mixed case with what is missing.
4. List fixes in the order they unblock the flow: missing tool, `gh auth login`, run `ios-orchestration-setup` for missing plugins, install an iOS runtime, set the branch prefix with `ios-orchestration-flow-config`, clear an expired gate with `ticket_gate.py clear <KEY>`.
