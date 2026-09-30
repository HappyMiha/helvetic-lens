# Shared feed-check history — 1.80

Scope recorded before code, 30 September 2026. VERIFYING production activation.
MV2-002/011/020/024 and broad C20–C24/professional/human acceptance remain OPEN.

## Whole outcome and source readiness

In the existing dossier Source coverage reader, expand a selected official stream
and inspect retained shared collection runs: actual start/finish, successful,
partial, failed, queued/running or unknown outcome, reported aggregate events and
item errors, pagination and recovery after a failed read. Current selection,
subscription, catalogue and scheduling state remain distinct from historical runs.
Both Legal and Pharma use the same reader and Core. This is shared collection,
not proof that this dossier reviewed each document or that its question has no
relevant changes. Zero recorded events never means the source is unchanged.

ConnectorRun already stores the required safe operational metadata. Reuse it and
current topic revisions/pack selection from product_coverage, source_capabilities,
topic_coverage snapshots, existing native ingestion/jobs/auth and ResourceReader.
No new schema, database, ingestion, provider call, model request, subscription,
notification, monitoring consent or scheduler change. Local fictional connector
acquisition and durable jobs provide acceptance evidence; no live/private/paid
research, browser/preview/DOM/screenshots or frozen evaluation.

## Authority and honest provenance

Require current dossier/product/principal access, current selected pack and stream
in its retained definition, and a supported public-source capability. Never expose
another workspace's requesting identity, raw error text, job IDs, cursors or raw
provider payloads. Missing/unselected/unsupported streams cannot reveal run history.
Draft, paused or disconnected selections may read shared operational history but
must remain explicitly unmonitored/disconnected. Invited dossier readers use their
existing grants; revocation removes history. No private event bodies are read.

Read bounded scalar ConnectorRun metadata, ten rows per page and a fixed created
cutoff. Actual timestamps only; queue time is not start time and absent completion
remains unknown. Retries can update existing rows. Aggregate new/changed/error
counts are reported counters, not an exact immutable membership manifest. A
successful retry can retain earlier item errors; never label them all unresolved.

Do not reconstruct event membership with synchronization._events_for_run: it has
only a lower time bound. ConnectorReceipt has no run FK, and the existing job
result records a page reference but no pinned event membership. Therefore do not
invent per-run source, topic-match or research links. Explain this limit in the
reader. Normalized SourceHealth and exact feed-member provenance remain OPEN.

## Acceptance

- Both products: actual scripted native connector -> partial collection -> retry
  and persisted records -> new completed run -> failed source; retained earlier
  success, honest aggregate counts and no additional work caused by reading.
- Queued/running/unknown/legacy statuses and absent times cannot imply freshness;
  recorded errors remain distinct from currently unresolved failure.
- Ten-row stable-cutoff paging; new runs require refresh; updated rows may change.
- Current topic revision, pack/stream removal, unsupported capability, draft,
  paused/disconnected source, guest/tenant/product/session and revocation boundaries.
- No raw errors/cursors/job/requestor IDs or document bodies in the response.
- Actual reader lifecycle: on-demand requests, failure, retry, session invalidation,
  pagination, escaped supplied text, existing compact reader preserved.
- Affected Core tests, exact API lint and backlog guard; both full client suites,
  lint/types/build, source/privacy/parity, tested main push and normal deployments.


## Local acceptance

40 distinct Core checks passed: ten new product history cases, 29 affected coverage,
connector, synchronization and topic-coverage regressions, and the backlog guard.
Actual local fictional ConnectorRunner acquisition and native durable jobs exercised
partial persistence, resumed persistence with retained old errors, no newly recorded
events and failed discovery. Read-only history did not fetch, enqueue or call a
model; raw errors/cursors/requester/job data were absent. Current selection,
source/pack removal, product/tenant/guest grants and revocation, draft/disconnected/
paused state, fixed-cutoff pagination and missing timestamps were checked.

The initial missing-time test exposed a non-null timestamp formatter; replaced it
with the existing nullable coverage formatter and all ten product cases passed.
The backlog guard then caught a broad planned task incorrectly marked in progress
in its index; restored its parent status and the guard passed. Scoped history does
not close broad native ingestion acceptance.

Both clients passed all 447 tests, lint, types and production builds. Five new
reader cases include actual React lifecycle behavior: deferred fetching, bounded
paging, refresh, failure/retry and session reset. A test-loader teardown declaration
was corrected before the final full suites. Current collection errors remain
separate from earlier successful evidence; absent times and unknown outcomes are
explicit. UI reuses existing folded source sections and reading styles. No browser
or human usability/semantic acceptance was performed. Exact production verification
follows separately; full target architecture remains OPEN.
