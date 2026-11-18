---
name: adit-workflow-audit-review-code
description: Run an audit loop then a review loop over the current changes (git diff, staged and unstaged, plus untracked files), fixing findings until good to ship, then ask before commit and push. Use for /adit-workflow-audit-review-code or "audit and review my changes".
---

# adit-workflow-audit-review-code

Scope = the changes only (`git status`, `git diff HEAD`, untracked files). Not the whole repo. Pass this scope to every audit and review call.

## Severity tiers

Map every finding to one tier:

- **must fix**: bug, security hole, data loss, breaks callers or tests.
- **should fix**: real risk or quality problem. Missing test for risky code, slow path, needless code.
- **nice to have**: style, polish, optional cleanup.

## Loop 1: audit

1. Invoke `ponytail:ponytail-audit` on the changes. Tell it to limit scope to the changes and to label each finding must fix / should fix / nice to have.
2. Stop loop 1 when the result is "good to ship", or only nice to haves remain.
3. Otherwise fix all must fix and should fix findings. Fix nice to haves too. Then go to step 1.
4. Cap: 5 rounds. If still not clean, stop and report what remains.

## Loop 2: review

Same as loop 1, but invoke `ponytail:ponytail-review` instead of `ponytail:ponytail-audit`. Same tiers, same stop rule, same cap.

## After both loops

Report in a few lines: rounds run per loop, what was fixed, any nice to haves left unfixed. Then ask the user whether to commit and push. Do not commit or push before they say yes.
