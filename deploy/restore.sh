#!/bin/sh
set -eu

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
DOCUMENT_ROOT=${DOCUMENT_ROOT:-/documents}
BACKUP_ID=${BACKUP_ID:-}

if [ "$BACKUP_ROOT" != "/backups" ] || [ "$DOCUMENT_ROOT" != "/documents" ]; then
  echo "Refusing unexpected restore paths." >&2
  exit 2
fi
case "$BACKUP_ID" in 20??????T??????Z) ;; *) echo "BACKUP_ID must be a timestamped backup directory." >&2; exit 2 ;; esac
if [ "${CONFIRM_RESTORE:-}" != "$BACKUP_ID" ]; then
  echo "Set CONFIRM_RESTORE to the exact BACKUP_ID." >&2
  exit 2
fi

source_dir="$BACKUP_ROOT/$BACKUP_ID"
if [ ! -d "$source_dir" ]; then
  echo "Backup does not exist." >&2
  exit 2
fi
(cd "$source_dir" && sha256sum -c SHA256SUMS)

PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
  --host "$POSTGRES_HOST" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  "$source_dir/database.dump"

find "$DOCUMENT_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf '{}' ';'
tar -C "$DOCUMENT_ROOT" -xzf "$source_dir/documents.tar.gz"
echo "Restore $BACKUP_ID completed. Review environment and Caddyfile from the backup before restarting."
