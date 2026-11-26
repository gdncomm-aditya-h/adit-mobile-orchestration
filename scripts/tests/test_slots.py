import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gitfixture import SCRIPTS, env, git, make_repo

sys.path.insert(0, str(SCRIPTS))
import slot_health  # noqa: E402
import ticket_slots  # noqa: E402

SLOTS = str(SCRIPTS / "ticket_slots.py")
APP_PBX = "x = com.apple.product-type.application;"


class PureTest(unittest.TestCase):
    def test_letters(self):
        self.assertEqual(ticket_slots.slot_letters(4), "abcd")
        self.assertEqual(ticket_slots.slot_letters(1), "a")

    def test_pick_runtime_and_device(self):
        runtimes = [
            {"identifier": "com.apple.CoreSimulator.SimRuntime.iOS-17-5", "version": "17.5", "isAvailable": True},
            {"identifier": "com.apple.CoreSimulator.SimRuntime.iOS-26-5", "version": "26.5", "isAvailable": True},
            {"identifier": "com.apple.CoreSimulator.SimRuntime.iOS-27-0", "version": "27.0", "isAvailable": False},
            {"identifier": "com.apple.CoreSimulator.SimRuntime.watchOS-11-0", "version": "11.0", "isAvailable": True},
        ]
        types = [{"name": "iPhone 15", "identifier": "d15", "productFamily": "iPhone"},
                 {"name": "iPhone 17 Pro", "identifier": "d17", "productFamily": "iPhone"},
                 {"name": "iPad Pro", "identifier": "dpad", "productFamily": "iPad"}]
        self.assertEqual(ticket_slots.pick_runtime_and_device(runtimes, types),
                         ("com.apple.CoreSimulator.SimRuntime.iOS-26-5", "d17"))
        self.assertEqual(ticket_slots.pick_runtime_and_device(runtimes, types[:1])[1], "d15")
        with self.assertRaises(ticket_slots.Fail):
            ticket_slots.pick_runtime_and_device([], types)

    def test_classify_and_ticket_from_branch(self):
        self.assertEqual(slot_health.classify(True, {"since": 0}, 100 * 3600), "STALE")
        self.assertEqual(slot_health.classify(True, {"since": 100 * 3600}, 101 * 3600), "busy")
        self.assertEqual(slot_health.classify(True, None, 0), "claiming")
        self.assertEqual(slot_health.classify(False, None, 0), "free")
        self.assertEqual(slot_health.ticket_from_branch("jane/bugfix/IOS-47206"), "IOS-47206")
        self.assertIsNone(slot_health.ticket_from_branch("develop"))


class PoolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.work = (Path(self.tmp.name) / "work").resolve()  # macOS: /var is a symlink to /private/var
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_slots(self, repo_dir, *args, check=True):
        r = subprocess.run([sys.executable, SLOTS, *args], cwd=repo_dir, capture_output=True, text=True,
                           env=env(self.home))
        if check:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def app_repo(self, name="SellerApp", extra=None):
        repo = make_repo(self.work, name, files={"App.xcodeproj/project.pbxproj": APP_PBX, **(extra or {})})
        git(repo, "remote", "set-url", "origin", f"git@github.com:gdncomm/{name}.git", e=env(self.home))
        git(repo, "remote", "add", "local", str(self.work / f"{name}-origin.git"), e=env(self.home))
        git(repo, "config", "url." + str(self.work / f"{name}-origin.git") + ".insteadOf",
            f"git@github.com:gdncomm/{name}.git", e=env(self.home))
        return repo

    def test_app_pool_fills_then_reports_busy_then_releases(self):
        repo = self.app_repo()
        first = json.loads(self.run_slots(repo, "acquire", "IOS-1", "--type", "improvement", "--base", "develop",
                                          "--prefix", "jane").stdout)
        self.assertEqual((first["kind"], first["slot"], first["branch"]), ("app", "a", "jane/improvement/IOS-1"))
        self.assertTrue(first["worktree"].endswith("worktrees/SellerApp/slot-a"))
        again = json.loads(self.run_slots(repo, "acquire", "IOS-1", "--type", "improvement", "--base", "develop",
                                          "--prefix", "jane").stdout)
        self.assertEqual(again["slot"], "a")
        full = self.run_slots(repo, "acquire", "IOS-2", "--type", "bugfix", "--base", "develop",
                              "--prefix", "jane", check=False)
        self.assertEqual(full.returncode, 3)  # other app repos default to a single slot
        self.assertIn("1/1 slots busy", full.stderr)
        self.run_slots(repo, "release", "IOS-1")
        second = json.loads(self.run_slots(repo, "acquire", "IOS-2", "--type", "bugfix", "--base", "develop",
                                           "--prefix", "jane").stdout)
        self.assertEqual(second["branch"], "jane/bugfix/IOS-2")

    def packages_repo(self, script):
        return self.app_repo(extra={"SwiftPackages.sh": script, "SwiftPackageList.txt": "a\n"})

    def test_packages_retry_once_then_recheck_only_downloads_when_changed(self):
        tries = self.work / "tries"
        repo = self.packages_repo(f'n=$(cat {tries} 2>/dev/null || echo 0); echo $((n+1)) > {tries}\n'
                                  f'[ $((n+1)) -ge 2 ] || exit 1\nmkdir -p SwiftPackages\n')
        args = ("acquire", "IOS-1", "--type", "task", "--base", "develop", "--prefix", "jane")
        first = json.loads(self.run_slots(repo, *args).stdout)
        self.assertEqual(first["packages"], "downloaded")  # first try failed, the retry worked
        self.assertEqual(self.run_slots(repo, "packages", "IOS-1").stdout.strip(), "unchanged")
        (Path(first["worktree"]) / "SwiftPackageList.txt").write_text("a\nb\n")  # e.g. after a merge from base
        self.assertEqual(self.run_slots(repo, "packages", "IOS-1").stdout.strip(), "downloaded")

    def test_packages_failure_after_retry_is_reported_and_exits_4(self):
        repo = self.packages_repo("echo boom >&2\nexit 1\n")
        first = json.loads(self.run_slots(repo, "acquire", "IOS-1", "--type", "task", "--base", "develop",
                                          "--prefix", "jane").stdout)
        self.assertTrue(first["packages"].startswith("failed:"))
        r = self.run_slots(repo, "packages", "IOS-1", check=False)
        self.assertEqual(r.returncode, 4)
        self.assertIn("failed: ", r.stdout)
        self.assertEqual(self.run_slots(repo, "packages", "IOS-404", check=False).returncode, 4)

    def test_resume_keeps_the_tickets_own_uncommitted_edits(self):
        repo = self.app_repo()
        args = ("acquire", "IOS-1", "--type", "task", "--base", "develop", "--prefix", "jane")
        first = json.loads(self.run_slots(repo, *args).stdout)
        (Path(first["worktree"]) / "wip.txt").write_text("half done\n")
        again = json.loads(self.run_slots(repo, *args).stdout)
        self.assertEqual((again["slot"], again["reused"]), ("a", True))
        self.assertTrue((Path(first["worktree"]) / "wip.txt").exists())

    def test_inject_branch_is_recut_from_latest_base(self):
        repo = self.app_repo()
        args = ("acquire", "IOS-9", "--type", "inject", "--base", "develop", "--prefix", "inject",
                "--branch", "inject/Sdk-IOS-9")
        first = json.loads(self.run_slots(repo, *args).stdout)
        self.run_slots(repo, "release", "IOS-9")
        (repo / "new.txt").write_text("moved\n")
        git(repo, "add", "-A", e=env(self.home))
        git(repo, "commit", "-q", "-m", "develop moved", e=env(self.home))
        git(repo, "push", "-q", "origin", "develop", e=env(self.home))
        self.run_slots(repo, *args)
        self.assertTrue((Path(first["worktree"]) / "new.txt").exists())

    def test_dirty_slot_is_skipped_and_reported(self):
        repo = self.app_repo()
        first = json.loads(self.run_slots(repo, "acquire", "IOS-1", "--type", "task", "--base", "develop",
                                          "--prefix", "jane").stdout)
        (Path(first["worktree"]) / "scratch.txt").write_text("keep me\n")
        self.run_slots(repo, "release", "IOS-1")
        r = self.run_slots(repo, "acquire", "IOS-2", "--type", "task", "--base", "develop", "--prefix", "jane",
                           check=False)
        self.assertEqual(r.returncode, 4)
        self.assertIn("scratch.txt", r.stderr)
        self.assertTrue((Path(first["worktree"]) / "scratch.txt").exists())

    def test_package_repo_gets_plain_worktree_removed_on_release(self):
        repo = make_repo(self.work, "blue-utils", branch="master", files={"Package.swift": 'Package(name: "U")'})
        git(repo, "config", "url." + str(self.work / "blue-utils-origin.git") + ".insteadOf",
            "git@github.com:gdncomm/blue-utils.git", e=env(self.home))
        git(repo, "remote", "set-url", "origin", "git@github.com:gdncomm/blue-utils.git", e=env(self.home))
        out = json.loads(self.run_slots(repo, "acquire", "IOS-9", "--type", "story", "--base", "master",
                                        "--prefix", "jane").stdout)
        self.assertEqual((out["kind"], out["simulator"]), ("package", None))
        self.assertTrue(Path(out["worktree"]).is_dir())
        self.assertTrue(out["worktree"].endswith("worktrees/blue-utils/IOS-9"))
        self.run_slots(repo, "release", "IOS-9")
        self.assertFalse(Path(out["worktree"]).exists())

    def test_unknown_repo_stops_and_asks(self):
        repo = make_repo(self.work, "docs")
        git(repo, "config", "url." + str(self.work / "docs-origin.git") + ".insteadOf",
            "git@github.com:gdncomm/docs.git", e=env(self.home))
        git(repo, "remote", "set-url", "origin", "git@github.com:gdncomm/docs.git", e=env(self.home))
        r = self.run_slots(repo, "acquire", "IOS-3", "--type", "task", "--base", "develop", "--prefix", "jane",
                           check=False)
        self.assertEqual(r.returncode, 4)
        self.assertIn("cannot tell app from package", r.stderr)

    def test_legacy_pool_is_kept_for_blibli_ios_app(self):
        repo = make_repo(self.work, "BlibliIOSApp", files={"BlibliMobile-iOS/x": "x"})
        legacy = self.work / "worktrees" / ".slots"
        legacy.mkdir(parents=True)
        _, pool, _ = ticket_slots.pool_dirs("gdncomm/BlibliIOSApp", repo)
        self.assertEqual(pool, self.work / "worktrees")
        _, pool2, _ = ticket_slots.pool_dirs("gdncomm/Other", repo)
        self.assertEqual(pool2, self.work / "worktrees" / "Other")

    def test_repo_slug(self):
        repo = make_repo(self.work, "r")
        for url, want in (("git@github.com:gdncomm/BlibliIOSApp.git", "gdncomm/BlibliIOSApp"),
                          ("https://github.com/gdncomm/blue-core-ios", "gdncomm/blue-core-ios")):
            git(repo, "remote", "set-url", "origin", url, e=env(self.home))
            self.assertEqual(ticket_slots.repo_slug(repo), want)


if __name__ == "__main__":
    unittest.main()
