# Daily interest feed

Today (`/`) is a read projection, not a new corpus or a model request. The previous
document overview remains at `/overview`. Registry, discovery, Impact inbox and
law timelines retain their routes. Do not replace their complete histories with
this current-relevance shortlist.

## Sources of a card

`GET /api/interest-feed` selects persisted RegulatoryEvent IDs with any of:

- a current, active MonitoringTopic revision and saved TopicEventMatch, with an
  organization event admission; expired records are excluded;
- an OrganizationRelationCandidate delivered to this organization;
- a visible document mapping with an active DocumentWatch in this organization.

The second stage rechecks topic rule/evidence fingerprints and decision currency.
A stale, rejected or muted *current* topic decision cannot deliver a current topic
card. A retained old review does not pretend to confirm corrected evidence.
One event ID yields one card with all eligible topics, direct watches and watched
law impacts. Topic confidence measures matching confidence, not legal severity.
Missing AI analysis remains unknown/awaiting, never low impact. Existing relation
analysis freshness checks apply; original history/citations are not rewritten.

No models, new AI jobs, copies of evidence, emails or production mutations occur
when opening or paging the feed. Model-independent events remain visible.

## Paging and state

Parameters: `period=all|today|yesterday|week|month`,
`state=unread|read|dismissed|muted` (empty means all), `limit=1..50` (default 20),
optional `cursor`. Week/month mean the last 7/30 Zurich calendar days including
today; yesterday is a complete local calendar day. Filters use *detected* dates,
not publication/effective dates. Event-specific source dates preserve precision
and provenance; missing dates remain unknown, never inferred from work dates.

Cursor order is detected_at + event ID, descending. A capture watermark excludes
later admissions/matches/watches even when their events are backdated. Cursor
scope binds the current organization, principal and filters, not authorization:
every page independently rechecks access. It is a live authorized view, not an
immutable snapshot; changing/revoking evidence can remove items. Sparse candidate
pages keep a next cursor and must not be presented as exhausted source coverage.
Counts describe the scanned page only. No full-history count/body load is needed.

`PATCH /api/interest-feed/events/{id}/state` accepts the four personal states.
The event must still qualify for this feed. It writes the same
RegulatoryEventUserState used by the Impact inbox, keyed by organization and
principal. Viewers may change their own state but not organization relevance.
The UI invalidates scoped feed/inbox/digest reads without a document reload.

## Exact development and evidence context

`/?event=<saved-event-id>` and `GET /api/interest-feed?event=<id>` select one
currently eligible event without traversing newer pages. All existing visibility,
organization admission, topic freshness and personal filters still apply. An
unavailable/revoked/no-longer-relevant event produces an empty result, not an
access bypass or immutable historical snapshot. The UI explains the scoped view
and offers All developments. The cursor scope now includes event ID; old cursors
must return to the first page through the existing recovery control.

A card's collapsed source context exposes recorded jurisdiction(s), the language
of its same-work expression, event detection provenance and connector state at
recording. Missing jurisdiction stays unknown rather than being inferred as CH.
Work metadata can be updated; these fields do not claim immutable historical work
status. Connector state is explicitly a detection-time record, **not live health**.
Known provenance methods and language names use localized labels; unfamiliar
source codes remain visible. Official event dates retain raw year/month/day/instant
precision and their own source links; a work publication date is not substituted.

Saved evidence links come from the event's exact document version, including
when only a topic matches. A scalar join checks the version's expression belongs
to that event's work and the mapped legacy Version and Law are visible. It never
substitutes the monitored law's newest version, materializes original document
bodies, or calls a model. Existing `/evidence/{version}` authorization still applies.
Native-only corpus versions without a legacy binding now link directly to
`/corpus-evidence/{id}`; see `NATIVE_EVIDENCE.md`. The viewer distinguishes saved
passages, text-only/metadata-only records and an unavailable original.
The publisher link may show newer content. A missing file is handled by the
existing evidence viewer; the feed does not probe storage on every read.

## Deliberate limits and follow-up

- Grouping is by saved event ID, not semantic publisher story or language edition.
- Current topics only; paused/revised/expired matches remain in topic history.
- One event page is bounded; all interests for its selected events are returned.
  Very large per-event fan-out still needs separate paging (HL-099/HL-076).
- Shared topic relevance review is a separate evidence-bound flow linked from
  Today and saved matches in Topics; see `TOPIC_MATCH_REVIEWS.md`. Independent
  organization AI briefs remain separate work. Topic notices are not yet digests.
- Coverage is explicitly limited to saved, evaluated evidence. The UI links to
  topic coverage/source settings but does not claim sources are healthy/current.
- Work lifecycle status is distinct from an event date. Recorded jurisdiction,
  provenance/date precision and exact mapped saved-version links are now exposed.
  Native evidence is viewable; fully normalized jurisdiction/status labels
  and live coverage remain open; existing timeline/review routes are retained.
- Draft translations and browser geometry checks do not replace native-language
  or real-user usability review. There is no new deployment or data migration.

## Reproduce checks

- API: `python -m pytest services/api/tests/test_interest_feed.py -q`
- UI: `npm run build` then `npm run check:feed:browser` (isolated production Next
  instance and temporary headless browser; every API request is synthetic).
- Empty local PostgreSQL only: `scripts/check_inbox_history_postgres.py` suites
  `feed`, `feed-pages`, `feed-watch`. This harness refuses existing tables and
  databases other than the explicitly named disposable `hl099_regression`.
