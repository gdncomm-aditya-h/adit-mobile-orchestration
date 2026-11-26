#!/usr/bin/env python3
"""Ticket slot pool: a fixed set of long-lived worktrees (slot-a through slot-d), each with its own
in-tree DerivedData, Swift packages and simulator, so a new ticket gets an incremental build, not a cold one.

  ticket-slots.py acquire <KEY> --type <type> --base <branch> [--branch <name>]   (run in any checkout of the repo)
  ticket-slots.py release <KEY|slot-letter>
  ticket-slots.py packages <KEY>   re-check the Swift packages of the ticket's slot (download only when they changed)
  ticket-slots.py status

acquire prints one JSON object on stdout: slot, worktree, branch, simulator (name, udid), packages, reused.
Exit codes: 0 ok, 3 every slot busy (table on stderr), 4 setup failed (reason on stderr; the slot is released).
Pool: <main checkout>/../worktrees/slot-<x>. State: <pool>/.slots/<x>.{lock,json}. Never runs git clean/reset/stash.

shortcut: a lock is only freed by `release` (the ticket flow runs it when the draft PR exists); a crashed
session keeps its slot until `release <KEY>` or `release <letter>`. `status` shows each slot's age.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SLOTS = os.environ.get("TICKET_SLOTS", "abcd")  # pool size = number of letters
RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-26-5"
DEVICE = "com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro"
APP = "BlibliMobile-iOS"
SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>BuildLocationStyle</key>
	<string>UseAppPreferences</string>
	<key>CustomBuildLocationType</key>
	<string>RelativeToDerivedData</string>
	<key>DerivedDataLocationStyle</key>
	<string>WorkspaceRelativePath</string>
	<key>DerivedDataCustomLocation</key>
	<string>DerivedData</string>
</dict>
</plist>
"""


class Fail(Exception):
    pass


def run(*cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise Fail(f"{' '.join(cmd)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def pool_dirs():
    common = run("git", "rev-parse", "--path-format=absolute", "--git-common-dir")
    pool = Path(common).parent.parent / "worktrees"
    return Path(common).parent, pool, pool / ".slots"


def info(st, slot):
    try:
        return json.loads((st / f"{slot}.json").read_text())
    except (OSError, ValueError):
        return None


def holder(st, key):
    return next((s for s in SLOTS if (i := info(st, s)) and i["key"] == key), None)


def status_text(st):
    rows = []
    for s in SLOTS:
        i = info(st, s)
        if i:
            rows.append(f"slot-{s}: {i['key']} ({int((time.time() - i['since']) / 60)} min)")
        else:
            rows.append(f"slot-{s}: free" if not (st / f"{s}.lock").exists() else f"slot-{s}: claiming")
    busy = sum(1 for s in SLOTS if (st / f"{s}.lock").exists())
    return f"{busy}/{len(SLOTS)} slots busy\n" + "\n".join(rows)


def free(st, slot):
    (st / f"{slot}.json").unlink(missing_ok=True)
    try:
        (st / f"{slot}.lock").rmdir()
    except OSError:
        pass


def simulator(slot):
    name = f"slot-{slot}"
    devs = json.loads(run("xcrun", "simctl", "list", "devices", "-j"))["devices"]
    for group in devs.values():
        for d in group:
            if d["name"] == name and d.get("isAvailable"):
                return {"name": name, "udid": d["udid"]}
    return {"name": name, "udid": run("xcrun", "simctl", "create", name, DEVICE, RUNTIME)}


def packages(wt, st, slot):
    proj = wt / APP
    if not (proj / "SwiftPackages.sh").exists():
        return "no SwiftPackages.sh"
    parts = [proj / "SwiftPackageList.txt", proj / "Podfile.lock",
             proj / f"{APP}.xcworkspace/xcshareddata/swiftpm/Package.resolved"]
    h = hashlib.sha256(b"".join(p.read_bytes() for p in parts if p.exists())).hexdigest()
    mark = st / f"{slot}.pkg"
    if mark.exists() and mark.read_text() == h and (proj / "SwiftPackages").exists():
        return "unchanged"
    for _ in range(2):  # one automatic retry: a flaky download should not need a human
        r = subprocess.run(["sh", "SwiftPackages.sh", "download"], cwd=proj, capture_output=True, text=True)
        if not r.returncode:
            break
    if r.returncode:
        return "failed: " + " ".join(r.stdout.splitlines()[-3:] + r.stderr.splitlines()[-3:])
    mark.write_text(h)
    return "downloaded"


def setup(root, wt, st, slot, args):
    run("git", "fetch", "origin", cwd=root)
    if not wt.exists():
        run("git", "worktree", "add", "--detach", str(wt), f"origin/{args.base}", cwd=root)
    dirty = [l for l in run("git", "status", "--porcelain", cwd=wt).splitlines() if ".jira-context/" not in l]
    if dirty:
        raise Fail(f"slot-{slot} has uncommitted changes, left untouched:\n" + "\n".join(dirty))
    exclude = Path(run("git", "rev-parse", "--path-format=absolute", "--git-path", "info/exclude", cwd=wt))
    if ".jira-context/" not in exclude.read_text():
        exclude.write_text(exclude.read_text().rstrip("\n") + "\n.jira-context/\n")
    branch = args.branch or f"adit/{args.type}/{args.key}"
    reused = bool(run("git", "branch", "--list", branch, cwd=root))
    if reused:
        run("git", "switch", branch, cwd=wt)
    elif run("git", "branch", "-r", "--list", f"origin/{branch}", cwd=root):
        reused = True
        run("git", "switch", "--track", "-c", branch, f"origin/{branch}", cwd=wt)
    else:
        run("git", "switch", "--no-track", "-c", branch, f"origin/{args.base}", cwd=wt)
    d = wt / APP / f"{APP}.xcworkspace/xcuserdata/{os.environ.get('USER', 'user')}.xcuserdatad"
    if not (d / "WorkspaceSettings.xcsettings").exists():
        d.mkdir(parents=True, exist_ok=True)
        (d / "WorkspaceSettings.xcsettings").write_text(SETTINGS)
    sim = None if os.environ.get("TICKET_SLOTS_NO_SIM") else simulator(slot)
    return {"slot": slot, "worktree": str(wt), "branch": branch, "reused": reused,
            "packages": packages(wt, st, slot), "simulator": sim}


def acquire(args):
    root, pool, st = pool_dirs()
    st.mkdir(parents=True, exist_ok=True)
    errors, mine = [], holder(st, args.key)
    for s in ([mine] if mine else SLOTS):
        if not mine:
            try:
                (st / f"{s}.lock").mkdir()  # mkdir is atomic: two sessions cannot claim the same slot
            except FileExistsError:
                continue
            (st / f"{s}.json").write_text(json.dumps({"key": args.key, "since": time.time()}))
        try:
            print(json.dumps(setup(root, pool / f"slot-{s}", st, s, args), indent=2))
            return
        except Fail as e:  # e.g. dirty slot: free it and try the next one
            if not mine:
                free(st, s)
            errors.append(str(e))
    if errors:
        print("acquire failed:\n" + "\n".join(errors), file=sys.stderr)
        sys.exit(4)
    print(status_text(st), file=sys.stderr)
    sys.exit(3)


def release(args):
    root, pool, st = pool_dirs()
    slot = args.target if args.target in SLOTS else holder(st, args.target)
    if not slot:
        print(f"{args.target}: no slot held")
        return
    wt = pool / f"slot-{slot}"
    ctx = wt / ".jira-context"
    if ctx.is_dir():
        arch = pool / ".jira-archive"
        arch.mkdir(exist_ok=True)
        for f in ctx.glob("*.md"):
            shutil.move(f, arch / f"{f.stem}-{datetime.date.today()}.md")
    if wt.exists() and not run("git", "status", "--porcelain", cwd=wt):
        run("git", "switch", "--detach", cwd=wt, check=False)  # frees the branch for a later re-acquire
    free(st, slot)
    print(f"released slot-{slot}")


def recheck_packages(args):
    """Prints unchanged, downloaded or failed: ... for the slot that holds the ticket. Exit 4 on failure.
    Used after a sync with the base branch and before the first build."""
    _, pool, st = pool_dirs()
    slot = holder(st, args.key)
    if not slot:
        raise Fail(f"no slot holds {args.key}")
    result = packages(pool / f"slot-{slot}", st, slot)
    print(result)
    if result.startswith("failed"):
        sys.exit(4)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("acquire")
    a.add_argument("key")
    a.add_argument("--type", required=True)
    a.add_argument("--base", required=True)
    a.add_argument("--branch")
    r = sub.add_parser("release")
    r.add_argument("target")
    k = sub.add_parser("packages")
    k.add_argument("key")
    sub.add_parser("status")
    args = p.parse_args()
    try:
        if args.cmd == "acquire":
            acquire(args)
        elif args.cmd == "release":
            release(args)
        elif args.cmd == "packages":
            recheck_packages(args)
        else:
            print(status_text(pool_dirs()[2]))
    except Fail as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
