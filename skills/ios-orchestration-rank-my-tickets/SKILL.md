---
name: ios-orchestration-rank-my-tickets
description: List every open Jira ticket assigned to the current user in the iOS project, ranked from easiest to hardest, so the next ticket is easy to pick. Read-only. Use when the user runs /ios-orchestration-rank-my-tickets or asks for low hanging fruit, easiest tickets, what to pick next, or to rank their open tickets.
argument-hint: [project key]
---

# rank-my-tickets

Rank the user's open tickets from easiest to hardest. Read-only: never transition, comment on, edit or implement a ticket.

Project key: the argument, else `jiraProject` from `python3 <skill_dir>/../../scripts/flowconfig.py get jiraProject` (default `IOS`).

## 1. Fetch
Call `searchJiraIssuesUsingJql` (Atlassian MCP; load it with ToolSearch if it is deferred). Get the cloud id once with `getAccessibleAtlassianResources`; if the account has several sites, use the one the project key resolves on and say which.
- `jql`: `project = <KEY> AND assignee = currentUser() AND status = Open ORDER BY updated DESC`
- `fields`: `["summary","description","status","issuetype","priority","labels","issuelinks","subtasks"]`
- `view`: `evidence` (the compact view drops `description`).
- `maxResults`: 100. Page with `nextPageToken` until `isLast` is true.

"Open" means status exactly `Open` (not started). Tickets in Code Review, Dev Testing, In Development or In Progress are excluded. If the result is saved to a file because it is too large, parse it with `python3 -I` and read only those fields.

## 2. Rank
Order by effort still remaining, easiest first. Judge scope from the summary and description only; do not open code.
- Easier: copy or config change, one screen, a clear DoD, a bug with a known cause, tests only, tracker events with a given spec.
- Harder: no DoD or an unclear one, design or copy not ready, backend or API dependency, many screens or modules, a bug with no repro or cause, a refactor with wide impact.
- A missing DoD or blocking dependency ranks harder, and the reason says so.

Effort labels, printed in full:
- `Small (hours)`, `Medium (~1 day)`, `Large (days or blocked)`, `Unknown` (description too thin: rank by title and say so).

## 3. Output
One table, easiest first: `| # | Key | Type | Summary | Effort | Why |`. Link each key to the site's `/browse/<KEY>`. `Why` is one short line. End with one line naming the suggested first pick, and do not start work on it. No tickets: say so in one line.
