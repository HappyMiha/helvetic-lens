#!/bin/sh
set -eu
umask 077
# Runtime signing secret stays in the Docker volume, never in Git or logs.
secret=/var/cache/searxng/helvetic-secret
if [ ! -s "$secret" ]; then
  head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$secret"
fi
sed "s/ultrasecretkey/$(cat "$secret")/" /configuration/settings.yml > /etc/searxng/settings.yml
exec /usr/local/searxng/entrypoint.sh
