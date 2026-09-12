# Monitoring navigation and Pollen availability — 12 September 2026

## Authorized receiving task

The user requested a Monitoring navigation group containing Pollen Watch, access
for all users, and merging **all Monitoring changes into main**. MV2-031 records
this receiving subtask. This supersedes the earlier no-main rule for this merge.
The Monitoring branch remains the active backlog; the two sites retain separate
deployments, databases and private configuration. The frozen MVP tag is unchanged.

## Behavior

Desktop navigation and the mobile More menu expose Monitoring → Pollen Watch to
every authenticated role in all five locales. Existing legal navigation is preserved.
An explicit workspace_id "*" rollout grant covers current and future authenticated
workspaces for the exact pollen-watch template version 1. Exact workspace decisions
override that fallback; ambiguous grants fail closed. Explicit disabled policies
remain a kill switch. Membership, owner scope, viewer restrictions, source readiness
and separate email consent remain enforced. New installations default to public
Pollen access; explicit environment policies take precedence.

Main and monitoring-v2 support draft/live/scheduler/delivery/retention paths. The
existing bounded decoder now belongs to shared production Compose, retaining its
private network, read-only filesystem, resource bounds and absence of ports,
credentials and persistent volumes. Each instance still requires its own approved
POLLEN_SOURCE_POLICY. Git integration copies no private data or source approvals
to HappySnowman. Code availability does not establish live source coverage.

## Verification

- 350 Pollen/Monitoring API tests passed, including access for new accounts on both
  instances, private-data isolation, source-gated Start, exact revocation, duplicate
  grants, kill switch and populated-database-copy preservation.
- 56 authentication, production manifest and release-isolation tests passed.
- All 14 delivery tests passed after adding both-instance scheduling/delivery
  coverage; consent rechecks and deduplication remain enforced.
- Production web build and localization, shell, resource, report and help checks
  passed. Thirty browser navigation journeys cover five locales, three roles and
  two mobile widths, plus desktop group checks after resize.
- Complete synthetic Pollen browser journeys passed in five locales, including
  47 full-document axe checkpoints, runtime recovery, source revocation, consent,
  editing, backup, deletion and geolocation errors. Independent accessibility and
  pilot acceptance remain separate.
- scripts/check_pollen_compose.py passed both channels with public defaults and
  explicit disable. It renders synthetic configuration without starting services.
- main's divergent 4aa4981 commit only changes routing documentation. All 36
  Monitoring commits through c5a9155 are retained. Conflicts preserve later task
  definitions/evidence and main's explicit link to the authoritative backlog.

## Activation boundary

Before publication, public Monitoring readiness verified c5a9155; the controller
records successful activation at 2026-09-12 04:30:50 UTC. Main readiness responded
successfully but did not expose an immutable release identity.

At 08:17 UTC the authorized wildcard grant was staged in Monitoring's private
environment under the deployment lock, with a configuration backup. Existing
grants and all other environment values, including four approved source channels,
were preserved. No private monitor, consent or running service was changed.
The old release accepts this schema; only the new release interprets the wildcard.
Effective all-user access therefore awaits its normal deployment.

This record establishes implementation and local verification, not activation of
its own commit. Main source activation and exact public release identity require
separate operational verification. Existing MV2-031/071 acceptance remains open.
