---
name: adit-workflow-check-slot-bliblimobileios
description: Read-only health table for the BlibliIOSApp worktree slots (slot-a, slot-b, slot-c). Use when asked to check slots, slot status, which slot is free, slot DerivedData, last built, or which ticket a slot held.
---

# Check BlibliIOSApp slots

Run from any checkout of the BlibliIOSApp repo:

```bash
python3 ~/.claude/skills/adit-workflow-check-slot-bliblimobileios/check_slot.py
```

Show the table as printed. Columns: slot, status (free, busy, claiming, STALE), ticket, branch, last used, last built, DerivedData size, packages (ok, stale, missing), git (dirty files, ahead/behind), simulator.

Rules:
- Read-only. Never free a slot, delete DerivedData, or run `ticket-slots.py release` from this skill.
- STALE means busy for more than 24h. Relay the script's hint line and let the user decide.
- A free slot shows its last ticket as `<KEY> (released)`, read from the worktree's branch name.
- Outside a git repo the script prints one error line and exits 1.
