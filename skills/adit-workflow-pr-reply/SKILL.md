---
name: adit-workflow-pr-reply
description: Reply to and update a GitHub PR from its review comments. Give it a PR URL. It triages every unresolved review thread, replies to nits and resolves them, fixes real issues following codebase patterns, builds, pushes, replies with the change, resolves fixed threads, posts pushback on wrong or unclear comments (left open), and lists what still needs you. Use for "reply my PR comments", "address PR review", /adit-workflow-pr-reply.
argument-hint: <PR URL>
---

# adit-workflow-pr-reply

Input: one PR URL (`https://github.com/<owner>/<repo>/pull/<n>`). Helper: `~/.claude/skills/adit-workflow-pr-reply/pr-threads.sh` (`threads <url>`, `reply <thread-id> <text>`, `resolve <thread-id>`). Set `DRY_RUN=1` to rehearse without posting.

Track the steps below with the task list.

## 1. Preconditions

- `gh auth status` must pass.
- Work only in the one dedicated worktree, never in the user's main checkout, and never create a second worktree. Reuse keeps disk use low and keeps build caches warm (the path must stay the same).
  1. Find the main repo: the cwd's `git rev-parse --git-common-dir` parent. Its `origin` URL must match the PR's `<owner>/<repo>`, else stop and ask.
  2. Worktree path: `<main repo parent>/worktrees/pr-reply`. If it does not exist, create it once: `git worktree add --detach <path> origin/<headRefName>`. Never remove it.
  3. In the worktree: `git status --porcelain` must be empty, else stop and ask (never stash or discard). Then `git fetch origin <headRefName>` and `git checkout -B <headRefName> origin/<headRefName>`. Switching branches is allowed here because this worktree is only for this skill. If git refuses because the branch is checked out in another worktree, stop and ask.
  4. Run every later step (fix, build, commit, push) inside this worktree. After the run, leave the worktree in place on the PR branch.
- The user runs one PR fix at a time. If the worktree has uncommitted changes, treat that as another run in progress and stop.

## 2. Fetch

Run `pr-threads.sh threads <url>`. Skip threads with `resolved: true`. Keep outdated-but-unresolved threads. Read each thread's full `comments` array before deciding anything, because earlier replies may already change the answer.

## 3. Triage

Invoke `superpowers:receiving-code-review`. Verify every comment against the actual code before acting. No performative agreement.

Classify each thread:

- **nit**: the comment labels itself nit, nitpick, optional or minor, or it is purely cosmetic (naming taste, spacing, typo in a comment). If unsure, it is not a nit.
- **fix**: a valid point about behavior, correctness, safety, tests, or a deviation from codebase pattern.
- **pushback**: the comment is wrong, unclear, or conflicts with the codebase pattern or a better practice. Collect the evidence (file and line of the existing pattern, or the reason).

## 4. Fix (only for `fix` threads)

1. Find the existing pattern in the codebase first (grep similar code, same module). The codebase pattern is the top priority.
2. Then apply best practice, following `ponytail:ponytail`: the smallest change that fully solves it, including callers and tests it touches.
3. Use the repo's own codegen or style skills when they exist (for Swift in the Blibli iOS repo: `mobileapps-ios:swift-codegen`).
4. Nits get no code change. Pushbacks get no code change.

## 5. Build

Skip steps 5 and 6 when nothing was changed.

Build with the repo's own method and run the tests the change touches. For iOS simulator builds use normal signing and never pass `CODE_SIGNING_ALLOWED=NO`. If it is red, fix and retry, at most 2 rounds. Still red: stop. Do not push, do not reply. Report the shortest decisive error line.

## 6. Commit and push

- One commit. Follow the repo's message convention; include the Jira key from the branch name or PR title when present. End the message with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Plain `git push`. Never force push. A rejected push, or a hook denial that running the missing step does not fix, means stop and report.

## 7. Reply and resolve

Only after the push succeeded (or when nothing needed pushing). Write every reply in caveman style (`caveman:caveman`): one to three sentences, name the file and what changed.

| Thread | Reply | Resolve |
|---|---|---|
| nit | one line: noted, no change, or why | yes |
| fix | what changed and where, one to three sentences | yes |
| pushback | polite reason, with the pattern file or best-practice cite; or a clarifying question | **no, leave open** |

Post with `pr-threads.sh reply <thread-id> <text>`, then `pr-threads.sh resolve <thread-id>` where the table says yes. Never resolve a thread whose reply failed. Replies to bots are one line.

## 8. Report

Report in this order:

1. Counts: nits resolved, fixes pushed and resolved, pushbacks posted.
2. The text of every pushback posted.
3. **Still open or untouched**: every unresolved thread you did not resolve, each with its URL (`url` field) and one line on why (pushback awaiting reviewer, reply failed, skipped).
4. Build, push and commit hash, or why they were skipped.

Never merge, never mark the PR ready, never request re-review.
