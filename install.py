#!/usr/bin/env python3
"""Installer for adit-mobile-orchestration. Standard library only, Python 3.8+.

  python3 install.py install   [--target auto|claude|codex|both] [--prefix NAME] [--dry-run] [--skip-deps]
  python3 install.py doctor    [--target ...] [--json]
  python3 install.py uninstall [--target ...] [--dry-run]

Skills are copied once into ~/.agents/skills and symlinked into ~/.claude/skills and ~/.codex/skills.
Everything it changes is recorded in ~/.claude/adit-workflow/install-manifest.json and backed up under
~/.claude/adit-workflow/backups/<timestamp>/. Running install twice is safe.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
NAME = "adit-mobile-orchestration"
BEGIN = "<!-- %s:begin -->" % NAME
END = "<!-- %s:end -->" % NAME
GATE = "ticket-flow-gate.py"
GATE_CMD = 'python3 "$HOME/.claude/hooks/ticket-flow-gate.py"'
GATE_MATCHER = "Bash|mcp__github__create_pull_request|mcp__github__merge_pull_request"
SKILL_DIRS = {"claude": ".claude/skills", "codex": ".codex/skills"}
UATB_TEMPLATE = {"email": "REPLACE_ME", "password": "REPLACE_ME", "otp": "REPLACE_ME"}


def load(name):
    return json.loads((REPO / name).read_text())


class Ctx:
    def __init__(self, home, dry):
        self.home = Path(home)
        self.dry = dry
        self.stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.state = self.home / ".claude/adit-workflow"
        self.warnings = []
        self.failures = []

    def say(self, msg):
        print(("[dry-run] " if self.dry else "") + msg)

    def warn(self, msg):
        self.warnings.append(msg)
        print("warning: " + msg)

    def backup(self, path):
        path = Path(path)
        if self.dry or not (path.exists() or path.is_symlink()):
            return
        dest = self.state / "backups" / self.stamp / path.relative_to(self.home)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dest))


def snapshot(c, path):
    """Copy a file we are about to edit into the backup folder (backup() moves, this copies)."""
    path = Path(path)
    if path.exists():
        dest = c.state / "backups" / c.stamp / path.relative_to(c.home)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)


def pick_targets(c, choice):
    if choice == "both":
        return ["claude", "codex"]
    if choice in ("claude", "codex"):
        return [choice]
    found = [t for t, d in (("claude", ".claude"), ("codex", ".codex")) if (c.home / d).exists()]
    return found or ["claude"]


def default_prefix():
    try:
        out = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
        word = re.sub(r"[^a-z0-9]", "", out.split()[0].lower()) if out else ""
    except Exception:
        word = ""
    return word or re.sub(r"[^a-z0-9]", "", os.environ.get("USER", "me").lower()) or "me"


# ---------- skills ----------

def copy_skill(c, name):
    src, dst = REPO / "skills" / name, c.home / ".agents/skills" / name
    c.say("copy %s -> %s" % (name, dst))
    if c.dry:
        return
    if dst.is_symlink():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))


def link_skill(c, target, name):
    link, dst = c.home / SKILL_DIRS[target] / name, c.home / ".agents/skills" / name
    if link.is_symlink() and os.path.realpath(link) == os.path.realpath(dst):
        return
    c.say("link %s -> %s" % (link, dst))
    if c.dry:
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    else:
        c.backup(link)
    link.symlink_to(dst)


# ---------- hooks and settings ----------

def copy_hooks(c):
    for f in sorted((REPO / "hooks").glob("*.py")):
        dst = c.home / ".claude/hooks" / f.name
        c.say("copy hook %s -> %s" % (f.name, dst))
        if not c.dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            dst.chmod(0o755)


def read_settings(c):
    p = c.home / ".claude/settings.json"
    if not p.exists():
        return p, {}
    try:
        return p, json.loads(p.read_text())
    except ValueError:
        return p, None


def gate_registered(data):
    return any(GATE in h.get("command", "") for e in data.get("hooks", {}).get("PreToolUse", []) for h in e.get("hooks", []))


def register_gate(c):
    p, data = read_settings(c)
    if data is None:
        c.warn("%s is not valid JSON, so the ticket-flow gate was not registered. Fix the file and re-run." % p)
        return
    if gate_registered(data):
        return
    c.say("register ticket-flow gate in %s" % p)
    if c.dry:
        return
    snapshot(c, p)
    data.setdefault("hooks", {}).setdefault("PreToolUse", []).append(
        {"matcher": GATE_MATCHER, "hooks": [{"type": "command", "command": GATE_CMD, "timeout": 30}]})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n")


def unregister_gate(c):
    p, data = read_settings(c)
    if not data or not gate_registered(data):
        return
    c.say("remove ticket-flow gate from %s" % p)
    if c.dry:
        return
    snapshot(c, p)
    pre = data["hooks"]["PreToolUse"]
    for e in pre:
        e["hooks"] = [h for h in e.get("hooks", []) if GATE not in h.get("command", "")]
    data["hooks"]["PreToolUse"] = [e for e in pre if e["hooks"]]
    p.write_text(json.dumps(data, indent=2) + "\n")


# ---------- CLAUDE.md / AGENTS.md block ----------

def upsert_block(c, path, body):
    path = Path(path)
    text = path.read_text() if path.exists() else ""
    block = "%s\n%s\n%s\n" % (BEGIN, body.rstrip("\n"), END)
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        new = head + block + rest.split(END, 1)[1].lstrip("\n")
    else:
        new = text.rstrip("\n") + ("\n\n" if text.strip() else "") + block
    if new == text:
        return
    c.say("write managed block in %s" % path)
    if c.dry:
        return
    snapshot(c, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new)


def remove_block(c, path):
    path = Path(path)
    if not path.exists() or BEGIN not in path.read_text():
        return
    c.say("remove managed block from %s" % path)
    if c.dry:
        return
    text = path.read_text()
    head, rest = text.split(BEGIN, 1)
    tail = rest.split(END, 1)[1].lstrip("\n") if END in rest else ""
    snapshot(c, path)
    path.write_text(head.rstrip("\n") + ("\n\n" + tail if tail else "\n"))


def render_block(name, prefix):
    return (REPO / "claude-md" / name).read_text().replace("{{PREFIX}}", prefix)


# ---------- test-account template ----------

def uatb_path(c):
    return c.state / "uatb-account.json"


def ensure_uatb_template(c):
    p = uatb_path(c)
    if p.exists():
        return
    c.say("create %s (fill it in before running verify-before-pr)" % p)
    if not c.dry:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(UATB_TEMPLATE, indent=2) + "\n")
        p.chmod(0o600)


# ---------- plugins ----------

def claude_state(c):
    base = c.home / ".claude/plugins"
    def read(n):
        try:
            return json.loads((base / n).read_text())
        except Exception:
            return {}
    inst = read("installed_plugins.json")
    inst = inst.get("plugins", inst)
    versions = {k: (v[0].get("version") if isinstance(v, list) and v else None) for k, v in inst.items()}
    return versions, set(read("known_marketplaces.json"))


def market_source(m):
    return m["repo"] if m["source"] == "github" else m["url"]


def run_cli(c, args):
    c.say("run: claude " + " ".join(args))
    if c.dry:
        return True
    try:
        r = subprocess.run(["claude"] + args, capture_output=True, text=True, timeout=600)
    except Exception as e:
        c.warn("claude %s failed: %s" % (" ".join(args), e))
        return False
    if r.returncode != 0:
        c.warn("claude %s failed: %s" % (" ".join(args), (r.stderr or r.stdout).strip().splitlines()[-1:] or ""))
    return r.returncode == 0


def install_deps(c):
    deps = load("deps.json")
    versions, markets = claude_state(c)
    missing_m = [(n, m) for n, m in deps["marketplaces"].items() if n not in markets]
    missing_p = [p for p in deps["plugins"] if "%s@%s" % (p["name"], p["marketplace"]) not in versions]
    if not shutil.which("claude"):
        if missing_m or missing_p:
            print("The claude CLI is not on PATH. Run these inside a Claude Code session instead:")
            for n, m in missing_m:
                print("  /plugin marketplace add %s" % market_source(m))
            for p in missing_p:
                print("  /plugin install %s@%s" % (p["name"], p["marketplace"]))
        return
    for n, m in missing_m:
        if not run_cli(c, ["plugin", "marketplace", "add", market_source(m)]) and m.get("private"):
            c.warn("%s is a private marketplace. You need access to %s." % (n, market_source(m)))
    for p in missing_p:
        run_cli(c, ["plugin", "install", "%s@%s" % (p["name"], p["marketplace"])])


# ---------- commands ----------

def cmd_install(c, a):
    targets = pick_targets(c, a.target)
    prefix = a.prefix or default_prefix()
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", prefix):
        sys.exit("--prefix must be lowercase letters, digits or hyphens")
    print("Installing %s for %s with branch prefix '%s'" % (NAME, " and ".join(targets), prefix))
    names = [s["name"] for s in load("skills.json")["skills"]]
    for n in names:
        copy_skill(c, n)
        for t in targets:
            link_skill(c, t, n)
    copy_hooks(c)
    if "claude" in targets:
        register_gate(c)
        upsert_block(c, c.home / ".claude/CLAUDE.md", render_block("ticket-flow.md", prefix))
        ensure_uatb_template(c)
    if "codex" in targets:
        upsert_block(c, c.home / ".codex/AGENTS.md", render_block("codex.md", prefix))
    if not a.skip_deps:
        install_deps(c)
    if not c.dry:
        c.state.mkdir(parents=True, exist_ok=True)
        (c.state / "install-manifest.json").write_text(json.dumps(
            {"version": (REPO / "VERSION").read_text().strip(), "targets": targets, "prefix": prefix, "skills": names}, indent=2) + "\n")
    print("\nDone. Run `python3 install.py doctor` to verify. Restart Claude Code or Codex so it picks up the new skills.")
    for w in c.warnings:
        print("  - " + w)


def cmd_uninstall(c, a):
    targets = pick_targets(c, a.target)
    for n in [s["name"] for s in load("skills.json")["skills"]]:
        dst = c.home / ".agents/skills" / n
        for t in ("claude", "codex"):
            link = c.home / SKILL_DIRS[t] / n
            if link.is_symlink() and os.path.realpath(link) == os.path.realpath(dst) and t in targets:
                c.say("unlink %s" % link)
                if not c.dry:
                    link.unlink()
        still = [t for t in ("claude", "codex") if (c.home / SKILL_DIRS[t] / n).is_symlink()]
        if dst.exists() and not still:
            c.say("remove %s" % dst)
            if not c.dry:
                shutil.rmtree(dst)
    if "claude" in targets:
        unregister_gate(c)
        remove_block(c, c.home / ".claude/CLAUDE.md")
        for f in (REPO / "hooks").glob("*.py"):
            h = c.home / ".claude/hooks" / f.name
            if h.exists():
                c.say("remove %s" % h)
                if not c.dry:
                    h.unlink()
    if "codex" in targets:
        remove_block(c, c.home / ".codex/AGENTS.md")
    print("Left in place: plugins, %s and your backups under %s." % (uatb_path(c), c.state / "backups"))


def cmd_doctor(c, a):
    targets = pick_targets(c, a.target)
    rows = []

    def add(area, item, status, note=""):
        rows.append({"area": area, "item": item, "status": status, "note": note})
        if status == "fail":
            c.failures.append(item)

    skills = load("skills.json")["skills"]
    for t in targets:
        miss = [s["name"] for s in skills if not (c.home / SKILL_DIRS[t] / s["name"] / "SKILL.md").exists()]
        add(t, "skills installed", "ok" if not miss else "fail", "missing: " + ", ".join(miss) if miss else "%d of %d" % (len(skills), len(skills)))
    for f in sorted((REPO / "hooks").glob("*.py")):
        add("hooks", f.name, "ok" if (c.home / ".claude/hooks" / f.name).exists() else "fail")
    if "claude" in targets:
        _, data = read_settings(c)
        add("claude", "ticket-flow gate registered", "ok" if data and gate_registered(data) else "fail", "" if data else "settings.json unreadable")
        md = c.home / ".claude/CLAUDE.md"
        add("claude", "CLAUDE.md block", "ok" if md.exists() and BEGIN in md.read_text() else "fail")
        try:
            vals = json.loads(uatb_path(c).read_text())
            filled = all(vals.get(k) not in (None, "", "REPLACE_ME") for k in UATB_TEMPLATE)
            add("claude", "uatb test account file", "ok" if filled else "warn", "" if filled else "still has placeholders")
        except Exception:
            add("claude", "uatb test account file", "warn", "missing; only verify-before-pr needs it")
        versions, markets = claude_state(c)
        deps = load("deps.json")
        for p in deps["plugins"]:
            key = "%s@%s" % (p["name"], p["marketplace"])
            if key not in versions:
                add("plugins", key, "fail" if not p.get("private") else "warn", "not installed" + (" (private marketplace)" if p.get("private") else ""))
            elif versions[key] and versions[key] != p["tested"]:
                add("plugins", key, "warn", "installed %s, tested with %s" % (versions[key], p["tested"]))
            else:
                add("plugins", key, "ok", versions[key] or "")
    if "codex" in targets:
        md = c.home / ".codex/AGENTS.md"
        add("codex", "AGENTS.md block", "ok" if md.exists() and BEGIN in md.read_text() else "fail")
        add("codex", "plugin dependencies", "warn", "not checked; Codex support is experimental, see docs/compatibility.md")
    for tool in load("deps.json")["externalTools"]:
        ok = shutil.which(tool["name"]) is not None
        add("tools", tool["name"], "ok" if ok else ("warn" if tool.get("optional") else "fail"), "" if ok else "not on PATH")
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print("%-5s %-8s %-34s %s" % (r["status"].upper(), r["area"], r["item"], r["note"]))
    return 1 if c.failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["install", "uninstall", "doctor"])
    ap.add_argument("--target", default="auto", choices=["auto", "claude", "codex", "both"])
    ap.add_argument("--prefix", help="branch prefix for ticket branches, e.g. your first name (default: from git config)")
    ap.add_argument("--dry-run", action="store_true", help="print what would change and change nothing")
    ap.add_argument("--skip-deps", action="store_true", help="do not install plugin dependencies")
    ap.add_argument("--json", action="store_true", help="doctor: machine-readable output")
    ap.add_argument("--home", default=str(Path.home()), help=argparse.SUPPRESS)
    a = ap.parse_args()
    c = Ctx(a.home, a.dry_run)
    if a.command == "doctor":
        sys.exit(cmd_doctor(c, a))
    {"install": cmd_install, "uninstall": cmd_uninstall}[a.command](c, a)


if __name__ == "__main__":
    main()
