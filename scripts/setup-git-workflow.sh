#!/bin/sh
# Run once per clone. Worktrees share this host identity and relative hooks path.
set -eu
case "${1:-}" in
    HappyDucky02|HappySnowman) host=$1 ;;
    *) printf 'Usage: sh scripts/setup-git-workflow.sh HappyDucky02|HappySnowman [--production]\n' >&2; exit 1 ;;
esac
[ "$#" -le 2 ] && { [ "$#" -eq 1 ] || [ "$2" = --production ]; } || exit 1
root=$(git rev-parse --show-toplevel)
cd "$root"
configured_host=$(git config --get helvetic.host || true)
if [ -n "$configured_host" ] && [ "$configured_host" != "$host" ]; then
    printf 'Existing host is %s; refusing to silently relabel this clone.\n' "$configured_host" >&2
    exit 1
fi
hooks=$(git config --get core.hooksPath || true)
if [ -n "$hooks" ] && [ "$hooks" != .githooks ]; then
    printf 'Existing core.hooksPath=%s; integrate those hooks before installing these.\n' "$hooks" >&2
    exit 1
fi
if [ -z "$hooks" ]; then
    previous=$(git rev-parse --git-path hooks)
    for hook in "$previous"/*; do
        [ -f "$hook" ] || continue
        case "$hook" in *.sample) continue ;; esac
        printf 'Existing hook %s; refusing to disable it.\n' "$hook" >&2
        exit 1
    done
fi
for hook in pre-commit prepare-commit-msg pre-push; do
    [ -f ".githooks/$hook" ] || { printf 'Missing .githooks/%s\n' "$hook" >&2; exit 1; }
    chmod +x ".githooks/$hook"
done
git config --local helvetic.host "$host"
git config --local core.hooksPath .githooks
git config --local pull.ff only
git config --local push.default simple
if [ "${2:-}" = --production ]; then
    protected=$(git config --get helvetic.productionCheckout || true)
    if [ -n "$protected" ] && [ "$protected" != "$root" ]; then
        printf 'Another worktree is already marked production: %s\n' "$protected" >&2
        exit 1
    fi
    git config --local helvetic.productionCheckout "$root"
fi
printf 'Configured %s: task branches, host trailers, fast-forward push guard.\n' "$host"
printf 'Clone-local settings are not transferred by git pull; install on each PC.\n'
