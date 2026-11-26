---
name: ios-orchestration-sdk-inject-test
description: Test a verified change to an iOS SDK or library inside the latest develop of gdncomm/BlibliIOSApp. Either injects the engineer's SDK worktree into a warm app slot and builds the app (reporting compile errors only), or prints the exact steps so the engineer tests it themselves. Never fixes app code, never pushes. Use from ios-orchestration-ticket-to-pr for SDK repos, or for "test my SDK change in the app" and /ios-orchestration-sdk-inject-test.
argument-hint: [build | steps] [--sdk owner/repo] [--key TICKET-KEY]
---

# sdk-inject-test

Run inside the SDK's ticket worktree (or pass `--sdk`). Scripts are in `<skill_dir>/../../scripts/` (`<skill_dir>` is the base directory shown when this skill loads). The mode is the argument: `build` (we inject and build with a warm slot) or `steps` (print the steps, do nothing). No argument: ask once with `AskUserQuestion`, as in `ios-orchestration-ticket-to-pr` step 6.

Report only. If the app fails to compile because the SDK change broke an API, list the errors and stop. Never edit app code, never draft an app-side fix, never push. This step never changes the verified state of the SDK ticket.

Honest limit: how an SDK reaches the app differs per SDK, and I have not verified every case. Do exactly what is described for the mechanism you find. If it is not one of them, switch to `steps` and say so.

## 0. Preflight
Run `python3 <scripts>/doctor.py --preflight --need git,gh,xcode`. Silent means ready (tool results are cached for 24 hours). A `BLOCKER:` line means this skill cannot run: show it with its fix and stop. `WARN:` lines: mention once and continue.

## 1. Find how the app consumes this SDK
Read `gdncomm/BlibliIOSApp` at `develop` without a clone: `gh api repos/gdncomm/BlibliIOSApp/contents/<path>?ref=develop` for `BlibliMobile-iOS/SwiftPackageList.txt`, the `BlibliMobile-iOS.xcodeproj/project.pbxproj` package references, and `BlibliMobile-iOS/Podfile.lock`. Match the SDK's repo name.
- **A. SwiftPackageList.txt**: a line `git@github.com:gdncomm/<name>.git, <version>`. The app builds it from the cached clone `BlibliMobile-iOS/SwiftPackages/<name>`.
- **B. Remote Swift package**: an `XCRemoteSwiftPackageReference "<name>"` in the project, not in the list.
- **C. CocoaPods**: the name is in `Podfile.lock`.
- None found: say the SDK is not consumed by the app under that name, and stop.
Also read the other lines of `SwiftPackageList.txt` and list SDKs whose version equals this SDK's pinned version. They move in lockstep, so tell the engineer these may need matching versions. Do not choose versions for them.

## 2. `steps` mode
Print, for the mechanism found, the commands below with the engineer's real paths filled in, then stop. Mention that the throwaway branch must never be pushed.

## 3. `build` mode (mechanism A or B only; C: print steps)
1. Get an app slot on latest `develop` with a throwaway branch:
   `python3 <scripts>/ticket_slots.py --repo gdncomm/BlibliIOSApp acquire <KEY> --type inject --base develop --prefix inject --branch inject/<SDK>-<KEY>`
   (Use the SDK's ticket key. State is kept per repo, so this does not collide with the SDK ticket.) Exit 3: every app slot is busy, report it and fall back to `steps`. Exit 4: report the reason and stop.
2. Work in the returned `worktree`, inside `BlibliMobile-iOS/`. Do not run `SwiftPackages.sh download` or `reset` while the SDK is injected.
3. Inject.
   - **A**: copy, never symlink. `SwiftPackages.sh` runs `git stash` and `git clean -f -x` inside a package folder, which would hit the engineer's SDK worktree through a link. Run: `mv SwiftPackages/<name> SwiftPackages/<name>.orig` then `rsync -a --exclude .git <sdk worktree>/ SwiftPackages/<name>/`.
   - **B**: add the SDK folder to `BlibliMobile-iOS.xcworkspace/contents.xcworkspacedata` as `<FileRef location="absolute:<sdk worktree>"></FileRef>`. Xcode then resolves that local package in place of the remote one of the same name. This edits a tracked file; step 6 restores it.
4. Build the app scheme with `xcodebuild build -workspace <workspace> -scheme <scheme> -destination 'platform=iOS Simulator,id=<udid>'` (scheme and workspace as in `ios-orchestration-verify-ticket` step 1; `<udid>` from the acquire output). Run it in the background with a log file. Never pass `-derivedDataPath`, never clean, never use `CODE_SIGNING_ALLOWED=NO`.
5. Report: built, or the compile errors (file:line and message, at most 20, shortest decisive lines), plus the lockstep list from step 1.
6. Restore, always, even after a failure:
   - **A**: `rm -rf SwiftPackages/<name>` then `mv SwiftPackages/<name>.orig SwiftPackages/<name>`. Check that `SwiftPackages/<name>/.git` exists again. If the original is missing, tell the engineer: the next ticket in this slot would silently reuse the injected copy, so do not release the slot until it is fixed.
   - **B**: `git checkout -- BlibliMobile-iOS.xcworkspace/contents.xcworkspacedata`, and check `git status --porcelain` is empty.
7. Release the slot: `python3 <scripts>/ticket_slots.py --repo gdncomm/BlibliIOSApp release <KEY>`. The gate hook denies any push or PR from `inject/*`.

Final line for the caller: `app integration: built` or `app integration: failed (N errors)` or `app integration: not run (<reason>)`.
