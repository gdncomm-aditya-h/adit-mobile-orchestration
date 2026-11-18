# adit-mobile-orchestration (Codex, experimental)

The skills named `adit-workflow-*` are installed in `~/.agents/skills`. Use them by name.

Skills that work without Claude-only tooling: `adit-workflow-low-hanging-fruit`, `adit-workflow-generate-plan-from-ticket`, `adit-workflow-check-slot-bliblimobileios`, `adit-workflow-graphify`.

Skills that call plugin skills Codex may not have: `adit-workflow-audit-review-code`, `adit-workflow-pr-reply`, `adit-workflow-review-pr-blibli-mobile-ios`. If a plugin skill is missing, say so and carry on with the review by hand.

The full ticket flow (`adit-workflow-plan-enrich` and `adit-workflow-verify-before-pr`) needs Claude Code plan mode, session tools and the commit gate hook. Do not run it from Codex.
