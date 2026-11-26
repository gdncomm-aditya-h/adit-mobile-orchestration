#!/usr/bin/env python3
"""Ticket worktrees for the iOS repos, one pool per repo.

  ticket_slots.py acquire <KEY> --type <type> --base <branch> --prefix <branch prefix> [--branch <name>]
  ticket_slots.py release <KEY|slot-letter>
  ticket_slots.py packages <KEY>  re-check the Swift packages of the ticket's slot (download only when they changed)
  ticket_slots.py status
  ticket_slots.py pool-dir        print this repo's worktree pool folder

Run in any checkout of the repo. The repo is read from `origin`, its profile from the files (repo_profile.py).

app repo      A pool of long-lived worktrees slot-a, slot-b, ... each with its own in-tree DerivedData, Swift
              packages and simulator, so a new ticket gets an incremental build. Pool size comes from
              flowconfig.py (default 4 for BlibliIOSApp, 1 for other app repos).
package repo  No pool. One plain worktree per ticket: <pool>/<KEY>. `release` removes it when it is clean.

acquire prints one JSON object on stdout: kind, worktree, branch, reused and, for app repos, slot, simulator, packages.
Exit codes: 0 ok, 3 every slot busy (table on stderr), 4 setup failed (reason on stderr; the slot is released).

Pool folder: <main checkout parent>/worktrees/<repo>/. BlibliIOSApp keeps using the older <parent>/worktrees/ when a
slot already lives there, so existing warm builds are not lost. State: <pool>/.slots/. Never runs git clean/reset/stash.

shortcut: a lock is only freed by `release`; a crashed session keeps its slot until `release <KEY>` or
`release <letter>`. `status` shows each slot's age.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flowconfig  # noqa: E402
import repo_profile  # noqa: E402

LETTERS = "abcdefgh"
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


def repo_slug(root):
    """owner/repo from origin; falls back to the folder name when there is no GitHub origin."""
    url = run("git", "config", "--get", "remote.origin.url", cwd=root, check=False)  # raw: ignores insteadOf rewrites
    tail = url.replace(":", "/")
    if tail.endswith(".git"):
        tail = tail[:-4]
    parts = [p for p in tail.split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else Path(root).name


def pool_dirs(repo_name, root=None):
    """(main checkout, pool folder, state folder) for this repo."""
    common = run("git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=root)
    main = Path(common).parent
    legacy = main.parent / "worktrees"
    name = repo_name.split("/")[-1]
    pool = legacy if (name == "BlibliIOSApp" and (legacy / ".slots").is_dir()) else legacy / name
    return main, pool, pool / ".slots"


def slot_letters(count):
    return LETTERS[:count]


def info(st, slot):
    try:
        return json.loads((st / f"{slot}.json").read_text())
    except (OSError, ValueError):
        return None


def holder(st, key, letters):
    return next((s for s in letters if (i := info(st, s)) and i["key"] == key), None)


def status_text(st, letters):
    rows = []
    for s in letters:
        i = info(st, s)
        if i:
            rows.append(f"slot-{s}: {i['key']} ({int((time.time() - i['since']) / 60)} min)")
        else:
            rows.append(f"slot-{s}: free" if not (st / f"{s}.lock").exists() else f"slot-{s}: claiming")
    busy = sum(1 for s in letters if (st / f"{s}.lock").exists())
    return f"{busy}/{len(letters)} slots busy\n" + "\n".join(rows)


def free(st, slot):
    (st / f"{slot}.json").unlink(missing_ok=True)
    try:
        (st / f"{slot}.lock").rmdir()
    except OSError:
        pass


def pick_runtime_and_device(runtimes, devicetypes):
    """Newest available iOS runtime; iPhone 17 Pro if installed, else the newest iPhone device type."""
    ios = [r for r in runtimes if r.get("isAvailable") and r.get("platform", "iOS") == "iOS"
           and "SimRuntime.iOS" in r.get("identifier", "")]
    if not ios:
        raise Fail("no available iOS simulator runtime (install one in Xcode > Settings > Components)")
    ios.sort(key=lambda r: [int(x) for x in r.get("version", "0").split(".") if x.isdigit()])
    iphones = [d for d in devicetypes if d.get("productFamily") == "iPhone"]
    if not iphones:
        raise Fail("no iPhone simulator device type")
    chosen = next((d for d in iphones if d["name"] == "iPhone 17 Pro"), iphones[-1])
    return ios[-1]["identifier"], chosen["identifier"]


def simulator(slot):
    name = f"slot-{slot}"
    devs = json.loads(run("xcrun", "simctl", "list", "devices", "-j"))["devices"]
    for group in devs.values():
        for d in group:
            if d["name"] == name and d.get("isAvailable"):
                return {"name": name, "udid": d["udid"]}
    runtimes = json.loads(run("xcrun", "simctl", "list", "runtimes", "-j"))["runtimes"]
    types = json.loads(run("xcrun", "simctl", "list", "devicetypes", "-j"))["devicetypes"]
    runtime, device = pick_runtime_and_device(runtimes, types)
    return {"name": name, "udid": run("xcrun", "simctl", "create", name, device, runtime)}


def packages(wt, st, slot, profile):
    script = profile.get("packagesScript")
    app_dir = profile.get("appDir")
    if not script or not app_dir:
        return "not needed"
    proj = wt / app_dir
    if not (proj / script).exists():
        return f"no {script}"
    ws = profile.get("workspace") or ""
    parts = [proj / "SwiftPackageList.txt", proj / "Podfile.lock", proj / f"{ws}/xcshareddata/swiftpm/Package.resolved"]
    h = hashlib.sha256(b"".join(p.read_bytes() for p in parts if p.exists())).hexdigest()
    mark = st / f"{slot}.pkg"
    if mark.exists() and mark.read_text() == h and (proj / "SwiftPackages").exists():
        return "unchanged"
    for _ in range(2):  # one automatic retry: a flaky download should not need a human
        r = subprocess.run(["sh", script, "download"], cwd=proj, capture_output=True, text=True)
        if not r.returncode:
            break
    if r.returncode:
        return "failed: " + " ".join(r.stdout.splitlines()[-3:] + r.stderr.splitlines()[-3:])
    mark.write_text(h)
    return "downloaded"


def switch_branch(root, wt, branch, base):
    """Check the ticket branch out in wt: reuse a local or remote one as is (never reset), else cut from base.
    A throwaway inject/* branch is always cut afresh from base, so a second test never builds on stale develop."""
    if run("git", "branch", "--show-current", cwd=wt) == branch:
        return True  # resuming: the worktree is already on the ticket branch
    if branch.startswith("inject/"):
        run("git", "switch", "--no-track", "-C", branch, f"origin/{base}", cwd=wt)
        return False
    reused = bool(run("git", "branch", "--list", branch, cwd=root))
    if reused:
        run("git", "switch", branch, cwd=wt)
    elif run("git", "branch", "-r", "--list", f"origin/{branch}", cwd=root):
        reused = True
        run("git", "switch", "--track", "-c", branch, f"origin/{branch}", cwd=wt)
    else:
        run("git", "switch", "--no-track", "-c", branch, f"origin/{base}", cwd=wt)
    return reused


def check_clean(wt, label, branch):
    """Refuse a dirty worktree, unless it already sits on the ticket branch (a resumed ticket keeps its edits)."""
    if run("git", "branch", "--show-current", cwd=wt) == branch:
        return
    dirty = [l for l in run("git", "status", "--porcelain", cwd=wt).splitlines() if ".jira-context/" not in l]
    if dirty:
        raise Fail(f"{label} has uncommitted changes, left untouched:\n" + "\n".join(dirty))


def setup_app(root, wt, st, slot, args, profile):
    run("git", "fetch", "origin", cwd=root)
    if not wt.exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        run("git", "worktree", "add", "--detach", str(wt), f"origin/{args.base}", cwd=root)
    branch = args.branch or f"{args.prefix}/{args.type}/{args.key}"
    check_clean(wt, f"slot-{slot}", branch)
    exclude = Path(run("git", "rev-parse", "--path-format=absolute", "--git-path", "info/exclude", cwd=wt))
    if ".jira-context/" not in exclude.read_text():
        exclude.write_text(exclude.read_text().rstrip("\n") + "\n.jira-context/\n")
    reused = switch_branch(root, wt, branch, args.base)
    ws, app_dir = profile.get("workspace"), profile.get("appDir")
    if ws and app_dir:
        d = wt / app_dir / f"{ws}/xcuserdata/{os.environ.get('USER', 'user')}.xcuserdatad"
        if not (d / "WorkspaceSettings.xcsettings").exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / "WorkspaceSettings.xcsettings").write_text(SETTINGS)
    sim = None if os.environ.get("TICKET_SLOTS_NO_SIM") else simulator(slot)
    return {"kind": "app", "slot": slot, "worktree": str(wt), "branch": branch, "reused": reused,
            "packages": packages(wt, st, slot, profile), "simulator": sim}


def acquire_package(root, pool, st, args):
    st.mkdir(parents=True, exist_ok=True)
    wt = pool / args.key
    run("git", "fetch", "origin", cwd=root)
    if not wt.exists():
        pool.mkdir(parents=True, exist_ok=True)
        run("git", "worktree", "add", "--detach", str(wt), f"origin/{args.base}", cwd=root)
    branch = args.branch or f"{args.prefix}/{args.type}/{args.key}"
    check_clean(wt, args.key, branch)
    reused = switch_branch(root, wt, branch, args.base)
    (st / f"{args.key}.json").write_text(json.dumps({"key": args.key, "since": time.time(), "kind": "package"}))
    print(json.dumps({"kind": "package", "worktree": str(wt), "branch": branch, "reused": reused,
                      "simulator": None, "packages": "not needed"}, indent=2))


def acquire(args):
    root = Path(run("git", "rev-parse", "--show-toplevel"))
    repo = args.repo or repo_slug(root)
    cfg = flowconfig.load()
    kind = cfg["profile"].get(repo) or repo_profile.detect(root, repo.split("/")[-1])["kind"]
    if kind == "unknown":
        raise Fail(f"{repo}: cannot tell app from package. Ask the engineer, then run: "
                   f"flowconfig.py set profile.{repo} app|package")
    profile = repo_profile.detect(root, repo.split("/")[-1])
    profile["kind"] = kind
    main, pool, st = pool_dirs(repo, root)
    if kind == "package":
        return acquire_package(main, pool, st, args)
    letters = slot_letters(flowconfig.slots_for(cfg, repo, kind))
    st.mkdir(parents=True, exist_ok=True)
    errors, mine = [], holder(st, args.key, letters)
    for s in ([mine] if mine else letters):
        if not mine:
            try:
                (st / f"{s}.lock").mkdir()  # mkdir is atomic: two sessions cannot claim the same slot
            except FileExistsError:
                continue
            (st / f"{s}.json").write_text(json.dumps({"key": args.key, "since": time.time()}))
        try:
            print(json.dumps(setup_app(main, pool / f"slot-{s}", st, s, args, profile), indent=2))
            return
        except Fail as e:  # e.g. dirty slot: free it and try the next one
            if not mine:
                free(st, s)
            errors.append(str(e))
    if errors:
        print("acquire failed:\n" + "\n".join(errors), file=sys.stderr)
        sys.exit(4)
    print(status_text(st, letters), file=sys.stderr)
    sys.exit(3)


def release(args):
    root = Path(run("git", "rev-parse", "--show-toplevel"))
    repo = args.repo or repo_slug(root)
    cfg = flowconfig.load()
    kind = cfg["profile"].get(repo) or repo_profile.detect(root, repo.split("/")[-1])["kind"]
    main, pool, st = pool_dirs(repo, root)
    if kind == "package":
        wt = pool / args.target
        (st / f"{args.target}.json").unlink(missing_ok=True)
        if wt.exists() and not run("git", "status", "--porcelain", cwd=wt):
            run("git", "worktree", "remove", str(wt), cwd=main)
            print(f"removed worktree {args.target}")
        else:
            print(f"{args.target}: worktree kept (missing or has changes)")
        return
    letters = slot_letters(flowconfig.slots_for(cfg, repo, "app"))
    slot = args.target if args.target in letters else holder(st, args.target, letters)
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
    """Re-run the package check for the slot that holds the ticket. Prints unchanged, downloaded or failed: ...
    Exit 4 on failure. Used after a sync with the base branch and before the first build."""
    root = Path(run("git", "rev-parse", "--show-toplevel"))
    repo = args.repo or repo_slug(root)
    cfg = flowconfig.load()
    profile = repo_profile.detect(root, repo.split("/")[-1])
    if (cfg["profile"].get(repo) or profile["kind"]) != "app":
        print("not needed")
        return
    _, pool, st = pool_dirs(repo, root)
    slot = holder(st, args.key, slot_letters(flowconfig.slots_for(cfg, repo, "app")))
    if not slot:
        raise Fail(f"no slot holds {args.key}")
    result = packages(pool / f"slot-{slot}", st, slot, profile)
    print(result)
    if result.startswith("failed"):
        sys.exit(4)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", help="owner/repo, default: read from origin")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("acquire")
    a.add_argument("key")
    a.add_argument("--type", required=True)
    a.add_argument("--base", required=True)
    a.add_argument("--prefix", required=True)
    a.add_argument("--branch")
    r = sub.add_parser("release")
    r.add_argument("target")
    k = sub.add_parser("packages")
    k.add_argument("key")
    sub.add_parser("status")
    sub.add_parser("pool-dir")
    args = p.parse_args()
    try:
        if args.cmd == "acquire":
            acquire(args)
        elif args.cmd == "packages":
            recheck_packages(args)
        elif args.cmd == "release":
            release(args)
        elif args.cmd == "pool-dir":
            root = Path(run("git", "rev-parse", "--show-toplevel"))
            print(pool_dirs(args.repo or repo_slug(root), root)[1])
        else:
            root = Path(run("git", "rev-parse", "--show-toplevel"))
            repo = args.repo or repo_slug(root)
            cfg = flowconfig.load()
            _, _, st = pool_dirs(repo, root)
            print(status_text(st, slot_letters(flowconfig.slots_for(cfg, repo, "app"))))
    except Fail as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
