#!/bin/sh
# Shared by the hooks; Git for Windows and Linux both provide a POSIX shell.
set -eu

die() {
    printf 'Helvetic Lens: %s\n' "$*" >&2
    exit 1
}

root=$(git rev-parse --show-toplevel) || exit 1
cd "$root"
host=$(git config --get helvetic.host || true)
case "$host" in
    HappyDucky02|HappySnowman) ;;
    *) die 'Set this clone up with sh scripts/setup-git-workflow.sh <host-alias>.' ;;
esac

production=$(git config --get helvetic.productionCheckout || true)
if [ -n "$production" ] && [ "$root" = "$production" ]; then
    die 'This is the production checkout. Use a separate development worktree/clone.'
fi

require_task_branch() {
    branch=$(git symbolic-ref --quiet --short HEAD || true)
    case "$branch" in
        codex/"$host"/?*) ;;
        *) die "Commit on a unique codex/$host/<task> branch, not main/detached HEAD/another host's branch." ;;
    esac
}

is_zero() {
    case "$1" in *[!0]*) return 1 ;; *) return 0 ;; esac
}
