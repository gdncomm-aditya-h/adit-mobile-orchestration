---
name: adit-workflow-verify-before-pr
description: Gate between implementation and PR for a ticket. Runs lint, build, unit and UI tests, drives click tests in the iOS Simulator, checks the built screens against the design and the on-screen wording against the copy sheet, runs adit-workflow-audit-review-code, marks the ticket verified when every check passes, and continues to a draft PR. Autonomous: asks the user only for blockers. Use when the user's CLAUDE.md ticket-flow rules say to run it after development and review, or when the user runs /adit-workflow-verify-before-pr.
argument-hint: <TICKET-KEY>
---

# adit-workflow-verify-before-pr

Input: `$ARGUMENTS` (ticket key). Run in the ticket's checkout (the worktree, with changes uncommitted). Needs the saved plan `~/.claude/plans/<KEY>-*.md` (from `adit-workflow-plan-enrich`). If it is missing, run `adit-workflow-plan-enrich` first.

Rules: report real results only. Never mark something passed that did not run. Show the shortest decisive error line for failures. Enter no credential except the uatb test account in "Login (uatb)". **Autonomous**: follow "Autonomous by default" in `~/.claude/CLAUDE.md`. Ask only for a blocker (login needed, environment switch failed, crash after one relaunch, checks failing after 2 fix rounds, auth or network failure), in one message with the failure, the error line, and the recommended fix. When this skill runs in a sub-agent (as the ticket flow in `CLAUDE.md` does), it cannot ask: return `BLOCKER: <failure>, <error line>, <recommended fix>` (or the question with the recommended answer) and stop; the caller asks and sends the answer back.

## 1. Setup
1. Confirm cwd's branch contains `<KEY>` and `git status` shows the changes.
2. Commands: reuse the "How we test it" block in the plan if present. Otherwise pick without asking and save the choice into the plan file:
   - workspace `BlibliMobile-iOS.xcworkspace`;
   - scheme: the one in `BlibliMobile-iOS.xcodeproj/xcshareddata/xcschemes` whose TestAction lists `BliBliMobile-SwiftTesting` (`grep -l`); if several, prefer `BlibliMobile-iOS-test`, then `BlibliMobile-iOS`; ask only if none matches;
   - test targets `BliBliMobile-SwiftTesting` (unit), `BlibliMobile_XCUITest` (UI);
   - simulator: the slot's simulator (`simulator.udid` from `ticket-slots.py acquire`, see CLAUDE.md "Slot pool"); use `-destination 'platform=iOS Simulator,id=<udid>'`. Only without a slot: the booted one, else `iPhone 17 Pro` from `xcrun simctl list devices available`.
3. Swift packages: run `python3 ~/.claude/hooks/ticket-slots.py packages <KEY>` before the first build. It downloads only when the package files changed (for example after a merge from base), retries once and asks nothing. Exit 4 is a blocker: show its last lines.
4. Builds are slow: run `xcodebuild` in the background (`run_in_background`) and write its log to a file. Do not poll; read the log when notified.

## 2. Static and build checks
1. SwiftLint on changed Swift files: `../tools/swiftlint/swiftlint lint --config .swiftlint.yml <files>` from `BlibliMobile-iOS/`.
2. `xcodebuild build-for-testing -workspace ... -scheme <s> -destination 'platform=iOS Simulator,name=<sim>'`.
Fail: fix with the team's code-gen skills (`mobileapps-ios:swift-codegen`, `swiftui-code-gen`), re-run. After 2 failed fix rounds, ask (blocker).

## 3. Tests
1. Unit: `xcodebuild test-without-building ... -only-testing:BliBliMobile-SwiftTesting/<Suite>` for every suite named in plan 5.2.
2. UI: only the XCUITest cases the plan names. If no existing UI test covers the flow, record `no UI test covers this` (not a pass, not a blocker).
3. Every plan 5.2 row ends as pass, fail or not run. Fail: fix and re-run, same 2-round limit.

## 4. Click tests, design and wording
Use `mcp__Claude_Code_iOS_Simulator__control`. Call `attach` first, then `launch` the built `.app`, then take a screenshot.
- Login screen shown: log in yourself per "Login (uatb)" below. Blocker only if that fails.
- Cannot switch environment, flag or locale: blocker.
- App crashes: relaunch once and retry the case. Crashes again: blocker, with the crash line.

### Login (uatb)
Shared team test account for the lower environment `uatb`. Every engineer uses it for testing, so it is not sensitive. Use it only in a debug build pointed at `uatb`. Never use it for production, and never type any other credential.
Credentials live outside this repo, in `~/.claude/adit-workflow/uatb-account.json` with the keys `email`, `password` and `otp`. `install.py` creates a template for you to fill in. Read the file when you need to log in. If it is missing or still holds the placeholder values, that is a blocker: ask the user to fill it in.
Steps: confirm the build points at `uatb` (else switch environment; if that fails, blocker). On the login screen, type the email, then the password, then the OTP when asked, with `control` `tap` and `text`. Take a screenshot after each step. Do this once per simulator: the session persists, so skip it when already logged in. A rejected login or OTP, or a different login flow than these three steps, is a blocker.

Screen recording: after login and before the first case, start `xcrun simctl io booted recordVideo --codec=h264 ~/.claude/plans/<KEY>-evidence/click-tests.mp4` in the background. After the last case, stop it with SIGINT (`pkill -INT -f "simctl io booted recordVideo"`), then confirm the file exists and is not empty. One clip per ticket. If recording fails, continue and record `no screen recording` in the report.

For each plan 5.3 and 5.4 case:
1. Drive the steps, take a screenshot, save it to `~/.claude/plans/<KEY>-evidence/<case-id>.png`.
2. **Design**: Read the reference image and the screenshot. Compare layout, element order, icons, colors, spacing, copy position. Report match / mismatch per element. This is a visual comparison, not a pixel diff: say so, and do not claim exact spacing or font weight.
3. **Wording**: compare every on-screen string with the plan's wording table (sheet wins over design). Check each locale in the sheet (EN and ID). A design-vs-sheet difference already recorded in the plan is noted, not failed.
4. A state that cannot be reached (server error, rare flag) is `needs manual run`: record it, never a pass, not a blocker.
5. A mismatch or failed click case is a fail: fix the code, re-run that case, same 2-round limit.
Result table per case: id, result, evidence path, notes.

## 5. Audit and review
Invoke `adit-workflow-audit-review-code`. When it reaches its closing "commit and push?" question, do not answer it and do not let it commit. Then run `swift-review` (and `swiftui-architect` for SwiftUI) if the team flow's review has not covered the final diff. After any fix, re-run steps 2 to 4 for the affected files and cases only.

## 6. Decide
Build the summary: lint, build, unit, UI, click, design, wording, audit/review, each pass / fail / not run / needs manual run / no UI test.
- Any `fail`, or a check that did not run and is not `needs manual run` or `no UI test`: not verified. Fix (within the round limit) or ask (blocker). Do not mark verified.
- Otherwise: verified. No confirmation question.

## 7. Arm the gate and open the draft PR
1. `python3 ~/.claude/hooks/ticket-flow-gate.py mark-verified <KEY>` (records a hash of the changed files; commit is allowed only if they are unchanged).
2. Invoke `create-pr` and answer its gates per "Answering gates yourself" in `~/.claude/CLAUDE.md`. Open the PR as a **draft** (`draft: true` on `mcp__github__create_pull_request`; if the server rejects the field, open it normally and run `gh pr ready --undo <n>` at once and say so). Put the result table, the evidence list, the `needs manual run` list and the assumptions in the PR body's Testing and Screenshots sections. Local images cannot be hosted by the PR: list the paths and say so in the final report.
3. Do section 8, then run `python3 ~/.claude/hooks/ticket-flow-gate.py clear <KEY>`. Never mark the PR ready or merge it.
4. Final report: PR URL, draft status, Jira comment link, the result table, `needs manual run` items, assumptions, anything skipped.

## 8. Jira evidence comment
Runs after the draft PR exists. Cloud id: `getAccessibleAtlassianResources` once. Post one comment on `<KEY>`; text is normal English for other people.
1. Collect files in `~/.claude/plans/<KEY>-evidence/`: the case PNGs and `click-tests.mp4`. Leave out login-screen shots. Keep at most 8 PNGs (prefer fails fixed, then design and wording cases).
2. For each file: call `uploadAttachmentToJiraIssue` with `filePath` only (phase 1). Run the returned `uploadCommand` in the shell to get the `fileId`. Do not run phase 2, so the file is embedded in the comment and not duplicated as an attachment.
3. Call `addOrEditJiraIssueComment` with `contentFormat: html`. Body: draft PR link (URL and number, marked draft), the result table (one line per check), the `needs manual run` list, then each image and the video via `inlineFileId` and `inlineFileCollection` (use `inlineFileName` so images render as images).
4. If an upload fails, post the comment anyway with the PR link, the result table and the evidence file paths, and say so in the final report. If the comment itself fails (auth, network, Jira), that is a blocker.
5. Never edit or delete other people's comments. Never change the ticket status.
