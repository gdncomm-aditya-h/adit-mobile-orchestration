import argparse
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ticket_slots", REPO / "hooks" / "ticket-slots.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)


class PackagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.pool, self.st = root / "pool", root / "pool" / ".slots"
        self.wt = self.pool / "slot-a"
        self.proj = self.wt / ts.APP
        self.proj.mkdir(parents=True)
        self.st.mkdir()
        (self.proj / "SwiftPackageList.txt").write_text("a\n")
        (self.st / "a.json").write_text(json.dumps({"key": "IOS-1", "since": 0}))
        self.tries = root / "tries"
        self.orig = ts.pool_dirs
        ts.pool_dirs = lambda: (None, self.pool, self.st)

    def tearDown(self):
        ts.pool_dirs = self.orig
        self.tmp.cleanup()

    def script(self, body):
        (self.proj / "SwiftPackages.sh").write_text(body)

    def recheck(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ts.recheck_packages(argparse.Namespace(key="IOS-1"))
        return out.getvalue().strip()

    def test_retries_once_then_downloads_only_when_the_package_files_change(self):
        self.script(f"n=$(cat {self.tries} 2>/dev/null || echo 0); echo $((n+1)) > {self.tries}\n"
                    f"[ $((n+1)) -ge 2 ] || exit 1\nmkdir -p SwiftPackages\n")
        self.assertEqual(ts.packages(self.wt, self.st, "a"), "downloaded")  # first try failed, the retry worked
        self.assertEqual(self.recheck(), "unchanged")
        (self.proj / "SwiftPackageList.txt").write_text("a\nb\n")  # e.g. after a merge from base
        self.assertEqual(self.recheck(), "downloaded")

    def test_failure_after_the_retry_is_reported_and_exits_4(self):
        self.script("echo boom >&2\nexit 1\n")
        self.assertTrue(ts.packages(self.wt, self.st, "a").startswith("failed:"))
        with self.assertRaises(SystemExit) as e:
            self.recheck()
        self.assertEqual(e.exception.code, 4)

    def test_unknown_ticket_is_an_error(self):
        with self.assertRaises(ts.Fail):
            ts.recheck_packages(argparse.Namespace(key="IOS-404"))


if __name__ == "__main__":
    unittest.main()
