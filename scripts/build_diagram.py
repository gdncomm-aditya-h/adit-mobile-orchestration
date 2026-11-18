#!/usr/bin/env python3
"""Regenerate assets/dependency-graph.svg. Edit ROWS when a skill or its dependencies change.

  python3 scripts/build_diagram.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets" / "dependency-graph.svg"

# (skill, summary, platform, plugin-skill lines, script/tool lines)
ROWS = [
    ("verify-before-pr", "Gate before the PR", "claude",
     ["mobileapps-ios: swift-codegen, swiftui-code-gen,", "swiftui-architect, swift-review", "mobileapps-foundation: create-pr"],
     ["ticket-flow-gate.py, ticket-slots.py", "xcodebuild, swiftlint", "iOS Simulator MCP"]),
    ("plan-enrich", "DoD, test cases, reviewer pass", "claude",
     ["team skills: jira-plan, jira-develop", "mobileapps-foundation: localization, figma-mcp", "ecc: planner"],
     ["ticket-flow-gate.py", "Jira MCP, Figma MCP"]),
    ("audit-review-code", "Audit loop, then review loop", "experimental",
     ["ponytail: ponytail-audit, ponytail-review"],
     ["git"]),
    ("pr-reply", "Answer PR review threads", "experimental",
     ["superpowers: receiving-code-review", "mobileapps-ios: swift-codegen", "caveman: caveman"],
     ["pr-threads.sh", "gh api, Jira MCP"]),
    ("review-pr-blibli-mobile-ios", "Batch PR review", "experimental",
     ["ecc: swift-reviewer, security-reviewer", "code-review"],
     ["gh api, gh pr"]),
    ("generate-plan-from-ticket", "Ticket to reviewed plan", "ok",
     [], ["Jira MCP, gh pr"]),
    ("check-slot-bliblimobileios", "Worktree slot health", "ok",
     [], ["check_slot.py", "reads ticket-slots.py state"]),
    ("low-hanging-fruit", "Rank your open IOS tickets", "ok",
     [], ["Jira MCP (JQL search)"]),
    ("graphify", "Codebase knowledge graph", "ok",
     [], ["graphify CLI", "subagents"]),
]
PLATFORM = {
    "ok": ("teal", "Claude and Codex"),
    "experimental": ("amber", "Claude, Codex experimental"),
    "claude": ("gray", "Claude only"),
}
BOTTOM = [
    ("ticket-flow-gate.py", "PreToolUse hook. Blocks commit, push", "and PR creation until verified."),
    ("ticket-slots.py", "Three long-lived worktrees,", "one simulator and DerivedData each."),
    ("CLAUDE.md block", "Autonomous ticket-flow rules,", "written between marker comments."),
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
    W, H = 1000, 1040
    a_x, a_w, b_x, b_w, c_x, c_w = 64, 250, 364, 330, 722, 240
    y0, pitch, h = 136, 82, 66
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img">' % (W, H, W, H),
         "<title>adit-mobile-orchestration dependency graph</title>",
         "<desc>Nine adit-workflow skills, the plugin skills and tools each one calls, and the hooks and rules installed with them.</desc>",
         "<style>%s</style>" % CSS,
         '<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#7f8790" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker>'
         '<marker id="ph" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#7f77dd" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>',
         '<rect width="%d" height="%d" fill="var(--bg)" rx="12"/>' % (W, H),
         t(40, 46, "adit-mobile-orchestration", "title"),
         t(40, 68, "Nine skills, two hooks and one rules block that take a Jira ticket to a verified draft PR", "sub")]
    # legend
    lx = 40
    for dot, label in (("var(--ok)", "Claude and Codex"), ("var(--ex)", "Codex experimental"), ("var(--co)", "Claude only")):
        o.append('<circle cx="%d" cy="90" r="4.5" fill="%s"/>' % (lx + 5, dot))
        o.append(t(lx + 16, 94, label, "p"))
        lx += 16 + len(label) * 6 + 22
    o.append('<line x1="%d" y1="90" x2="%d" y2="90" class="call" marker-end="url(#ph)"/>' % (lx, lx + 26))
    o.append(t(lx + 34, 94, "calls another adit skill", "p"))
    for x, label in ((a_x, "Skills (adit-workflow-*)"), (b_x, "Plugin skills they call"), (c_x, "Scripts and tools")):
        o.append(t(x, 122, label, "col"))
    yc = lambda i: y0 + i * pitch + h // 2
    o.append('<path d="M%d %d H46 V%d H%d" class="call" marker-end="url(#ph)"/>' % (a_x, yc(0), yc(1), a_x - 2))
    o.append('<path d="M%d %d H28 V%d H%d" class="call" marker-end="url(#ph)"/>' % (a_x, yc(0), yc(2), a_x - 2))
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
    o.append(t(58, by + 24, "Installed alongside the skills", "col"))
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
