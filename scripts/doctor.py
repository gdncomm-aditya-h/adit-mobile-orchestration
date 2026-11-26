#!/usr/bin/env python3
"""Checks the machine-side prerequisites of the ios-orchestration skills and prints one line per check.

  doctor.py [<checkout dir>]                       full table; exit code is always 0
  doctor.py --preflight --need git,gh,xcode [--fresh]   quiet check run first by the flow skills
  doctor.py --plugins                              JSON: which plugins are missing and the commands that install them

Preflight prints nothing when the machine is ready. It prints `BLOCKER: ...` lines for a missing tool the skill
needs (exit code 1) and `WARN: ...` lines for stale gate markers. Tool results are cached for 24 hours and until the
plugin version changes (--fresh skips the cache), so a ready machine costs one file read.
Plugin checks read the client's installed-plugins file; when it cannot be read (another client) they report "unknown"
and never block. Installing is done by the ios-orchestration-setup skill, never by this script.
Checks that need the model's tool list (Atlassian MCP, simulator control, permission-mode switching) are done by the
ios-orchestration-flow-doctor skill.
"""
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
import ticket_gate  # noqa: E402


def sh(*cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return r.returncode, (r.stdout or r.stderr).strip()


def check_tools():
    rows = []
    for tool, why in (("git", "all flows"), ("gh", "PRs, reviews, repo validation"), ("python3", "gate hook and scripts"),
                      ("xcodebuild", "app and package builds"), ("xcrun", "simulators"),
                      ("jq", "PR watcher")):
        rows.append((tool, "ok" if shutil.which(tool) else "MISSING", why))
    if shutil.which("gh"):
        code, out = sh("gh", "auth", "status")
        rows.append(("gh auth", "ok" if code == 0 else "NOT LOGGED IN", "run: gh auth login" if code else ""))
    if sys.version_info < (3, 8):
        rows.append(("python3 version", "TOO OLD", f"{sys.version.split()[0]}, need 3.8+"))
    return rows


PLUGINS = (
    # name, marketplace, source for `claude plugin marketplace add`, required, used for
    ("mobileapps-foundation", "agent-plugins", "git@github.com:gdncomm/agent-plugins.git", True,
     "create-pr, localization, figma-mcp, jira-doc-generator"),
    ("superpowers", "claude-plugins-official", "anthropics/claude-plugins-official", False,
     "brainstorming step in plan mode"),
    ("ponytail", "ponytail", "DietrichGebert/ponytail", False, "audit and review loops"),
    ("ecc", "ecc", "affaan-m/ECC", False, "fallback reviewer when ponytail is missing"),
)


def installed_plugins():
    """(installed 'name@marketplace' keys, known marketplace names), or None when the client keeps no such file."""
    d = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "plugins"
    try:
        have = set(json.loads((d / "installed_plugins.json").read_text())["plugins"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:
        markets = set(json.loads((d / "known_marketplaces.json").read_text()))
    except (OSError, ValueError, TypeError):
        markets = set()
    return have, markets


def check_plugins():
    state = installed_plugins()
    if state is None:
        return [("plugins", "unknown", "cannot read the Claude plugin list (another client?), not checked")]
    have = state[0]
    rows = [(name, "ok" if f"{name}@{market}" in have else ("MISSING" if required else "not installed"),
             why + ("" if required else ". optional"))
            for name, market, _, required, why in PLUGINS]
    if all(status != "ok" for name, status, _ in rows if name in ("ponytail", "ecc")):
        rows.append(("audit engine", "not installed", "ponytail and ecc are both missing: audit-changes has no reviewer"))
    return rows


def missing_plugins():
    """Plugins to install, each with the exact CLI commands. None when the plugin list cannot be read."""
    state = installed_plugins()
    if state is None:
        return None
    have, markets = state
    return [{"name": name, "required": required, "why": why,
             "commands": ([["claude", "plugin", "marketplace", "add", source]] if market not in markets else [])
             + [["claude", "plugin", "install", f"{name}@{market}"]]}
            for name, market, source, required, why in PLUGINS if f"{name}@{market}" not in have]


def check_config():
    p = flowconfig.path()
    if not p.exists():
        return [("config", "none yet", "defaults apply (BlibliIOSApp). Run ios-orchestration-flow-config to set a repo and branch prefix")]
    try:
        json.loads(p.read_text())
    except ValueError:
        return [("config", "UNREADABLE", f"{p} is not valid JSON; defaults are used")]
    cfg = flowconfig.load()
    rows = [("config", "ok", f"repo={cfg['defaultRepo']} prefix={cfg['branchPrefix'] or 'NOT SET'} jira={cfg['jiraProject']}")]
    return rows


def check_gate():
    rows, st = [], ticket_gate.state_dir() / "active"
    if st.is_dir():
        import time
        for f in sorted(st.iterdir()):
            try:
                age = time.time() - float(f.read_text())
            except (OSError, ValueError):
                continue
            if age >= ticket_gate.TTL_SECONDS:
                rows.append((f"gate {f.name}", "EXPIRED", "ignored by the hook; clear with ticket_gate.py clear " + f.name))
            elif age > 24 * 3600:
                rows.append((f"gate {f.name}", "old", f"armed {int(age / 3600)}h ago; clear it if the ticket is abandoned"))
    return rows or [("gate", "ok", "no stale markers")]


def check_repo(root):
    code, out = sh("git", "rev-parse", "--show-toplevel", cwd=root)
    if code:
        return [("repo", "n/a", "not inside a git checkout")]
    top = Path(out)
    prof = repo_profile.detect(top)
    rows = [("repo profile", prof["kind"], f"{prof['name']}")]
    if prof["kind"] == "app" and prof.get("swiftlint"):
        sl = (top / (prof.get("appDir") or ".") / prof["swiftlint"])
        rows.append(("swiftlint", "ok" if sl.exists() else "MISSING", str(sl)))
    if prof["kind"] == "app" and shutil.which("xcrun"):
        code, out = sh("xcrun", "simctl", "list", "runtimes", "-j")
        ok = False
        try:
            ok = any(r.get("isAvailable") and "SimRuntime.iOS" in r.get("identifier", "") for r in json.loads(out)["runtimes"])
        except (ValueError, KeyError):
            pass
        rows.append(("iOS simulator runtime", "ok" if ok else "MISSING",
                     "" if ok else "install one in Xcode > Settings > Components"))
    return rows


PREFLIGHT_TTL = 24 * 3600
NEED = {"git": ("git", "python3 version"), "gh": ("gh", "gh auth"), "xcode": ("xcodebuild", "xcrun"), "watch": ("gh", "gh auth", "jq"),
        "plugins": ("mobileapps-foundation",)}
BAD = ("MISSING", "NOT LOGGED IN", "TOO OLD")
FIX = {"git": "install git", "gh": "brew install gh", "gh auth": "run: gh auth login",
       "xcodebuild": "install Xcode and run: sudo xcode-select -s /Applications/Xcode.app",
       "xcrun": "install Xcode command line tools: xcode-select --install", "jq": "brew install jq",
       "mobileapps-foundation": "run /ios-orchestration-setup", "python3 version": "install Python 3.8 or newer"}


def plugin_version():
    try:
        return json.loads((Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json").read_text())["version"]
    except (OSError, ValueError, KeyError):
        return "dev"


def cache_path():
    return flowconfig.home() / "state" / "preflight.json"


def machine_rows(now=None, fresh=False):
    """Tool checks, cached for 24 hours and until the plugin version changes."""
    now = now or time.time()
    if not fresh:
        try:
            c = json.loads(cache_path().read_text())
            if c["version"] == plugin_version() and 0 <= now - c["at"] < PREFLIGHT_TTL:
                return [tuple(r) for r in c["rows"]]
        except (OSError, ValueError, KeyError):
            pass
    rows = check_tools()
    if any(status in BAD for _, status, _ in rows):
        return rows  # never cache a failure: the engineer fixes it, then the next preflight must see it
    try:
        cache_path().parent.mkdir(parents=True, exist_ok=True)
        cache_path().write_text(json.dumps({"at": now, "version": plugin_version(), "rows": rows}))
    except OSError:
        pass
    return rows


def preflight(need, rows):
    """BLOCKER lines for the groups in `need`, plus a WARN line for each stale gate marker."""
    wanted = {name for g in need for name in NEED.get(g, ())}
    out = [f"BLOCKER: {name} {status}. {FIX.get(name, '')}".rstrip() for name, status, _ in rows
           if name in wanted and status in BAD]
    return out + [f"WARN: {n} {s}. {note}" for n, s, note in check_gate() if s in ("EXPIRED", "old")]


def main(argv):
    if "--preflight" in argv:
        need = argv[argv.index("--need") + 1].split(",") if "--need" in argv else []
        rows = machine_rows(fresh="--fresh" in argv) + (check_plugins() if "plugins" in need else [])
        lines = preflight(need, rows)
        for line in lines:
            print(line)
        return 1 if any(l.startswith("BLOCKER") for l in lines) else 0
    if "--plugins" in argv:
        missing = missing_plugins()
        print(json.dumps({"checked": missing is not None, "missing": missing or []}, indent=2))
        return 0
    root = argv[1] if len(argv) > 1 else "."
    for name, status, note in check_tools() + check_plugins() + check_config() + check_gate() + check_repo(root):
        print(f"{name:<24} {status:<14} {note}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
