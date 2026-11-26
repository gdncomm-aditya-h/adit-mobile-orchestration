## What changed

<!-- One or two sentences, from the point of view of someone using the skills. -->

## How you checked it

<!-- Tests run, or the ticket you ran the changed flow on. -->

## Checklist

- [ ] `python3 -m unittest discover -s scripts/tests` and `python3 -m unittest discover -s tests` pass
- [ ] `tools/sync_from_pr.sh --check` prints `identical` (the mirrored files were not edited by hand)
- [ ] `tools/build_diagram.py` and the README table match the change, and the diagrams are rebuilt
- [ ] No credentials, tokens or personal IDs in the diff
- [ ] `CHANGELOG.md` and `VERSION` updated if users will notice
