# Bounded inbox reads

HL-099 is in progress. The current Impact inbox still groups persisted law-related candidates; it is not yet the unified topic/law feed.

## Analysis-history selection

For each organization candidate, `ImpactInboxReader._latest_analyses` transfers at most two `RelationImpactAnalysis` records. It selects the latest attempt in SQL, then the latest successful result under the current relation-result schema (if different). History size comes from `COUNT`, not from loading every result/evidence JSON into Python. Empty history uses one query, a latest current success uses two, and a failed/obsolete latest attempt with a separate current result uses three. These counts describe this helper, not the entire inbox request.

Ordering is stable by `created_at DESC, id DESC`. The second selection and count cannot pass the latest attempt's timestamp/ID, so a newer attempt arriving between queries appears on the next read. This ceiling is not a database-wide snapshot of arbitrarily backdated inserts or concurrent updates. The current validated conclusion remains visible when a newer attempt fails, and old-schema successes remain historical. Existing organization scoping applies to selections and counts. No inference runs on reads or digest delivery.

Migration `fa27c61d3098` adds the organization/candidate/time/ID index used for history traversal. The database still counts matching history and may inspect older rows to find a current-schema result; the change bounds transferred payloads and application materialization, not total database work or latency for every corpus shape. A maintained projection or more selective index remains an option if measured query plans justify it.

## Verification

`scripts/check_inbox_history_postgres.py --database-url <url>` refuses an existing database or any destination other than an empty loopback PostgreSQL database named `hl099_regression`. A 10,001-row synthetic history verifies three selection/count queries, two materialized payloads, the actual inbox response, equal-timestamp ordering, failed-latest fallback and an index downgrade/upgrade with saved history preserved. It uses test fetch/model doubles and does not contact a paid model. Remove the task-owned database container after the check.

SQLite regressions additionally exercise empty/legacy/current results, another organization's access, and a newer attempt inserted at the query boundary. This is regression evidence, not an independent concurrency or capacity benchmark on HappySnowman.

## Still required

- Move organization event/candidate filtering and grouping into bounded SQL or a maintained read projection; the current `page` method still loads the whole organization's candidate set.
- Batch entity/review lookups and share an event-centered cursor contract with the future Today feed, with pages no larger than 50.
- Restrict digest selection to its saved period/preferences and provide durable continuation; digest work still inherits the unpaginated inbox.
- Preserve deep links, personal state, stale-evidence states and grouped law/topic relationships during that transition.
- Run the representative 100k-event/20-reader and overlapping sync/AI/digest workload on the intended host. The 500 ms p95 target and memory/SQL workload gates remain unverified.
