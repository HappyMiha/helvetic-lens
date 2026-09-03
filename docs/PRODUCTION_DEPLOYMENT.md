# Production single-server deployment

This is the public single-host baseline for Helvetic Lens. It expects Linux, Docker Engine with Compose, the NVIDIA driver and NVIDIA Container Toolkit, 32 GB RAM, and the two planned GTX 1080 GPUs. The host remains one failure domain: maintenance, a motherboard or disk failure, and a PostgreSQL outage stop the product. This layout provides recoverability and bounded exposure, not high availability.

## Prepare the host

Point the public DNS name at the server and allow inbound TCP 80/443 plus UDP 443. Do not publish Docker, SSH, PostgreSQL, Redis, the API, or the model-manager port to the Internet. Keep administrative SSH behind the operator's normal restricted access.

Copy the environment template and replace every `CHANGE_ME` value:

```sh
cp deploy/production.env.example .env.production
python3 -c "import secrets; print(secrets.token_urlsafe(36))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use the first generated value as `HELVETIC_LENS_DB_PASSWORD` and the second as `HELVETIC_LENS_CREDENTIAL_KEY`. Store `.env.production` and the credential key in the operator's password manager. The credential key must be restored with the database or saved integration credentials cannot be decrypted. Set `HELVETIC_LENS_RELEASE` to the exact Git commit or immutable release identifier being deployed.

Create `HELVETIC_LENS_BACKUP_DIR` on a separate mounted disk or protected remote-backed filesystem. The directory contains the database, immutable evidence, configuration, and credential material and must not be served by Caddy or included in Git.

## Validate and start

The supported production startup is:

```sh
python3 scripts/validate_production_env.py --env-file .env.production && docker compose --env-file .env.production -f compose.production.yaml up -d --build --wait
```

Validation stops before Docker when anonymous access, insecure cookies, HTTP public URLs, placeholder/weak secrets, private-network fetching, inline jobs, cloud-first AI, oversized uploads, or a relative backup destination is configured. The application repeats the security-critical checks at startup. Do not bypass the validator.

The migration container must exit successfully before the API starts. API readiness then requires both PostgreSQL and Redis. Workers and the web wait for readiness; Caddy waits for the web. Caddy obtains and renews public certificates automatically. Only Caddy publishes host ports 80/443. The API, PostgreSQL, Redis, workers, and local model endpoint have no host port mappings.

Inspect state without exposing an internal service:

```sh
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml logs --tail 100 api worker-cpu worker-ai model-manager caddy
```

Open `https://<HELVETIC_LENS_DOMAIN>/api/health` for liveness and `https://<HELVETIC_LENS_DOMAIN>/api/ready` for the database/broker readiness boundary. The readiness endpoint reports component booleans and no credentials.

## Network and persistence boundary

- `edge` contains only Caddy and the web process.
- `app`, `data`, and `model-control` are internal Docker networks.
- `outbound` gives the API, connector worker, and model manager controlled egress for official sources, explicitly selected cloud calls, and allowlisted model downloads; none publishes a port.
- PostgreSQL, Redis AOF, document evidence, model files, and Caddy certificates use named volumes.
- Container logs rotate at 20 MB with five files per service.
- Redis uses AOF `everysec` and `noeviction`. PostgreSQL remains the source of truth for jobs, so Redis loss can be reconciled rather than treated as successful completion.

The 1.5B quantized Apertus profile remains the production default until the checked-in benchmark passes on the actual dual-GTX-1080 host. Download and accept a model license from the platform administration UI after the stack is healthy. Never expose llama.cpp or the model manager directly.

## Backup and restore

The `backup` service starts with the production stack, writes one backup immediately, and repeats every `BACKUP_INTERVAL_SECONDS` (daily by default). Each timestamped directory contains a PostgreSQL custom dump, the complete document/evidence volume, the exact deployment environment, the Caddy configuration, metadata, and SHA-256 checksums. A directory is moved into place only after every component succeeds. Completed backup directories expire after `BACKUP_RETENTION_DAYS`; partial directories and a failed run never replace `LATEST_SUCCESS`.

The application can read only a small status marker in a separate named volume. It cannot read the off-host dumps or copied secrets. Confirm the platform administration page shows a recent backup. Run an extra backup before an upgrade:

```sh
docker compose --env-file .env.production -f compose.production.yaml run --rm backup once
cat "$HELVETIC_LENS_BACKUP_DIR/LATEST_SUCCESS"
```

Copy or replicate `HELVETIC_LENS_BACKUP_DIR` off the server. A second directory on the same physical disk does not protect against disk or host loss.

Restore is intentionally disruptive and requires the timestamp twice. First check out the intended application release and inspect the backup's `METADATA`, `environment`, and checksums. Stop every writer and public entry point while leaving PostgreSQL running:

```sh
docker compose --env-file .env.production -f compose.production.yaml stop caddy web scheduler worker-ai worker-cpu api backup model-manager
export BACKUP_ID=20260903T155446Z
export CONFIRM_RESTORE="$BACKUP_ID"
docker compose --env-file .env.production -f compose.production.yaml --profile restore run --rm -e BACKUP_ID -e CONFIRM_RESTORE restore
```

The restore verifies every checksum before changing data, replaces the database objects from the dump, then replaces the document/evidence volume. It never overwrites the host's current environment automatically. Compare the backed-up `environment` and `Caddyfile` with the checked-out release; restore the backed-up credential key when restoring its database. Then run the normal validated startup command and verify `/api/ready`, sign-in, one evidence file, one comparison, and the model inventory.

The development-host rehearsal created a PostgreSQL row and evidence file, backed them up, changed both, restored, and observed both original `before-backup` values. Repeat this rehearsal on the real backup mount before public registration and after material storage changes.

## Upgrade and rollback boundary

1. Record the current Git release and Compose image identifiers.
2. Run and verify an extra backup as above.
3. Pull the intended commit, set `HELVETIC_LENS_RELEASE` to that immutable identifier, validate, build, and start. The one-shot migration finishes before API readiness.
4. Verify readiness, authentication, registry reads, one connector, one saved comparison, and one local-model request.
5. If application verification fails before an irreversible migration, return to the recorded commit and release images. If a migration ran, restore the pre-upgrade database and evidence backup with the matching credential key; do not assume a code-only downgrade can reverse schema or data changes.

Caddy stores certificates in its named volume and renews them automatically while ports 80/443 and DNS remain correct. Check Caddy logs and certificate expiry during the target-host rehearsal.

Automated operational retention, cross-service correlation/metrics completion, Redis-loss recovery, and the full target-host install/upgrade/rollback exercise remain open HL-048 gates.
