#!/usr/bin/env python3
"""Generate the target-design ticket-to-PR flow diagram (SVG).

  python3 scripts/build_flow_diagram.py                 # standalone SVG -> assets/ticket-to-pr-workflow.svg
  python3 scripts/build_flow_diagram.py --out X.svg     # standalone SVG elsewhere
  python3 scripts/build_flow_diagram.py --inline X.html # fragment without its own theme variables,
                                                        # for pages that already define them

Edit ITEMS when the flow changes. Chip and gate styles match the presentation page,
so light and dark mode both work (standalone files carry their own variables).
"""
import argparse
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "assets" / "ticket-to-pr-workflow.svg"

W = 940
NODE_X, NODE_W = 110, 330
SPINE = NODE_X + 165
CHIP_X, CHIP_MAX = 490, 920
GAP = 44
CHAR = 6.7  # mono 11px advance, close to IBM Plex Mono and Menlo

VARS = """
:root{--bg:#f3f5f8;--surface:#fff;--line:#c4ccd6;--fg:#18202a;--muted:#5a6878;--team:#2457c5;--own:#0b7a6b;--sp:#6b46c1;--pt:#b0397f;--ag:#6d6f12;--warn:#b86e00;--bad:#c0392b;--ok:#1f8a4c;--tool:#4b5968;--sans:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#0e1319;--surface:#161c24;--line:#2d3743;--fg:#e3e9f0;--muted:#92a0b0;--team:#7fa6ff;--own:#4fd1bd;--sp:#b79cff;--pt:#ff9ad0;--ag:#c9cd5b;--warn:#f0b04a;--bad:#ff8a7a;--ok:#5fd38d;--tool:#a9b6c4}}
"""

CSS = """
svg text{font-family:var(--sans)}
.tx{font-size:11.5px;fill:var(--fg)}
.node{fill:var(--surface);stroke:var(--line);stroke-width:1.5}
.nt{font-size:13px;font-weight:600;fill:var(--fg)}
.ns{font-size:11px;fill:var(--muted)}
.gu{fill:color-mix(in srgb,var(--warn) 28%,var(--surface));stroke:var(--warn);stroke-width:1.8}
.ga{fill:var(--surface);stroke:var(--warn);stroke-width:1.8;stroke-dasharray:5 3}
.ln{stroke:var(--muted);stroke-width:1.5;fill:none}.arh{fill:var(--muted)}
.dash{stroke:var(--line);stroke-width:1.2;stroke-dasharray:3 3}
.trunk{stroke:var(--line);stroke-width:1.2}
.hair{stroke:var(--line);stroke-width:1;opacity:.55;stroke-dasharray:2 4}
.pin{fill:var(--bg);stroke:var(--fg);stroke-width:1.5}
.br{stroke:var(--line);stroke-width:2}
.ph{font-size:10.5px;letter-spacing:.08em;fill:var(--muted);font-weight:600}
.band-bad{fill:color-mix(in srgb,var(--bad) 22%,var(--surface));stroke:var(--bad)}
.band-ok{fill:color-mix(in srgb,var(--ok) 22%,var(--surface));stroke:var(--ok)}
.band-off{fill:var(--surface);stroke:var(--line)}
.bandt{font-size:10px;font-weight:600;letter-spacing:.06em;fill:var(--fg)}
.bl{fill:var(--bad)}.blt{font-size:11px;font-weight:600;fill:#fff}
.note{font-size:11px;font-style:italic;fill:var(--muted)}
.opt{fill:var(--surface);stroke:var(--line);stroke-width:1.5}
.optg{fill:color-mix(in srgb,var(--warn) 10%,var(--surface));stroke:var(--warn);stroke-width:1.5}
.optb{fill:color-mix(in srgb,var(--bad) 12%,var(--surface));stroke:var(--bad);stroke-width:1.5}
.chip{--c:var(--tool)}
.chip.team{--c:var(--team)}.chip.pt{--c:var(--pt)}.chip.ag{--c:var(--ag)}.chip.own{--c:var(--own)}.chip.sp{--c:var(--sp)}.chip.hook{--c:var(--bad)}.chip.hook0{--c:var(--muted)}.chip.hookok{--c:var(--ok)}
.chip rect{fill:color-mix(in srgb,var(--c) 13%,var(--surface));stroke:var(--c);stroke-width:1.3}
.chip text{fill:var(--c);font:500 11px var(--mono)}
.ttl{font-size:20px;font-weight:600;fill:var(--fg)}
.lg{font-size:11px;fill:var(--muted)}
"""

P = "ios-orchestration-"

# kinds: node (spine stage), branch (header stage plus parallel boxes)
# chips: (class, text); class one of own team sp pt ag tool hook hook0 hookok
ITEMS = [
    dict(id="entry", kind="node", title="Entry: implement <KEY>",
         sub="Skill " + P + "ticket-to-pr owns the whole flow. Plugin hooks stay passive until armed.",
         chips=[("own", P + "ticket-to-pr"), ("hook0", "hooks.json PreToolUse")]),
    dict(id="resolve", kind="node", title="Ask which repo, then which version", stop=True,
         sub="Always asks the repo first, then the version. Base is release/v<Fix Version> when it exists, else the default branch. Key matches [A-Z]+-\\d+, else ask for the ticket URL.",
         chips=[("own", P + "flow-config"), ("tool", "gh repo view")],
         note="Default gdncomm/BlibliIOSApp. Config in ~/.claude/ios-ticket-flow/config.json."),
    dict(id="doctor", kind="node", title="Quick health check",
         sub="Tools, auth, plugins and repo profile (app or package) are present. A missing required plugin points to setup.",
         chips=[("own", P + "flow-doctor"), ("own", P + "setup"), ("tool", "doctor.py --preflight"), ("tool", "repo_profile.py"), ("tool", "gh auth, Jira MCP")],
         note="setup installs missing plugins only after a yes, never during a ticket run."),
    dict(id="cap", kind="branch", title="Client capability", gate="auto",
         sub="Detected once per run.",
         boxes=[("App client", ["Switch permission mode.", "Simulator control for click tests,", "design and wording checks."], "opt"),
                ("CLI client", ["Tell the dev to press Shift+Tab.", "Click, design and wording checks", "become needs manual run."], "opt")]),
    dict(id="plan", kind="node", title="Plan mode, read ticket",
         sub="EnterPlanMode, read-only. Bug moves to Initial Review. Brainstorm, pick one approach.",
         chips=[("tool", "EnterPlanMode"), ("tool", "Jira MCP"), ("sp", "superpowers:brainstorming")]),
    dict(id="draft", kind="node", title="Draft the plan with plan-from-ticket", stop=True,
         sub="Explores the code with a subagent, asks only blocking questions, writes the draft: steps, risks, before and after.",
         chips=[("own", P + "plan-from-ticket"), ("ag", "Explore subagent"),
                ("team", "mobileapps-foundation:repo-index")],
         note="Never implements. Non-blocking gaps become assumptions in the plan."),
    dict(id="enrich", kind="node", title="Enrich the plan with enrich-plan", stop=True,
         sub="DoD traceability, test cases, design and copy references, reviewer pass. Saved as one plan.",
         chips=[("own", P + "enrich-plan"), ("team", "mobileapps-foundation:figma-mcp"),
                ("team", "mobileapps-foundation:localization"), ("ag", "ecc:planner"),
                ("ag", "general-purpose")],
         note="Blockers (missing DoD, design or copy) are asked once, in one batch."),
    dict(id="approve", kind="node", title="Plan approval", gate="you",
         sub="ExitPlanMode. The third planned stop, after repo and version. Everything after it runs without questions.",
         chips=[("tool", "ExitPlanMode")]),
    dict(id="dev", kind="node", title="Move ticket to its in-work status",
         sub="First step after approval. Story, Task: In Development. Bug: In Progress. Read from the workflow.",
         chips=[("tool", "Jira listJiraIssueTransitions"), ("tool", "Jira transitionJiraIssue")],
         note="Prints one line: moved, or not moved and why. A failed move is reported, not a stop. App client then switches to auto mode."),
    dict(id="profile", kind="branch", title="Slot or worktree by repo profile", gate="auto",
         sub="Branch <prefix>/<type>/<KEY>.",
         boxes=[("App repo: slot pool", ["Free slot of a to d (4 for BlibliIOSApp).", "Own DerivedData, simulator and packages:", "warm, so the build is incremental.", "Packages download when changed, retried once, never asked."], "opt"),
                ("Package repo: worktree", ["One plain worktree per ticket.", "No simulator, no login, no click tests.", "Removed on release."], "opt")]),
    dict(id="arm", kind="node", title="Save plan, arm the gate",
         sub="mark-active. From here commit, push and PR create are denied until verified.",
         chips=[("own", P + "enrich-plan (Finalize)"), ("hook", "ticket_gate.py mark-active"), ("tool", "ticket_slots.py acquire")],
         arm=True),
    dict(id="impl", kind="node", title="Implement in a sub-agent",
         sub="One sub-agent writes the change from the saved plan and returns a short report. It never commits, pushes or asks. The approved plan wins over any draft.",
         chips=[("ag", "sub-agent: general-purpose"), ("team", "mobileapps-ios:swift-codegen"), ("team", "mobileapps-ios:swiftui-code-gen"),
                ("team", "mobileapps-ios:swiftui-architect"), ("team", "mobileapps-ios:add-api"),
                ("team", "mobileapps-ios:tdd"), ("team", "mobileapps-foundation:localization")]),
    dict(id="audit", kind="node", title="Audit the changes", stop=True,
         sub="Audit loop, then review loop. Fixes must-fix and should-fix, at most 2 rounds.",
         chips=[("own", P + "audit-changes"), ("pt", "ponytail:ponytail-audit"), ("pt", "ponytail:ponytail-review"),
                ("ag", "ecc:code-reviewer (fallback)")],
         note="Blocker or major findings after round 2 stop and ask."),
    dict(id="verify", kind="branch", title="Verify the ticket in a sub-agent", stop=True, gate="auto",
         sub="A sub-agent runs it and returns the result table. Packages are re-checked first. Never marks a check passed that did not run. Stops after 2 failed fix rounds.",
         chips=[("own", P + "verify-ticket"), ("ag", "sub-agent: general-purpose"), ("team", "mobileapps-ios:run-tests"), ("tool", "ticket_slots.py packages"), ("tool", "xcodebuild, swiftlint"), ("hookok", "ticket_gate.py mark-verified")],
         boxes=[("App repo", ["lint, build-for-testing, unit tests,", "UI tests named in the plan,", "click, design, wording (app client)."], "opt"),
                ("Package repo", ["xcodebuild build and test,", "then lint, then audit.", "No login, no click tests."], "opt"),
                ("Nothing buildable", ["Lint, parse, API diff,", "grep consumers. Gate waits", "for an override reason."], "optb"),
                ("Tests do not compile", ["A failed check, never", "skipped. Gate waits for an", "override: tests-unverified."], "optb")],
         ok=True),
    dict(id="sdk", kind="node", title="Optional: test the SDK inside the app", gate="you",
         sub="SDK repos only. Compile errors are reported, never fixed app-side. Branch inject/<SDK>-<KEY> is never pushed.",
         chips=[("own", P + "sdk-inject-test")],
         note="(a) warm BlibliIOSApp slot on develop, or (b) the dev tests with printed steps."),
    dict(id="pr", kind="node", title="Open the draft PR",
         sub="Draft only, enforced by the gate. Bug fixes need the root cause section. build-unverified or tests-unverified label if overridden.",
         chips=[("team", "mobileapps-foundation:create-pr"), ("tool", "gh")],
         note="Edit after verify denies the gate again.", unlocked=True),
    dict(id="jira", kind="node", title="Jira evidence comment",
         sub="PR URL, screenshots, screen recording or needs manual run list.",
         chips=[("tool", "Jira MCP addOrEditJiraIssueComment")]),
    dict(id="doc", kind="node", title="Optional: Confluence page (--doc)", gate="you",
         sub="Context, plan and test cases for QA. Shows the full draft, publishes only after a yes, then links it on the ticket.",
         chips=[("own", P + "publish-doc"), ("team", "mobileapps-foundation:jira-doc-generator"), ("tool", "Atlassian MCP")]),
    dict(id="release", kind="node", title="Release and clear", cleared=True,
         sub="Slot or worktree released, gate cleared. Never mark ready, never merge.",
         chips=[("hook0", "ticket_gate.py clear"), ("tool", "ticket_slots.py release")]),
    dict(id="watch", kind="node", title="Watch the PR in the background",
         sub="Shell script polls gh and jq at no model cost. Wakes on comments, CI failure, conflicts, ready, merged or closed.",
         chips=[("own", P + "pr-watch"), ("tool", "pr_watch.sh"), ("own", P + "reply-pr-comments")],
         note="Never merges, never marks ready. Gives up after 8 hours."),
    dict(id="wrap", kind="node", title="After the merge: wrap-up",
         sub="Bug to Code Review, other types to Dev Testing. Clears the gate, releases the slot, archives the plan.",
         chips=[("own", P + "wrap-up"), ("tool", "Jira transitionJiraIssue")]),
    dict(id="done", kind="node", title="Done: final report",
         sub="PR URL, result table, needs manual run items, assumptions.", chips=[]),
]

PHASES = [("entry", "approve", "PLAN MODE · read-only"),
          ("dev", "audit", "BUILD · auto mode"),
          ("verify", "done", "VERIFY AND SHIP")]
BANDS = [("entry", "profile", "band-off", "not armed yet"),
         ("arm", "verify", "band-bad", "HOOK · denies commit, push, PR create"),
         ("sdk", "jira", "band-ok", "UNLOCKED"),
         ("release", "done", "band-off", "cleared")]

LEGEND = [("own", "ios-orchestration skill"), ("sp", "superpowers"), ("pt", "ponytail"), ("team", "team skill"),
          ("ag", "subagent"), ("tool", "tool or command"), ("hook", "hook event")]


def wrap(s, n):
    return textwrap.wrap(s, n) or [""]


def chip_rows(chips, note):
    """Lay chips out in rows starting at CHIP_X. Returns (placements, height)."""
    placed, x, row = [], CHIP_X, 0
    for cls, text in chips:
        w = int(len(text) * CHAR + 22)
        if x + w > CHIP_MAX and x > CHIP_X:
            x, row = CHIP_X, row + 1
        placed.append((cls, text, x, row, w))
        x += w + 8
    h = (row + 1) * 28 if chips else 0
    nl = wrap(note, 70) if note else []
    return placed, nl, h + (len(nl) * 14 + 4 if nl else 0)


def node_height(it):
    left = 18 + 17 + 14 * len(wrap(it["sub"], 52)) + 10
    _, _, right = chip_rows(it.get("chips", []), it.get("note"))
    return max(44, left, right + 4)


def layout():
    y = 70
    for it in ITEMS:
        it["y"] = y
        it["h"] = node_height(it)
        if it["kind"] == "branch":
            n = len(it["boxes"])
            it["bw"] = (920 - NODE_X - 16 * (n - 1)) // n
            it["bh"] = 22 + 14 * max(len(b[1]) for b in it["boxes"]) + 12
            it["split"] = y + it["h"] + 14
            it["boxy"] = y + it["h"] + 28
            it["merge"] = it["boxy"] + it["bh"] + 14
            it["out"] = it["merge"]
            y = it["merge"] + 30
        else:
            it["out"] = y + it["h"]
            y = y + it["h"] + GAP
    return y - GAP + 24


def diamond(cx, cy, cls, r=9):
    return '<path d="M%d %d l%d %d l-%d %d l-%d -%d z" class="%s"/>' % (cx, cy - r, r, r, r, r, r, r, cls)


def arrow(x1, y1, x2, y2):
    return '<line x1="%d" y1="%d" x2="%d" y2="%d" class="ln" marker-end="url(#ar)"/>' % (x1, y1, x2, y2)


def render(H, standalone):
    byid = {it["id"]: it for it in ITEMS}
    o = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" role="img" xmlns="http://www.w3.org/2000/svg" '
         'aria-label="Target design of the ticket to PR flow: repo and key resolution, health check, client capability branch, plan mode with approval, slot or worktree by repo profile, implement, audit, verify, optional SDK test, draft PR, Jira evidence and release, with the three gate states">'
         % (W, H, W, H)]
    if standalone:
        o.append("<style>%s%s</style>" % (VARS, CSS))
        o.append('<rect width="%d" height="%d" fill="var(--surface)"/>' % (W, H))
    o.append('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 1 L10 5 L0 9 z" class="arh"/></marker></defs>')

    # gate-state bands and phase brackets, split halfway between two stages
    def edge(before):
        i = [it["id"] for it in ITEMS].index(before)
        return (ITEMS[i]["out"] + ITEMS[i + 1]["y"]) // 2
    end = ITEMS[-1]["out"] + 12
    for y1, y2, cls, label, pin in (
            (24, edge("profile"), "band-off", "not armed yet", False),
            (edge("profile"), edge("verify"), "band-bad", "HOOK · denies commit, push, PR create", True),
            (edge("verify"), edge("jira"), "band-ok", "UNLOCKED", True),
            (edge("jira"), end, "band-off", "cleared", True)):
        mid = (y1 + y2) / 2
        o.append('<rect x="18" y="%d" width="22" height="%d" rx="3" class="%s"/>' % (y1, y2 - y1, cls))
        o.append('<text x="33" y="%.1f" transform="rotate(-90 33 %.1f)" text-anchor="middle" class="bandt">%s</text>' % (mid, mid, escape(label)))
        if pin:
            o.append('<line x1="40" y1="%d" x2="486" y2="%d" class="hair"/><circle cx="29" cy="%d" r="4" class="pin"/>' % (y1, y1, y1))
    for y1, y2, label in ((24, edge("approve"), "PLAN MODE · read-only"),
                          (edge("approve"), edge("audit"), "BUILD · auto mode"),
                          (edge("audit"), end, "VERIFY AND SHIP")):
        mid = (y1 + y2) / 2
        o.append('<line x1="62" y1="%d" x2="62" y2="%d" class="br"/>' % (y1 + 2, y2 - 2))
        o.append('<text x="80" y="%.1f" transform="rotate(-90 80 %.1f)" text-anchor="middle" class="ph">%s</text>' % (mid, mid, escape(label)))

    # spine arrows
    for prev, nxt in zip(ITEMS, ITEMS[1:]):
        o.append(arrow(SPINE, prev["out"] + 2, SPINE, nxt["y"] - 2))

    for it in ITEMS:
        y, h = it["y"], it["h"]
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="5" class="node"/>' % (NODE_X, y, NODE_W, h))
        o.append('<text x="%d" y="%d" class="nt">%s</text>' % (NODE_X + 15, y + 20, escape(it["title"])))
        for k, ln in enumerate(wrap(it["sub"], 52)):
            o.append('<text x="%d" y="%d" class="ns">%s</text>' % (NODE_X + 15, y + 36 + 14 * k, escape(ln)))
        if it.get("gate"):
            o.append(diamond(NODE_X + NODE_W - 22, y + h // 2, "gu" if it["gate"] == "you" else "ga"))
        if it.get("stop"):
            o.append('<circle cx="%d" cy="%d" r="8" class="bl"/><text x="%d" y="%d" text-anchor="middle" class="blt">!</text>'
                     % (NODE_X, y, NODE_X, y + 4))
        chips = it.get("chips", [])
        placed, nlines, _ = chip_rows(chips, it.get("note"))
        if chips or nlines:
            o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="dash"/>' % (NODE_X + NODE_W + 2, y + 22, CHIP_X - 4, y + 22))
        for cls, text, x, row, w in placed:
            cy = y + 4 + row * 28
            o.append('<g class="chip %s"><rect x="%d" y="%d" width="%d" height="22" rx="11"/><text x="%.1f" y="%d" text-anchor="middle">%s</text></g>'
                     % (cls, x, cy, w, x + w / 2, cy + 15, escape(text)))
        if nlines:
            ny = y + 4 + ((max(p[3] for p in placed) + 1) * 28 if placed else 0) + 10
            for k, ln in enumerate(nlines):
                o.append('<text x="%d" y="%d" class="note">%s</text>' % (CHIP_X, ny + 14 * k, escape(ln)))
        if it["kind"] == "branch":
            n, bw = len(it["boxes"]), it["bw"]
            centers = [NODE_X + i * (bw + 16) + bw // 2 for i in range(n)]
            lo, hi = min(SPINE, centers[0]), max(SPINE, centers[-1])
            o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="ln"/>' % (SPINE, y + h, SPINE, it["split"]))
            o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="ln"/>' % (lo, it["split"], hi, it["split"]))
            for i, (bt, lines, cls) in enumerate(it["boxes"]):
                bx = NODE_X + i * (bw + 16)
                o.append(arrow(centers[i], it["split"], centers[i], it["boxy"] - 2))
                o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" class="%s"/>' % (bx, it["boxy"], bw, it["bh"], cls))
                o.append('<text x="%d" y="%d" class="nt">%s</text>' % (bx + 12, it["boxy"] + 18, escape(bt)))
                for k, ln in enumerate(lines):
                    o.append('<text x="%d" y="%d" class="ns">%s</text>' % (bx + 12, it["boxy"] + 34 + 14 * k, escape(ln)))
                o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="ln"/>' % (centers[i], it["boxy"] + it["bh"], centers[i], it["merge"]))
            o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="ln"/>' % (lo, it["merge"], hi, it["merge"]))

    # legend, bottom
    ly = H - 34
    x = 110
    for cls, label in LEGEND:
        o.append('<g class="chip %s"><rect x="%d" y="%d" width="22" height="12" rx="6"/></g>' % (cls, x, ly - 10))
        o.append('<text x="%d" y="%d" class="lg">%s</text>' % (x + 28, ly, escape(label)))
        x += 28 + int(len(label) * 5.6) + 14
    ly += 20
    x = 110
    o.append(diamond(x + 8, ly - 4, "gu", 6))
    o.append('<text x="%d" y="%d" class="lg">gate, you decide</text>' % (x + 20, ly))
    x += 20 + 90 + 14
    o.append(diamond(x + 8, ly - 4, "ga", 6))
    o.append('<text x="%d" y="%d" class="lg">gate, auto</text>' % (x + 20, ly))
    x += 20 + 62 + 14
    o.append('<circle cx="%d" cy="%d" r="6" class="bl"/><text x="%d" y="%d" text-anchor="middle" class="blt" style="font-size:9px">!</text>' % (x + 6, ly - 4, x + 6, ly - 1))
    o.append('<text x="%d" y="%d" class="lg">can stop and ask</text>' % (x + 18, ly))
    o.append("</svg>")
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--light", action="store_true", help="drop the dark-mode block (for rendering a light PNG)")
    ap.add_argument("--inline", type=Path, help="write a fragment without theme variables")
    a = ap.parse_args()
    H = layout() + 60
    if a.inline:
        a.inline.write_text(render(H, False))
        print("wrote", a.inline)
    else:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        svg = render(H, True)
        if a.light:
            i = svg.index("@media (prefers-color-scheme:dark)")
            j = svg.index("\n", i)
            svg = svg[:i] + svg[j:]
        a.out.write_text(svg)
        print("wrote", a.out)


if __name__ == "__main__":
    main()
