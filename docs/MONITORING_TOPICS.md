# Monitoring topics

Monitoring topics turn an organization interest such as “follow simplified naturalisation” into an explicit, reviewable plan. A plan records its goal, terms, exclusions, jurisdictions, languages, source packs, document and event kinds, and minimum importance. The plan is organization-scoped and every edit or status change creates an immutable revision.

## Creation flow

An organization administrator can build a plan manually even when the model is unavailable. The optional **Draft with local AI** action creates a separate, inactive draft through the configured provider. Its structured output is validated and repaired once when necessary. The interface then exposes every proposed field for editing.

The administrator must run the deterministic preview before the activation control appears. Preview examines at most 500 recent saved events admitted to the current organization and returns at most 10 representative candidates. It uses the same deterministic scorer as saved-history and live activation, including normalized official identifiers, lexical terms, synonyms, metadata, exclusions and source/kind/language/jurisdiction/importance filters. It returns identical reason signals and confidence for the same plan and evidence, makes no model call and never labels a topic match as a confirmed legal relation. No draft, preview, or model response silently activates monitoring.

Preview reports the actual inspected count, capture time, detected-time range, rule version, organization visibility scope, whether more saved events remain, and whether only a subset of the sample’s matching results is displayed. The five-language UI labels these as a sample, keeps the source-coverage disclaimer for empty or complete saved samples, and does not turn a zero into “nothing relevant happened”. Source-pack availability is managed in Sources; this read-only action does not fetch or activate a source pack. Activation may see later events or changed evidence, so a preview is not a promise of a fixed future result count.

When an AI draft is explicitly confirmed, the resulting revision records provider, model, and prompt revision. A manual revision keeps those fields empty. Topic creation accepts an organization-scoped idempotency key; retries return the same topic. Optimistic revision checks prevent overwriting a concurrent edit.

## Selected-source readiness

The same explicit preview returns `source_coverage`, a saved operational view of
only the plan's selected packs. It separates the organization's subscription from
shared connector schedules and recorded source health. A disabled subscription
may still have old admitted examples: preview and topic activation do not activate
source packs or prove delivery of future events. The Sources link uses the existing
administrator subscription/viewer request workflow.

For each known stream, the preview shows its actual persisted interval/jitter,
allowed hours, next scheduled attempt, last successful sync, last reported health
and latest recorded run status. Missing schedules, paused schedules, no successes,
partial runs and unknown stream definitions are explicit. A past next-run timestamp
is reported as past due, never as proof of a running worker or current outage.
Dates include localized time in Europe/Zurich. Static localized source capability
boundaries remain separate from recorded runtime health; neither guarantees full
coverage, current liveness, notification latency or future match volume.

The initial review shows subscription totals and attention counts; individual pack
and stream details are disclosed on demand. Users can still save a topic while
sources are inactive, with a visible warning. Viewers can review readiness in their
personal draft but cannot activate shared monitoring. The snapshot resets with the
existing preview on edits/recovery; it is refreshed by another explicit preview,
not inferred from a possibly older catalogue load.

`topic_coverage.snapshot` uses four scalar queries for one or all current packs:
selected definitions, explicitly organization-scoped subscriptions, selected
schedules with the latest status scalar subquery, and selected connector states.
It does not seed schedules or read error bodies, cursors, policy JSON, job payloads,
other organization subscriptions or full run histories. Known stream keys are
bounded by the capability catalogue and plans by twenty packs. Unknown keys are
counted as unknown rather than silently advertised as supported. This is a saved
read view, not an atomic multi-table historical snapshot or a 100-user throughput
benchmark; underlying latest-run query cost on mature histories remains part of
capacity verification.

Verification: six `test_topic_coverage.py` cases exercise no-schedule/no-write
preview, actual custom schedules, old success versus current degraded/partial
state, paused scheduling, privileged subscription isolation, four-query/scalar
bounds across all 23 current streams, unknown streams and the twenty-pack guard.
Four isolated PostgreSQL suites cover empty/state/scope/bounds. The contextual
browser suite covers twenty localized role/viewport journeys with readiness
warnings, opening/closing details, custom intervals/windows and explicit Zurich
hours. No live source requests, inference, schema or production changes.

## Duplicate review before saving

Preview also returns `matching_topics`: a separate check of up to 500 most recently
updated active/paused organization topics and up to ten matching current revisions.
The comparison uses case-insensitive sets separately for concepts, synonyms,
exclusions, jurisdictions, languages, source packs, document kinds and event kinds,
plus the importance floor. Name and goal are deliberately not matching rules; the
UI says descriptions can differ. Concepts are not interchangeable with synonyms
because their scorer/confidence behavior differs. There is no AI or fuzzy semantic
claim. Archived topics and an optional `exclude_topic_id` (the topic being edited)
are omitted. Both owner predicates remain explicit in privileged DB sessions.

The single scalar query does not read topic descriptions, previous revisions or
jobs. `scanned_count`, `scan_limit`, `count_is_complete`, `match_count` and
`display_truncated` describe this check separately from the event sample. An empty
bounded check is not a guarantee that no other equivalent topic exists. The UI
links matching names to existing topic cards, shows active/paused status, and asks
administrators to acknowledge the overlap before saving separately. A new preview,
form edit or restored draft invalidates that acknowledgement. Viewers may inspect
but cannot activate anything; existing API roles and idempotency remain unchanged.

This is a point-in-time **advisory**, not a server-side uniqueness constraint. It
does not merge plans, resume paused monitoring, reserve names, or stop two admins
from intentionally creating overlapping topics. No save-time locking, fuzzy
cross-language duplicate discovery or whole-organization scalability claim is
implied. Source/rule changes after preview may alter the comparison.

Verification: `test_topic_duplicates.py` covers current revision/status, distinct
rules and concept/synonym roles, description/case/order variations, both owner
predicates, self exclusion, actual 501-topic bounds/scalar hydration, no writes or
inference, and authenticated viewer access. Scratch PostgreSQL suites are
`topic-duplicates`, `topic-duplicates-scope`, `topic-duplicates-bounds`. The existing
`check:monitor-this:browser` includes all five locales, mobile/desktop, both roles,
matching topic links, incomplete-check messages, acknowledgement reset and
pointer/keyboard confirmation. Browser data is synthetic and intercepted.

## Lifecycle and access

Active topics can be paused and resumed. Archival is soft and keeps the topic and complete revision history; archived topics cannot be edited or reactivated. Viewers can inspect topics/revisions and prepare a personal browser-tab draft with a read-only candidate preview. They cannot request AI drafts or create, edit, pause, resume, or archive shared topics. See [Contextual topic setup](MONITORING_CONTEXT.md) for personal draft scope and contextual entry points. Database query criteria apply organization isolation to topics, revisions, and AI drafts.

## API

- `GET /api/monitoring-topics` lists active and paused topics; `include_archived=true` includes archived records.
- `GET /api/monitoring-topics/{id}` returns the current plan and revision history.
- `POST /api/monitoring-topics/draft` creates an optional, unconfirmed AI proposal.
- `POST /api/monitoring-topics/preview` returns bounded organization-visible candidates, shared reason/confidence values and separate scanned/displayed sample boundaries.
- `POST /api/monitoring-topics` activates a reviewed plan idempotently.
- `PUT /api/monitoring-topics/{id}` adds an immutable plan revision.
- `PATCH /api/monitoring-topics/{id}/status` pauses, resumes, or archives the topic through a new revision.

Topic matching over new events and durable match evidence are introduced separately by HL-075. HL-074 establishes the plan, preview, provenance, access, and lifecycle contract they consume.
