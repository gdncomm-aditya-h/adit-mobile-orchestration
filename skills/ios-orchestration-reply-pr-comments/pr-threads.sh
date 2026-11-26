#!/usr/bin/env bash
# List, reply to and resolve GitHub PR review threads.
# Usage: pr-threads.sh threads <pr-url> | reply <thread-id> <text> | resolve <thread-id>
# DRY_RUN=1 prints reply/resolve instead of posting.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

parse_url() {
	# shortcut: github.com only, no enterprise hosts; upgrade if a GHE repo is needed
	[[ ${1:-} =~ github\.com/([^/]+)/([^/]+)/pull/([0-9]+) ]] || { echo "bad PR url: ${1:-}" >&2; exit 2; }
	OWNER=${BASH_REMATCH[1]} REPO=${BASH_REMATCH[2]} NUM=${BASH_REMATCH[3]}
}

threads() {
	parse_url "${1:-}"
	local after="" out="[]" page nodes
	while :; do
		local args=(-f owner="$OWNER" -f repo="$REPO" -F num="$NUM")
		[[ -n $after ]] && args+=(-f after="$after")
		page=$(gh api graphql "${args[@]}" -f query='
query($owner:String!,$repo:String!,$num:Int!,$after:String){
  repository(owner:$owner,name:$repo){pullRequest(number:$num){
    reviewThreads(first:50,after:$after){
      pageInfo{hasNextPage endCursor}
      nodes{id isResolved isOutdated path line
        comments(first:50){nodes{author{login} body url}}}}}}}')
		nodes=$(jq '.data.repository.pullRequest.reviewThreads.nodes' <<<"$page")
		out=$(jq -s '.[0] + .[1]' <(echo "$out") <(echo "$nodes"))
		[[ $(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage' <<<"$page") == true ]] || break
		after=$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor' <<<"$page")
	done
	jq 'map({id, resolved: .isResolved, outdated: .isOutdated, path, line,
		url: .comments.nodes[0].url,
		comments: [.comments.nodes[] | {author: (.author.login // "ghost"), body}]})' <<<"$out"
}

reply() {
	[[ -n ${1:-} && -n ${2:-} ]] || { echo "usage: reply <thread-id> <text>" >&2; exit 2; }
	if [[ ${DRY_RUN:-} == 1 ]]; then echo "DRY: reply $1: $2"; return; fi
	gh api graphql -f id="$1" -f body="$2" -f query='
mutation($id:ID!,$body:String!){
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$id,body:$body}){comment{url}}}' \
		--jq '.data.addPullRequestReviewThreadReply.comment.url'
}

resolve() {
	[[ -n ${1:-} ]] || { echo "usage: resolve <thread-id>" >&2; exit 2; }
	if [[ ${DRY_RUN:-} == 1 ]]; then echo "DRY: resolve $1"; return; fi
	gh api graphql -f id="$1" -f query='
mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' \
		--jq '.data.resolveReviewThread.thread.isResolved'
}

cmd=${1:-}; shift || true
case $cmd in
	threads) threads "$@" ;;
	reply) reply "$@" ;;
	resolve) resolve "$@" ;;
	*) echo "usage: pr-threads.sh threads <pr-url> | reply <thread-id> <text> | resolve <thread-id>" >&2; exit 2 ;;
esac
