# Pollen release recovery — incident and bounded repair

## Incident, 12 September 2026

Candidate `0ec41a916b4fdba62ae59651c2f9c623aedca294` passed the real full API gate
and image builds. Its normal Compose startup failed because the decoder health
probe invoked `python` without the micromamba entrypoint's activated PATH. The
server process itself remained running; Docker health exec reported executable
not found. This was missed by the earlier HTTP rehearsal, which ran Python through
the image entrypoint rather than exercising the declared Docker health probe.

Rollback to `6d7a5997b480c7da8fd78ec7938bf12d50c05737` failed while restoring
backup `20260912T013436Z`: a newer `monitoring_deliveries` foreign key prevented
dropping the old `users` primary key. The old `pg_restore --clean` operation was
not transactional. The controller had already stopped application services;
public readiness returned Cloudflare 1033. The old SHA in status is not proof of
a currently serving application. Do not label the release accepted.

## Repair scope (defined before implementation)

Use the decoder's absolute interpreter in the unchanged real health probe. Test
normal image startup and the exact Compose health command, not an overridden
entrypoint. Make restore remove the dedicated public application schema and replay
the verified archive in one SQL transaction. Refuse system databases and unrelated
schemas; a failed SQL replay must preserve the original database and documents.
Keep exact backup confirmation and checksums mandatory. Rehearse an older backup
against newer dependent tables, SQL failure, invalid archive, and a normal repeat.

This is one MV2-071 operational repair in a new feature worktree. Source/human
acceptance remains HOLD. No release gate is removed and the published migration
is immutable. The pinned controller still invokes the previous release's restore
script during rollback; committing this repaired script cannot retroactively
replace the old immutable snapshot or repair the already partial database.

## Concrete recovery boundary

Before further production activation: serialize recovery against the running
controller, preserve the exact pre-failure backup `20260912T013436Z`, verify all
checksums, restore that snapshot using the rehearsed repair, restart the previous
accepted stack, and independently verify public readiness and login. Do not take
a partially restored database as a new trusted baseline or substitute LATEST for
the named backup. Do not edit the serving source, bypass quality gates, overwrite
secrets or restore into the main product. Manual production recovery requires
its own authorization under AGENTS.md; routine feature publication alone does
not authorize these database/restart operations. No such action is performed by
the isolated regression script.

## Verification

`scripts/check_pollen_release_recovery.py --decoder-image <locally-built-image>`
uses a unique Compose project, an internal network, disposable PostgreSQL tmpfs,
synthetic credentials and temporary fixtures. It never loads production env or
volumes. Normal decoder entrypoint/CMD with the exact production health command
passed. The retained pre-fix restore failure was reproduced; the fixed restore
recovered older users/documents and removed newer dependent tables. Repeated
restore passed. An injected SQL error after reset/replay rolled back both schema
and data while leaving documents untouched. Unrelated schemas and an invalid
checksummed archive were refused before destructive changes.

The 80 affected production-deployment, release-instance, manager, history and
mandatory Monitoring backlog tests passed. Ruff passed the regression harness.
The exact production backup was checked read-only: all five checksums passed,
metadata release is `git-6d7a5997b480c7da8fd78ec7938bf12d50c05737`, and the database
archive is 51,479,280 bytes. This is a recovery candidate, not completed recovery.

## Proposed authorized recovery sequence

1. Temporarily disable `HelveticLens-Monitoring-v2-AutoDeploy`, stop only its exact
   active quality-gate container, let the current poll finish, and acquire the
   existing deployment lock. Do not run concurrent deployment commands.
2. Revalidate `20260912T013436Z` and retain it unchanged. Use the repaired restore
   script as an explicit read-only override for the previous release's restore
   service. Restore this exact snapshot with matching BACKUP_ID/CONFIRM_RESTORE.
3. Start the previous accepted `6d7a599` stack with its existing private selectors
   and secrets; remove only obsolete services of this same Compose project. Verify
   database readiness, application health and the exact public release SHA.
4. Integrate the reviewed recovery feature into Monitoring, release the lock and
   re-enable the existing scheduler. Its normal full quality gates remain required
   before the repaired Pollen candidate can activate.

The task branch may be published for review now. Monitoring integration and the
manual production sequence are held pending the explicit recovery decision.
