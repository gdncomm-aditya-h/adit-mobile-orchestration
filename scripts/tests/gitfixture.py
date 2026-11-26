"""Throwaway git repos and a private state folder for the script tests."""
import os
import subprocess
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
ENV_BASE = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}


def env(home):
    e = dict(os.environ)
    e.update(ENV_BASE)
    e["IOS_TICKET_FLOW_HOME"] = str(home)
    e["TICKET_SLOTS_NO_SIM"] = "1"
    return e


def git(cwd, *args, e=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                          env=e or env(tempfile.gettempdir())).stdout.strip()


def make_repo(root, name, branch="develop", files=None):
    """A bare 'origin' plus a clone of it at root/name, with one commit on `branch`. Returns the clone path."""
    origin = Path(root) / f"{name}-origin.git"
    clone = Path(root) / name
    subprocess.run(["git", "init", "-q", "--bare", "-b", branch, str(origin)], check=True, env=env(root))
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True, env=env(root))
    for rel, text in (files or {"README.md": "x\n"}).items():
        f = clone / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    git(clone, "checkout", "-q", "-B", branch, e=env(root))
    git(clone, "add", "-A", e=env(root))
    git(clone, "commit", "-q", "-m", "init", e=env(root))
    git(clone, "push", "-q", "-u", "origin", branch, e=env(root))
    return clone
