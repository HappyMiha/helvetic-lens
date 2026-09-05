# Bounded inbox reads

HL-099 is in progress. The current Impact inbox still groups persisted law-related candidates; it is not yet the unified topic/law feed.

## Analysis-history selection

For each organization candidate, `ImpactInboxReader._latest_analyses` transfers at most two `RelationImpactAnalysis` records. It selects the latest attempt in SQL, then the latest successful result under the current relation-result schema (if different). History size comes from `COUNT`, not from loading every result/evidence JSON into Python. Empty history uses one query, a latest current success uses two, and a failed/obsolete latest attempt with a separate current result uses three. These counts describe this helper, not the entire inbox request.

Ordering is stable by `created_at DESC, id DESC`. The second selection and count cannot pass the latest attempt's timestamp/ID, so a newer attempt arriving between queries appears on the next read. This ceiling is not a database-wide snapshot of arbitrarily backdated inserts or concurrent updates. The current validated conclusion remains visible when a newer attempt fails, and old-schema successes remain historical. Existing organization scoping applies to selections and counts. No inference runs on reads or digest delivery.

Migration `fa27c61d3098` adds the organization/candidate/time/ID index used for history traversal. The database still counts matching history and may inspect older rows to find a current-schema result; the change bounds transferred payloads and application materialization, not total database work or latency for every corpus shape. A maintained projection or more selective index remains an option if measured query plans justify it.

## Digest detection periods

Preview captures one end instant and delivery reuses its saved start/end. SQL selects `detected_at >= start AND detected_at < end`, optional connector/authority choices and personal dismissed/muted exclusions before hydrating candidate/evidence records. Read events remain eligible; another user's or organization's mute cannot suppress this recipient's event. Source choices use distinct scalar columns over the organization's available candidates, so a quiet period or active source filter does not erase the menu.

The summary repeats the period/state/source/severity checks and marks `truncated` only when a 51st eligible event actually exists. This fixes the false flag at exactly 50. Web preview, delivery history and email now expose the selection limit and point to the full saved Impact inbox. Each event retains `impact_count` and `impacts_truncated` after severity filtering; up to five affected laws are summarized, with an actual shown/eligible count. Older saved summaries without these fields do not invent a count or infer truncation merely from a five-item list. The event-limit wording also tolerates historical pre-fix flags without inventing an exact number of omitted events. Delayed/retried jobs keep their saved detection period but reevaluate current preferences, private state and saved conclusions; this is not a frozen database snapshot. Backdated admissions inside a completed period still need a separate catch-up policy.

## Event pages for digest consumers

`iter_groups` selects at most 50 distinct event IDs per SQL keyset page, ordered by `detected_at DESC, id DESC`, then hydrates only those event groups. Related laws are never split between pages. Digest preview and delivery stop after 50 eligible summarized events plus one eligible overflow sentinel; up to 49 additional groups can have been prefetched in that last page. Severity still uses the actual persisted assessment/review rules after hydration, so sparse matches may require traversing the full selected period.

The traversal fixes an admission-time ceiling (`OrganizationRelationCandidate.created_at < traversal_start`); newly admitted events or law deliveries wait for the next traversal. The cursor advances through selected keys even when presentation filtering removes every group. Existing evidence/state changes are not frozen. Arbitrarily backdated admission timestamps or edits to event detection timestamps are outside this traversal guarantee. The public inbox API remains unchanged and is not yet paginated.

This bounds retained event pages, not every dimension of work: one event can affect many watched laws; related entity/review/history lookups are still per item, and SQL DISTINCT/sorting can inspect many candidate rows. Worker preparation now checkpoints one 50-event page per execution; per-event law fanout, query cost and SMTP duration still need workload validation before claiming a hard wall-clock or memory bound.

## Durable digest preparation

`digest_delivery` jobs prepare one page (at most 50 event keys plus a scalar overflow sentinel) per worker execution. A versioned checkpoint in the existing Job JSON binds the delivery, organization, recipient, period and preference fingerprint. It stores the admission ceiling, keyset cursor, inspected/page counts and at most 51 selected event IDs; it does not duplicate source/evidence bodies. Checkpoint and outbox yield commit together under the owned job lock. Failed page work rolls back, while completed pages survive retry/cancel-and-resume. Successful yields reset only the consecutive failure budget and rejoin the queue behind earlier waiting work.

A completed selection skips period rescanning on email retries. Before dispatch, the worker refreshes only those IDs against current organization admissions, personal read/mute state, source/severity filters and saved conclusions. Newly ineligible selected items are removed without filling their places from already scanned history; this is bounded revalidation, not a frozen corpus snapshot. Preference changes restart preparation for the same saved period and capture a fresh admission ceiling; repeated preference editing can postpone completion. Preview still streams in one request and has no durable worker checkpoint.

The dispatch transaction verifies the current lease/type/target, cancellation, enabled subscription, active account and organization membership. Locks serialize duplicate delivery attempts and recipient/preference changes around mail dispatch. Completed successful deliveries are not resent by an ordinary retry. An older delayed delivery cannot rewind `last_sent_at`. SMTP remains an external side effect: a crash/ambiguous transport response after SMTP accepts a message but before the database commit can still duplicate a retry despite the stable Message-ID. These tests do not claim exactly-once mail delivery.

No schema migration is required. Existing queued jobs without checkpoints initialize on first execution. The two existing job stages remain selection and delivery; inspection/batch/selected counts are saved as diagnostic progress, with no invented total-corpus percentage. Invalid or foreign checkpoints fail instead of silently skipping evidence.

## Verification

`scripts/check_inbox_history_postgres.py --database-url <url>` refuses an existing database or any destination other than an empty loopback PostgreSQL database named `hl099_regression`. A 10,001-row synthetic history verifies three selection/count queries, two materialized payloads, the actual inbox response, equal-timestamp ordering, failed-latest fallback and an index downgrade/upgrade with saved history preserved. It uses test fetch/model doubles and does not contact a paid model. Remove the task-owned database container after the check.

`--suite periods` separately verifies 10,000 archived events are excluded before loading payloads, exact start/end boundaries, source selection, private mute/read states, foreign organization isolation and column-only source options. SQLite delivery regressions inject an email failure, retry the same saved period and assert no resend after success; no actual email is sent.

`--suite pages` verifies 121 equal-time event keys on PostgreSQL, pages emptied by severity filtering, and a newly admitted backdated event excluded until the next traversal. SQLite additionally verifies a 260-event corpus stops after four 50-key pages when the first 120 groups do not match severity, one event retains multiple related laws, invalid page sizes are rejected and the summarizer never consumes beyond the 51st eligible event.

`--suite resume` separately exercises the actual PostgreSQL worker/outbox lifecycle with two opted-in organization members: 50-event yield, fair dispatch of the other recipient, continuation to 61 events and one recorded send via a mail double. SQLite tests inject rollback before checkpoint commit, cancel/retry, failed mail, final preference races, stale leases, revoked membership/admission, disabled users/subscriptions and out-of-order delivery completion.

SQLite regressions additionally exercise empty/legacy/current results, another organization's access, and a newer attempt inserted at the query boundary. This is regression evidence, not an independent concurrency or capacity benchmark on HappySnowman.

## Still required

- Move organization event/candidate filtering and grouping into bounded SQL or a maintained read projection; the current `page` method still loads the whole organization's candidate set.
- Batch entity/review lookups and share an event-centered cursor contract with the future Today feed, with pages no larger than 50.
- Bound per-event law fanout and measure query/dispatch wall-clock work; worker preparation now yields each 50-event page, while sparse interactive previews can still traverse the full selected period.
- Preserve deep links, personal state, stale-evidence states and grouped law/topic relationships during that transition.
- Run the representative 100k-event/20-reader and overlapping sync/AI/digest workload on the intended host. The 500 ms p95 target and memory/SQL workload gates remain unverified.
