#!/usr/bin/env bash
# Watch one PR with `gh` until something needs a human or the agent. No model tokens are spent while it polls.
#
#   pr_watch.sh <pr-number|pr-url> [--repo owner/repo] [--interval 60] [--timeout 28800]
#
# Prints ONE JSON line and exits when the first of these happens (checked in this order):
#   merged | closed | dirty (merge conflicts) | ci_fail | comments (unresolved review threads) | ready (draft -> ready) | timeout | error
#   {"event":"ci_fail","pr":3512,"repo":"o/r","detail":"build, lint"}
# Exit 0 for every event except `error` (1). Needs gh (logged in) and jq. Read-only: it never writes to the PR.
# No `set -u`: macOS bash 3.2 rejects an empty array under it.

PR="" REPO="" INTERVAL=60 TIMEOUT=28800
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --interval) INTERVAL="${2:-}"; shift 2 ;;
    --timeout) TIMEOUT="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) PR="$1"; shift ;;
  esac
done
[ -n "$PR" ] || { echo '{"event":"error","detail":"usage: pr_watch.sh <pr-number|pr-url> [--repo owner/repo]"}'; exit 1; }
command -v gh >/dev/null 2>&1 && command -v jq >/dev/null 2>&1 || { echo '{"event":"error","detail":"needs gh and jq"}'; exit 1; }
case "$INTERVAL$TIMEOUT" in *[!0-9]*|"") echo '{"event":"error","detail":"--interval and --timeout are seconds"}'; exit 1 ;; esac

if [[ "$PR" =~ ^https://github\.com/([^/]+/[^/]+)/pull/([0-9]+) ]]; then
  REPO="${BASH_REMATCH[1]}"; PR="${BASH_REMATCH[2]}"
fi
[[ "$PR" =~ ^[0-9]+$ ]] || { echo '{"event":"error","detail":"PR must be a number or a github.com pull request URL"}'; exit 1; }
[ -n "$REPO" ] && REPO_ARGS=(--repo "$REPO") || REPO_ARGS=()
[ -n "$REPO" ] || REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"
OWNER="${REPO%%/*}" NAME="${REPO##*/}"

emit() { jq -nc --arg e "$1" --argjson pr "$PR" --arg repo "$REPO" --arg d "${2:-}" '{event:$e,pr:$pr,repo:$repo,detail:$d}'; }

start=$(date +%s) errors=0 was_draft=""
while :; do
  if v=$(gh pr view "$PR" "${REPO_ARGS[@]}" --json state,isDraft,mergeable,mergeStateStatus,statusCheckRollup 2>/dev/null); then
    errors=0
    state=$(jq -r .state <<<"$v"); draft=$(jq -r .isDraft <<<"$v")
    [ -n "$was_draft" ] || was_draft="$draft"
    [ "$state" = MERGED ] && { emit merged; exit 0; }
    [ "$state" = CLOSED ] && { emit closed; exit 0; }
    if [ "$(jq -r '.mergeable' <<<"$v")" = CONFLICTING ] || [ "$(jq -r .mergeStateStatus <<<"$v")" = DIRTY ]; then
      emit dirty "merge conflicts with the base branch"; exit 0
    fi
    failed=$(jq -r '[.statusCheckRollup[]? | select((.conclusion // .state // "") | test("^(FAILURE|TIMED_OUT|CANCELLED|ACTION_REQUIRED|STARTUP_FAILURE|ERROR)$")) | (.name // .context)] | unique | join(", ")' <<<"$v")
    [ -n "$failed" ] && { emit ci_fail "$failed"; exit 0; }
    q='query($o:String!,$n:String!,$p:Int!){repository(owner:$o,name:$n){pullRequest(number:$p){reviewThreads(first:100){nodes{isResolved isOutdated}}}}}'
    if t=$(gh api graphql -f query="$q" -F o="$OWNER" -F n="$NAME" -F p="$PR" 2>/dev/null); then
      open=$(jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved|not)] | length' <<<"$t")
      [ "${open:-0}" -gt 0 ] && { emit comments "$open unresolved review thread(s)"; exit 0; }
    fi
    [ "$was_draft" = true ] && [ "$draft" = false ] && { emit ready "marked ready for review"; exit 0; }
  else
    errors=$((errors + 1))
    [ "$errors" -ge 3 ] && { emit error "gh pr view failed 3 times in a row"; exit 1; }
  fi
  [ $(( $(date +%s) - start )) -ge "$TIMEOUT" ] && { emit timeout "no event in ${TIMEOUT}s"; exit 0; }
  sleep "$INTERVAL"
done
