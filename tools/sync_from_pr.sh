#!/bin/sh
# Keeps skills/ios-orchestration-*, scripts/ and hooks/hooks.json identical to the plugin in agent-plugins.
#
#   tools/sync_from_pr.sh           copy them from the source branch into this repo
#   tools/sync_from_pr.sh --check   change nothing, exit 1 if this repo differs from the source
#
# Source: SRC_DIR (a local agent-plugins checkout), else a shallow clone of SRC_REPO at SRC_BRANCH.
# SRC_BRANCH is the head of agent-plugins#595 until it merges; set it to main afterwards.
# The clone needs read access to the private gdncomm/agent-plugins repo.
set -eu

SRC_REPO=${SRC_REPO:-gdncomm/agent-plugins}
SRC_BRANCH=${SRC_BRANCH:-adit/orchestration/mobile-ios-orchestration}
PLUGIN=plugins/mobileapps/ios
HERE=$(cd "$(dirname "$0")/.." && pwd)
MODE=${1:-sync}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

if [ -n "${SRC_DIR:-}" ]; then
  src=$SRC_DIR/$PLUGIN
else
  git clone -q --depth 1 --branch "$SRC_BRANCH" "git@github.com:$SRC_REPO.git" "$tmp/src"
  src=$tmp/src/$PLUGIN
fi
[ -d "$src/scripts" ] || { echo "not a plugin checkout: $src" >&2; exit 2; }

stage=$tmp/stage
mkdir -p "$stage/skills" "$stage/hooks"
cp -R "$src/scripts" "$stage/scripts"
cp -R "$src"/skills/ios-orchestration-* "$stage/skills/"
cp "$src/hooks/hooks.json" "$stage/hooks/"

drift=0
for part in scripts skills hooks; do
  diff -r -x __pycache__ -x '*.pyc' "$stage/$part" "$HERE/$part" >"$tmp/diff.txt" 2>&1 || {
    drift=1
    [ "$MODE" = "--check" ] && { echo "differs: $part"; head -20 "$tmp/diff.txt"; }
  }
done

if [ "$MODE" = "--check" ]; then
  [ "$drift" = 0 ] && echo "identical to $SRC_REPO ${SRC_DIR:-$SRC_BRANCH}"
  exit "$drift"
fi

for part in scripts skills hooks; do
  rm -rf "${HERE:?}/$part"
  cp -R "$stage/$part" "$HERE/$part"
done
find "$HERE/scripts" -name __pycache__ -prune -exec rm -rf {} +
echo "synced from $SRC_REPO ${SRC_DIR:-$SRC_BRANCH}"
