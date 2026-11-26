import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYNC = REPO / "tools" / "sync_from_pr.sh"


def sync(src, *args, script=SYNC):
    return subprocess.run(["sh", str(script), *args], capture_output=True, text=True,
                          env={**os.environ, "SRC_DIR": str(src)})


class MirrorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "agent-plugins"
        plugin = self.src / "plugins/mobileapps/ios"
        shutil.copytree(REPO / "scripts", plugin / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "skills", plugin / "skills", ignore=shutil.ignore_patterns("__pycache__"))
        (plugin / "skills" / "swift-codegen").mkdir()  # a sibling plugin skill that must not be mirrored
        (plugin / "skills" / "swift-codegen" / "SKILL.md").write_text("other\n")
        shutil.copytree(REPO / "hooks", plugin / "hooks")
        self.plugin = plugin

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_copy_passes_and_ignores_other_plugin_skills(self):
        r = sync(self.src, "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_drift_is_reported(self):
        (self.plugin / "scripts" / "doctor.py").write_text("# changed\n")
        r = sync(self.src, "--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("differs: scripts", r.stdout)

    def test_sync_copies_the_source_into_a_repo_copy(self):
        work = Path(self.tmp.name) / "repo"
        (work / "tools").mkdir(parents=True)
        shutil.copy(SYNC, work / "tools" / "sync_from_pr.sh")
        (work / "scripts").mkdir()
        (work / "scripts" / "stale.py").write_text("old\n")
        script = work / "tools" / "sync_from_pr.sh"  # always the copy: the script writes next to itself
        r = sync(self.src, script=script)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sync(self.src, "--check", script=script).returncode, 0)
        self.assertFalse((work / "scripts" / "stale.py").exists())
        self.assertFalse((work / "skills" / "swift-codegen").exists())


if __name__ == "__main__":
    unittest.main()
