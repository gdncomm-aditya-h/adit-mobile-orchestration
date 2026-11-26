---
name: ios-orchestration-ticket-status
description: Show the state of in-flight iOS tickets: armed gates with their age, and the worktree slot table for the current app repo (ticket, branch, last built, DerivedData size, packages, git state, simulator). Read-only unless the user asks to clear a gate or release a slot. Use for "check slots", "which slot is free", "what tickets are active", or /ios-orchestration-ticket-status.
argument-hint: [--repo owner/repo]
---

# ticket-status

Scripts are in `<skill_dir>/../../scripts/` (`<skill_dir>` is the base directory shown when this skill loads). Run from inside a checkout of the repo.

1. Gates: `python3 <scripts>/ticket_gate.py list`. Each line is a ticket key, `verified` or `not verified`, and the age. `EXPIRED` means the hook already ignores it.
2. Slots: `python3 <scripts>/slot_health.py [--repo owner/repo]`. Print the table as it is. Columns: Slot, Status, Ticket, Branch, Last used, Last built, DerivedData, Packages, Git, Simulator. A package-only repo has no slots; the script says so.
3. Add one line per finding that needs a decision:
   - `STALE` slot (claimed more than 24 hours ago): the script prints the release command.
   - A gate armed for a ticket with no slot, or older than a day.
   - `Packages: stale` means the package list changed since the last download; the next `acquire` refreshes it.

Never release a slot, clear a gate, delete a worktree or touch DerivedData on your own. Do it only when the user names the ticket or slot: `python3 <scripts>/ticket_slots.py [--repo owner/repo] release <KEY|letter>` and `python3 <scripts>/ticket_gate.py clear <KEY>`. A slot with uncommitted changes is never discarded: tell the user which files are there and let them decide.
