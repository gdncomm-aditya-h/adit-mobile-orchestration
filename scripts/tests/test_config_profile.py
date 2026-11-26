import os
import sys
import tempfile
import unittest
from pathlib import Path

from gitfixture import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import flowconfig  # noqa: E402
import repo_profile  # noqa: E402

APP_PBX = "x = com.apple.product-type.application; y"
LIB_PBX = "x = com.apple.product-type.framework; y"


def write(root, rel, text=""):
    f = Path(root) / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["IOS_TICKET_FLOW_HOME"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("IOS_TICKET_FLOW_HOME", None)
        self.tmp.cleanup()

    def test_defaults_when_missing(self):
        cfg = flowconfig.load()
        self.assertEqual(cfg["defaultRepo"], "gdncomm/BlibliIOSApp")
        self.assertEqual(cfg["jiraProject"], "IOS")
        self.assertIsNone(cfg["branchPrefix"])

    def test_corrupt_file_falls_back(self):
        write(self.tmp.name, "config.json", "{not json")
        self.assertEqual(flowconfig.load()["defaultRepo"], "gdncomm/BlibliIOSApp")

    def test_set_and_reload(self):
        cfg = flowconfig.load()
        flowconfig.set_value(cfg, "defaultRepo", "gdncomm/blue-core-ios")
        flowconfig.set_value(cfg, "branchPrefix", "jane")
        flowconfig.set_value(cfg, "slots.gdncomm/BlibliSellerChatIOS", "2")
        flowconfig.save(cfg)
        again = flowconfig.load()
        self.assertEqual(again["defaultRepo"], "gdncomm/blue-core-ios")
        self.assertEqual(again["branchPrefix"], "jane")
        self.assertEqual(again["slots"]["gdncomm/BlibliSellerChatIOS"], 2)

    def test_rejects_bad_values(self):
        cfg = flowconfig.load()
        for key, value in (("defaultRepo", "not a repo"), ("branchPrefix", "a b"), ("jiraProject", "ios"),
                           ("slots.gdncomm/x", "0"), ("profile.gdncomm/x", "weird"), ("nope", "1")):
            with self.assertRaises(ValueError, msg=key):
                flowconfig.set_value(cfg, key, value)

    def test_slot_counts(self):
        cfg = flowconfig.load()
        self.assertEqual(flowconfig.slots_for(cfg, "gdncomm/BlibliIOSApp", "app"), 4)
        self.assertEqual(flowconfig.slots_for(cfg, "gdncomm/BlibliSellerChatIOS", "app"), 1)
        self.assertEqual(flowconfig.slots_for(cfg, "gdncomm/blue-core-ios", "package"), 0)


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_known_app_layout(self):
        write(self.root, "BlibliMobile-iOS/placeholder")
        p = repo_profile.detect(self.root, "BlibliIOSApp")
        self.assertEqual((p["kind"], p["appDir"], p["workspace"]), ("app", "BlibliMobile-iOS", "BlibliMobile-iOS.xcworkspace"))

    def test_generic_app_detected_from_project_file(self):
        write(self.root, "Chat.xcodeproj/project.pbxproj", APP_PBX)
        write(self.root, "Chat.xcworkspace/contents.xcworkspacedata")
        p = repo_profile.detect(self.root, "BlibliSellerChatIOS")
        self.assertEqual((p["kind"], p["appDir"], p["workspace"]), ("app", ".", "Chat.xcworkspace"))

    def test_package_with_scheme_from_manifest(self):
        write(self.root, "Package.swift", 'let package = Package(\n    name: "BlueIOSUtils",\n')
        p = repo_profile.detect(self.root, "blue-ios-utils")
        self.assertEqual((p["kind"], p["scheme"]), ("package", "BlueIOSUtils"))

    def test_library_project_is_package(self):
        write(self.root, "blue-core-ios.xcodeproj/project.pbxproj", LIB_PBX)
        write(self.root, "Package.swift", 'Package(name: "BlueCore")')
        self.assertEqual(repo_profile.detect(self.root, "blue-core-ios")["kind"], "package")

    def test_app_project_beats_package_manifest(self):
        write(self.root, "App.xcodeproj/project.pbxproj", APP_PBX)
        write(self.root, "Package.swift", 'Package(name: "X")')
        self.assertEqual(repo_profile.detect(self.root, "x")["kind"], "app")

    def test_pods_projects_are_ignored(self):
        write(self.root, "Pods/Pods.xcodeproj/project.pbxproj", APP_PBX)
        write(self.root, "Package.swift", 'Package(name: "X")')
        self.assertEqual(repo_profile.detect(self.root, "x")["kind"], "package")

    def test_app_project_two_folders_deep(self):
        write(self.root, "ios/App/App.xcodeproj/project.pbxproj", APP_PBX)
        p = repo_profile.detect(self.root, "x")
        self.assertEqual((p["kind"], p["appDir"], p["workspace"]), ("app", "ios/App", None))

    def test_sdk_with_example_app_is_still_a_package(self):
        write(self.root, "Package.swift", 'Package(name: "X")')
        write(self.root, "Example/Demo.xcodeproj/project.pbxproj", APP_PBX)
        write(self.root, "Carthage/Checkouts/Dep/Dep.xcodeproj/project.pbxproj", APP_PBX)
        write(self.root, "SwiftPackages/Dep/Dep.xcodeproj/project.pbxproj", APP_PBX)
        self.assertEqual(repo_profile.detect(self.root, "x")["kind"], "package")

    def test_unknown(self):
        write(self.root, "README.md", "hi")
        self.assertEqual(repo_profile.detect(self.root, "docs")["kind"], "unknown")


if __name__ == "__main__":
    unittest.main()
