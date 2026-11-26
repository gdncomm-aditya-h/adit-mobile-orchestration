import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from gitfixture import SCRIPTS, env, make_repo

sys.path.insert(0, str(SCRIPTS))
import doctor  # noqa: E402


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"

    def tearDown(self):
        self.tmp.cleanup()

    def run_doctor(self, cwd):
        r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py")], cwd=cwd, capture_output=True, text=True,
                           env=env(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_runs_outside_a_repo_and_reports_defaults(self):
        out = self.run_doctor(self.tmp.name)
        self.assertIn("config", out)
        self.assertIn("none yet", out)
        self.assertIn("not inside a git checkout", out)

    def test_reports_expired_gate_marker(self):
        active = self.home / "state" / "gate" / "active"
        active.mkdir(parents=True)
        (active / "IOS-7").write_text(str(time.time() - 9 * 24 * 3600))
        self.assertIn("EXPIRED", self.run_doctor(self.tmp.name))

    def test_reports_repo_profile(self):
        repo = make_repo(self.tmp.name, "lib", files={"Package.swift": 'Package(name: "L")'})
        self.assertIn("package", self.run_doctor(repo))

    def test_pool_dir_prints_repo_pool(self):
        repo = make_repo(self.tmp.name, "lib2", files={"Package.swift": 'Package(name: "L")'})
        r = subprocess.run([sys.executable, str(SCRIPTS / "ticket_slots.py"), "--repo", "gdncomm/lib2", "pool-dir"],
                           cwd=repo, capture_output=True, text=True, env=env(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().endswith("worktrees/lib2"))


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["IOS_TICKET_FLOW_HOME"] = self.tmp.name
        self.calls = 0
        self.good = False
        self.orig = doctor.check_tools
        doctor.check_tools = self.fake_tools

    def tearDown(self):
        doctor.check_tools = self.orig
        os.environ.pop("IOS_TICKET_FLOW_HOME", None)
        self.tmp.cleanup()

    def fake_tools(self):
        self.calls += 1
        if self.good:
            return [("git", "ok", ""), ("gh", "ok", ""), ("gh auth", "ok", ""), ("xcodebuild", "ok", "")]
        return [("git", "ok", ""), ("gh", "MISSING", "x"), ("gh auth", "NOT LOGGED IN", ""), ("xcodebuild", "ok", "")]

    def test_blockers_only_for_needed_groups(self):
        rows = self.fake_tools()
        self.assertEqual(doctor.preflight(["git"], rows), [])
        self.assertEqual(doctor.preflight(["xcode"], rows), [])
        lines = doctor.preflight(["git", "gh"], rows)
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(l.startswith("BLOCKER: gh") for l in lines))
        self.assertIn("brew install gh", lines[0])
        self.assertIn("gh auth login", lines[1])

    def test_failed_checks_are_never_cached(self):
        doctor.machine_rows()
        doctor.machine_rows()
        self.assertEqual(self.calls, 2)  # a fixed `gh auth login` must show up on the very next preflight

    def test_result_is_cached_for_a_day(self):
        self.good = True
        doctor.machine_rows()
        doctor.machine_rows()
        self.assertEqual(self.calls, 1)
        doctor.machine_rows(now=time.time() + 25 * 3600)
        self.assertEqual(self.calls, 2)
        doctor.machine_rows(fresh=True)
        self.assertEqual(self.calls, 3)

    def test_new_plugin_version_invalidates_cache(self):
        self.good = True
        doctor.machine_rows()
        orig = doctor.plugin_version
        doctor.plugin_version = lambda: "9.9.9"
        try:
            doctor.machine_rows()
        finally:
            doctor.plugin_version = orig
        self.assertEqual(self.calls, 2)

    def test_stale_gate_is_a_warning_not_a_blocker(self):
        active = Path(self.tmp.name) / "state" / "gate" / "active"
        active.mkdir(parents=True)
        (active / "IOS-5").write_text(str(time.time() - 9 * 24 * 3600))
        lines = doctor.preflight(["git"], self.fake_tools())
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("WARN: gate IOS-5"))

    def test_gate_dir_in_active_folder_does_not_crash(self):
        (Path(self.tmp.name) / "state" / "gate" / "active" / "tmp").mkdir(parents=True)
        self.assertEqual(doctor.check_gate(), [("gate", "ok", "no stale markers")])

    def test_cli_is_silent_and_exits_zero_when_ready(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py"), "--preflight", "--need", "git"],
                           capture_output=True, text=True, env=env(self.tmp.name))
        self.assertEqual((r.returncode, r.stdout), (0, ""))


class PluginTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plugins = Path(self.tmp.name) / "plugins"
        self.plugins.mkdir()
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.tmp.cleanup()

    def write(self, installed, markets=("agent-plugins", "ponytail", "ecc", "claude-plugins-official")):
        (self.plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {k: [] for k in installed}}))
        (self.plugins / "known_marketplaces.json").write_text(json.dumps({m: {} for m in markets}))

    def status(self):
        return {n: s for n, s, _ in doctor.check_plugins()}

    def test_all_installed_is_clean(self):
        self.write(["mobileapps-foundation@agent-plugins", "superpowers@claude-plugins-official",
                    "ponytail@ponytail", "ecc@ecc"])
        self.assertTrue(all(s == "ok" for s in self.status().values()))
        self.assertEqual(doctor.missing_plugins(), [])
        self.assertEqual(doctor.preflight(["plugins"], doctor.check_plugins()), [])

    def test_missing_required_plugin_blocks_and_optional_does_not(self):
        self.write(["superpowers@claude-plugins-official", "ecc@ecc"])
        st = self.status()
        self.assertEqual((st["mobileapps-foundation"], st["ponytail"]), ("MISSING", "not installed"))
        lines = doctor.preflight(["plugins"], doctor.check_plugins())
        self.assertEqual(len(lines), 1)
        self.assertIn("BLOCKER: mobileapps-foundation", lines[0])
        self.assertIn("/ios-orchestration-setup", lines[0])

    def test_no_audit_engine_when_ponytail_and_ecc_are_both_missing(self):
        self.write(["mobileapps-foundation@agent-plugins"])
        self.assertEqual(self.status()["audit engine"], "not installed")

    def test_install_commands_add_the_marketplace_only_when_unknown(self):
        self.write([], markets=("agent-plugins",))
        by_name = {m["name"]: m for m in doctor.missing_plugins()}
        self.assertEqual(by_name["mobileapps-foundation"]["commands"],
                         [["claude", "plugin", "install", "mobileapps-foundation@agent-plugins"]])
        self.assertEqual(by_name["ponytail"]["commands"],
                         [["claude", "plugin", "marketplace", "add", "DietrichGebert/ponytail"],
                          ["claude", "plugin", "install", "ponytail@ponytail"]])

    def test_unreadable_plugin_list_never_blocks(self):
        self.assertEqual([s for _, s, _ in doctor.check_plugins()], ["unknown"])
        self.assertIsNone(doctor.missing_plugins())
        self.assertEqual(doctor.preflight(["plugins"], doctor.check_plugins()), [])

    def test_plugins_cli_prints_json(self):
        self.write(["mobileapps-foundation@agent-plugins"])
        r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py"), "--plugins"], capture_output=True, text=True,
                           env=dict(os.environ))
        out = json.loads(r.stdout)
        self.assertTrue(out["checked"])
        self.assertEqual({m["name"] for m in out["missing"]}, {"superpowers", "ponytail", "ecc"})


if __name__ == "__main__":
    unittest.main()
