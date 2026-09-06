# Regulatory registry and document timeline

HL-037 adds a saved-data read model for answering two different questions:

- **My monitored documents** shows the latest saved activity for each document on the current organization's watchlist.
- **All discovered events** shows normalized regulatory events, including events that are not yet linked to a monitored document.

Neither view fetches an official source or calls an AI provider. Connector synchronization and analysis can remain queued while the registry renders the last committed PostgreSQL state.

## Time semantics

`detected_at` is the time Helvetic Lens observed or stored a record. The API converts it to the `Europe/Zurich` calendar before assigning exactly one group: Today, Yesterday, Last 7 days, Last 30 days, Older, or Custom range. The boundaries are calendar-day boundaries, so daylight-saving transitions do not turn a local day into a fixed 24-hour interval.

Official dates remain separate values with their own precision and provenance:

- publication date;
- version date;
- decision date;
- effective from;
- effective to.

When the connector has not supplied an official date, the UI displays `unknown`. It never copies `detected_at` into a legal-date field.

## Registry API

`GET /api/registry` accepts `view=monitored|events`, `q`, `limit`, `cursor`, `start`, `end`, and filters for authority, connector, document kind, language, lifecycle, impact, watched state, read state, and connector health. Results use a stable descending `(detected_at, id)` order and an opaque cursor. The response includes both a flat page and time-grouped rows for direct rendering.

`PATCH /api/registry/events/{event_id}/read` stores read state per organization and user (or the explicit anonymous-development principal). A read marker from one workspace cannot affect another workspace.

Each row explains what happened, why it is visible, its analysis and connector states, linked monitored laws, official dates, and the available evidence, comparison, timeline, and source actions.

## Document timeline

`GET /api/laws/{law_id}/timeline` returns the normalized regulatory identity attached to a monitored document. The Law detail page renders:

- authority, document kind, lifecycle, and monitoring state;
- official identifiers and language expressions;
- normalized immutable versions and official dates;
- saved lifecycle events;
- incoming and outgoing confirmed or proposed relations;
- document snapshots, comparisons, and source provenance.

Legacy direct-URL watches remain usable through their explicit provisional corpus mapping. As official connectors reconcile those documents, later tasks can merge aliases into the same authority-level work without rewriting immutable evidence.

## Verification

Automated tests cover midnight and daylight-saving boundaries, custom ranges, filters, stable cursor pagination, organization-scoped read state, watched and unwatched events, timeline composition, and the rule that registry reads make no model calls. The production Next.js build and a migrated PostgreSQL Compose deployment exercise the same endpoints used by the browser.


## Event-list SQL paging — 6 September 2026

`view=events` now applies ownership, authority, connector, kind, lifecycle, impact,
recorded health, language, watched/read state and Zurich date boundaries in SQL.
Descending `(detected_at, id)` keysets select at most 100 scalar candidates per
query; the public API retains its existing 1–100 page-size contract. Only the
returned page plus one matching lookahead is retained. The composite
`ix_regulatory_event_registry_page` index supports this order; migration
`a183fc729650` adds it without changing saved events.

Literal Unicode/accent-insensitive substring search retains the existing Python
normalization. It traverses 100-candidate SQL batches until the requested page
and lookahead are found or the eligible history is exhausted. A sparse match after
200 newer nonmatches is still reachable. This bounds candidate materialization,
**not total database work or latency for sparse/no-match searches**.

The candidate projection excludes event evidence, work/expression metadata and
full per-user state objects. Languages are selected for each candidate batch.
Related watched laws, expression IDs and official-date values are expanded only
for returned rows; evidence links retain the existing exact-version access checks.
Watched/read predicates explicitly constrain the organization, and read state
also constrains the user. Existing relation directions and paused-watch inclusion
are preserved: a link is not a new assertion of legal relevance or confirmed impact.

Six dedicated regressions run on SQLite and independent empty PostgreSQL 16.15
scratch databases: 231 equal-time events traversed 100/100/31, sparse literal
search, the 23-hour Zurich spring day, privileged-session tenant/user isolation,
related watches in both directions including foreign-watch exclusion, and populated
index downgrade/upgrade. SQL instrumentation rejects event/work JSON hydration;
no model calls occur. Existing registry/evidence tests also remain green.

Remaining HL-099 work: the monitored-document view and document timeline still
materialize their older read models; per-visible-work lookups and exceptionally
large relation/watch/date/expression fan-out need further batching/paging. The
query planner may still inspect many eligible records. This is not the intended-host
100k-event/20-reader test, the ≤500 ms p95 gate, or a deployment/migration of a
working database. Cursor results reflect current saved filters/visibility; this
slice adds no cross-request snapshot or late/backdated-admission policy.


## Monitored-document SQL pages — 6 September 2026

`view=monitored` now joins each organization watch to a visible law and optional
visible mapping/work. A correlated scalar selection chooses the latest event for
that work by `(detected_at, id)` before applying event filters. No matching event
means the existing `last_checked`, then watch `created_at`, fallback is used;
missing language expressions remain `und`. Paused watches remain visible.

Both registry views share candidate traversal: SQL filters/order, at most 100
scalar candidates per query, page plus one matching lookahead, and complete
Unicode literal search through successive batches. The public 1–100 limit and
row shape remain compatible. A cursor from the other view is rejected with the
existing invalid-cursor response. Read markers refer to the latest event and the
current organization/user; an older event's marker does not mark a new event read.

Only selected-page law IDs enter the scalar latest-comparison window query.
Comparison timestamps use ID as a deterministic tie breaker and exclude foreign
private comparisons. Expression IDs and official-date values are selected in
batches for returned rows, not once per document. No full comparison diff,
version text, work metadata, event evidence or watch/state ORM objects are needed
to construct a monitoring page. Existing source, current-version evidence,
comparison and timeline links retain their meanings.

Migration `b294ad830761` adds `(work_id, detected_at, id)` index
`ix_regulatory_event_work_latest`, supporting per-work latest-event selection.
It neither changes data nor replaces the global event-list index. Applying this
migration to a working deployment remains a separate operator action.

The tests traverse 231 watches against 231 equal-time events (100/100/31 pages),
assert five bounded candidate selects and three date/three comparison batch
queries, and reject full-object/large-JSON hydration. Additional cases cover
sparse literal search and unmapped defaults, user/tenant state, private
law/mapping/work fallbacks, the 25-hour Zurich autumn day, comparison visibility
and tie breaking, and populated index migration. See the verification record for
final SQLite/PostgreSQL results.

Limits: ordering watches by derived latest activity can still require significant
SQL work as the watchlist grows. Language/expression/date fan-out and visible-law
comparison ranking need intended-host measurement. The document timeline and
Discover's related-law/date expansion are separate remaining work. This is a
**live saved-state list**, not a cross-request snapshot: a new event or changed
last-check time can move a watch above an earlier cursor. Refresh starts from the
latest state; snapshot/reconciliation semantics remain an explicit HL-099 gate.
No 100-user capacity, complete mature-corpus bound or production deployment is
claimed by this slice.
