#!/bin/sh
set -eu

SOURCE_ROOT=${HELVETIC_LENS_SOURCE_REPO:-/srv/helvetic-lens/helvetic-lens}
CONTROL_ROOT=${HELVETIC_LENS_DEPLOY_CONTROL_DIR:-/srv/helvetic-lens/deploy-control}
STATE_ROOT=${HELVETIC_LENS_DEPLOY_STATE_DIR:-/srv/helvetic-lens/deploy-state}
MARKER='# helvetic-lens-auto-deploy'

install -d -m 755 "$CONTROL_ROOT" "$CONTROL_ROOT/uv-cache" "$STATE_ROOT"
install -d -m 750 "$STATE_ROOT/logs"
install -m 755 "$SOURCE_ROOT/deploy/release_manager.py" "$CONTROL_ROOT/release_manager.py"

temporary=$(mktemp)
trap 'rm -f "$temporary"' EXIT INT TERM
crontab -l 2>/dev/null | grep -Fv "$MARKER" > "$temporary" || true
printf '%s\n' "*/2 * * * * /usr/bin/python3 $CONTROL_ROOT/release_manager.py --poll >/dev/null 2>&1 $MARKER" >> "$temporary"
crontab "$temporary"

echo "Automatic deployment installed. Git main is checked every 2 minutes."
echo "Run once now: /usr/bin/python3 $CONTROL_ROOT/release_manager.py --poll"
