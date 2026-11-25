#!/usr/bin/env python3
"""Regenerate assets/dependency-graph.svg. Edit ROWS when a skill or its dependencies change.

  python3 scripts/build_diagram.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets" / "dependency-graph.svg"

# (skill, summary, platform, plugin-skill lines, script/tool lines)
P = "ios-orchestration-"
ROWS = [
    (P + "ticket-to-pr", "Entry, owns the whole flow", "claude",
     ["mobileapps-ios: swift-codegen, swiftui-code-gen,", "swiftui-architect, add-api, tdd", "mobileapps-foundation: create-pr, localization", "superpowers: brainstorming"],
     ["ticket_gate.py, ticket_slots.py", "EnterPlanMode, Jira MCP, gh"]),
    (P + "flow-config", "Repo, branch prefix, Jira project", "claude",
     [], ["config.json, gh repo view"]),
    (P + "flow-doctor", "Quick health check", "claude",
     [], ["repo_profile.py", "gh auth, Jira MCP"]),
    (P + "enrich-plan", "DoD, test cases, reviewer pass", "claude",
     ["mobileapps-foundation: localization, figma-mcp", "ecc: planner (reviewer pass)"],
     ["ticket_gate.py mark-active", "Jira MCP, Figma MCP"]),
    (P + "audit-changes", "Audit loop, then review loop", "claude",
     ["ponytail: ponytail-audit, ponytail-review", "ecc: code-reviewer (fallback)"],
     ["git"]),
    (P + "verify-ticket", "Results only, gate before PR", "claude",
     ["mobileapps-ios: run-tests"],
     ["ticket_gate.py mark-verified", "xcodebuild, swiftlint", "iOS Simulator MCP (app client)"]),
    (P + "sdk-inject-test", "Optional SDK test in the app", "claude",
     [], ["ticket_slots.py (warm app slot)", "never pushed, report only"]),
    (P + "ticket-status", "Slot and gate health, clear markers", "claude",
     [], ["ticket_slots.py status", "ticket_gate.py"]),
    (P + "reply-pr-comments", "Answer PR review threads", "claude",
     ["superpowers: receiving-code-review", "mobileapps-ios: swift-codegen"],
     ["pr-threads.sh", "gh api, Jira MCP"]),
    (P + "review-open-prs", "Batch PR review, any repo", "claude",
     ["mobileapps-ios: swift-review (local checkout)", "ecc: swift-reviewer, security-reviewer"],
     ["gh api, gh pr"]),
    (P + "plan-from-ticket", "Draft step: explore and plan", "claude",
     ["mobileapps-foundation: repo-index"], ["Explore subagent", "Jira MCP, gh"]),
    (P + "rank-my-tickets", "Rank your open tickets", "claude",
     [], ["Jira MCP (JQL search)"]),
]
PLATFORM = {
    "claude": ("gray", "Claude Code only"),
}
BOTTOM = [
    ("ticket_gate.py", "PreToolUse hook. Blocks commit, push", "and PR creation until verified."),
    ("ticket_slots.py", "Four warm slots for BlibliIOSApp,", "one simulator and DerivedData each."),
    ("hooks.json", "Plugin hooks, passive until a", "ticket arms the gate."),
]

CSS = """
  :root{--bg:#ffffff;--text:#1f2328;--muted:#59636e;--line:#c7ced6;
    --pf:#eeedfe;--ps:#534ab7;--pt:#3c3489;
    --tf:#e1f5ee;--ts:#0f6e56;--tt:#085041;
    --gf:#f4f2ec;--gs:#8a8880;--gt:#2c2c2a;
    --af:#faeeda;--as:#ba7517;--at:#633806;--ok:#1d9e75;--ex:#ba7517;--co:#888780}
  @media (prefers-color-scheme: dark){
    :root{--bg:#0d1117;--text:#e6edf3;--muted:#9198a1;--line:#3d444d;
    --pf:#26215c;--ps:#afa9ec;--pt:#eeedfe;
    --tf:#04342c;--ts:#5dcaa5;--tt:#e1f5ee;
    --gf:#22211f;--gs:#888780;--gt:#f1efe8;
    --af:#412402;--as:#ef9f27;--at:#faeeda;--ok:#5dcaa5;--ex:#ef9f27;--co:#9a988f}}
  text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:var(--text)}
  .title{font-size:22px;font-weight:600}
  .sub{font-size:13px;fill:var(--muted)}
  .col{font-size:12px;fill:var(--muted);letter-spacing:.2px}
  .h{font-size:14px;font-weight:600}
  .s{font-size:12px}
  .m{font-size:12px;fill:var(--muted)}
  .p{font-size:11px;fill:var(--muted)}
  .card-p{fill:var(--pf);stroke:var(--ps);stroke-width:1}
  .card-t{fill:var(--tf);stroke:var(--ts);stroke-width:1}
  .card-g{fill:var(--gf);stroke:var(--gs);stroke-width:1}
  .card-n{fill:none;stroke:var(--line);stroke-width:1;stroke-dasharray:4 4}
  .tp{fill:var(--pt)} .tt{fill:var(--tt)} .tg{fill:var(--gt)}
  .arr{stroke:var(--muted);stroke-width:1.4;fill:none}
  .call{stroke:var(--ps);stroke-width:1.6;fill:none}
"""


def t(x, y, s, cls, extra=""):
    return '<text x="%d" y="%d" class="%s"%s>%s</text>' % (x, y, cls, extra, escape(s))


def build():
    W = 1000
    H = 136 + len(ROWS) * 82 + 28 + 128 + 24
    a_x, a_w, b_x, b_w, c_x, c_w = 64, 300, 384, 322, 722, 240
    y0, pitch, h = 136, 82, 66
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img">' % (W, H, W, H),
         "<title>ios-orchestration dependency graph (in review)</title>",
         "<desc>Twelve ios-orchestration skills, the plugin skills and tools each one calls, and the hooks that ship with them. In review as agent-plugins#595, not released.</desc>",
         "<style>%s</style>" % CSS,
         '<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#7f8790" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker>'
         '<marker id="ph" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#7f77dd" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>',
         '<rect width="%d" height="%d" fill="var(--bg)" rx="12"/>' % (W, H),
         t(40, 46, "ios-orchestration", "title"),
         t(40, 68, "Twelve skills and plugin hooks that take a Jira ticket to a verified draft PR (in review as agent-plugins#595, not released)", "sub")]
    # legend
    lx = 40
    for dot, label in (("var(--co)", "Claude Code only"),):
        o.append('<circle cx="%d" cy="90" r="4.5" fill="%s"/>' % (lx + 5, dot))
        o.append(t(lx + 16, 94, label, "p"))
        lx += 16 + len(label) * 6 + 22
    o.append('<line x1="%d" y1="90" x2="%d" y2="90" class="call" marker-end="url(#ph)"/>' % (lx, lx + 26))
    o.append(t(lx + 34, 94, "calls another ios-orchestration skill", "p"))
    for x, label in ((a_x, "Skills (ios-orchestration-*)"), (b_x, "Plugin skills they call"), (c_x, "Scripts and tools")):
        o.append(t(x, 122, label, "col"))
    yc = lambda i: y0 + i * pitch + h // 2
    # ticket-to-pr (row 0) calls these steps; the farthest target gets the leftmost line so the lines never cross
    steps = [i for i, row in enumerate(ROWS) if row[0].endswith(("plan-from-ticket", "enrich-plan", "audit-changes", "verify-ticket", "sdk-inject-test"))]
    for k, i in enumerate(sorted(steps, reverse=True)):
        o.append('<path d="M%d %d H%d V%d H%d" class="call" marker-end="url(#ph)"/>' % (a_x, yc(0), 14 + 9 * k, yc(i), a_x - 2))
    for i, (name, summary, plat, plug, tools) in enumerate(ROWS):
        y = y0 + i * pitch
        color, label = PLATFORM[plat]
        dot = {"teal": "var(--ok)", "amber": "var(--ex)", "gray": "var(--co)"}[color]
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" class="card-p"/>' % (a_x, y, a_w, h))
        o.append(t(a_x + 14, y + 23, name, "h tp"))
        o.append(t(a_x + 14, y + 41, summary, "s tp"))
        o.append('<circle cx="%d" cy="%d" r="4" fill="%s"/>' % (a_x + 18, y + 55, dot))
        o.append(t(a_x + 28, y + 59, label, "p"))
        for x1, x2 in ((a_x + a_w, b_x), (b_x + b_w, c_x)):
            o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="arr" marker-end="url(#ah)"/>' % (x1, y + h // 2, x2 - 3, y + h // 2))
        for x, w, lines, cls, ncls, empty in ((b_x, b_w, plug, "card-t", "tt", "no plugin skills"), (c_x, c_w, tools, "card-g", "tg", "")):
            if lines:
                o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" class="%s"/>' % (x, y, w, h, cls))
                start = y + (h - 15 * len(lines)) // 2 + 11
                for k, ln in enumerate(lines):
                    o.append(t(x + 14, start + 15 * k, ln, "s " + ncls))
            else:
                o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" class="card-n"/>' % (x, y, w, h))
                o.append(t(x + 14, y + h // 2 + 4, empty, "m"))
    by = y0 + len(ROWS) * pitch + 28
    o.append('<rect x="40" y="%d" width="%d" height="128" rx="10" class="card-n"/>' % (by, W - 80))
    o.append(t(58, by + 24, "Ships with the skills", "col"))
    bw = (W - 80 - 36 - 2 * 16) // 3
    for i, (title, l1, l2) in enumerate(BOTTOM):
        x = 58 + i * (bw + 16)
        o.append('<rect x="%d" y="%d" width="%d" height="78" rx="8" class="card-g"/>' % (x, by + 36, bw))
        o.append(t(x + 14, by + 60, title, "h tg"))
        o.append(t(x + 14, by + 80, l1, "s tg"))
        o.append(t(x + 14, by + 96, l2, "s tg"))
    o.append("</svg>")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build())
    print("wrote", OUT)
