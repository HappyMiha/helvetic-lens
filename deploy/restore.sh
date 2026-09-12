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

# Validate the archive before changing either database or documents. Application
# migrations use public; refuse unrelated schemas rather than cascading into them.
case "$POSTGRES_DB" in postgres|template0|template1|'') echo "Refusing a system database restore." >&2; exit 2 ;; esac
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT INT TERM
tar -tzf "$source_dir/documents.tar.gz" > /dev/null
pg_restore \
  --file="$work_dir/archive.sql" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  "$source_dir/database.dump"

cat > "$work_dir/reset.sql" <<'SQL'
DO $restore$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace
             WHERE nspname NOT IN ('public', 'information_schema')
               AND nspname NOT LIKE 'pg\_%' ESCAPE '\') THEN
    RAISE EXCEPTION 'Restore requires a dedicated application database with only the public schema';
  END IF;
END
$restore$;
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
SQL

# --clean alone cannot remove newer tables absent from an older archive. Their
# foreign keys can block restoring users/organizations. Reset and replay together:
# any SQL error rolls the entire database back and leaves documents untouched.
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host "$POSTGRES_HOST" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --no-psqlrc \
  --set ON_ERROR_STOP=1 \
  --single-transaction \
  --file "$work_dir/reset.sql" \
  --file "$work_dir/archive.sql"

find "$DOCUMENT_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf '{}' ';'
tar -C "$DOCUMENT_ROOT" -xzf "$source_dir/documents.tar.gz"
echo "Restore $BACKUP_ID completed. Review environment and Caddyfile from the backup before restarting."
