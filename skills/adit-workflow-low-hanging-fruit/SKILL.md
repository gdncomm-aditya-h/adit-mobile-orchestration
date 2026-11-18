---
name: adit-workflow-low-hanging-fruit
description: List every open IOS Jira ticket assigned to the current user, ranked from easiest to hardest, so the next ticket is easy to pick. Read-only. Use when the user runs /adit-workflow-low-hanging-fruit or asks for low hanging fruit, easiest tickets, what to pick next, or to rank my open tickets.
---

# Low hanging fruit

Rank the user's open IOS tickets from easiest to hardest. Read-only: never transition, comment on, edit or implement a ticket.

Board: https://gdncomm.atlassian.net/jira/software/c/projects/IOS/boards/369

## 1. Fetch

Call `searchJiraIssuesUsingJql` (Atlassian MCP; load it with ToolSearch if it is deferred):

- `cloudId`: `gdncomm.atlassian.net`
- `jql`: `project = IOS AND assignee = currentUser() AND status = Open ORDER BY updated DESC`
- `fields`: `["summary","description","status","issuetype","priority","labels","issuelinks","subtasks"]`
- `view`: `evidence`. The default compact view drops `description`. With an explicit `fields` list, evidence returns only those fields.
- `maxResults`: 100. Page with `nextPageToken` until `isLast` is true.

"Open" means status exactly `Open` (not started). Tickets already in Code Review, DEV TESTING, In Development or In Progress are excluded.

If the result is saved to a file because it is too large, parse it with `python3 -I` and read only the fields above. Always pass the explicit `fields` list; without it, evidence adds large custom-field data.

## 2. Rank

Order by effort still remaining, easiest first.

- Judge scope from the summary and description:
  - Easier: copy or config change, one screen, a clear DoD, a bug with a known cause, tests only, tracker events with a given spec.
  - Harder: no DoD or an unclear one, design or copy not ready, backend or API dependency, many screens or modules, a bug with no repro or no known cause, a refactor with wide impact.
- A ticket with a missing DoD or a blocking dependency ranks harder, and the reason says so.
- Do not open each ticket's code to estimate. Use the ticket text only. If the description is empty or too thin to judge, rank it by title, mark effort `Unknown`, and say so in the reason.

Effort labels. Print the full label, never the bare letter:
- `Small (hours)`: a few hours of work.
- `Medium (~1 day)`: about a day.
- `Large (days or blocked)`: several days, or waiting on another team or on design.
- `Unknown`: the description is too thin to judge.

## 3. Output

One table, easiest first:

| # | Key | Type | Summary | Effort | Why |
|---|-----|------|---------|--------|-----|

Every row has status `Open`, so there is no Status column.

Rules:
- Link each key as `https://gdncomm.atlassian.net/browse/<KEY>`.
- `Why` is one short line: the main reason for its position.
- End with one line naming the suggested first pick. Do not start work on it.
- If the query returns no tickets, say so in one line.
