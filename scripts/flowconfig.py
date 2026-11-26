#!/usr/bin/env python3
"""Per-engineer settings for the ios-orchestration skills.

  flowconfig.py get [key]            print one value (or the whole file)
  flowconfig.py set <key> <value>    key: defaultRepo | branchPrefix | jiraProject | slots.<owner/repo> | profile.<owner/repo>
  flowconfig.py slots <owner/repo> <app|package>   print the slot count that applies

The file is ~/.claude/ios-ticket-flow/config.json (override the folder with IOS_TICKET_FLOW_HOME).
It is the source of truth: skills read it, they never rely on model memory for these values.
A missing or unreadable file means defaults, never an error.
"""
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_REPO = "gdncomm/BlibliIOSApp"
DEFAULTS = {"defaultRepo": DEFAULT_REPO, "branchPrefix": None, "jiraProject": "IOS", "slots": {}, "profile": {}}
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def home():
    return Path(os.environ.get("IOS_TICKET_FLOW_HOME") or Path.home() / ".claude" / "ios-ticket-flow")


def path():
    return home() / "config.json"


def load():
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        data = json.loads(path().read_text())
    except (OSError, ValueError):
        return cfg
    if isinstance(data, dict):
        for k, v in data.items():
            if k in ("slots", "profile") and not isinstance(v, dict):
                continue
            cfg[k] = v
    return cfg


def save(cfg):
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")


def valid_repo(name):
    return bool(REPO_RE.match(name or ""))


def set_value(cfg, key, value):
    if key in ("defaultRepo",):
        if not valid_repo(value):
            raise ValueError(f"{value!r} is not owner/repo")
        cfg[key] = value
    elif key == "branchPrefix":
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value or ""):
            raise ValueError("branchPrefix must be letters, digits, dot, dash or underscore")
        cfg[key] = value
    elif key == "jiraProject":
        if not re.fullmatch(r"[A-Z][A-Z0-9]+", value or ""):
            raise ValueError("jiraProject must look like IOS")
        cfg[key] = value
    elif key.startswith("slots."):
        repo = key[len("slots."):]
        if not valid_repo(repo) or not value.isdigit() or not 1 <= int(value) <= 8:
            raise ValueError("use slots.<owner/repo> <1-8>")
        cfg["slots"][repo] = int(value)
    elif key.startswith("profile."):
        repo = key[len("profile."):]
        if not valid_repo(repo) or value not in ("app", "package"):
            raise ValueError("use profile.<owner/repo> app|package")
        cfg["profile"][repo] = value
    else:
        raise ValueError(f"unknown key {key}")


def slots_for(cfg, repo, kind):
    """Slot count for an app repo. Package repos never use a pool (0)."""
    if kind != "app":
        return 0
    if repo in cfg["slots"]:
        return cfg["slots"][repo]
    return 4 if repo == DEFAULT_REPO else 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "get":
        cfg = load()
        out = cfg.get(argv[2]) if len(argv) > 2 else cfg
        print(json.dumps(out, indent=2) if not isinstance(out, str) else out)
    elif len(argv) == 4 and argv[1] == "set":
        cfg = load()
        try:
            set_value(cfg, argv[2], argv[3])
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        save(cfg)
        print(f"{argv[2]} = {argv[3]}")
    elif len(argv) == 4 and argv[1] == "slots":
        print(slots_for(load(), argv[2], argv[3]))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
