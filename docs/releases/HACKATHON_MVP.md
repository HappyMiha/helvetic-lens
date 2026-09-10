# Helvetic Lens 1.0 — Hackathon MVP

Release date: **10 September 2026**. Product snapshot tag:
**`v1.0.0-hackathon-mvp`**. Exact source commit:
**`7109a2891f9c99e53572008cc7c1a86001792a57`**.

This freezes the existing product before planning **Helvetic Lens Monitoring**.
It includes the Basel-Stadt first-material journey (`ea2796f`) and the English
Page guide for all 30 page routes (`7109a28`). The tag identifies an MVP
prerelease, not a claim that every production/pilot acceptance gate is complete.
Historical package/API version fields remain `0.1.0`; identify this product
release by the tag and full Git commit, not those internal package fields.

The annotated tag points at the original source commit. This guide and the
manifest are companion release assets, maintained on the release branch; they
are not additional application changes inside that tag. The freeze does not
advance `main`, start a deployment, or modify a running database.

## What is preserved

The [GitHub release](https://github.com/HappyMiha/helvetic-lens/releases/tag/v1.0.0-hackathon-mvp)
contains:

- `helvetic-lens-hackathon-mvp-source.zip`: the exact tracked source tree.
- `helvetic-lens-hackathon-mvp.bundle`: Git history and the annotated release tag,
  usable without GitHub access.
- `release-manifest.json`: commit/tree identity, critical file checksums, build
  inputs and explicit preservation limits.
- `HACKATHON_MVP.md`: this deployment and preservation guide.
- `SHA256SUMS`: SHA-256 checksums for the downloadable companion assets.

These files contain no production environment, credentials, user data or model
weights. A source archive is not an offline Docker/npm/Python/model archive.

## Retrieve the exact version

Use a fresh checkout on a **dedicated compatible Linux host**:

```sh
git clone --branch v1.0.0-hackathon-mvp --single-branch \
  https://github.com/HappyMiha/helvetic-lens.git helvetic-lens-hackathon-mvp
cd helvetic-lens-hackathon-mvp
test "$(git rev-parse HEAD)" = 7109a2891f9c99e53572008cc7c1a86001792a57
```

For a downloaded bundle, verify the companion assets in their download directory
and clone the included tag instead:

```sh
sha256sum -c SHA256SUMS
git clone --branch v1.0.0-hackathon-mvp \
  helvetic-lens-hackathon-mvp.bundle helvetic-lens-hackathon-mvp
cd helvetic-lens-hackathon-mvp
git bundle verify ../helvetic-lens-hackathon-mvp.bundle
test "$(git rev-parse HEAD)" = 7109a2891f9c99e53572008cc7c1a86001792a57
```

The ZIP is suitable for building without Git history. Keep its manifest beside
it, since the extracted ZIP has no `.git` directory. Obtain checksums through the
trusted release channel; matching checksums detect corruption, not publisher
identity independently of that channel. The tag is annotated, not cryptographically
signed.

## Fresh deployment

The frozen production layout requires Docker Engine with Compose, Linux, an
NVIDIA driver and NVIDIA Container Toolkit. It explicitly requests GPUs. The
documented target is 32 GB RAM and two GTX 1080 GPUs; its hardware/answer-quality
acceptance limits still apply. There is no separately verified CPU-only production
recipe in this release. Configure DNS, HTTPS and working SMTP on the intended host.

Create a private environment file and edit it before running Docker:

```sh
umask 077
cp deploy/production.env.example .env.production
```

Set `HELVETIC_LENS_RELEASE=7109a2891f9c99e53572008cc7c1a86001792a57`.
Set the real HTTPS domain and SMTP values; generate a unique URL-safe database
password and a stable credential-encryption key. Choose a dedicated, protected
absolute `HELVETIC_LENS_BACKUP_DIR` and a distinct deployment-state directory.
`DEFAULT_LOCALE=en-CH` sets the server fallback. Choose English in the language
selector, or open `/login?locale=en-CH`, for the interface; browser, cookie and
account preferences can otherwise determine its language. Keep this file and the
credential key in protected operator storage, outside Git.

```sh
python3 scripts/validate_production_env.py --env-file .env.production &&
docker compose --project-name helvetic-lens-hackathon-mvp \
  --env-file .env.production -f compose.production.yaml config --quiet &&
docker compose --project-name helvetic-lens-hackathon-mvp \
  --env-file .env.production -f compose.production.yaml up -d --build --wait
```

Use that same project name, environment file and Compose file for every later
command. The project name isolates named volumes and networks; it does **not**
remove the fixed Caddy port bindings on 80/443. Coexistence with another deployment
requires another host or a deliberately reviewed entry-point override.

The migration service applies the frozen schema before API startup. This snapshot
contains 57 migrations with head **`ef5169a0c32d`**. Check the result:

```sh
docker compose --project-name helvetic-lens-hackathon-mvp \
  --env-file .env.production -f compose.production.yaml ps
docker compose --project-name helvetic-lens-hackathon-mvp \
  --env-file .env.production -f compose.production.yaml exec api alembic current
```

Confirm the deployment's public `/api/ready` endpoint and `/login`. Register and
verify the operator account, then use the existing admin CLI when platform access
is required:

```sh
docker compose --project-name helvetic-lens-hackathon-mvp \
  --env-file .env.production -f compose.production.yaml \
  exec api helvetic-lens-admin promote operator@your-domain.ch
```

Model license acceptance, download and start are explicit steps in Models.
Fresh installation has no existing accounts, user corpus or downloaded models.
Check one source collection, saved evidence, a comparison and an actual local
model request separately; service readiness does not prove those workflows.

For the supported tunnel alternative and detailed operational instructions, use
the [production guide pinned to this release](https://github.com/HappyMiha/helvetic-lens/blob/7109a2891f9c99e53572008cc7c1a86001792a57/docs/PRODUCTION_DEPLOYMENT.md).

## Keep the MVP frozen

Do not install or poll the default automatic release manager for this frozen
installation. It follows `origin/main`; it has no deploy-tag mode. If restoring
on a host with an existing manager, explicitly stop its scheduling for that
installation before starting a manual release. Otherwise a later Monitoring
commit can replace the MVP. No scheduler was changed while preparing this release.

Never move or replace this tag. Use a new version/tag for fixes. Future Monitoring
development and its dedicated backlog remain separate from this snapshot.

## Preserve a populated environment as well

A Git tag cannot restore users, evidence or configuration. Before upgrading an
existing populated environment, take and verify its normal backup using its
actual Compose project and environment. Keep an archival copy outside rotating
retention. Retain the matching credential key and private configuration.

The built-in backup includes PostgreSQL, evidence documents, the environment,
Caddyfile and checksums. It does not include Docker images, model-library files,
Redis AOF, Caddy certificates, deployment journals or Cloudflare credentials.
Preserve those separately where needed and under their applicable access/license
rules. Never attach private backups or credentials to the public release.

Do not start this older code against a database migrated by a future Monitoring
version and call it a rollback. Restore a matching database/evidence backup and
key into a separate environment, following the frozen restore procedure. Schema
and data downgrades are not implied by changing Git tags.

## Rebuild and verification limits

The source contains npm and uv dependency locks and digest-pinned main container
base images. It does not fully lock build tooling (`uv`, Hatchling), apt
repositories or all model-manager transitive dependencies. Registry, package,
model and official-source availability can change. This is a recoverable source
release with a build recipe, not a guarantee of bit-identical or offline runtime
recreation. For exact binary restoration, archive the successfully built runtime
images and their checksums on the deployment host as well.

Existing source-baseline evidence includes the frontend build/checks, 30 help
routes, 20 Basel-Stadt browser journeys, 30 shell-navigation journeys, 48 axe
checkpoints across help/Basel tests and bounded live Basel source acceptance.
See the [frozen verification record](https://github.com/HappyMiha/helvetic-lens/blob/7109a2891f9c99e53572008cc7c1a86001792a57/docs/VERIFICATION.md).
The release manifest separately records packaging/build checks performed during
the freeze. Earlier full-API runs in that record are not a new complete test run
of this exact release.

Basel-Stadt remains the explicitly limited German legislation pilot. Court,
parliament, full-gazette and annex coverage are not supplied by that package.
Independent unaided-onboarding research, field-pilot acceptance, legal-answer
quality and target-host deployment acceptance remain separate gates. Creating
this release does not assert that a new production deployment was rehearsed.
