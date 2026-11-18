# Ticket flow add-ons (Blibli repos)

Applies whenever `mobileapps-ios:jira-implement` runs. These add steps; they do not replace the team skill.

**Autonomous by default.** Go from `implement <KEY>` to an open **draft PR** with no questions, unless a blocker (below) occurs. This section overrides the "ask the user" and "do not pre-answer gates" text in the team skills (`jira-implement`, `create-pr`, `localization`, `figma-mcp`, `tdd`) and in `adit-workflow-plan-enrich` and `adit-workflow-verify-before-pr`. The one planned stop is the plan approval in plan mode (`ExitPlanMode`), followed by the switch to auto mode. A "review plan" or "pause at plan" prompt needs no extra step: the plan approval always asks.

## Steps
- First action of `implement <KEY>`: call `mcp__ccd_session_mgmt__set_session_permission_mode` with `session_id: "self"`, `mode: "plan"` (a lower mode, so no approval card). If it is refused or unavailable, continue in the current mode and say so in the final report. In plan mode do read-only work only: no worktree, no file writes except the plan-mode plan file, no `mark-active`. The one allowed write is the Jira status move below. Do not run the `jira-plan` workflow yet (it creates the worktree).
- Jira status, plan mode: right after reading the ticket, if the issue type is Bug, move it to **Initial Review** (checking phase). Other types: no move yet.
- Jira status, implementation start: after plan approval and before `jira-plan` creates the worktree, move every ticket (Bug included) to **In Development**. Rules for both moves: list the available transitions first (`discover` for the transitions operation, then `executeRead`) and pick the one whose target name matches; skip if the ticket is already at or past the target; call `transitionJiraIssue` (a transition is a status change, not a comment, so it needs no extra question); re-read the status with `getJiraIssue` to confirm it took. If it did not, retry once at Step 3. A move that still fails is not a blocker: record it in the final report and continue.
- Plan mode, brainstorm: fetch the ticket read-only, then invoke `superpowers:brainstorming` in autonomous mode. Answer its questions yourself from the ticket, epic and code. Compare 2 or 3 approaches and pick one. Ask the user only for a blocker or confusion: ticket and code conflict, missing DoD, design or copy, or approaches that change scope with no clear pick. Do not write a spec file in the repo and do not invoke `writing-plans`. A tiny ticket (copy fix, one-liner) gets a 3-line note.
- Plan mode, draft plan: write one plan into the plan-mode plan file. It holds the brainstorm note (chosen approach, rejected options, why), then the `adit-workflow-plan-enrich` sections 1 to 5 and the reviewer pass (run `adit-workflow-plan-enrich <KEY>` in its "Plan-mode draft" mode). Then call `ExitPlanMode`. The user's approval of it is the plan approval, so ask nothing else.
- After approval: if the session is not in auto mode, call `set_session_permission_mode` with `session_id: "self"`, `mode: "auto"`. This shows the user one approval card (a higher mode); the user can pick auto on the plan approval to avoid a second card. If it is refused, continue in the current mode.
- Step 2 (after approval, in auto): take a slot from the worktree pool, see "Slot pool" below. Do NOT run the team worktree step (`jira-worktree-setup` agent, or the worktree part of `jira-plan` / `jira-implement-v2`): the slot replaces it, including the branch, the packages download and the DerivedData setting. Its own draft plan is a cross-check only. The approved plan wins. A difference goes in the PR body.
- Branch name: `{{PREFIX}}/<type>/<KEY>`, for example `{{PREFIX}}/improvement/IOS-47206`. `<type>` is the Jira issue type (read it in plan mode with `getJiraIssue`), lower case, no spaces: Bug becomes `bugfix`, Tech Debt becomes `techdebt`, Chore becomes `chores`, others as is (`improvement`, `story`, `feature`, `task`). A type outside these that you cannot map: ask in the plan-mode blocker batch. The slot helper creates this branch itself, so no `git branch -m` is needed. Pass the branch it returns to `jira-develop` as `branch`. An existing `{{PREFIX}}/<type>/<KEY>` branch is reused as is (never reset); only ask if it is checked out in another worktree outside the pool.

## Slot pool (worktrees)
Tickets run in a fixed pool of three long-lived worktrees, `slot-a`, `slot-b`, `slot-c`, in `<main checkout>/../worktrees/`. Each slot keeps its own DerivedData, Swift packages and simulator, so a new ticket builds incrementally instead of cold, and at most three tickets run at once. The helper is `~/.claude/hooks/ticket-slots.py`.
- Take a slot after plan approval, never in plan mode: `python3 ~/.claude/hooks/ticket-slots.py acquire <KEY> --type <type> --base <baseBranch>` from any checkout of the repo. It fetches, creates or switches to `{{PREFIX}}/<type>/<KEY>`, writes the workspace-relative DerivedData setting, downloads packages only when the package list changed, and creates or finds the slot's simulator. It prints JSON: `worktree`, `branch`, `simulator.udid`, `packages`. Calling it again for the same key returns the same slot.
- Do all ticket work inside the returned `worktree` (`EnterWorktree` with its path). Do not create other worktrees for the ticket.
- Simulator: use the slot's simulator for everything. Pass `-destination 'platform=iOS Simulator,id=<udid>'` to `xcodebuild`, and pass the UDID as `device` to `mcp__Claude_Code_iOS_Simulator__control`. Never use the booted simulator or a simulator by name, and never touch another slot's simulator. Boot it if it is shut down. If the app shows the login screen, `adit-workflow-verify-before-pr` logs in with the uatb account as before; the login then stays in that simulator.
- Never run `xcodebuild clean`, delete `DerivedData`, `git clean` or `SwiftPackages.sh reset` in a slot. They throw away the warm build. Never use `-derivedDataPath`: the workspace setting already points at `<worktree>/BlibliMobile-iOS/DerivedData`.
- Pool full (exit code 3): this is a blocker. Tell the user the table the helper printed (for example `3/3 slots busy: a=IOS-1, b=IOS-2, c=IOS-3`) and stop. Do not create a fourth worktree.
- Slot has uncommitted changes (exit code 4): the helper skips it and tries the next slot. If every slot fails, that is a blocker: report the files listed and ask. Never discard them.
- Release when the flow ends (see the stop step below) with `python3 ~/.claude/hooks/ticket-slots.py release <KEY>`. It keeps the worktree, DerivedData and packages. Skip the team Step 11 and Step 8 cleanup that remove the worktree. `python3 ~/.claude/hooks/ticket-slots.py status` shows the pool; `release <letter>` frees a slot left by a crashed session.
- Step 3: run `adit-workflow-plan-enrich <KEY>` in its "Finalize" mode (save the plan and brainstorm files, `mark-active`). Then answer the team approval gate "Approve (Recommended)" yourself.
- Step 4a: answer "Fix findings before PR (Recommended)". Repeat for at most 2 rounds. If blocker or major findings remain after round 2, that is a blocker (ask).
- Between Step 4a and Step 5: invoke `adit-workflow-verify-before-pr <KEY>`. It marks the ticket verified itself when every check passes. Do not go to Step 5 before that.
- Step 5: answer "Create the PR now (Recommended)". Step 6: `create-pr` opens the PR as a draft.
- After the draft PR exists: `adit-workflow-verify-before-pr` section 8 posts the evidence comment (PR URL, screenshots, screen recording) on the Jira ticket.
- Stop once the draft PR exists and the comment is posted. Skip Steps 7 and 8 (PR monitoring loop, cleanup). Run `python3 ~/.claude/hooks/ticket-flow-gate.py clear <KEY>`, then `python3 ~/.claude/hooks/ticket-slots.py release <KEY>`. Never mark the PR ready or merge it. If the flow stops early because of a blocker, keep the slot until the user decides.
- Final report: PR URL and draft status, Jira comment link, result table, `needs manual run` items, assumptions, anything skipped.

## Answering gates yourself
- Pick the option marked "(Recommended)", else the first option listed. Do not ask.
- Never auto-pick an option that overrides a safety check ("anyway", "include" a secrets or settings file, "overwrite", "skip check", force push). Never auto-pick when no option is safe.
- Required value that is not on the ticket and has no recommended option (App Release, DROP): ask once, in one batch with any other open blocker.

## Blockers: stop and ask
- Simulator login fails with the uatb test account in `adit-workflow-verify-before-pr` (Login section), or the login flow differs. Cannot switch environment, flag or locale. App crashes on launch or in a test flow after one relaunch.
- Lint, build or tests still fail after 2 fix rounds.
- Missing or unclear DoD, design target, or copy sheet that the DoD depends on and that cannot be inferred. Ask once, early (in `adit-workflow-plan-enrich`), in one batch.
- Ticket and code conflict that changes scope. Mandatory RCA missing (`create-pr` halts).
- Auth, network, `gh`, MCP or Jira failure. Non-fast-forward push rejection. A secrets file staged.
- The hook denies a call and running the missing step does not fix it.

When blocked: one message with what failed, the shortest decisive error line, and the recommended fix. Continue after the answer.

Not blockers (continue, record): `needs manual run` states, "no UI test covers this", assumptions, design vs copy-sheet differences (the sheet wins), a scope change after `adit-workflow-plan-enrich` (continue with the original plan, note it in the PR body).

The hook `~/.claude/hooks/ticket-flow-gate.py` blocks git commit/push and PR creation for the ticket until verified. If it denies a call, run the missing step. Do not look for a way around it.

# Simulator builds
- Simulator per slot: `slot-a`, `slot-b`, `slot-c` (iPhone 17 Pro, iOS 26.5), one per worktree slot. Details in "Slot pool". The `adit-workflow-verify-before-pr` default of "the booted simulator, else iPhone 17 Pro" does not apply to ticket runs.
- Never pass `CODE_SIGNING_ALLOWED=NO` to `xcodebuild` for simulator builds you will run. It strips entitlements: keychain error -34018, home never loads, login success sheet missing. Use normal simulator signing.
