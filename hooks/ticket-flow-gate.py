#!/usr/bin/env python3
"""Ticket-flow gate: PreToolUse hook (Bash, github create/merge PR) plus a small CLI.

CLI:  ticket-flow-gate.py mark-active|mark-verified|clear <KEY>   (run inside the ticket's checkout)
Hook: reads the tool call as JSON on stdin. Only acts when ~/.claude/state/ticket-flow/active/<KEY>
exists for the ticket key found in the current git branch name. Any other branch or session is untouched.

While active:
  - git commit / git push / gh pr create|ready|merge need a `verified` marker for <KEY>.
  - git commit also needs the changed files to match the content hash recorded at mark-verified.
  - mcp create_pull_request needs the marker and draft=true. merge_pull_request is always denied.
  - git stash|reset|rebase|merge|cherry-pick are always denied.
Fails open (allows the call) on any unexpected error, so a bug here cannot block unrelated work.

shortcut: matches commands by regex, so `git -c k=v commit` or a script that runs git is not seen;
upgrade to a shell parser if that ever matters.
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

STATE = Path.home() / ".claude/state/ticket-flow"
KEY_RE = re.compile(r"[A-Z]+-\d+")
GIT = r"\bgit\b(?:\s+-C\s+\S+)?\s+"
NEEDS_VERIFIED = re.compile(GIT + r"(commit|push)\b|\bgh\s+pr\s+(create|ready|merge)\b")
ALWAYS_BLOCKED = re.compile(GIT + r"(stash|reset|rebase|merge|cherry-pick)\b")
COMMIT = re.compile(GIT + r"commit\b")


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, check=True).stdout


def ticket_key(cwd):
    m = KEY_RE.search(git(cwd, "branch", "--show-current").decode())
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


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def cli(action, key):
    cwd = str(Path.cwd())
    for sub in ("active", "verified"):
        (STATE / sub).mkdir(parents=True, exist_ok=True)
    if action == "mark-active":
        (STATE / "active" / key).write_text(str(time.time()))
    elif action == "mark-verified":
        (STATE / "verified" / key).write_text(content_hash(cwd))
    elif action == "clear":
        for sub in ("active", "verified"):
            (STATE / sub / key).unlink(missing_ok=True)
    else:
        sys.exit(f"unknown action {action}")
    print(f"{action} {key}: ok")


def hook():
    data = json.load(sys.stdin)
    cwd = data.get("cwd") or "."
    key = ticket_key(cwd)
    if not key or not (STATE / "active" / key).exists():
        return
    tool, inp = data.get("tool_name", ""), data.get("tool_input", {})
    marker = STATE / "verified" / key
    verified = marker.exists()

    if tool == "mcp__github__merge_pull_request":
        deny(f"ticket-flow {key}: merging is never done by the agent.")
    if tool == "mcp__github__create_pull_request":
        if not verified:
            deny(f"ticket-flow {key}: run adit-workflow-verify-before-pr first (no verified marker).")
        if inp.get("draft") is not True:
            deny(f"ticket-flow {key}: open the PR as a draft (draft: true).")
        return
    if tool != "Bash":
        return

    cmd = inp.get("command", "")
    if ALWAYS_BLOCKED.search(cmd):
        deny(f"ticket-flow {key}: stash/reset/rebase/merge/cherry-pick are blocked during the flow.")
    if NEEDS_VERIFIED.search(cmd):
        if not verified:
            deny(f"ticket-flow {key}: run adit-workflow-verify-before-pr first (no verified marker). "
                 "Commit, push and PR creation stay blocked until build, tests, click tests and review pass.")
        if COMMIT.search(cmd) and marker.read_text().strip() != content_hash(cwd):
            deny(f"ticket-flow {key}: files changed since verification. Re-run adit-workflow-verify-before-pr "
                 f"(or `ticket-flow-gate.py mark-verified {key}` if the change is intended).")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        cli(sys.argv[1], sys.argv[2])
    else:
        try:
            hook()
        except SystemExit:
            raise
        except Exception:
            pass  # fail open
