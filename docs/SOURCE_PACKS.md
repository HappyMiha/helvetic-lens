# Organization source packs

Source packs let an organization select official coverage without configuring authority URLs or starting its own connector copies. The global definitions are versioned records. Organization subscriptions only control which shared regulatory events enter that organization's feed state.

## Swiss Federal Starter

The starter is an aggregate control over five visible subpacks:

- Fedlex legislation: language feeds plus bounded CC, OC, and Federal Gazette reconciliation.
- Federal consultations: proposals, drafts, and explanatory material kept distinct from enacted law.
- Swiss Parliament: recent, active, catalogue, and official-notice streams.
- Federal courts: Federal Supreme Court latest/reconciliation and Federal Criminal Court latest decisions.
- Official policy and regulators: News Service Bund and FINMA notices.

Each subpack can be enabled or disabled independently. The Sources screen shows its authorities, content kinds, languages, cadences, last successful connector sync, expected first data, coverage boundary, current subscription state, and number of saved events included. The underlying claims come from the same 23-stream [source capability catalogue](SOURCE_CAPABILITIES.md) used by operations.

## Data and job behavior

`SourcePackDefinition` is global. `SourcePackSubscription` and `SourcePackChangeRequest` are organization-scoped. Enabling a pack creates one idempotent durable backfill job per affected subpack on the existing `ingest` queue. The job selects at most 500 unseen matching events from the shared corpus, creates only organization feed-state rows, and reports active, partial, or failed state with progress. A later continuation resumes from unseen rows rather than copying the same records.

Connector cursors, normalized works, expressions, versions, events, and immutable artifacts remain global and are never duplicated per organization. New connector events fan out to active subscriptions as organization event-state rows. Disabling a pack stops that future inclusion. It retains prior organization event state and all shared legal evidence.

Mutation endpoints are organization-admin only and are covered by the existing administrative audit middleware. A viewer can inspect all pack state and submit an idempotent activate/deactivate request through `POST /api/source-pack-requests`; the viewer cannot change the subscription directly. An administrator action fulfils matching pending requests.

## API

- `GET /api/source-packs` returns the starter, its five subpacks, live schedule facts, exact capability manifests, subscription progress, and any pending request.
- `POST /api/source-packs/{pack_id}/activate` queues bounded backfill for one subpack or every child of the starter.
- `POST /api/source-packs/{pack_id}/deactivate` disables future organization inclusion without deleting evidence.
- `POST /api/source-pack-requests` records a viewer's requested action for one visible subpack.

An unavailable or partial source stays visibly limited. Pack activation never turns a missing source response into a claim that nothing changed.
