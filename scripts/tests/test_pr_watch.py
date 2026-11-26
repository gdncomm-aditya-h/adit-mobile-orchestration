import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from gitfixture import SCRIPTS

WATCH = str(SCRIPTS / "pr_watch.sh")
FAKE_GH = """#!/bin/sh
d="$FAKE_DIR"
case "$1 $2" in
  "pr view") [ -f "$d/fail" ] && exit 1; cat "$d/view.json" ;;
  "api graphql") cat "$d/threads.json" ;;
  "repo view") echo o/r ;;
esac
"""


def view(state="OPEN", draft=False, mergeable="MERGEABLE", merge_state="CLEAN", checks=()):
    return {"state": state, "isDraft": draft, "mergeable": mergeable, "mergeStateStatus": merge_state,
            "statusCheckRollup": list(checks)}


def threads(*resolved):
    return {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
        {"isResolved": r, "isOutdated": False} for r in resolved]}}}}}


@unittest.skipUnless(shutil.which("jq"), "jq is required by pr_watch.sh")
class PrWatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        gh = self.dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.set(view(), threads())

    def tearDown(self):
        self.tmp.cleanup()

    def set(self, v, t):
        (self.dir / "view.json").write_text(json.dumps(v))
        (self.dir / "threads.json").write_text(json.dumps(t))

    def run_watch(self, *args, timeout="0"):
        env = dict(os.environ, PATH=f"{self.dir}:{os.environ['PATH']}", FAKE_DIR=str(self.dir))
        r = subprocess.run(["bash", WATCH, *args, "--interval", "1", "--timeout", timeout],
                           capture_output=True, text=True, env=env, timeout=30)
        return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])

    def event(self, v, t=None):
        self.set(v, t or threads())
        return self.run_watch("12", "--repo", "o/r")[1]["event"]

    def test_terminal_states(self):
        self.assertEqual(self.event(view("MERGED")), "merged")
        self.assertEqual(self.event(view("CLOSED")), "closed")

    def test_conflicts_are_dirty(self):
        self.assertEqual(self.event(view(mergeable="CONFLICTING", merge_state="DIRTY")), "dirty")

    def test_failed_check_lists_names(self):
        checks = [{"name": "build", "conclusion": "FAILURE"}, {"name": "lint", "conclusion": "SUCCESS"},
                  {"context": "ci/legacy", "state": "ERROR"}]
        self.set(view(checks=checks), threads())
        code, out = self.run_watch("12", "--repo", "o/r")
        self.assertEqual((code, out["event"], out["detail"]), (0, "ci_fail", "build, ci/legacy"))

    def test_pending_and_green_checks_do_not_fire(self):
        checks = [{"name": "build", "conclusion": ""}, {"name": "lint", "conclusion": "SUCCESS"}]
        self.assertEqual(self.event(view(checks=checks)), "timeout")

    def test_unresolved_threads_only(self):
        self.assertEqual(self.event(view(), threads(True, False, False)), "comments")
        self.assertEqual(self.event(view(), threads(True, True)), "timeout")

    def test_ready_fires_only_after_it_was_draft(self):
        # A single poll sees one state, so a PR that is already ready was never a draft: no `ready` event.
        self.assertEqual(self.event(view(draft=False)), "timeout")

    def test_url_argument_and_error_exit(self):
        self.set(view("MERGED"), threads())
        code, out = self.run_watch("https://github.com/o/r/pull/12")
        self.assertEqual((code, out["event"], out["pr"], out["repo"]), (0, "merged", 12, "o/r"))
        (self.dir / "fail").write_text("")
        code, out = self.run_watch("12", "--repo", "o/r", timeout="60")
        self.assertEqual((code, out["event"]), (1, "error"))
        self.assertEqual(self.run_watch("not-a-pr")[0], 1)


if __name__ == "__main__":
    unittest.main()
