#!/usr/bin/env python3
"""Read-only health table for the BlibliIOSApp worktree slots. Never writes, frees, or deletes."""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SLOTS = os.environ.get("TICKET_SLOTS", "abcd")
APP = "BlibliMobile-iOS"
STALE_HOURS = 24
COLS = ["Slot", "Status", "Ticket", "Branch", "Last used", "Last built",
        "DerivedData", "Packages", "Git", "Simulator"]


def ticket_from_branch(branch):
    m = re.fullmatch(r"[A-Z]+-\d+", branch.rsplit("/", 1)[-1])
    return m.group(0) if m else None


def classify(has_lock, claim, now, stale_hours=STALE_HOURS):
    if claim:
        return "STALE" if now - claim["since"] > stale_hours * 3600 else "busy"
    return "claiming" if has_lock else "free"


def ago(ts, now):
    if ts is None:
        return "never"
    s = max(0, now - ts)
    return f"{int(s // 86400)}d" if s >= 86400 else f"{int(s // 3600)}h" if s >= 3600 else f"{int(s // 60)}m"


def sh(*cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def read_claim(st, s):
    try:
        return json.loads((st / f"{s}.json").read_text())
    except (OSError, ValueError):
        return None


def branch_of(wt):
    b = sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=wt)
    return "(detached)" if b in (None, "HEAD") else b


def last_used(wt, claim):
    times = [claim["since"]] if claim else []
    ct = sh("git", "log", "-1", "--format=%ct", cwd=wt)
    if ct:
        times.append(float(ct))
    gd = sh("git", "rev-parse", "--absolute-git-dir", cwd=wt)
    if gd and (Path(gd) / "logs/HEAD").exists():
        times.append((Path(gd) / "logs/HEAD").stat().st_mtime)
    return max(times) if times else None


def last_built(dd):
    logs = list(dd.glob("*/Logs/Build/*.xcactivitylog"))
    return max(p.stat().st_mtime for p in logs) if logs else None


def dd_size(dd):
    if not dd.exists():
        return "missing"
    kb = sh("du", "-sk", str(dd))
    if not kb:
        return "?"
    mb = int(kb.split()[0]) / 1024
    return f"{mb / 1024:.1f}G" if mb >= 1024 else f"{mb:.0f}M"


def packages(wt, st, s):
    proj = wt / APP
    if not (proj / "SwiftPackages").exists():
        return "missing"
    parts = [proj / "SwiftPackageList.txt", proj / "Podfile.lock",
             proj / f"{APP}.xcworkspace/xcshareddata/swiftpm/Package.resolved"]
    h = hashlib.sha256(b"".join(p.read_bytes() for p in parts if p.exists())).hexdigest()
    mark = st / f"{s}.pkg"
    return "ok" if mark.exists() and mark.read_text() == h else "stale"


def git_state(wt):
    dirty = [l for l in (sh("git", "status", "--porcelain", cwd=wt) or "").splitlines()
             if ".jira-context/" not in l]
    ab = sh("git", "rev-list", "--left-right", "--count", "@{u}...HEAD", cwd=wt)
    sync = "+{1}/-{0}".format(*ab.split()) if ab else "no upstream"
    return f"dirty={len(dirty)} {sync}"


def simulators():
    out = sh("xcrun", "simctl", "list", "devices", "-j")
    try:
        groups = json.loads(out)["devices"].values()
    except (TypeError, ValueError, KeyError):
        return {}
    return {d["name"]: d for g in groups for d in g if d.get("isAvailable")}


def row(pool, st, s, sims, now):
    wt = pool / f"slot-{s}"
    claim = read_claim(st, s)
    status = classify((st / f"{s}.lock").exists(), claim, now)
    sim = sims.get(f"slot-{s}")
    sim_txt = f"{sim['udid'][:8]} {sim['state']}" if sim else "none"
    if not wt.exists():
        return [f"slot-{s}", status, "-", "no worktree", "-", "-", "-", "-", "-", sim_txt]
    branch = branch_of(wt)
    key = claim["key"] if claim else None
    if not key:
        t = ticket_from_branch(branch)
        key = f"{t} (released)" if t else "-"
    dd = wt / APP / "DerivedData"
    return [f"slot-{s}", status, key, branch, ago(last_used(wt, claim), now),
            ago(last_built(dd), now), dd_size(dd), packages(wt, st, s), git_state(wt), sim_txt]


def progress(msg):
    """Status line on stderr, overwritten in place; silent when not a terminal."""
    if sys.stderr.isatty():
        sys.stderr.write(f"\r\033[K{msg}")
        sys.stderr.flush()


def main():
    common = sh("git", "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        print("error: run inside a BlibliIOSApp checkout")
        return 1
    pool = Path(common).parent.parent / "worktrees"
    st, now = pool / ".slots", time.time()
    progress("Listing simulators...")
    sims = simulators()
    rows = [COLS]
    for i, s in enumerate(SLOTS, 1):
        progress(f"Checking slot-{s} ({i}/{len(SLOTS)}): git, DerivedData size, packages...")
        rows.append(row(pool, st, s, sims, now))
    progress("")
    cols = list(zip(*rows))
    widths = [max(len(c) for c in col) for col in zip(*cols)]
    for r in cols:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
    for r in rows[1:]:
        if r[1] == "STALE":
            print(f"{r[0]} STALE: ticket {r[2]}. If abandoned: python3 ~/.claude/hooks/ticket-slots.py release {r[0][-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
