---
name: ios-orchestration-verify-ticket
description: Gate between implementation and PR for a ticket on any iOS repo. App repos get lint, build, unit and UI tests, simulator click tests, design and wording checks. Package repos get build and test on the package scheme. Reports real results, then arms the verified marker when every check passes. Does not open the PR or touch Jira. Use from ios-orchestration-ticket-to-pr, or when the user runs /ios-orchestration-verify-ticket.
argument-hint: <TICKET-KEY>
---

# verify-ticket

Input: `$ARGUMENTS` (ticket key). Run in the ticket's worktree with the changes uncommitted. Scripts are in `<skill_dir>/../../scripts/` (`<skill_dir>` is the base directory shown when this skill loads). Needs the saved plan `~/.claude/ios-ticket-flow/plans/<KEY>-*.md` (from `ios-orchestration-enrich-plan`); if it is missing, run that skill first.

Rules: report real results only. Never mark something passed that did not run. Show the shortest decisive error line for failures. Enter no credential except the shared `uatb` test account in "Login". Ask only for a blocker, in one message with the failure, the error line and the recommended fix. When this skill runs in a sub-agent (as `ios-orchestration-ticket-to-pr` does), it cannot ask: return `BLOCKER: <failure>, <error line>, <recommended fix>` (or the override question with the recommended answer) and stop; the caller asks and sends the answer back. This skill returns a result table and arms the gate. It never creates a PR and never posts to Jira.

## 0. Preflight
Run `python3 <scripts>/doctor.py --preflight --need git,xcode`. Silent means ready (tool results are cached for 24 hours). A `BLOCKER:` line means this skill cannot run: show it with its fix and stop. `WARN:` lines: mention once and continue.

## 1. Setup
1. Confirm the branch contains `<KEY>` and `git status` shows the changes.
2. Profile: `python3 <scripts>/repo_profile.py detect`. It decides the ladder below.
3. Commands: reuse the "How we test it" block of the plan if present. Otherwise choose without asking and save the choice into the plan file:
   - app: workspace and scheme from the profile; scheme = the one in the project's shared schemes whose TestAction lists the profile's `unitTarget` (`grep -l`); if several, prefer the one ending in `-test`; ask only if none matches. Simulator = the slot's `simulator.udid`, passed as `-destination 'platform=iOS Simulator,id=<udid>'`.
   - package: `xcodebuild -scheme <profile.scheme> -destination 'generic/platform=iOS Simulator'` for build, and `test` with a concrete simulator destination for tests.
4. Swift packages (app repos with a slot): run `python3 <scripts>/ticket_slots.py packages <KEY>` before the first build. It downloads only when the package files changed since the last check (for example after a merge from base), retries once, and asks nothing. Exit 4 is a blocker: show its last lines.
5. Builds are slow: run `xcodebuild` in the background (`run_in_background`) and write the log to a file. Do not poll; read the log when notified.

## 2. Static and build checks
1. SwiftLint on the changed Swift files, using the repo's own config and the profile's `swiftlint` path when present. No config means skip and record `not run: no swiftlint config`.
2. Build: `xcodebuild build-for-testing` (app) or `build` (package).
Fail: fix with the team codegen skills (`swift-codegen`, `swiftui-code-gen`), re-run. After 2 failed fix rounds, ask (blocker).
**The test target must compile.** `build-for-testing` failing, or unit tests that cannot compile or launch, is a `fail`, never `not run` and never a reason to carry on to the click tests. After the 2 fix rounds the only way forward is a written override reason from the engineer (`AskUserQuestion`, same as section 5). Record `tests-unverified: <reason>` in the plan and the result table, list every test that did not run, and the draft PR gets the label `tests-unverified` and the reason in its body. The gate stays closed until they answer.

## 3. Tests
1. Unit tests: use `run-tests` for the suites in plan 5.2 when it covers them (it picks the simulator, falls back to Rosetta and reports coverage). Run `xcodebuild test-without-building ... -only-testing:<unitTarget>/<Suite>` yourself for anything `run-tests` cannot select.
2. UI tests (app repos): only the XCUITest cases the plan names. No UI test covers the flow: record `no UI test covers this` (not a pass, not a blocker).
3. Every plan 5.2 row ends as pass, fail or not run. Fail: fix and re-run, same 2-round limit.

## 4. Click tests, design, wording (app repos, `app` mode only)
An app repo plan with no section 5.3 is incomplete: run `ios-orchestration-enrich-plan <KEY>` first, so click tests are never skipped for lack of a plan.
Needs `mcp__Claude_Code_iOS_Simulator__control`. Without it (CLI), record every plan 5.3 and 5.4 case as `needs manual run: no simulator tool in this client` and go to step 5.
Call `attach` first with the slot's `device`, then `launch` the built `.app`, then take a screenshot.
- Login screen shown: log in per "Login". A failure is a blocker.
- Cannot switch environment, flag or locale: blocker. App crashes: relaunch once and retry the case; crashes again: blocker with the crash line.

### Login
Shared team test account for the lower environment `uatb`, used only in a debug build pointed at `uatb`. Never use it for production and never type any other credential. The values live in `~/.claude/ios-ticket-flow/uatb-account.json` with the keys `email`, `password`, `otp`. Missing file or placeholder values: blocker, ask the engineer to fill it in. **Confirm the environment before any credential is typed:** take a screenshot of the app's environment indicator (debug menu, settings or the login screen's footer) and read the environment name from it. State it in one line (`environment: uatb (from <screen>)`) and keep that screenshot as evidence. It is not `uatb`: switch it, and re-read it. It cannot be switched, or the indicator cannot be found: ask the engineer once (`AskUserQuestion`: "Is this build pointed at uatb?"); anything but a yes is a blocker. Never infer `uatb` from the build configuration or from earlier runs. Type the email, then the password, then the OTP when asked, with `control` `tap` and `text`, with a screenshot after each step. Do this once per simulator: the session persists.

Screen recording: after login and before the first case, start `xcrun simctl io <udid> recordVideo --codec=h264 ~/.claude/ios-ticket-flow/evidence/<KEY>/click-tests.mp4` in the background. After the last case, stop it with SIGINT (`pkill -INT -f "simctl io <udid> recordVideo"`), then confirm the file exists and is not empty. If recording fails, record `no screen recording`.

For each plan 5.3 and 5.4 case:
1. Drive the steps. Take a screenshot at every point the plan's Evidence column names, and at least one that shows the screen opened and one that shows the changed element, saved as `~/.claude/ios-ticket-flow/evidence/<KEY>/<case-id>-<n>.png`. Do not skip a screenshot to keep the count low: the Jira comment attaches all that show the change.
2. **Design** is advisory. Read the reference image and the screenshot and compare layout, element order, icons, colors, spacing and copy position. Report match or mismatch per element. This is a visual comparison, not a pixel diff: say so, and do not claim exact spacing or font weight. A design mismatch alone does not fail the gate; a clear functional or wording failure does.
3. **Wording**: compare every on-screen string with the plan's wording table (sheet wins over design), for each locale in the sheet. A design-versus-sheet difference already in the plan is noted, not failed.
4. A state that cannot be reached (server error, rare flag) is `needs manual run`: record it, never a pass, not a blocker.
5. A failed click or wording case is a fail: fix the code, re-run that case, same 2-round limit.

## 5. Nothing can be built
If the build in step 2 cannot run for this repo (no buildable scheme, a toolchain or dependency that cannot be resolved), do the checks that need no build: lint, a syntax parse of the changed files, a public-API diff of the change, and a grep for users of the changed API in `gdncomm/BlibliIOSApp`. Then ask the engineer once for a written override reason (`AskUserQuestion`). The gate stays closed until they give one. Record `build-unverified: <reason>` in the plan and in the result table, and list every check that did not run.

## 6. Decide
Build the table: lint, build, unit, UI, click, design, wording, each pass / fail / not run / needs manual run / no UI test.
- Any `fail`, or a check that did not run and is not `needs manual run`, `no UI test`, an accepted `build-unverified` or an accepted `tests-unverified`: not verified. Fix within the round limit or ask. Do not mark verified.
- Otherwise: verified, no confirmation question. Run `python3 <scripts>/ticket_gate.py mark-verified <KEY>` inside the worktree (it records a hash of the changed files; commit is allowed only while they are unchanged).
Return the table and the evidence paths to the caller.
