# Bounded monitoring-topic matching

HL-075 extends the existing normalized event, evidence, relation-candidate, and source-pack pipeline. A topic match means that a saved public event is relevant to an organization's stated interest. It is never presented as proof that one legal work amends, repeals, or otherwise legally affects another.

## Retrieval contract

Matching begins only after connector evidence is committed and organization event state has been fanned out. It therefore considers only organizations entitled to see the event. For each event the production query uses exact SR/RS and article references plus PostgreSQL `simple` full-text search over the current active topic revision. Controlled filters then enforce the selected source packs, document and event kinds, jurisdiction, language, importance floor, and exclusions. The final signals record exact concepts, synonyms, official identifiers, article references, or normalized full-text terms.

The existing HL-044 normalizers provide title tokens and legal-reference extraction. pgvector remains disabled: the checked-in five-language positive and noise cases do not establish a measured recall gap that would justify embeddings. Ambiguous AI expansion is also disabled at the current threshold. If a later labelled evaluation enables it, `TOPIC_MATCH_AI_CANDIDATES_PER_EVENT` is the hard ceiling after deterministic filtering; the default is three and the normal deterministic path makes zero model calls.

## Persistence and bounds

`TopicEventMatch` stores the organization and topic revision, immutable event/work/expression/document-version references, reason signals, exact source and official-identifier evidence, evidence and rule fingerprints, confidence band, review decision, model provenance when applicable, and timestamps. Repeating the same event and fingerprints reuses the row. Changed event evidence updates the candidate and returns its decision to `pending`; editing a topic creates a new immutable revision and therefore a new match identity.

Defaults are explicit and configurable:

| Bound | Default |
| --- | ---: |
| Organizations considered per event | 100 |
| Current topics considered per organization/event | 50 |
| Persisted matches per organization/event | 20 |
| Saved events examined per history-job execution | 500 (resumable, not a lifetime cap) |
| Ambiguous AI candidates per event | 3 (currently unused) |
| Pending/rejected/muted match retention | 180 days |

Creating, editing, or resuming a topic enqueues one idempotent `topic_match_backfill` job for that immutable revision on the ingest queue. Historical replay targets only its owning organization, independent of the global live fan-out caps. Each execution examines up to `TOPIC_MATCH_BACKFILL_LIMIT` already-visible saved events, ordered by organization admission time and ID. An index covers that keyset; no ever-growing list of event IDs or offset pagination is used.

The capture cutoff is the job's first start time (retained even if the first batch fails). The checkpoint includes owner, topic and plan/rule revision, eligible count, cursor, processed/matched/updated/reused/excluded counts, remaining work and removed unchecked admissions. Capture/cursor timestamps describe local visibility, not publication, legal validity or complete source coverage. Later admissions are outside this snapshot and use live ingestion. The checkpoint does not freeze mutable source evidence; changed fingerprints continue to invalidate matches normally.

The worker locks its durable job and the plan for one bounded batch. Matches, counters, checkpoint and the next outbox message commit atomically. A successful batch returns to the queue behind previously waiting outbox messages, resets the consecutive failure budget and releases the worker. Failure rolls back that batch; retry starts at the last committed cursor. Cancellation is applied at a safe batch boundary and preserves that cursor. A changed or inactive revision stops the old job as superseded; resuming a topic starts a check of its new immutable revision. Lease recovery skips locked batches rather than reclaiming work while its transaction is committing.

`GET /api/monitoring-topics` and topic detail return `history_scan` with status and coverage counters. The five-language topic card uses the existing scoped resource cache/poller. `POST /api/monitoring-topics/{topic_id}/history-scan` is an organization-admin mutation: it reuses active/complete work, retries failed/cancelled work, or creates a versioned replacement for an older `bounded_complete` result that still had more events. It never rewrites the old job or pretends its unknown remaining count was zero. It does not trigger a model call or send a notification.

The **live** event path still has the 100-organization / 50-topic / 20-match caps above. Resumable live fan-out, preview/scorer parity and feed-wide source freshness/degradation are unfinished HL-094 work. This history change does not certify those paths as complete.

`GET /api/monitoring-topics/{topic_id}/matches` returns at most 200 evidence-linked candidates in newest-first order. Expired pending, rejected, and muted candidates are removed by bounded operational cleanup; confirmed decisions remain reviewable.

## Evaluation gate

The automated labelled set covers a relevant and irrelevant example in German, French, Italian, Romansh, and English, exact official-reference evidence, exclusions, paused topics, fingerprint reuse, tenant isolation, durable backfill, and the 100-organization cap. Current deterministic test results are 5/5 relevant examples retained and all explicit noise/exclusion controls rejected. These are regression results, not a production precision claim.

Before changing thresholds or enabling AI/pgvector, record on a representative reviewed sample:

- precision/noise and missed relevant items by language and source;
- evidence-open rate;
- confirm and reject rates;
- mute rate;
- the share of topics refined after reviewing results.

HL-076 will expose shared review decisions and interaction measures in the unified interest feed. Until that measured sample exists, defaults stay fixed.

## PostgreSQL history smoke gate

`scripts/check_topic_history_postgres.py --database-url <url>` requires an **empty disposable local database named `hl094_regression`** and refuses existing tables. It runs the 501-event/outbox test with the real PostgreSQL dialect, checks index downgrade/upgrade on populated data, and checks that active batch/plan locks prevent unsafe lease recovery and mid-batch plan changes. It uses synthetic data and a model double. Stop/remove the dedicated test container afterwards; never point this gate at an application database.

The normal API suite uses isolated SQLite databases for transactional failure/retry, cancellation, revision supersession, cross-organization scope, removed/excluded events and idempotent legacy recovery. Browser component fixtures are regression evidence, not independent human usability or legal-relevance evaluation.
