import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from gitfixture import SCRIPTS, env, git, make_repo

GATE = str(SCRIPTS / "ticket_gate.py")


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.repo = make_repo(self.tmp.name, "app")
        git(self.repo, "checkout", "-q", "-b", "adit/improvement/IOS-1", e=env(self.home))
        (self.repo / "a.txt").write_text("one\n")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, GATE, *args], cwd=self.repo, capture_output=True, text=True,
                              env=env(self.home))

    def hook(self, tool, tool_input, cwd=None):
        r = subprocess.run([sys.executable, GATE], input=json.dumps(
            {"cwd": str(cwd or self.repo), "tool_name": tool, "tool_input": tool_input}),
            capture_output=True, text=True, env=env(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else "allow"

    def bash(self, cmd):
        return self.hook("Bash", {"command": cmd})

    def test_passive_without_marker(self):
        for cmd in ("git commit -m x", "git push", "git stash", "gh pr create"):
            self.assertEqual(self.bash(cmd), "allow", cmd)

    def test_commit_needs_verified_then_hash(self):
        self.cli("mark-active", "IOS-1")
        self.assertEqual(self.bash("git commit -m x"), "deny")
        self.cli("mark-verified", "IOS-1")
        self.assertEqual(self.bash("git commit -m x"), "allow")
        (self.repo / "a.txt").write_text("two\n")
        self.assertEqual(self.bash("git commit -m x"), "deny")

    def test_push_and_pr_need_verified(self):
        self.cli("mark-active", "IOS-1")
        self.assertEqual(self.bash("git push origin HEAD"), "deny")
        self.assertEqual(self.bash("gh pr create --draft"), "deny")
        self.cli("mark-verified", "IOS-1")
        self.assertEqual(self.bash("git push origin HEAD"), "allow")

    def test_gh_merge_ready_and_non_draft_create_are_denied_once_verified(self):
        self.cli("mark-active", "IOS-1")
        self.cli("mark-verified", "IOS-1")
        self.assertEqual(self.bash("gh pr create --title x --draft"), "allow")
        self.assertEqual(self.bash("gh pr create --title x"), "deny")
        self.assertEqual(self.bash("gh pr merge 42 --squash"), "deny")
        self.assertEqual(self.bash("gh pr ready 42"), "deny")
        self.assertEqual(self.bash("gh pr ready --undo 42"), "allow")

    def test_draft_false_and_graphql_ready_are_denied(self):
        self.cli("mark-active", "IOS-1")
        self.cli("mark-verified", "IOS-1")
        self.assertEqual(self.bash("gh pr create --title x --draft=true"), "allow")
        self.assertEqual(self.bash("gh pr create --title x --draft=false"), "deny")
        self.assertEqual(self.bash("gh api graphql -f query='mutation{markPullRequestReadyForReview(input:{pullRequestId:\"x\"}){clientMutationId}}'"), "deny")

    def test_cli_needs_a_valid_key(self):
        for args in (("clear",), ("mark-active",), ("mark-active", "../x"), ("bogus", "IOS-1")):
            r = self.cli(*args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertIn("Usage", r.stderr)
        self.assertEqual(self.cli("list").returncode, 0)

    def test_stash_reset_cherry_pick_blocked(self):
        self.cli("mark-active", "IOS-1")
        for cmd in ("git stash", "git reset --hard", "git cherry-pick abc"):
            self.assertEqual(self.bash(cmd), "deny", cmd)

    def test_base_sync_allowed_other_merge_denied(self):
        self.cli("mark-active", "IOS-1")
        self.assertEqual(self.bash("git merge origin/develop"), "allow")
        self.assertEqual(self.bash("git rebase origin/develop"), "allow")
        self.assertEqual(self.bash("git rebase --continue"), "allow")
        self.assertEqual(self.bash("git merge some-feature"), "deny")

    def test_expired_marker_is_ignored(self):
        self.cli("mark-active", "IOS-1")
        marker = self.home / "state" / "gate" / "active" / "IOS-1"
        marker.write_text(str(time.time() - 8 * 24 * 3600))
        self.assertEqual(self.bash("git commit -m x"), "allow")
        self.assertIn("EXPIRED", self.cli("list").stdout)

    def test_clear_removes_gate(self):
        self.cli("mark-active", "IOS-1")
        self.cli("clear", "IOS-1")
        self.assertEqual(self.bash("git commit -m x"), "allow")

    def test_other_branch_untouched(self):
        self.cli("mark-active", "IOS-1")
        git(self.repo, "checkout", "-q", "-b", "adit/improvement/IOS-2", e=env(self.home))
        self.assertEqual(self.bash("git commit -m x"), "allow")

    def test_non_git_bash_skips_everything(self):
        self.cli("mark-active", "IOS-1")
        self.assertEqual(self.hook("Bash", {"command": "ls -la"}, cwd=self.tmp.name), "allow")

    def test_not_a_repo_fails_open(self):
        self.assertEqual(self.hook("Bash", {"command": "git commit -m x"}, cwd=self.tmp.name), "allow")

    def test_github_tools(self):
        self.cli("mark-active", "IOS-1")
        self.assertEqual(self.hook("mcp__github__merge_pull_request", {}), "deny")
        self.assertEqual(self.hook("mcp__github__create_pull_request", {"draft": True}), "deny")
        self.cli("mark-verified", "IOS-1")
        self.assertEqual(self.hook("mcp__github__create_pull_request", {"draft": False}), "deny")
        self.assertEqual(self.hook("mcp__github__create_pull_request", {"draft": True}), "allow")

    def test_inject_branch_never_pushed(self):
        git(self.repo, "checkout", "-q", "-b", "inject/Blibli-Assets-IOS-1", e=env(self.home))
        self.assertEqual(self.bash("git push origin HEAD"), "deny")
        self.assertEqual(self.bash("gh pr create"), "deny")
        self.assertEqual(self.hook("mcp__github__create_pull_request", {"draft": True}), "deny")
        self.assertEqual(self.bash("git commit -m wip"), "allow")

    def test_inject_push_from_another_cwd_is_denied(self):
        inject = Path(self.tmp.name) / "inject"
        git(self.repo, "worktree", "add", "-q", "-b", "inject/Sdk-IOS-9", str(inject), e=env(self.home))
        self.assertEqual(self.bash(f"cd {inject} && git push -u origin inject/Sdk-IOS-9"), "deny")
        self.assertEqual(self.bash(f"git -C {inject} push origin HEAD"), "deny")
        self.assertEqual(self.hook("mcp__github__create_pull_request", {"head": "inject/Sdk-IOS-9", "draft": True}), "deny")
        self.assertEqual(self.bash("git push origin HEAD"), "allow")  # session branch is a plain ticket branch


if __name__ == "__main__":
    unittest.main()
