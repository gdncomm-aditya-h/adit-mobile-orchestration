---
name: ios-orchestration-audit-changes
description: Run an audit loop then a review loop over the current changes (git diff, staged and unstaged, plus untracked files) and fix the findings that matter. Never commits or pushes. Use from ios-orchestration-ticket-to-pr, or for "audit and review my changes" and /ios-orchestration-audit-changes.
---

# audit-changes

Scope = the changes only (`git status`, `git diff HEAD`, untracked files). Not the whole repo. Pass this scope to every audit and review call.

## Engines
- Audit: `ponytail:ponytail-audit`. Review: `ponytail:ponytail-review`.
- If the `ponytail` plugin is not installed: use the `ecc:code-reviewer` agent for both loops, or `swift-review` for Swift files. Say once which engine you used.

## Severity tiers
Map every finding to one tier:
- **must fix**: bug, security hole, data loss, breaks callers or tests.
- **should fix**: real risk or quality problem. Missing test for risky code, slow path, needless code.
- **nice to have**: style, polish, optional cleanup.

## Loop 1: audit
1. Run the audit engine on the changes. Tell it to limit scope to the changes and to label each finding must fix / should fix / nice to have.
2. Stop the loop when the result is "good to ship", or only nice to haves remain.
3. Otherwise fix every must fix and should fix finding, then go to step 1. Do not fix nice to haves: they widen the diff. List them.
4. Cap: 2 rounds when called from `ios-orchestration-ticket-to-pr`, 5 when run on its own. If still not clean, stop and report what remains.

## Loop 2: review
Same as loop 1 with the review engine. Same tiers, same stop rule, same cap.

## After both loops
Report in a few lines: rounds run per loop, what was fixed, the nice to haves left unfixed, and anything still must fix or should fix. This skill never commits or pushes. Run on its own, you may then offer to commit and push; do not do it before the user says yes. Called from `ios-orchestration-ticket-to-pr`, just return the report.
