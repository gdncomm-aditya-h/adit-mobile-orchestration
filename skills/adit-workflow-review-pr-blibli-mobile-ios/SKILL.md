---
name: adit-workflow-review-pr-blibli-mobile-ios
description: Batch-review open PRs in gdncomm/BlibliIOSApp one by one. Posts inline comments only for critical/major/security/risky issues, inline nits for the rest, approves when nothing above nit is found, and remembers reviewed PRs (by head SHA) so the next run skips them. Use for "review PR blibli mobile ios", "review the iOS PR list", or "review PR <number>".
argument-hint: [help] [<pr-number> ...] [--dry-run] [--force] [--limit N]
allowed-tools: [Bash, Read, Write, Agent, Skill]
---

# Review PR — Blibli Mobile iOS

Repo: `gdncomm/BlibliIOSApp` (iOS code under `BlibliMobile-iOS/`). Args in `$ARGUMENTS`.

## Help

If `$ARGUMENTS` contains `help`, `--help` or `-h`: print the block below verbatim, then stop. Do not call `gh`, do not review, do not touch state.

```
adit-workflow-review-pr-blibli-mobile-ios — review open PRs in gdncomm/BlibliIOSApp

Usage: /adit-workflow-review-pr-blibli-mobile-ios [help] [<pr-number> ...] [--dry-run] [--force] [--limit N]

  (no args)       sweep every OPEN, non-draft PR: new/changed head SHA -> review (only the new
                  commits if reviewed before, and approve if earlier blocking issues are fixed);
                  same SHA but new comments from others -> only 👍 / reply, no re-review
                  every PR: my own unresolved threads whose code is now fixed -> resolved
  <pr-number> ... review only these PRs (still skips drafts / non-open)
  --dry-run       print the review per PR, post nothing, write no state
  --force         ignore state; re-review PRs already reviewed at the same SHA
  --limit N       review at most N PRs this run (oldest updated first)
  help, -h        show this text

Examples:
  /adit-workflow-review-pr-blibli-mobile-ios --dry-run --limit 3
  /adit-workflow-review-pr-blibli-mobile-ios
  /adit-workflow-review-pr-blibli-mobile-ios 3211 3209
  /adit-workflow-review-pr-blibli-mobile-ios 3211 --force

Always skipped: drafts, closed/merged, your own PRs, PRs you already approved at this SHA.
Result: blocking finding (critical/major/security/risky) -> inline comments, event COMMENT.
        only nits or nothing -> inline nits (if any), event APPROVE.
Dedup: finding already raised by someone else -> 👍 on their comment (no new comment).
       same problem + something to add -> reply in their thread.
Resolve: only threads I started, only when the fix is verified in the code at head. Never others'.
Memory: ~/.claude/state/adit-workflow-review-pr-blibli-mobile-ios.json  {PR: head SHA, comment stamp, findings}. Delete an entry to re-review that PR.
```

## Permissions (always allowed, never ask)

Within this skill, do these without asking the user, per PR and per run:

1. Read everything on the PR via `gh`: metadata, diff, files, reviews, inline comments, issue comments, reactions.
2. Compose review comments.
3. Post them (inline review comments, thread replies, 👍 reactions).
4. Approve (event `APPROVE`) when the rules below allow it.
5. Resolve **my own** review threads once the code is fixed (step 3b). Never anyone else's.

The rules below still decide *what* to post. Permission to post is not permission to skip verification.

## Rules (fixed)

| Severity | Meaning | Output |
|---|---|---|
| critical | crash, data loss, broken core flow | inline comment, blocks approval |
| major | wrong behavior, race, leak/retain cycle, broken contract | inline comment, blocks approval |
| security | secrets, insecure storage/transport, unvalidated deeplink/URL/webview input, PII in logs | inline comment, blocks approval |
| risky | unsafe force-unwrap/cast, missing error path, main-thread blocking, migration hazard, missing tests on risky logic | inline comment, blocks approval |
| nit | naming, style, small simplification, minor docs | inline comment prefixed `nit:`, never blocks |

- Every finding is an **inline** comment on a diff line. Never write an overview comment.
- Review body stays empty (GitHub requires none for `COMMENT`/`APPROVE`).
- Only blocking findings present → event `COMMENT`. Never `REQUEST_CHANGES`.
- Zero findings, or nits only → event `APPROVE` (nits posted inline in the same review).
- Only comment on lines this PR added or changed. No praise comments. No speculative findings: if unsure it is real, drop it or downgrade to nit.

## State (memory)

File: `~/.claude/state/adit-workflow-review-pr-blibli-mobile-ios.json`, shape:
`{"<pr>": {"sha": "<head sha reviewed>", "at": "<iso>", "result": "approved|commented|skipped:<reason>", "cmt": "<newest updated_at of all inline + conversation comments, by anyone>", "findings": [{"path","line","sev","text"}]}}`.
`findings` = every critical/major/security/risky/nit finding of the last review (New, Same and Partial), kept for follow-up and dedup-only runs.
Create `~/.claude/state/` and the file (`{}`) if missing. Write the entry **only after** the review posts successfully (or after an intentional skip). Old entries without `cmt`/`findings`: treat `cmt` as changed and `findings` as empty.

Each PR gets one mode:
- **full**: no entry, or `--force`. Review the whole diff.
- **incremental**: entry exists, head SHA differs from `sha` (new push). Review only the new commits (`gh api repos/gdncomm/BlibliIOSApp/compare/<old sha>...<COMMIT>`) with the full PR diff as context, and run the follow-up check (step 4.4a).
- **dedup-only**: same SHA, but `cmt` changed (someone commented or edited). No engine run, no new review. Re-run dedup (step 4.5) of the stored `findings` against the new comments only: 👍 / reply, then update `cmt`. Never re-run for comments already seen.
- **skip**: same SHA and same `cmt`.

## Steps

1. **Who am I**: `ME=$(gh api user -q .login)`.
2. **List**: only PRs with state `OPEN` and not draft are ever visited. If PR numbers were given in `$ARGUMENTS`, fetch exactly those with `gh pr view N -R gdncomm/BlibliIOSApp --json number,title,author,headRefOid,isDraft,state,reviewDecision,updatedAt`. Otherwise:
   `gh pr list -R gdncomm/BlibliIOSApp --state open --limit 100 --json number,title,author,headRefOid,isDraft,state,reviewDecision,updatedAt`
3. **Filter** (record the skip reason for each): `isDraft == true` (always skipped, even when the number is given explicitly), `state != "OPEN"` (closed/merged, even when the number is given explicitly), `author.login == $ME` (cannot approve own PR), state hit with same SHA and unchanged `cmt` (unless `--force`; fetch inline + conversation comments to compare `cmt`; a changed `cmt` means mode **dedup-only**, not skip), PR where `$ME` already has an `APPROVED` review on the current head SHA (`gh api repos/gdncomm/BlibliIOSApp/pulls/N/reviews`). Apply `--limit N` after filtering. Process oldest `updatedAt` first.
3b. **Resolve sweep** (every OPEN, non-draft PR not authored by `$ME`, **including PRs skipped by state**, ignores `--limit`). Closes my own threads whose problem the author already fixed but did not mark resolved. It runs before step 4 so the approve decision in step 4.6 sees the true set of still-open findings.
   1. List threads (paginate while `hasNextPage`):
      ```bash
      gh api graphql -F o=gdncomm -F r=BlibliIOSApp -F n=N -f query='query($o:String!,$r:String!,$n:Int!,$c:String){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100,after:$c){pageInfo{hasNextPage endCursor} nodes{id isResolved isOutdated viewerCanResolve path line comments(first:50){nodes{databaseId author{login} body createdAt}}}}}}}'
      ```
   2. **Candidate = all of**: `isResolved == false`, `viewerCanResolve == true`, and the **root comment** (`comments.nodes[0]`) `author.login == $ME`. Anything else is never touched: threads started by other people, threads where I only replied, threads already resolved. Skip the PR if there are no candidates.
   3. For each candidate, re-read the cited code at head `COMMIT` (`gh api repos/gdncomm/BlibliIOSApp/contents/<path>?ref=<COMMIT>`; the file may have moved or the line shifted, find the code by content, not by the old line number; `isOutdated` only means the line changed, not that the problem is fixed). Decide:
      - **Fixed**: the problem in my root comment no longer exists in the code (fix applied, code removed, or an equivalent fix that differs from my suggestion). Resolve.
      - **Open / unsure**: problem still there, or you cannot tell. Leave it. Never resolve on the author's reply alone (a "Fixed in <sha>" reply is a hint to check, not proof).
      - **Disputed**: a later comment from someone else disagrees, asks a question, or gives a reason instead of a fix. Leave it open and list it in the report as `needs your call`.
   4. Resolve, only after asserting the thread's root author is `$ME` right before the call:
      ```bash
      gh api graphql -F id=<threadId> -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{id isResolved}}}'
      ```
      Confirm `isResolved == true` in the response; otherwise count it as an error in the report. Post no "fixed" reply, no 👍.
   5. Remove resolved threads from the PR's stored `findings`. Threads left open that were blocking findings keep blocking approval.
   With `--dry-run`: print the would-resolve threads (id, path, one-line reason) and the left-open ones, resolve nothing.
4. **For each remaining PR, sequentially**:
   1. Re-fetch (`gh pr view N -R … --json headRefOid,isDraft,state`). Abort this PR if `isDraft` or `state != "OPEN"`. Pin the head SHA as `COMMIT`.
   2. Read context: `gh pr view N --json title,body,files`, `gh pr diff N`. Also read all existing feedback, for dedup in step 4.5: inline comments `gh api --paginate repos/gdncomm/BlibliIOSApp/pulls/N/comments` (keep `id`, `user.login`, `path`, `line`, `body`, `in_reply_to_id`), reviews `.../pulls/N/reviews`, and conversation comments `.../issues/N/comments`. Read the Jira key from the title (`IOS-xxxxx`) and use the PR body as the spec. For files whose diff is not self-explanatory, read the full file at `COMMIT` via `gh api repos/gdncomm/BlibliIOSApp/contents/<path>?ref=<COMMIT>` (no checkout, no worktree).
   3. **Review engine, in this priority order**:
      1. A review skill from the `mobileapps-ios` team plugin, if installed (look for a skill named `*review*` in `~/.claude/plugins/marketplaces/agent-plugins/plugins/mobileapps/ios/skills` and `foundation/skills`). As of 2026-11-02 none exists.
      2. `code-review` (mattpocock/skills, installed at `~/.claude/skills/code-review`). It expects a local checkout and a fixed point, so use it only if the PR branch is already checked out locally; otherwise skip to 3.
      3. Built-in pass (current default): use the `ecc:swift-reviewer` agent (Swift concurrency, ARC, retain cycles, force-unwrap) over the diff, plus `ecc:security-reviewer` when the diff touches networking, webviews, deeplinks/URLs, keychain/storage, auth, payment, or logging. Give agents the diff, the PR body, and the severity table above; require output as `path | line | severity | comment`.
      Whatever engine ran, map its output onto the severity table above and drop anything that does not fit.
   4. **Verify**: for each critical/major/security/risky finding, re-read the cited code and confirm it is real and the line is in the diff. Downgrade to nit or drop if not.
   4a. **Follow-up check** (mode **incremental** only): for each stored blocking finding, re-read the cited code at `COMMIT`. Problem gone → mark fixed, drop from `findings`. Still there → keep, and it still blocks approval. Resolving the thread is done in step 3b, not here; do not reply "fixed". Open own threads that step 3b left open also keep blocking, even when the PR has no stored `findings`. Use the result in the step 6 event: no remaining blocking finding and no new blocking finding → `APPROVE`, even though the earlier review at the old SHA was `COMMENT`.
   5. **Dedup against existing comments** (every finding, blocking and nit, vs. comments by anyone, including bots; skip threads whose root is by `$ME` unless it is a different SHA's leftover). Match on same file (or same code, even if the line moved) and same underlying problem, not same wording. Classify each finding:
      - **Same**: existing comment already states the identical problem (and fix is equivalent or absent). Do not post a new comment. Add a 👍 to the existing comment, only if `$ME` has not already reacted (`gh api repos/gdncomm/BlibliIOSApp/pulls/comments/<id>/reactions` — check for `+1` by `$ME`):
        `gh api -X POST repos/gdncomm/BlibliIOSApp/pulls/comments/<id>/reactions -f content='+1'`. For an issue (conversation) comment use `issues/comments/<id>/reactions`.
      - **Partial**: same problem, but you have something real to add (concrete fix, missed impact, root cause, extra call site, correction). Do not post a new top-level comment. Reply in that thread with only the added value, no repeat of what is already said:
        `gh api -X POST repos/gdncomm/BlibliIOSApp/pulls/N/comments/<id>/replies -f body='<text>'`. Reply to the thread root id. Add no 👍 unless it fully agrees.
      - **New**: no match. Goes into the review in step 6.
      When unsure whether it is the same, treat it as **New**, never as **Same** (a wrong 👍 hides a real finding). A **Same**/**Partial** finding still counts toward blocking/nit status for the approve decision in step 6.
   6. **Post** one review via the API (atomic, all inline) containing only the **New** findings:
      ```bash
      gh api -X POST repos/gdncomm/BlibliIOSApp/pulls/N/reviews --input review.json
      ```
      `review.json`: `{"commit_id": COMMIT, "event": "COMMENT"|"APPROVE", "comments": [{"path","line","side":"RIGHT","body"}]}`. Use `start_line`/`start_side` for multi-line. Blocking body format: `**<severity>**: <problem>. <fix>.` Nit body: `nit: <text>`. If the API rejects a line (422), retry that comment as a file-level comment (`"subject_type":"file"`, no `line`); if still rejected, drop it and note it in the final report.
      Event: any blocking finding (New, Same or Partial) → `COMMENT`; otherwise `APPROVE`. If there is a blocking finding but no **New** comments, skip the review call (reactions/replies already posted); do not post an empty `COMMENT` review. An `APPROVE` with zero comments is fine.
      With `--dry-run`: print the would-be `review.json`, plus the 👍 reactions and replies you would post (comment id + text), per PR; post nothing, write no state.
   7. Write the state entry (`result: approved` if approved, else `commented`), with the fresh `cmt` (re-fetch after posting, so your own comments do not count as new next run) and the current `findings`.
5. **Report** (terminal, short): table of `PR | author | result (approved/commented/skipped:reason) | #blocking | #nits | #👍 | #replies | #resolved | link to review`. List any dropped comments, any API errors, and the threads left open as `needs your call` (disputed or unsure), each with a link.

## Guardrails

- Never review a draft or non-`OPEN` PR. Re-check `isDraft`/`state` right before posting (step 4.1) and abort that PR if it changed.
- Never merge, never push, never edit PR branches, never dismiss existing reviews. Resolve only threads whose root comment is mine (`$ME`), only via step 3b and only when the fix is verified in code; never resolve another person's thread, a thread I only replied in, or one with an unanswered dispute. Never un-resolve anything. Replying to a thread is allowed only for a **Partial** dedup match (step 4.5); never reply just to agree or to argue.
- Never post a second review for the same SHA. 👍 reactions and **Partial** replies on existing threads are not reviews and do not count.
- Never 👍 your own comments, and never 👍 a comment you are unsure matches.
- Never approve if any blocking finding exists, or if verification (step 4.4) could not run.
- Post as the logged-in `gh` user only. If `gh auth status` fails, stop and say so.
- Comments are written for teammates: normal English, specific, with a concrete fix.
