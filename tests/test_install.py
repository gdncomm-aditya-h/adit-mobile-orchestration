import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = [s["name"] for s in json.loads((REPO / "skills.json").read_text())["skills"]]


def run(home, *args):
    return subprocess.run([sys.executable, str(REPO / "install.py"), *args, "--home", str(home)],
                          capture_output=True, text=True)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / ".claude").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, *extra):
        return run(self.home, "install", "--skip-deps", "--prefix", "tester", *extra)

    def test_manifest_matches_skill_folders(self):
        on_disk = sorted(p.name for p in (REPO / "skills").iterdir() if (p / "SKILL.md").exists())
        self.assertEqual(sorted(SKILLS), on_disk)

    def test_dry_run_changes_nothing(self):
        r = self.install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(self.home.rglob("*")), [self.home / ".claude"])

    def test_install_links_skills_registers_gate_and_writes_block(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in SKILLS:
            self.assertTrue((self.home / ".claude/skills" / n).is_symlink(), n)
            self.assertTrue((self.home / ".agents/skills" / n / "SKILL.md").exists(), n)
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertEqual(len(settings["hooks"]["PreToolUse"]), 1)
        md = (self.home / ".claude/CLAUDE.md").read_text()
        self.assertIn("tester/<type>/<KEY>", md)
        self.assertNotIn("{{PREFIX}}", md)
        self.assertEqual(json.loads((self.home / ".claude/adit-workflow/uatb-account.json").read_text())["password"], "REPLACE_ME")

    def test_install_twice_is_idempotent_and_keeps_user_content(self):
        (self.home / ".claude/CLAUDE.md").write_text("# mine\n\nkeep me\n")
        (self.home / ".claude/settings.json").write_text(json.dumps({"theme": "dark"}))
        self.install()
        self.install()
        md = (self.home / ".claude/CLAUDE.md").read_text()
        self.assertEqual(md.count("adit-mobile-orchestration:begin"), 1)
        self.assertIn("keep me", md)
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(len(settings["hooks"]["PreToolUse"]), 1)

    def test_existing_real_skill_dir_is_backed_up(self):
        old = self.home / ".claude/skills" / SKILLS[0]
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("old copy")
        self.install()
        self.assertTrue((self.home / ".claude/skills" / SKILLS[0]).is_symlink())
        backups = list((self.home / ".claude/adit-workflow/backups").rglob("SKILL.md"))
        self.assertEqual([b.read_text() for b in backups], ["old copy"])

    def test_invalid_settings_json_is_left_alone(self):
        (self.home / ".claude/settings.json").write_text("{not json")
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.home / ".claude/settings.json").read_text(), "{not json")
        self.assertIn("not valid JSON", r.stdout)

    def test_uninstall_removes_what_install_added(self):
        (self.home / ".claude/CLAUDE.md").write_text("keep me\n")
        self.install()
        r = run(self.home, "uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list((self.home / ".claude/skills").iterdir()), [])
        self.assertFalse((self.home / ".agents/skills" / SKILLS[0]).exists())
        self.assertEqual((self.home / ".claude/CLAUDE.md").read_text().strip(), "keep me")
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertEqual(settings["hooks"]["PreToolUse"], [])

    def test_codex_target_writes_agents_md_and_no_claude_block(self):
        (self.home / ".codex").mkdir()
        r = self.install("--target", "codex")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.home / ".codex/skills" / SKILLS[0]).is_symlink())
        self.assertIn("experimental", (self.home / ".codex/AGENTS.md").read_text())
        self.assertFalse((self.home / ".claude/CLAUDE.md").exists())

    def test_doctor_reports_failure_before_and_pass_for_skills_after(self):
        before = run(self.home, "doctor", "--target", "claude", "--json")
        self.assertEqual(before.returncode, 1)
        self.install()
        rows = json.loads(run(self.home, "doctor", "--target", "claude", "--json").stdout)
        by_item = {r["item"]: r["status"] for r in rows}
        self.assertEqual(by_item["skills installed"], "ok")
        self.assertEqual(by_item["ticket-flow gate registered"], "ok")
        self.assertEqual(by_item["CLAUDE.md block"], "ok")


if __name__ == "__main__":
    unittest.main()
