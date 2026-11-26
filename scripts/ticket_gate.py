#!/usr/bin/env python3
"""Ticket-flow gate: PreToolUse hook (Bash, github create/merge PR) plus a small CLI.

CLI:  ticket_gate.py mark-active|mark-verified|clear <KEY>   (run inside the ticket's checkout)
      ticket_gate.py list                                    (active tickets, age, verified or not)
Hook: reads the tool call as JSON on stdin. It acts only when <state>/active/<KEY> exists and is younger
than 7 days for the ticket key found in the current git branch name. Any other branch or session is untouched.

While active:
  - git commit / git push / gh pr create need a `verified` marker for <KEY>.
  - git commit also needs the changed files to match the content hash recorded at mark-verified.
  - gh pr create needs --draft (not --draft=false). gh pr merge is always denied. gh pr ready (or the GraphQL markPullRequestReadyForReview) is denied unless it is --undo.
  - mcp create_pull_request needs the marker and draft=true. merge_pull_request is always denied.
  - git stash|reset|cherry-pick are always denied. git merge|rebase are denied unless they sync with a remote
    branch (the command names `origin/...`) or continue/abort one.
Always, even with no active ticket: a branch named inject/* may not be pushed or turned into a PR.
The branch is read from the directory the command targets (`git -C <dir>` or `cd <dir>`), else from the session cwd.
Fails open (allows the call) on any unexpected error, so a bug here cannot block unrelated work.

State folder: ~/.claude/ios-ticket-flow/state/gate (override the base with IOS_TICKET_FLOW_HOME).

shortcut: matches commands by regex, so `git -c k=v commit` or a script that runs git is not seen;
upgrade to a shell parser if that ever matters.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TTL_SECONDS = 7 * 24 * 3600
KEY_RE = re.compile(r"[A-Z]+-\d+")
GIT = r"\bgit\b(?:\s+-C\s+\S+)?\s+"
PUSH_OR_PR = re.compile(GIT + r"push\b|\bgh\s+pr\s+(create|ready)\b")
NEEDS_VERIFIED = re.compile(GIT + r"(commit|push)\b|\bgh\s+pr\s+create\b")
GH_CREATE = re.compile(r"\bgh\s+pr\s+create\b")
GH_DRAFT = re.compile(r"--draft(?!=(false|0)\b)\b|\s-d\b")
GH_MERGE = re.compile(r"\bgh\s+pr\s+merge\b")
GH_READY = re.compile(r"\bgh\s+pr\s+ready\b|markPullRequestReadyForReview")
TARGET_DIR = re.compile(r"(?:\bgit\s+-C|\bcd)\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")
ALWAYS_BLOCKED = re.compile(GIT + r"(stash|reset|cherry-pick)\b")
SYNC_CMD = re.compile(GIT + r"(merge|rebase)\b")
SYNC_OK = re.compile(r"origin/|--continue|--abort|--quit")
COMMIT = re.compile(GIT + r"commit\b")


def state_dir():
    base = os.environ.get("IOS_TICKET_FLOW_HOME") or str(Path.home() / ".claude" / "ios-ticket-flow")
    return Path(base) / "state" / "gate"


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, check=True).stdout


def command_cwd(cmd, cwd):
    """Directory a Bash command works in: the last `git -C <dir>` or `cd <dir>` target, else the session cwd."""
    hits = TARGET_DIR.findall(cmd)
    if not hits:
        return cwd
    return str(Path(cwd) / Path(hits[-1].strip("\"'")).expanduser())


def branch_name(cwd):
    return git(cwd, "branch", "--show-current").decode().strip()


def ticket_key(branch):
    m = KEY_RE.search(branch)
    return m.group(0) if m else None


def content_hash(cwd):
    """Hash of every changed or untracked file, by path and bytes. Same before and after `git add`."""
    root = Path(git(cwd, "rev-parse", "--show-toplevel").decode().strip())
    out = git(cwd, "status", "--porcelain", "-z", "--untracked-files=all").decode().split("\0")
    paths, i = [], 0
    while i < len(out):
        entry = out[i]
        i += 1
        if len(entry) < 4:
            continue
        paths.append(entry[3:])
        if entry[0] in "RC":  # renames carry a second path
            i += 1
    h = hashlib.sha256()
    for p in sorted(set(paths)):
        f = root / p
        h.update(p.encode() + b"\0")
        h.update(f.read_bytes() if f.is_file() else b"<gone>")
    return h.hexdigest()


def is_active(key, now=None):
    marker = state_dir() / "active" / key
    try:
        started = float(marker.read_text())
    except (OSError, ValueError):
        return False
    return (now or time.time()) - started < TTL_SECONDS


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def cli(action, key=None):
    if action not in ("list", "mark-active", "mark-verified", "clear"):
        sys.exit(f"unknown action {action}. Usage: ticket_gate.py mark-active|mark-verified|clear <KEY> | list")
    if action != "list" and not (key and KEY_RE.fullmatch(key)):
        sys.exit(f"{action} needs a ticket key like IOS-123. Usage: ticket_gate.py mark-active|mark-verified|clear <KEY> | list")
    st = state_dir()
    for sub in ("active", "verified"):
        (st / sub).mkdir(parents=True, exist_ok=True)
    if action == "list":
        now = time.time()
        for f in sorted((st / "active").iterdir()):
            try:
                age = int((now - float(f.read_text())) / 3600)
            except (OSError, ValueError):
                age = -1
            state = "verified" if (st / "verified" / f.name).exists() else "not verified"
            expired = " EXPIRED" if age * 3600 >= TTL_SECONDS else ""
            print(f"{f.name}: {state}, armed {age}h ago{expired}")
        return
    if action == "mark-active":
        (st / "active" / key).write_text(str(time.time()))
    elif action == "mark-verified":
        (st / "verified" / key).write_text(content_hash(str(Path.cwd())))
    elif action == "clear":
        for sub in ("active", "verified"):
            (st / sub / key).unlink(missing_ok=True)
    print(f"{action} {key}: ok")


def hook():
    data = json.load(sys.stdin)
    cwd = data.get("cwd") or "."
    tool, inp = data.get("tool_name", ""), data.get("tool_input", {})
    if tool == "Bash" and not re.search(r"\b(git|gh)\b", inp.get("command", "")):
        return  # most Bash calls: skip the git lookup entirely
    if tool == "Bash":
        cwd = command_cwd(inp.get("command", ""), cwd)
    branch = branch_name(cwd)

    head = inp.get("head") or ""
    if branch.startswith("inject/") or head.startswith("inject/"):
        pushing = tool == "mcp__github__create_pull_request" or (
            tool == "Bash" and PUSH_OR_PR.search(inp.get("command", "")))
        if pushing:
            deny(f"ios-orchestration: {head or branch} is a throwaway SDK integration branch. It is never pushed or turned into a PR.")

    key = ticket_key(branch)
    if not key or not is_active(key):
        return
    st = state_dir()
    marker = st / "verified" / key
    verified = marker.exists()

    if tool == "mcp__github__merge_pull_request":
        deny(f"ios-orchestration {key}: merging is never done by the agent.")
    if tool == "mcp__github__create_pull_request":
        if not verified:
            deny(f"ios-orchestration {key}: run ios-orchestration-verify-ticket first (no verified marker).")
        if inp.get("draft") is not True:
            deny(f"ios-orchestration {key}: open the PR as a draft (draft: true).")
        return
    if tool != "Bash":
        return

    cmd = inp.get("command", "")
    if GH_MERGE.search(cmd):
        deny(f"ios-orchestration {key}: merging is never done by the agent.")
    if GH_READY.search(cmd) and "--undo" not in cmd:
        deny(f"ios-orchestration {key}: marking a PR ready is never done by the agent (gh pr ready --undo is fine).")
    if GH_CREATE.search(cmd) and not GH_DRAFT.search(cmd):
        deny(f"ios-orchestration {key}: open the PR as a draft (gh pr create --draft).")
    if ALWAYS_BLOCKED.search(cmd):
        deny(f"ios-orchestration {key}: stash/reset/cherry-pick are blocked during the flow.")
    if SYNC_CMD.search(cmd) and not SYNC_OK.search(cmd):
        deny(f"ios-orchestration {key}: merge/rebase are only allowed to sync with the base branch "
             "(name it as origin/<branch>) or to --continue/--abort.")
    if NEEDS_VERIFIED.search(cmd):
        if not verified:
            deny(f"ios-orchestration {key}: run ios-orchestration-verify-ticket first (no verified marker). "
                 "Commit, push and PR creation stay blocked until build, tests, click tests and review pass.")
        if COMMIT.search(cmd) and marker.read_text().strip() != content_hash(cwd):
            deny(f"ios-orchestration {key}: files changed since verification. Re-run ios-orchestration-verify-ticket "
                 f"(or `ticket_gate.py mark-verified {key}` if the change is intended).")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        try:
            hook()
        except SystemExit:
            raise
        except Exception:
            pass  # fail open
