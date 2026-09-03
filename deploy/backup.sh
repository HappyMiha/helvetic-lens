#!/bin/sh
set -eu

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
STATUS_ROOT=${BACKUP_STATUS_ROOT:-/status}
INTERVAL_SECONDS=${BACKUP_INTERVAL_SECONDS:-86400}
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

if [ "$BACKUP_ROOT" != "/backups" ] || [ "$STATUS_ROOT" != "/status" ]; then
  echo "Refusing unexpected backup paths." >&2
  exit 2
fi

case "$INTERVAL_SECONDS" in *[!0-9]*|'') echo "Invalid backup interval." >&2; exit 2 ;; esac
case "$RETENTION_DAYS" in *[!0-9]*|'') echo "Invalid backup retention." >&2; exit 2 ;; esac

run_backup() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  partial="$BACKUP_ROOT/.partial-$stamp-$$"
  final="$BACKUP_ROOT/$stamp"
  umask 077
  mkdir -p "$BACKUP_ROOT" "$STATUS_ROOT" "$partial"
  trap 'rm -rf "$partial"' EXIT INT TERM

  PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    --host "$POSTGRES_HOST" \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --format custom \
    --no-owner \
    --no-privileges \
    --file "$partial/database.dump"
  tar -C /documents -czf "$partial/documents.tar.gz" .
  cp /configuration/environment "$partial/environment"
  cp /configuration/Caddyfile "$partial/Caddyfile"
  {
    echo "backup_id=$stamp"
    echo "created_at=$stamp"
    echo "database_format=postgres-custom"
    echo "documents_format=tar-gzip"
    echo "release=${HELVETIC_LENS_RELEASE:-unknown}"
  } > "$partial/METADATA"
  (cd "$partial" && sha256sum database.dump documents.tar.gz environment Caddyfile METADATA > SHA256SUMS)

  mv "$partial" "$final"
  trap - EXIT INT TERM
  printf '%s\n' "$stamp" > "$BACKUP_ROOT/.LATEST_SUCCESS.tmp"
  mv "$BACKUP_ROOT/.LATEST_SUCCESS.tmp" "$BACKUP_ROOT/LATEST_SUCCESS"
  printf '{"backup_id":"%s","created_at":"%s","status":"available"}\n' "$stamp" "$stamp" \
    > "$STATUS_ROOT/.latest.json.tmp"
  mv "$STATUS_ROOT/.latest.json.tmp" "$STATUS_ROOT/latest.json"

  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' \
    -mtime "+$RETENTION_DAYS" -exec rm -rf '{}' ';'
  echo "Backup $stamp completed."
}

run_backup
if [ "${1:-schedule}" = "once" ]; then
  exit 0
fi
while sleep "$INTERVAL_SECONDS"; do
  run_backup
done
