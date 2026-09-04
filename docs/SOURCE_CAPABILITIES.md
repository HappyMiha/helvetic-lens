# Versioned source capability catalogue

Helvetic Lens treats source coverage as a product contract. The versioned catalogue in `source_capabilities.py` is the single source for the public capability API, the Sources page, and the operator schedule view. It covers every one of the 23 scheduled official streams.

Each manifest records the authority and publisher, jurisdiction, document kinds, languages, default cadence, incremental cursor, historical window, immutable artifact and provenance behavior, reuse attribution, known gaps, and the date of the last verified bounded live check. The catalogue revision changes when any of those claims changes.

`GET /api/connectors/capabilities` returns the whole catalogue. `GET /api/admin/connectors` embeds the identical manifest in each schedule together with its current runtime state.

## Two separate states

The catalogue and runtime answer different questions:

- `catalogue_state=available` means fixture, incremental-overlap, deduplication, provenance, drift, artifact-reopening, and bounded live-smoke evidence are all recorded.
- `catalogue_state=partial` means at least one promotion gate is not recorded. An implemented fixture-tested connector stays partial when the repository has no dated live-smoke evidence for that exact stream.
- Runtime `availability` is `available`, `syncing`, `healthy`, `degraded`, `unavailable`, or `partial`. A current job takes precedence as `syncing`; a partial run stays `partial`; healthy/degraded/error source state becomes healthy/degraded/unavailable.

These states are never converted into a claim that nothing changed. A missing item, failed request, incomplete bounded page, unverified stream, or unavailable source means that coverage is unknown or limited. The last good cursor and saved evidence remain intact.

## Current boundaries

- Fedlex schedules three language RSS feeds, three bounded collection reconciliations, and consultations. Only exact streams with checked-in live evidence are promoted.
- Parliament schedules recent-tail, known-active, complete catalogue, and official-notice streams. Proposals and notices remain distinct from enacted law.
- Federal Supreme Court latest and reconciliation streams retain official HTML, but their discovery windows are bounded.
- Federal Criminal Court covers the official latest-decision list and linked PDFs, not a complete historical catalogue.
- News Service Bund and FINMA provide contextual official notices. They remain partial until dated live-smoke evidence for their exact scheduled streams is recorded.

Fixture tests are regression evidence. They do not prove that an external authority is reachable today. Run the bounded source checks, inspect their artifacts, and update the manifest date and evidence gate only when the exact stream passes without weakening its declared boundary.
