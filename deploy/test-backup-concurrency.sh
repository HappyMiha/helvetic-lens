#!/bin/sh
set -eu

mkdir -p /backups /status /documents /configuration /mock-bin
printf 'evidence\n' > /documents/example.txt
printf 'APP_ENVIRONMENT=production\n' > /configuration/environment
printf 'example.test { respond "ok" }\n' > /configuration/Caddyfile

cat > /mock-bin/pg_dump <<'EOF'
#!/bin/sh
set -eu
output=
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--file" ]; then
    shift
    output=$1
  fi
  shift
done
sleep "${MOCK_BACKUP_DELAY:-0}"
printf 'database dump\n' > "$output"
EOF
chmod +x /mock-bin/pg_dump

PATH="/mock-bin:$PATH" MOCK_BACKUP_DELAY=2 \
  POSTGRES_PASSWORD=test POSTGRES_HOST=test POSTGRES_USER=test POSTGRES_DB=test \
  HELVETIC_LENS_RELEASE=test-release /bin/sh /operations/backup.sh once > /tmp/first.log 2>&1 &
first_pid=$!
sleep 1
PATH="/mock-bin:$PATH" MOCK_BACKUP_DELAY=0 \
  POSTGRES_PASSWORD=test POSTGRES_HOST=test POSTGRES_USER=test POSTGRES_DB=test \
  HELVETIC_LENS_RELEASE=test-release /bin/sh /operations/backup.sh once > /tmp/second.log 2>&1 &
second_pid=$!

wait "$first_pid"
wait "$second_pid"

backup_count=$(find /backups -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' | wc -l | tr -d ' ')
[ "$backup_count" = "2" ]
latest=$(cat /backups/LATEST_SUCCESS)
expected_latest=$(find /backups -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' | sort | tail -n 1)
expected_latest=${expected_latest##*/}
[ "$latest" = "$expected_latest" ]
[ -s "/backups/$latest/SHA256SUMS" ]
for backup in $(find /backups -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' | sort); do
  (cd "$backup" && sha256sum -c SHA256SUMS >/dev/null)
done
grep -q 'Backup .* completed.' /tmp/first.log
grep -q 'Backup .* completed.' /tmp/second.log
printf 'Concurrent backup serialization passed; two complete backups and one valid latest marker.\n'
