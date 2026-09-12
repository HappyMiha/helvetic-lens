#!/bin/sh
set -eu
die() { printf 'Helvetic Lens: %s\n' "$*" >&2; exit 1; }
root=$(git rev-parse --show-toplevel) || exit 1
cd "$root"
production=$(git config --get helvetic.productionCheckout || true)
if [ -n "$production" ] && [ "$root" = "$production" ]; then
    die 'This is the production checkout. Use the development checkout.'
fi
require_main() {
    branch=$(git symbolic-ref --quiet --short HEAD || true)
    [ "$branch" = main ] || die 'Develop and commit on main in the development checkout.'
}
is_zero() { case "$1" in *[!0]*) return 1 ;; *) return 0 ;; esac; }
