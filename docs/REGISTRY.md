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

`PATCH /api/registry/events/{event_id}/read` stores read state per organization. A read marker from one workspace cannot affect another workspace.

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
