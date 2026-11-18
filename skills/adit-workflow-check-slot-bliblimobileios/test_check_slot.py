import unittest
from check_slot import ticket_from_branch, classify, ago


class T(unittest.TestCase):
    def test_ticket(self):
        self.assertEqual(ticket_from_branch("adit/improvement/IOS-47206"), "IOS-47206")
        self.assertIsNone(ticket_from_branch("develop"))
        self.assertIsNone(ticket_from_branch("(detached)"))

    def test_classify(self):
        self.assertEqual(classify(False, None, 0), "free")
        self.assertEqual(classify(True, None, 0), "claiming")
        self.assertEqual(classify(True, {"key": "K", "since": 0}, 3600), "busy")
        self.assertEqual(classify(True, {"key": "K", "since": 0}, 25 * 3600), "STALE")

    def test_ago(self):
        self.assertEqual(ago(None, 0), "never")
        self.assertEqual(ago(0, 120), "2m")
        self.assertEqual(ago(0, 3 * 3600), "3h")
        self.assertEqual(ago(0, 2 * 86400), "2d")


if __name__ == "__main__":
    unittest.main()
