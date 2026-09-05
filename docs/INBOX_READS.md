# Bounded inbox reads

HL-099 is in progress. The current Impact inbox still groups persisted law-related candidates; it is not yet the unified topic/law feed.

## Analysis and review history selection

Interactive pages, the compatibility inbox and digest consumers now select histories in batches of at most 100 organization candidates. For each history table, one scalar window query chooses the latest row, the latest relevant row and the exact count for every candidate in the batch. A second query hydrates only those chosen IDs (at most two records per candidate). A nonempty analysis-and-review batch therefore needs at most four history queries instead of up to six per law; a table with no history requires only its metadata query. Counts and ordering run in SQL without transferring archived JSON/evidence or review notes.

“Relevant” means a successful current-schema analysis, or the most recent confirmed/rejected human decision. A newer annotation does not replace that decision, and a newer failed attempt does not hide the last valid conclusion. Stable ordering is `created_at DESC, id DESC`. IDs and counts come from one statement snapshot per table, so appends arriving between metadata selection and hydration appear on the next read, not in a mismatched count/current/latest result. Existing selected rows may still be updated or deleted; this is not a frozen transaction-wide evidence snapshot. Both metadata and payload queries explicitly scope the organization, even in a privileged session.

The earlier single-candidate `_latest_analyses` helper remains compatible with its existing three-query ceiling tests, but page/digest assembly no longer calls it. Migration `fa27c61d3098` already indexes analysis organization/candidate/time/ID; this batching slice adds no schema migration. Window sorting/counting still examines selected candidates' histories in the database. The contract bounds transferred historical payloads and history-query round trips, not database CPU, per-event law fanout, total response size or all related-entity queries. There is no inference on reads.

## Related documents, events and links

The same batches of at most 100 organization candidates now share related context. Candidate/event/work/watch/relation records load in ID batches with only the columns used to render the inbox; deferred fields reject accidental lazy reads. Accessible law IDs, latest comparison IDs and original-artifact version IDs use scalar queries, so reading the inbox does not hydrate Law, Version, Comparison or RegulatoryDocumentVersion objects or their large document/diff bodies. Archived evidence is still available through its explicit detail routes.

Comparison selection ranks by `created_at DESC, id DESC` per law, with explicit public/current-owner scope. Artifact links require a visible legacy Version. For confirmed replacement relationships, multiple legacy URLs can map to the successor work: select this organization's active watch first, then its paused watch, then the oldest accessible mapping (time/ID tie-break). Another organization's active watch cannot make the successor appear monitored. This replaces the earlier arbitrary first-mapping choice.

Context requires at most nine SELECTs per candidate batch (the ninth is needed only for replacements), alongside the existing history selection. A synthetic real-HTTP fixture with no saved AI/review history executes 16 SELECTs for both one and 50 events: three configuration reads, event keys/private state/deliveries, two empty-history metadata reads and eight context queries. Populated histories, replacements, authentication and additional 100-candidate batches change the total. This is a measured regression bound for that fixture, not a universal request count or latency guarantee. Explicit organization/owner predicates also protect context lookup in privileged sessions.

## Digest detection periods

Preview captures one end instant and delivery reuses its saved start/end. SQL selects `detected_at >= start AND detected_at < end`, optional connector/authority choices and personal dismissed/muted exclusions before hydrating candidate/evidence records. Read events remain eligible; another user's or organization's mute cannot suppress this recipient's event. Source choices use distinct scalar columns over the organization's available candidates, so a quiet period or active source filter does not erase the menu.

The summary repeats the period/state/source/severity checks and marks `truncated` only when a 51st eligible event actually exists. This fixes the false flag at exactly 50. Web preview, delivery history and email now expose the selection limit and point to the full saved Impact inbox. Each event retains `impact_count` and `impacts_truncated` after severity filtering; up to five affected laws are summarized, with an actual shown/eligible count. Older saved summaries without these fields do not invent a count or infer truncation merely from a five-item list. The event-limit wording also tolerates historical pre-fix flags without inventing an exact number of omitted events. Delayed/retried jobs keep their saved detection period but reevaluate current preferences, private state and saved conclusions; this is not a frozen database snapshot. Backdated admissions inside a completed period still need a separate catch-up policy.

## Event pages for digest consumers

`iter_groups` selects at most 50 distinct event IDs per SQL keyset page, ordered by `detected_at DESC, id DESC`, then hydrates only those event groups. Related laws are never split between pages. Legacy digest preview and direct delivery stop after 50 eligible summarized events plus one eligible overflow sentinel; up to 49 additional groups can have been prefetched in that last page. Severity still uses the actual persisted assessment/review rules after hydration, so sparse matches may require traversing the full selected period.

The traversal fixes an admission-time ceiling (`OrganizationRelationCandidate.created_at < traversal_start`); newly admitted events or law deliveries wait for the next traversal. The cursor advances through selected keys even when presentation filtering removes every group. Existing evidence/state changes are not frozen. Arbitrarily backdated admission timestamps or edits to event detection timestamps are outside this traversal guarantee. The legacy public inbox API remains unchanged; an additive bounded route is now available as described below.

This bounds retained event pages, not every dimension of work: one event can affect many watched laws; related entity/review/history lookups now use 100-candidate batches, while SQL DISTINCT/sorting can inspect many candidate rows. Worker preparation now checkpoints one 50-event page per execution; per-event law fanout, query cost and SMTP duration still need workload validation before claiming a hard wall-clock or memory bound.

## Interactive digest preview pages

The web digest now opts into `GET /api/digests?preview_page=true&cursor=...`.
The same opt-in on `PUT /api/digests/preferences?preview_page=true` bounds the
response after saving preferences. Each request selects at most 50 event keys
plus a scalar overflow sentinel, then filters those groups by the recipient's
saved severities. There is no automatic scan through empty pages. The original
API response remains available without the opt-in for compatibility; it is not
a bounded interactive route.

The preview retains `events` and `truncated`, and adds `counts_scope: "page"`,
`scanned_event_count`, `period_start`, `period_end`, `has_more`, `current_cursor`
and `next_cursor`. An empty page with `has_more` is not evidence of an empty
period. `truncated` still refers to the old summary event cap, not the existence
of more pages. Each page retains the five-law summary/coverage notices.

Cursors pin the half-open detection period and exclusive admission ceiling,
including when returning to the first page. They bind organization, reader and
saved enabled/frequency/source/severity preferences. Invalid, malformed or
mismatched cursors return `invalid_digest_cursor` before event hydration. They
are bounded navigation tokens, not credentials: all reads independently enforce
organization and personal-state scope. Existing conclusions, muted/dismissed
states and deleted records remain live; these pages are not immutable snapshots.
Restarting captures a new period/admission ceiling.

The five-language UI labels page-only counts and the captured Zurich-time period,
explains that saved filters apply, and offers Previous, Next 50 and Restart.
Sparse pages retain Next; invalid cursors offer recovery without a permanent
loading indicator. Paging preserves unsaved form choices and moves keyboard
focus to the preview heading. Saving resets page history; late save results do
not prime a different account/workspace epoch or locale. Navigation buttons have
44 px minimum height. No preview read schedules email, changes read state or
runs inference. Browser QA uses intercepted synthetic API responses only.

This bounds inspected event keys per interactive request, not related-law fanout,
source-menu cardinality, SQL CPU/sorting, or the latency of a highly connected
event. Preference-save and explicit cache refreshes are separate bounded reads.
The actual send job and its 50-selected-event email cap are unchanged.

## Public inbox page API

`GET /api/impact-inbox/page` accepts the existing `source`, `severity`, `item_type`, `watched_law` and personal `state` filters, plus `limit` (1–50, default 50) and `cursor`. It selects at most 50 event keys plus a scalar overflow sentinel before hydrating selected events/deliveries. Source/authority, event/document kind, personal state and watched-law admission predicates run in SQL. Missing personal state means unread. All related laws for a selected event remain together; severity retains the existing event-before-watched-law filtering order.

The response includes `items`, `total_events`, `total_impacts`, `unread`, `counts_scope: "page"`, `scanned_event_count`, `limit`, `captured_at`, `has_more` and nullable `next_cursor`. The three totals describe only returned groups on this page, never the entire inbox. Severity still depends on saved analysis/review state after hydration: a page can contain no displayed events while `has_more` is true. Consumers must follow the next cursor rather than treating an empty display page as exhaustion.

The cursor carries the detection-time/ID position, initial admission ceiling and a versioned organization/principal/filter fingerprint. Invalid, oversized, malformed or mismatched tokens receive a recoverable 422. It is an opaque navigation value, not a signed credential: independently scoped queries enforce access even if a caller constructs a token. A new filter or account starts at the first page. The admission ceiling defers new deliveries until a fresh traversal; existing evidence and private state remain live. It is not a transaction snapshot or a guarantee for edits to detection timestamps/backdated admission metadata.

The legacy `/api/impact-inbox` route remains available with its original response shape. The Impact inbox web page now uses only the bounded route. Counters sit under “On this page”; top/bottom navigation offers older events and a fresh start, while browser back restores the prior URL. Empty severity pages still offer continuation. Invalid cursors retain a first-page recovery link. Filters reset the cursor and exit a pinned notification event; automatic refresh and action invalidation retain the current page rather than accumulating history. Event pagination does not bound one event's law fanout or database sorting cost; related lookups now use the candidate batches described above.

### Filter options and notification links

`GET /api/impact-inbox/law-options?q=...&selected=...` searches organization watch display names using scalar columns only, independently of current inbox filters/page. It returns up to 50 matches and an overflow flag (51st scalar sentinel), plus a separately selected organization-owned option so it stays visible outside the search window. Search treats wildcard characters literally. Paused watches remain selectable for their saved history. Law-ID and watch-ID links are supported; no source, version or analysis JSON is hydrated. A leading substring search/sort can still inspect many names in PostgreSQL; the transfer bound is not a constant CPU guarantee.

The UI submits law search explicitly, explains the first-50 limit and keeps the selected value while results load. `/impact?candidate=<organization_candidate_id>` resolves the linked event directly through an organization-scoped SQL predicate, even beyond the newest 50 keys. Unavailable/foreign links return no event; changing filters exits this focused view. The candidate parameter participates in cursor scope, so it cannot silently reuse another traversal. Complete event law groups, review controls and saved-analysis history remain accessible as before.

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

`--suite inbox` verifies the real bounded HTTP endpoint on PostgreSQL with 121 equal-time events in 50/50/21 pages, stable navigation, page-only counts and exactly the selected event/delivery payloads hydrated. SQLite also covers SQL filter parity, private-state/account isolation, sparse severity pages, concurrent admissions and invalid cursors/limits.

`--suite batches` verifies the real 50-event endpoint on PostgreSQL with 7,474 historical analysis/review rows, four history queries and 111 selected records. SQLite also covers chunking a 121-candidate legacy page into 100/21, concurrent appends after metadata selection, empty batches and explicit organization isolation in a privileged session.

`--suite options` separately checks independent scalar watch search and selected options beyond the cap on PostgreSQL. `npm run check:inbox:browser` starts isolated Next/Chrome processes against an existing production build and intercepts every application API request with synthetic fixtures. It checks real page navigation/back, sparse-page continuation, notification focus, filter reset, cursor recovery and responsive overflow; it never uses the running API or real organization data.

SQLite regressions additionally exercise empty/legacy/current results, another organization's access, and a newer attempt inserted at the query boundary. This is regression evidence, not an independent concurrency or capacity benchmark on HappySnowman.

`--suite context` verifies the 1/50-event constant-query and materialization checks on PostgreSQL. Separate empty-database `--suite links` and `--suite successors` runs verify stable scalar link selection, heavy-body exclusion, private ownership and current-organization successor alias ranking. The link fixtures are synthetic ID/visibility checks, not proof of legal-document identity matching. SQLite also verifies that 121 compatibility-route events split context into 100/21 candidate batches without losing events.

`--suite preview` verifies authenticated preference save and GET navigation on
PostgreSQL with 121 equal-time events: two empty 50-key severity pages and a final
21-match page, stable first/back period, unchanged compatibility output and no
new AI/mail/job/delivery/read-state writes. SQLite also rejects malformed,
foreign-reader/organization and changed-preference cursors, verifies late
admission exclusion until restart, and honors personal state changed after the
capture. `npm run check:digests:browser` requires all ten synthetic localized
390/1440 px journeys, including real pointer hits and focus recovery.

## Still required

- Migrate remaining full-list consumers such as the compatibility `page` route and future Today projections where appropriate. The interactive Impact inbox is paginated; severity eligibility still needs SQL/a maintained projection if measurements justify it.
- Share the event-centered cursor contract and batched context/history reader with the future Today feed, with pages no larger than 50.
- Bound per-event law fanout and measure query/dispatch wall-clock work; worker preparation now yields each 50-event page, and interactive web previews now inspect at most 50 keys per request. The compatibility preview can still traverse a full period.
- Preserve deep links, personal state, stale-evidence states and grouped law/topic relationships during that transition.
- Run the representative 100k-event/20-reader and overlapping sync/AI/digest workload on the intended host. The 500 ms p95 target and memory/SQL workload gates remain unverified.
