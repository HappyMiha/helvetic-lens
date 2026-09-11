# ADR MV2-001 — additive monitoring kernel, contract v1

Decision date: 2026-09-11. Accepted for implementation in the Monitoring channel.
This ADR implements the foundation task, not live Pollen Watch or a source gate.
Baseline: `7109a2891f9c99e53572008cc7c1a86001792a57`; immutable annotated MVP
tag object: `c33f3094e51019bfe1083bec71a53858eef1917c`. Integration baseline:
`cb47c01c0ef4c3632e0e65388d4092801ca42c2d`.

## Decision and versioned interfaces

Extend the existing modular API, PostgreSQL, worker/outbox and authenticated web
application. Add generic tables in MV2-070; do not insert environmental records
into RegulatoryWork/RegulatoryEvent, relax their legal CHECKs, reuse their enums,
or create a parallel pollen service. Existing legal ingestion stays authoritative.

Every persisted generic record carries `contract_version=1`. Unsupported versions
are rejected before writes or job acknowledgement. Versioned opaque IDs are
references, not encoded URLs, titles or user coordinates. Source adapters return
normalized source facts; they never assign workspace permissions or relevance.

| Record | Required identity, version and boundary |
|---|---|
| Template | Immutable `(template_id, version)`, configuration schema, source capabilities, rule revision; only confirmed coverage is selectable |
| Subject/revision | Private organization ID and owning principal, template/version, immutable configuration revision, active/paused/archived lifecycle; compare-and-swap edits and unique Start request key |
| Entity | Shared `(authority, stream, upstream_key, instance_key)` unique identity; station/metric/period or official object instance; no private subject configuration |
| State/evidence | Entity ID, source revision, normalized-schema and adapter versions, immutable payload and permitted evidence hash/reference, fetched/detected/source/effective time, precision, quality and rights policy/version |
| ChangeSet | Entity, old/new state IDs, rule/version, typed facts and materiality; unique ordered state pair plus rule version; timestamps alone do not establish materiality |
| Development | Stable story identity with immutable ChangeSets and atomic current pointer; source lifecycle independent of source health and user review |
| Relevance | Organization, subject revision, development change, deterministic method/version, positive or negative reasons and supporting state facts; configuration changes never rewrite history |
| Review/decision | Append-only organization, actor, reviewed change ID, time, choice and comment; material successor reopens while preserving earlier review/owner |
| Delivery | Recipient/organization/development/material change/policy version/channel uniqueness; multiple subjects contribute reasons to one delivery; authorization and consent rechecked before send |
| Deadline | Source or calculated provenance, timezone/precision, input state and rule version; reminder key binds current deadline revision; replacement cancels obsolete reminders |

Numeric values use Decimal and explicit units, aggregation periods and measurement
versus forecast type. Null/missing/invalid/stale is never zero, improvement or
source resolution. Forecast issue time and validity interval are distinct from
fetch time and measured time. MV2-069 defines exact station/allergen semantics;
MV2-070 supplies persistence validation and rule implementations. The contract
does not pre-approve any forecast URL or inferred measurement category.

Facts, calculations, optional AI explanations and human decisions occupy separate
fields and retain their own provenance. Calculations reference input states and
rule version; AI references model/prompt/evidence and cannot overwrite a fact;
decisions reference an actor and the reviewed revision. Core ingestion, numeric
rules, relevance, history and delivery never require an LLM.

## Rollout and authorization

`helvetic_lens.monitoring_contracts` implements the immutable rollout contract:
global kill switch off by default, then an exact workspace/template/version grant.
`legacy` uses existing readers; `shadow` compares retained projections without
publishing or delivering; `enabled` requires implemented code and a verified source
gate. Unknown or conflicting grants fail closed. Policy lookup is not authorization.
MV2-070 must wire this contract into API, worker, feed and delivery consumers;
MV2-001 adds no activation endpoint and changes no current reader.

Personal subjects live in the existing owner-only personal workspace. New private
models must join the central organization scope policy and negative IDOR tests.
Public entity/evidence records never include private location/profile/review data.
Service jobs carry a workspace and captured revision, then recheck current rights.
The shared corpus and user state must not become independently editable copies.

## Compatibility matrix and migration boundaries

| Existing boundary | Required behavior / owning implementation |
|---|---|
| Auth, organizations, membership, sessions, CSRF | Reuse unchanged. No new identity system; MV2-070 tests role revocation and owner-only personal state |
| `/api/laws`, corpus, versions, comparison and native evidence links | Preserve IDs, artifact bytes/hashes, routes and existing response fields; add separate generic APIs in MV2-070 |
| Topics, watches, source-pack subscriptions and legacy reader | Preserve writes and selectors; MV2-060 owns the legal bridge; MV2-070 contributes only needed C5 coexistence |
| Today/interest feed, read/mute/reviews, Ask and Basel onboarding | Legacy reader remains fallback; new material change cannot erase reviewed-through history; MV2-031 validates mixed daily workflow |
| Job dispatch, checkpoints, outbox and delivery receipts | Extend handlers with a version check; preserve old receipt identities; no replay delivery from baseline/backfill |
| Database / Alembic | Additive nullable or separately keyed structures, constraints and bounded indexes; no renames/drops/reinterpretation of old columns |

Bridge bindings are unique by legacy object ID and projection version. Legal writes
remain in legacy ingestion, followed by transactional outbox projection and a bounded,
resumable cursor. Preserve original object IDs and evidence URLs. Baseline/backfill
records carry a migration generation and admission cutoff; existing delivery IDs
remain aliases so retries do not notify again. Never populate a new source capability
from a legal enum or synthetic fixture.

Rollback first disables new readers/delivery, drains or quarantines incompatible jobs,
then uses the last compatible application on the additive schema. New records and
old evidence remain. Destructive downgrade requires an independently verified backup
and a separate migration procedure. MV2-056/070 own populated PostgreSQL upgrade,
restart/restore and bridge acceptance; this foundation's SQLite copy characterization
is not those later gates or a production-data test.

## Reproduction and acceptance evidence

Run `scripts/monitoring_compatibility_inventory.py --revision <commit> --output <path>`
from the task checkout. It verifies the MVP tag object and commit; extracts tracked
API/web routes, model declarations, migration hashes, dispatch literals and contract
file hashes from baseline/current Git blobs; and checks every one of the 35 unfinished
legacy IDs has exactly the existing disposition. Dynamic dispatch also requires
inspection of `service.py` and `interest_policy.py`; the inventory does not claim
runtime reachability or independent UX acceptance.

`test_monitoring_contracts.py` exercises exact rollout isolation and fail-closed
fallback. It populates a synthetic legacy database through existing API/corpus
paths, makes a separate SQLite backup copy, repeats migrations on the copy and
compares every table's rows, IDs, evidence files and the original law response.
It tries a pollen value against the legal CHECK and requires rejection. Existing
corpus/Basel tests supply legacy route, identity/replay and source compatibility
coverage. These tests use no production database, credentials or real email.

Review: Codex implementation review against ARCHITECTURE.md and the existing
schema/API/job boundary; not an independent human, language or user-test review.
Results and exact fixture hashes are recorded in MV2-001 evidence after execution.
