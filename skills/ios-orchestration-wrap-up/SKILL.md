---
name: ios-orchestration-wrap-up
description: After a ticket's PR is merged, move the Jira ticket to its post-merge status (Bug to Code Review, everything else to Dev Testing), release the worktree slot, clear the gate and archive the saved plan. Checks that the PR really is merged first. Use from ios-orchestration-pr-watch on `merged`, or for "wrap up IOS-123" and /ios-orchestration-wrap-up. Never merges.
argument-hint: <TICKET-KEY> [--repo owner/repo] [--pr <number>]
---

# wrap-up

Input: `$ARGUMENTS`. Scripts are in `<skill_dir>/../../scripts/` (`<skill_dir>` is the base directory shown when this skill loads). Data lives in `~/.claude/ios-ticket-flow/`.

Rules: change nothing until the PR is confirmed merged. Never delete a worktree with uncommitted changes, never delete DerivedData by hand, never touch a ticket's comments. Report real results only.

## 1. Confirm the merge
1. Repo = `--repo`, else the saved `defaultRepo` (`python3 <scripts>/flowconfig.py get defaultRepo`). PR = `--pr`, else the open or merged PR for the ticket's branch: `gh pr list --repo <repo> --search "<KEY>" --state all --json number,state,headRefName`.
2. `gh pr view <n> --repo <repo> --json state,mergedAt`. Not `MERGED`: say so and stop. No PR found: ask once for the PR number.

## 2. Move the ticket
Read the ticket with `getJiraIssue` (Atlassian MCP; `discover` if a tool is not listed). The target depends on the issue type and is read from the workflow, not assumed: a **Bug** goes to `Code Review`; every other type goes to `Dev Testing`.
1. `listJiraIssueTransitions`, then pick the transition whose **target status** matches (target status, not the transition's own name).
2. Skip when the ticket is already at or past that status. Neither reachable, or the call failing twice: continue, and report it.
3. `transitionJiraIssue` with that transition id, then confirm with `getJiraIssue`.
4. Print one line: `Jira <KEY>: <from> -> <to>` or `Jira <KEY>: not moved (<reason and the transitions offered>)`.

## 3. Clean up
1. `python3 <scripts>/ticket_gate.py clear <KEY>` (safe when nothing is armed).
2. `python3 <scripts>/ticket_slots.py --repo <repo> release <KEY>`, run inside a checkout of that repo (it prints `no slot held` when the slot is already free, which is fine; it keeps the warm worktree and DerivedData of an app repo for the next ticket, and removes a clean package worktree). A slot with uncommitted changes is never discarded: name the files and let the engineer decide.
3. Archive the plan: move `~/.claude/ios-ticket-flow/plans/<KEY>-*.md` to `~/.claude/ios-ticket-flow/plans/done/`. Leave `evidence/<KEY>/` where it is.

## 4. Report
One short block: PR and merge time, the Jira line, slot released or kept (and why), plan archived.
