#!/usr/bin/env python3
"""Tell an iOS repo checkout apart: full app flow, or a Swift package without an app.

  repo_profile.py detect [<checkout dir>]    print the profile as JSON (default: current directory)

kind "app"      has an application target. Slots, simulator, login and click tests apply.
kind "package"  Package.swift or a library project with no application target. Build and test only.
kind "unknown"  nothing recognisable. Callers must ask the engineer, never guess.

BlibliIOSApp is built in because its layout is fixed and known. Every other repo is detected from files.
"""
import json
import os
import re
import sys
from pathlib import Path

APP_PRODUCT = "com.apple.product-type.application"

KNOWN = {
    "BlibliIOSApp": {
        "kind": "app",
        "appDir": "BlibliMobile-iOS",
        "workspace": "BlibliMobile-iOS.xcworkspace",
        "packagesScript": "SwiftPackages.sh",
        "swiftlint": "../tools/swiftlint/swiftlint",
        "unitTarget": "BliBliMobile-SwiftTesting",
        "uiTarget": "BlibliMobile_XCUITest",
    },
}


def has_app_target(pbxproj):
    try:
        return APP_PRODUCT in pbxproj.read_text(errors="ignore")
    except OSError:
        return False


SKIP = {"Pods", "DerivedData", ".build", "Carthage", "SwiftPackages", ".git"}
SAMPLE = {"Example", "Examples", "Demo", "Demos", "Sample", "Samples", "Playground", "Playgrounds"}


def find_app_project(root):
    """First .xcodeproj with an application target, at any depth. Skips dependency, build and sample-app folders."""
    for dirpath, dirs, _ in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP | SAMPLE and not d.startswith(".") or d.endswith(".xcodeproj"))
        for d in list(dirs):
            if d.endswith(".xcodeproj"):
                dirs.remove(d)
                if has_app_target(Path(dirpath) / d / "project.pbxproj"):
                    return Path(dirpath) / d
    return None


def find_one(root, pattern, depth=1):
    """First match for a glob in root or one folder below it. Skips Pods and build folders."""
    skip = SKIP
    hits = sorted(root.glob(pattern))
    if not hits and depth:
        for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in skip and not p.name.startswith(".")):
            hits = sorted(d.glob(pattern))
            if hits:
                break
    return hits[0] if hits else None


def detect(root, repo_name=None):
    root = Path(root)
    name = repo_name or root.name
    if name in KNOWN and (root / KNOWN[name]["appDir"]).is_dir():
        return dict(KNOWN[name], name=name)
    proj = find_one(root, "*.xcodeproj")
    ws = find_one(root, "*.xcworkspace")
    pkg = (root / "Package.swift").exists()
    app_proj = find_app_project(root)
    base = {"name": name, "appDir": None, "workspace": ws.name if ws else None,
            "project": proj.name if proj else None, "packagesScript": None,
            "swiftlint": None, "unitTarget": None, "uiTarget": None}
    if app_proj:
        app_dir = app_proj.parent
        ws_here = sorted(app_dir.glob("*.xcworkspace"))
        base.update(kind="app", appDir=str(app_dir.relative_to(root)) if app_dir != root else ".",
                    workspace=ws_here[0].name if ws_here else None, project=app_proj.name)
        sl = app_dir / "../tools/swiftlint/swiftlint"
        base["swiftlint"] = "../tools/swiftlint/swiftlint" if sl.exists() else None
        base["packagesScript"] = "SwiftPackages.sh" if (app_dir / "SwiftPackages.sh").exists() else None
        return base
    if pkg or proj:
        base["kind"] = "package"
        base["scheme"] = package_scheme(root, name)
        return base
    base["kind"] = "unknown"
    return base


def package_scheme(root, name):
    """Scheme to pass to xcodebuild. A Swift package builds with its package name; fall back to the repo name."""
    try:
        m = re.search(r'name:\s*"([^"]+)"', (root / "Package.swift").read_text(), re.S)
        return m.group(1) if m else name
    except OSError:
        return name


def main(argv):
    if len(argv) >= 2 and argv[1] == "detect":
        root = Path(argv[2] if len(argv) > 2 else ".").resolve()
        print(json.dumps(detect(root), indent=2))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
