# Monitoring topics

Monitoring topics turn an organization interest such as “follow simplified naturalisation” into an explicit, reviewable plan. A plan records its goal, terms, exclusions, jurisdictions, languages, source packs, document and event kinds, and minimum importance. The plan is organization-scoped and every edit or status change creates an immutable revision.

## Creation flow

An organization administrator can build a plan manually even when the model is unavailable. The optional **Draft with local AI** action creates a separate, inactive draft through the configured provider. Its structured output is validated and repaired once when necessary. The interface then exposes every proposed field for editing.

The administrator must run the deterministic preview before the activation control appears. Preview examines at most 500 recent saved events and returns at most 10 representative candidates with the matching concept, synonym, and source-pack signals. It makes no model call and never labels a topic match as a confirmed legal relation. No draft, preview, or model response silently activates monitoring.

When an AI draft is explicitly confirmed, the resulting revision records provider, model, and prompt revision. A manual revision keeps those fields empty. Topic creation accepts an organization-scoped idempotency key; retries return the same topic. Optimistic revision checks prevent overwriting a concurrent edit.

## Lifecycle and access

Active topics can be paused and resumed. Archival is soft and keeps the topic and complete revision history; archived topics cannot be edited or reactivated. Viewers can inspect topics and revisions but cannot draft, create, edit, pause, resume, or archive them. Database query criteria apply organization isolation to topics, revisions, and AI drafts.

## API

- `GET /api/monitoring-topics` lists active and paused topics; `include_archived=true` includes archived records.
- `GET /api/monitoring-topics/{id}` returns the current plan and revision history.
- `POST /api/monitoring-topics/draft` creates an optional, unconfirmed AI proposal.
- `POST /api/monitoring-topics/preview` returns bounded deterministic candidates from saved events.
- `POST /api/monitoring-topics` activates a reviewed plan idempotently.
- `PUT /api/monitoring-topics/{id}` adds an immutable plan revision.
- `PATCH /api/monitoring-topics/{id}/status` pauses, resumes, or archives the topic through a new revision.

Topic matching over new events and durable match evidence are introduced separately by HL-075. HL-074 establishes the plan, preview, provenance, access, and lifecycle contract they consume.
