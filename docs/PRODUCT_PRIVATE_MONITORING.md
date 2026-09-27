# Private team monitoring

Status: DONE — scoped dynamic dossier stage 2b2, release 1.12.
Local implementation uses the shared core and both existing product clients.
Exact native and both-client production acceptance passes. The complete dynamic and visual specifications
remain IN PROGRESS.

## Audience and native authority

The owner chooses accepted dossier members or the whole workspace at activation.
Both clients default new setup to the invited team and enable native dossier roles
when necessary. Workspace sharing is disclosed with a separate confirmation.
Clients check the new native page-watch capability contract before private
activation; an older server cannot silently interpret that request as workspace
sharing. The native release is activated before either client is published.
Activation still requires native workspace administrator authority as well as the
dossier OWNER capability; private membership never grants broad native authority.
The audience stays fixed. Existing activated dossiers and native topics retain
their previous workspace audience. No existing private material is published.

Migration `fdc495bef124` adds a default-workspace audience to product dossiers and
an optional private dossier relation to native topics. A composite foreign key
binds each private topic to its dossier's organization. Private activation creates
these topics in the same transaction, using existing profile/card idempotency.
It does not copy the matching engine, queue, event corpus or delivery system.
Deleting a dossier cascades to its private topics. Native memberships and accepted
roles retain the 1.11 ownership, invitation and account-erasure boundaries.

## Read, write and delivery boundaries

One SQL predicate checks current accepted members for private topics. HTTP ORM
queries apply it to topics, revisions, matches, review history and their jobs,
including aliased queries and counts. Event-wide matching jobs expose their
operational state and job/step completion, while HTTP views omit internal cursors
and topic totals that span private teams. Durable worker checkpoints remain intact.
Native organization filters still apply.
The profile/product visibility predicate protects dossier lists, workspace search,
workbench, files, export, contributions, investigations and activity. Native topic
changes, reviews, history jobs, cancellation and retries also enforce current
dossier capabilities under the existing organization/account/session locks.

Background matching continues in the dossier's organization. Recipient feed and
digest projections explicitly apply the same topic predicate before event/cursor
selection. Preparing a digest is not permission to deliver it later: final delivery
rechecks membership while holding the organization lock. A queued private-only
digest is skipped after access is removed. Previously saved digest web views and
recipient job results redact topics whose access was revoked, including derived
brief text. The original delivery record remains intact. Already delivered email
and downloaded originals cannot be recalled. Digest jobs are readable by their
recipient, not other workspace members. No new invitation email or digest consent
is created by activation beyond the user's existing explicit delivery choice.

Private contribution reviews use the existing coordinator. Current actor/session
and dossier capability are checked before and after each operation; revocation
pauses queued work and prevents late findings from becoming retained claims.
Public snapshots remain separately authored, previewed and explicitly published.

## Source and inference limits

Private monitoring matches the selected approved source feeds. Source subscriptions
and independently shared source documents remain workspace resources. Shared
materialized AI briefs exclude private topics from their context; private detailed
research remains available through Ask / Investigate and contribution review.

Individual page watches currently use the workspace library. Private dossiers do
not create them: the API rejects that action before fetching, and both interfaces
explain the disabled capability. URLs selected during setup are saved as private
research references. This does not claim a new private page-watch engine or
unlimited Internet coverage. Existing public-query disclosure, source approval,
provider configuration, bounded search and evidence-quality constraints remain.

## Validation and deployment

Focused HTTP/database/job regressions pass for both products, including nonmember
workspace administrators, invited readers, removal, feed visibility, job mutation
roles, retained digest history, prepared-delivery revocation and private contribution
workers. Tests also verify alias/count isolation, shared-brief exclusion, migration
equivalence and legacy preservation, cross-organization foreign-key rejection,
and page-watch denial before any fetch. The broad affected native suite passes 661 cases with two conditional
PostgreSQL concurrency skips. The final private/job/live-matching run passes 31
cases; these counts overlap. Exact API lint and the required backlog gate pass.
Both final client suites pass 84 cases, lint, strict types and production builds;
each build contains 121 files. Configured provider credentials are absent. Both
GitHub CI runs succeed. Production verification passes 63 HTTP/auth/gateway checks
and 39 exact served JS/CSS hashes per custom domain. Native source hashes match
all 30 checked modules; private/team composite foreign keys, migration
`fdc495bef124` and the nine research tables are present. API and CPU worker health
pass; the AI worker is running without a configured Docker health check and its
local extraction fixture passes. Local Laya is healthy. Native functional release
`git-3378e6d33ada` activated at 18:06:26 UTC; Sites 15 Pharma and Loyer published at
18:07:42/18:08:14 UTC. [Exact release receipt](product-releases/2026-09-27-1.12.0.json).
No browser interaction, whole-page visual QA or professional factual-quality
acceptance is claimed. No paid provider calls or production
user records are needed for these checks.

Once private active monitoring exists, rolling back to code predating this policy
is unsafe even if schema columns remain. Roll forward with the access policy
preserved. The migration refuses downgrade while private topics are retained.

Remaining outcomes: invitations outside the workspace without broad native grants,
living public research through the same coordinator, cross-investigation claim
reconciliation, automatic material-change reopening and native visual migration.
All nine Monitoring sections remain visible; support is parked and customs/C4
remain deferred.
