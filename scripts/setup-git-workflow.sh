#!/bin/sh
# Install main-only safeguards, preserving unrelated hooks.
set -eu
[ "$#" -eq 0 ] || { [ "$#" -eq 1 ] && [ "$1" = --production ]; } || {
    printf 'Usage: sh scripts/setup-git-workflow.sh [--production]\n' >&2; exit 1;
}
root=$(git rev-parse --show-toplevel)
cd "$root"
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
for hook in pre-commit pre-push; do
    [ -f ".githooks/$hook" ] || { printf 'Missing .githooks/%s\n' "$hook" >&2; exit 1; }
    chmod +x ".githooks/$hook"
done
git config --local --unset-all helvetic.host || true
git config --local core.hooksPath .githooks
git config --local pull.ff only
git config --local push.default simple
if [ "${1:-}" = --production ]; then
    protected=$(git config --get helvetic.productionCheckout || true)
    if [ -n "$protected" ] && [ "$protected" != "$root" ]; then
        printf 'Another worktree is already marked production: %s\n' "$protected" >&2
        exit 1
    fi
    git config --local helvetic.productionCheckout "$root"
fi
printf 'Configured main-only development and fast-forward publication safeguards.\n'
