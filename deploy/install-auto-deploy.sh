#!/bin/sh
set -eu

SOURCE_ROOT=${HELVETIC_LENS_SOURCE_REPO:-/srv/helvetic-lens/helvetic-lens}
CONTROL_ROOT=${HELVETIC_LENS_DEPLOY_CONTROL_DIR:-/srv/helvetic-lens/deploy-control}
STATE_ROOT=${HELVETIC_LENS_DEPLOY_STATE_DIR:-/srv/helvetic-lens/deploy-state}
MARKER='# helvetic-lens-auto-deploy'
EXPECTED_REPOSITORY=${HELVETIC_LENS_EXPECTED_REPOSITORY:-https://github.com/HappyMiha/helvetic-lens.git}
update_only=false
revision=
while [ "$#" -gt 0 ]; do
    case "$1" in
        --update-only) update_only=true; shift ;;
        --revision)
            [ "$#" -ge 2 ] || { echo 'Missing full commit SHA after --revision.' >&2; exit 2; }
            revision=$2; shift 2 ;;
        *) echo 'Usage: install-auto-deploy.sh [--update-only] [--revision <full commit SHA>]' >&2; exit 2 ;;
    esac
done

for required in git python3 flock; do
    command -v "$required" >/dev/null 2>&1 || { echo "Required host tool is missing: $required" >&2; exit 2; }
done
if [ "$update_only" = false ]; then
    command -v crontab >/dev/null 2>&1 || { echo 'crontab is required for scheduler installation.' >&2; exit 2; }
fi

# Read a reviewed Git object, never uncommitted manager edits or a moving branch.
actual_repository=$(git -C "$SOURCE_ROOT" remote get-url origin)
actual_repository=${actual_repository%/}
expected_repository=${EXPECTED_REPOSITORY%/}
[ "${actual_repository%.git}" = "${expected_repository%.git}" ] || {
    echo 'Origin does not match the configured trusted repository.' >&2; exit 2;
}
[ -n "$revision" ] || revision=$(git -C "$SOURCE_ROOT" rev-parse --verify HEAD)
case "$revision" in ''|*[!0-9a-f]*) echo 'Use a full lowercase commit SHA.' >&2; exit 2 ;; esac
[ "${#revision}" -eq 40 ] || { echo 'Use a full 40-character commit SHA.' >&2; exit 2; }
git -C "$SOURCE_ROOT" cat-file -e "$revision^{commit}"
git -C "$SOURCE_ROOT" merge-base --is-ancestor "$revision" refs/remotes/origin/main || {
    echo 'The reviewed commit is not in fetched origin/main. Fetch the trusted origin first.' >&2; exit 2;
}

install -d -m 755 "$CONTROL_ROOT"
# Same lock as release_manager.py. Never replace a live runner or unlink its lock.
exec 9>"$CONTROL_ROOT/deployment.lock"
flock -n 9 || { echo 'A deployment is active; manager update was not applied.' >&2; exit 75; }
[ ! -L "$CONTROL_ROOT/release_manager.py" ] || { echo 'Refusing a symlink manager destination.' >&2; exit 2; }

candidate=$(mktemp "$CONTROL_ROOT/.release-manager.XXXXXXXX")
temporary=
trap 'rm -f "$candidate"; if [ -n "$temporary" ]; then rm -f "$temporary"; fi' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git -C "$SOURCE_ROOT" show "$revision:deploy/release_manager.py" > "$candidate"
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_bytes(), str(p), "exec")' "$candidate"
chmod 755 "$candidate"
if cmp -s "$candidate" "$CONTROL_ROOT/release_manager.py"; then
    echo "Manager already matches reviewed commit $revision."
else
    if [ -e "$CONTROL_ROOT/release_manager.py" ]; then
        backup=$(mktemp "$CONTROL_ROOT/release_manager.py.backup.XXXXXXXX")
        cp -p "$CONTROL_ROOT/release_manager.py" "$backup"
        echo "Previous manager preserved at $backup"
    fi
    mv -f "$candidate" "$CONTROL_ROOT/release_manager.py"
    echo "Installed manager from reviewed commit $revision."
fi

if [ "$update_only" = true ]; then
    echo 'Manager update complete. Cron, application containers, data and release state were not changed.'
    exit 0
fi

install -d -m 755 "$CONTROL_ROOT/uv-cache" "$STATE_ROOT"
install -d -m 750 "$STATE_ROOT/logs"

temporary=$(mktemp)
crontab -l 2>/dev/null | grep -Fv "$MARKER" > "$temporary" || true
quoted_manager=$(python3 -c 'import shlex,sys; print(shlex.quote(sys.argv[1]).replace("%", "\\%"))' "$CONTROL_ROOT/release_manager.py")
printf '%s\n' "*/2 * * * * /usr/bin/python3 $quoted_manager --poll >/dev/null 2>&1 $MARKER" >> "$temporary"
crontab "$temporary"

echo "Automatic deployment installed. Git main is checked every 2 minutes."
echo "Run once now: /usr/bin/python3 $CONTROL_ROOT/release_manager.py --poll"
