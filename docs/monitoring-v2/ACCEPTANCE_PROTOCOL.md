# Monitoring acceptance: nine directions and 116 active criteria

**Status: protocol prepared; no acceptance run or criterion closure claimed.**
Baseline inspected: `769795b525f11f90d4c67795164d671256cbb46a`, 15 September 2026.
The [unchanged criteria and supplemental requirements](REQUIREMENTS_TRACEABILITY.md)
remain authoritative. This protocol supplies concrete review procedures for all
116 active AC. C4's ten AC and deferred supplemental requirements stay deferred.
The [active backlog](../../BACKLOG_MONITORING_V2.md) retains task dependencies,
additional acceptance conditions and inherited legacy obligations. Neither this
document nor green unit tests complete those broader obligations.

## Run and evidence rules

Run functional scenarios in an isolated acceptance environment with synthetic
accounts and a test mail sink. Use the same release code, migrations and native
workers as production. Controlled source revisions below mean permitted retained
fixtures delivered through the actual adapter/journal boundary, never invented
changes to an official live service. Clearly label fixture runs as synthetic.
Do not seed fixtures into production or send test alerts to real recipients.

A source scenario also needs a separate permitted live observation on the exact
activated release. A fixture verifies behavior; it cannot establish current access,
publisher coverage, redistribution rights, authentic source identity or operational
freshness. An empty live feed cannot demonstrate detection of a nonempty event.
Keep live source acceptance open when that evidence is missing. Do not restart a
deployment or release gate merely to execute this protocol.

For every row, record: AC ID; release SHA and environment; test selector or manual
steps; fixture/source edition and hash; effective source timestamps; permission
record/reference and validity; actual result; evidence location; reviewer and
date; unresolved limits. Retain screenshots and logs privately, with redacted
credentials and personal data. Record `PASS`, `FAIL`, `BLOCKED` or `NOT RUN` for
each execution, independently of the parent's acceptance status. A document link
or test function's existence is not a passed execution.

Use separate owner, colleague, unrelated tenant and revoked-member accounts.
Repeat user-facing operations on desktop and mobile, keyboard-only, and all five
supported locales. Confirm cross-account denials after permission/session loss.
For human-understanding requirements, record what participants actually understood
without leading them. Agent-authored answers do not count as independent review.

For lifecycle scenarios, keep the same monitor and source object identity through
initial state, nonmaterial refresh, material update, review, reopening and
resolution. Record both source revision and personal review revision. Test retry,
out-of-order data, restart and failed/partial acquisition. Missing source data must
not become an official cancellation, clearance, zero value or safe condition.

## Existing automated entry points

These are code-inspection/navigation references, **not new run results**. Their
fixtures and assertions cover portions of the protocols below. The protocol's
expected outcome and the full original criterion determine acceptance; do not
assume a module covers everything in its category. Run relevant selectors using
the project Python environment and normal test prerequisites. Preserve existing
test evidence; do not duplicate a running deployment suite.

| Reference | Existing suites and implementation evidence |
|---|---|
| CORE | [Centre](../../services/api/tests/test_monitoring_centre.py), [native reviews](../../services/api/tests/test_monitoring_batch_native.py), [native evidence](../../services/api/tests/test_monitoring_evidence_native.py), [evidence versions](../../services/api/tests/test_monitoring_evidence_versions.py), [counts](../../services/api/tests/test_today_counts.py), [configuration drafts](../../services/api/tests/test_monitoring_configuration_drafts.py), [source history](SOURCE_HISTORY.md), [business sharing](BUSINESS_MONITOR_SHARING.md) |
| C1 | [HTTP](../../services/api/tests/test_hazard_api.py), [native feed workflow](../../services/api/tests/test_hazard_meteoalarm_workflow.py), [matching](../../services/api/tests/test_hazard_matching.py), [lifecycle](../../services/api/tests/test_hazard_lifecycle.py), [delivery](../../services/api/tests/test_hazard_delivery.py), [source scope](HAZARD_WATCH.md) |
| C2 | [HTTP](../../services/api/tests/test_commute_api.py), [private jobs](../../services/api/tests/test_commute_jobs.py), [delivery](../../services/api/tests/test_commute_delivery.py), [Today](../../services/api/tests/test_commute_today.py), [source/workflow evidence](TRANSPORT_WATCH.md) |
| C3 | [HTTP](../../services/api/tests/test_road_api.py), [evaluation](../../services/api/tests/test_road_evaluation.py), [reconciliation](../../services/api/tests/test_road_reconciliation.py), [jobs](../../services/api/tests/test_road_jobs.py), [recurring workflow](../../services/api/tests/test_road_recurring_workflow.py), [source/workflow evidence](ROAD_WATCH.md) |
| C5 | [HTTP](../../services/api/tests/test_pollen_live_api.py), [sources](../../services/api/tests/test_pollen_sources.py), [forecast](../../services/api/tests/test_pollen_forecast.py), [thresholds](../../services/api/tests/test_pollen_thresholds.py), [signal deduplication](../../services/api/tests/test_pollen_signal_dedup.py), [delivery](../../services/api/tests/test_pollen_delivery.py) |
| C6 | [complete River workflow](../../services/api/tests/test_river_watch.py), [Today](../../services/api/tests/test_river_today.py) |
| C7 | [complete Air workflow](../../services/api/tests/test_air_watch.py), [native evidence](../../services/api/tests/test_monitoring_evidence_native.py) |
| B2 | [HTTP](../../services/api/tests/test_tender_api.py), [Today](../../services/api/tests/test_tender_today.py), [delivery](../../services/api/tests/test_tender_delivery.py), [XLSX originals](TENDER_XLSX.md), [independent matching](BUSINESS_MATCHING_EVALUATION.md) |
| B7 | [HTTP](../../services/api/tests/test_trademark_api.py), [matching](../../services/api/tests/test_trademark_matching.py), [workflow](../../services/api/tests/test_trademark_workflow.py), [history](../../services/api/tests/test_trademark_history.py), [deadline journey](../../services/api/tests/test_trademark_deadline_journey.py), [independent matching](BUSINESS_MATCHING_EVALUATION.md) |
| B8 | [HTTP](../../services/api/tests/test_auction_api.py), [rules](../../services/api/tests/test_auction_rules.py), [sources](../../services/api/tests/test_auction_sources.py), [workflow](../../services/api/tests/test_auction_workflow.py), [reminders](../../services/api/tests/test_auction_reminders.py), [native collector](../../services/api/tests/test_aste_collection.py), [source/workflow evidence](AUCTION_WATCH.md) |

## Source acceptance prerequisites

| Direction | Required evidence and remaining boundary |
|---|---|
| C1 Local warnings | Reviewed publisher/type jurisdiction, current geography and a nonempty permitted warning. The native default covers Swiss MeteoAlarm wind/thunderstorm. Snow/ice separation, flood, forest fire, civil protection and power outages need their own proven coverage; do not inherit it from the weather channel. |
| C2 Commute | Current permitted situation and estimated-timetable channels, dated journey identity, stop/line/operator mapping and interchange evidence for multiple legs. A situation message alone cannot prove a numeric delay or actual restoration. |
| C3 Road | Current FEDRO channel permission, exact location-table/topology edition, direction mappings and source validity. Recurrence tests need the fixed-offset source semantics; an unsupported time or location remains unknown. |
| C5 Pollen | Separate observation/forecast permissions, method, station/allergen coverage and reviewed category scales. A nearby station is not a home measurement. Confirm a real forecast cycle independently of stored observations. |
| C6 River/Lake | Current official station/parameter metadata, units, period and explicit official danger field. A numerical water level cannot stand in for an official danger category. |
| C7 Air | Current supported station/pollutant/period metadata and units. A regional/hourly value is not personal exposure or a medical diagnosis. Rolling means need complete compatible source hours. |
| B2 Tender | SIMAP publication access and terms, publication timing/corrections, plus separate rights and authenticated access for documents and Q&A. A public detail link does not establish automatic document monitoring. |
| B7 Trademark | Current permitted IPI publication/register access, update and email rights; real publication dates and independently reviewed ranking/calibration evidence. A candidate never establishes infringement. |
| B8 Auction | Current permitted Ticino listing/detail/document access and category coverage. Typed prices and authoritative end times stay distinct. A second-canton conformance fixture does not activate or claim a second live source. |

## CORE — execute across all nine directions

The following procedures apply to **every applicable native reader**, not only
Pollen or one business category. Attach a nine-direction result matrix to each
CORE row. Use the CORE suites plus each domain's native workflow references.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-core-01"></a>AC-CORE-01 | Create a monitor through each native editor using ordinary locations/interests and configured source catalogues. A user must not type internal source IDs, grants or technical versions. Record unavailable source choices honestly. |
| <a id="ac-core-02"></a>AC-CORE-02 | Inspect each saved monitor's source resolution and permissions. Confirm a real authoritative source for its exact selected scope; unsupported scope cannot become active by toggling a feature flag. |
| <a id="ac-core-03"></a>AC-CORE-03 | Process two distinct source states, restart the application and read both. Confirm immutable prior values and current values, with source and configuration revisions. |
| <a id="ac-core-04"></a>AC-CORE-04 | Deliver a new source object, update it, then deliver another object with similar wording. The update stays attached to the first development; the second object retains its own identity. |
| <a id="ac-core-05"></a>AC-CORE-05 | Replay a formatting/transport-only change and then a domain-material change. Only the latter creates the configured material event; both retain appropriate source evidence. |
| <a id="ac-core-06"></a>AC-CORE-06 | Open every delivered card and its explanation. Check the actual matched location, threshold, time or profile terms against saved configuration; unrelated facts cannot be listed as reasons. |
| <a id="ac-core-07"></a>AC-CORE-07 | Follow evidence from each delivered item. Verify exact permitted source/version binding, source timestamp and original-field context. Withdraw source display rights and confirm redaction without fabricated substitute evidence. |
| <a id="ac-core-08"></a>AC-CORE-08 | Replay identical source data, restart the worker and retry the same job. Count logical developments and delivery intents; no new copies may appear for the same owner/material revision. |
| <a id="ac-core-09"></a>AC-CORE-09 | Review an item, deliver a material update and inspect history. The item becomes reviewable again and the prior decision stays tied to its old evidence revision. |
| <a id="ac-core-10"></a>AC-CORE-10 | Exercise reviewed, not relevant, continued monitoring and action-required outcomes in each applicable native vocabulary. Confirm persistence, allowed roles, visible meaning and version-conflict rejection. |
| <a id="ac-core-11"></a>AC-CORE-11 | Compare successful unchanged acquisition, empty complete acquisition, timeout, denied access and stale data. The UI must distinguish these states and must not label failure as no change. |
| <a id="ac-core-12"></a>AC-CORE-12 | Compare the displayed publication/measurement timestamp with the original. Separate source time, acquisition time and user decision time; retain timezone and precision rather than substituting the current clock. |
| <a id="ac-core-13"></a>AC-CORE-13 | Inspect deterministic facts and any admitted AI explanation. Check visible distinction and citations; disable the model/profile and confirm deterministic monitoring still works without fabricated generation. |
| <a id="ac-core-14"></a>AC-CORE-14 | Recalculate a threshold crossing from exact retained values, units, periods and rule revision. Repeat with boundary, missing, nonfinite and incompatible-unit inputs; invalid data cannot silently pass. |
| <a id="ac-core-15"></a>AC-CORE-15 | Compare notification preview, queued intent and send decision under configured materiality. Change consent, source rights and current revision after claim; stale/ineligible intents must not send. |
| <a id="ac-core-16"></a>AC-CORE-16 | Resolve a development, restart and traverse its permitted history. Confirm prior source/review states remain accessible within stated retention and rights, without presenting them as current. |
| <a id="ac-core-17"></a>AC-CORE-17 | Inspect native-to-shared projections for all nine categories. Check identity, source/configuration revision, status, relevance, evidence and review links against native records; preserve domain-specific distinctions. |
| <a id="ac-core-18"></a>AC-CORE-18 | In isolated fixtures add a second source using an existing domain boundary. Exercise discovery, update and review through the same section and domain workflow. A generic data model alone is insufficient proof. |
| <a id="ac-core-19"></a>AC-CORE-19 | Populate permitted developments in all nine directions and the legacy feed. Traverse Today across tied timestamps and new arrivals, verify filters/counts, and exclude other owners' private records. |
| <a id="ac-core-20"></a>AC-CORE-20 | Ask independent participants to open a delivered item and explain why it reached them and what evidence supports it. Record first-interaction answers and confusion; do not coach or substitute an agent assessment. |

## C1 — local official warnings

Use a verified Swiss footprint, an overlapping warning, a disjoint warning and
an update/cancellation chain with retained originals. Test each claimed hazard
type separately; storm evidence does not close all C1 source coverage.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-c1-01"></a>AC-C1-01 | Save and reopen a Swiss location through catalogue/manual location selection. Confirm the selected verified footprint and reject forged client geography proof. |
| <a id="ac-c1-02"></a>AC-C1-02 | Admit a new permitted warning intersecting that footprint, run the native worker and verify one private development with the actual type and official severity. |
| <a id="ac-c1-03"></a>AC-C1-03 | Admit a disjoint warning and one intersecting only a polygon hole. Neither may be delivered as affecting the saved footprint. |
| <a id="ac-c1-04"></a>AC-C1-04 | Increase official severity with a valid update identity. Check the new material event, prior severity and unchanged source meaning. |
| <a id="ac-c1-05"></a>AC-C1-05 | Read the update's predecessor relationship. Missing historical predecessors must be disclosed; a similar headline must not establish the link. |
| <a id="ac-c1-06"></a>AC-C1-06 | Compare original and updated severity, instructions, geography and validity. Each displayed difference must refer to the corresponding retained source revision. |
| <a id="ac-c1-07"></a>AC-C1-07 | Open the warning's permitted original and official link; verify attribution, issue time and unmodified instructions. Revocation must deny retained source display. |
| <a id="ac-c1-08"></a>AC-C1-08 | Mark the exact warning revision reviewed. Retry and submit a stale version; retain one current decision and reject conflicting stale writes. |
| <a id="ac-c1-09"></a>AC-C1-09 | Process an explicit authoritative cancellation/all-clear. Separately omit a record from a complete feed and fail a poll: neither absence nor failure may forge official clearance. |
| <a id="ac-c1-10"></a>AC-C1-10 | Replay the same CAP/Atom state and a technical-only refresh; inspect development/history/delivery identities and confirm no duplicate alert. |

## C2 — regular commute

Use an exact dated journey, supported stop/line/operator references, service dates,
overnight times and both permitted situation and delay evidence. Include an
unrelated line, a missed interchange and daylight-saving boundaries.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-c2-01"></a>AC-C2-01 | Save origin/destination, weekdays and travel window using catalogue names. Reopen the journey and verify stop IDs and dated leg/interchange readiness. |
| <a id="ac-c2-02"></a>AC-C2-02 | Admit an official cancellation for the selected dated journey and process it; verify one explained cancellation development. |
| <a id="ac-c2-03"></a>AC-C2-03 | Admit disruptions for a different operator/line/direction/service day. Verify that textual similarity does not make them relevant. |
| <a id="ac-c2-04"></a>AC-C2-04 | Set a ten-minute threshold; process explicit delays below, at and above it. Missing delay values remain unknown and are never inferred from a situation headline. |
| <a id="ac-c2-05"></a>AC-C2-05 | Replay low increments and repeated estimates for the same journey/revision. Confirm configured crossing behavior and no alert for every insignificant minute. |
| <a id="ac-c2-06"></a>AC-C2-06 | Change from delay to cancellation or another supported major state. Confirm a material update in the same journey development and retained prior evidence. |
| <a id="ac-c2-07"></a>AC-C2-07 | Process explicit restored-service evidence. Compare with disappearance/staleness/empty feed: only the supported source state may assert restoration. |
| <a id="ac-c2-08"></a>AC-C2-08 | Open the exact saved situation/timetable evidence, including publication/service time and source references. A revoked grant cannot expose old source payloads. |
| <a id="ac-c2-09"></a>AC-C2-09 | Repeat the disruption inside/outside selected weekdays and overnight windows. Confirm stated outside-window behavior and separate opt-in digest policy, including DST folds/gaps. |
| <a id="ac-c2-10"></a>AC-C2-10 | After restoration and restart, read disruption history and decisions. It must remain historical, permission-scoped and distinct from the current timetable state. |

## C3 — roads and tunnels

Use the exact reviewed location-table edition, two opposite corridors and a
planned/active/resolved event chain. Include overlapping feeds and recurring
closure windows; retain fixed source offsets without guessing daylight saving.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-c3-01"></a>AC-C3-01 | Save multiple named corridors from the catalogue; reopen and check segment/direction binding without requiring internal table numbers from the user. |
| <a id="ac-c3-02"></a>AC-C3-02 | Process a permitted closure on a selected segment and direction. Verify one relevant private event with exact source validity. |
| <a id="ac-c3-03"></a>AC-C3-03 | Process opposite-direction and unrelated segments. Confirm suppression; unsupported topology must remain unknown rather than be counted as a match. |
| <a id="ac-c3-04"></a>AC-C3-04 | Change live status and compare retained source facts. The prior version stays immutable; the reader must not silently substitute a newer source snapshot. |
| <a id="ac-c3-05"></a>AC-C3-05 | Change a planned closure's start/end or recurring windows. Check source/configuration history and the actual current/next interval through a private worker cycle. |
| <a id="ac-c3-06"></a>AC-C3-06 | Replay identical and overlapping source identities. Confirm one development for the same event and owner, without collapsing unrelated records. |
| <a id="ac-c3-07"></a>AC-C3-07 | Process explicit reopening/resolution, then a later closure. Check linked state transitions; a recurrence window ending alone cannot assert physical road clearance. |
| <a id="ac-c3-08"></a>AC-C3-08 | Read source attribution, record identity, original permitted facts and timestamps from the event. Revoked source/topology evidence must be redacted. |
| <a id="ac-c3-09"></a>AC-C3-09 | Edit materiality while paused, retain its revision and resume. Show that only matching configured changes notify; the edit itself must not forge source changes. |
| <a id="ac-c3-10"></a>AC-C3-10 | Traverse resolved event history across pages and restart. Check equal-time ordering, ownership, retained decisions and historical/current distinction. |

## C5 — Pollen Watch

Use supported observation and forecast channels, a real station/allergen/method
combination, numeric and category rules, and explicit source periods. Confirm
station representativeness and current metadata before starting a live monitor.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-c5-01"></a>AC-C5-01 | Select a location and supported station; deny browser geolocation and verify manual selection remains usable. Confirm distance and representativeness wording. |
| <a id="ac-c5-02"></a>AC-C5-02 | Select multiple supported pollen types, save and reopen. Unsupported station/allergen combinations cannot silently substitute another allergen. |
| <a id="ac-c5-03"></a>AC-C5-03 | Collect a permitted current official observation and inspect value, unit, method, period, station and immutable source binding after restart. |
| <a id="ac-c5-04"></a>AC-C5-04 | Cross a boundary in a reviewed category scale, then reverse. Confirm one auditable category transition using the exact applicable method/period scale. |
| <a id="ac-c5-05"></a>AC-C5-05 | Configure a threshold; test below/at/above values and missing readings. Only a valid configured crossing may trigger the corresponding development. |
| <a id="ac-c5-06"></a>AC-C5-06 | Show observation and forecast for the same pollen/location side by side. Verify labels, issue/valid times, periods and evidence; a forecast must not be called a measurement. |
| <a id="ac-c5-07"></a>AC-C5-07 | Review all labels, explanations, messages and optional assistant extracts with domain reviewers. No diagnosis, personalised treatment or invented health conclusion may appear. |
| <a id="ac-c5-08"></a>AC-C5-08 | Open current and historical evidence and compare source/station/time with retained originals. Ensure a refresh does not replace the pinned version without disclosure. |
| <a id="ac-c5-09"></a>AC-C5-09 | Replay identical values and small fluctuations around the rule boundary. Confirm hysteresis/cooldown/deduplication and consented delivery without repeated spam. |
| <a id="ac-c5-10"></a>AC-C5-10 | Resolve and restart, then traverse observations, material changes and decisions within retention. Withdraw display rights and verify historical-source redaction. |

## C6 — River / Lake Watch

Use a supported station and explicit parameters for level, flow, temperature and
official danger where available. Keep exact units and compatible time windows.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-c6-01"></a>AC-C6-01 | Select a supported station/water body through the catalogue. Verify parameter coverage and show an unavailable parameter without substituting another. |
| <a id="ac-c6-02"></a>AC-C6-02 | Collect and reopen a current official sample with its unit, period, station and source timestamp. A missing/null value cannot become zero. |
| <a id="ac-c6-03"></a>AC-C6-03 | Process a later compatible sample and inspect previous/current values and delta; incompatible periods/units or a missing baseline remain unknown. |
| <a id="ac-c6-04"></a>AC-C6-04 | Cross a configured threshold and run the worker twice. Confirm a single material event with the exact compared values and rule revision. |
| <a id="ac-c6-05"></a>AC-C6-05 | Raise an explicit official flood-danger field alongside an ordinary threshold crossing. Verify source-derived higher priority; water level alone cannot create official danger. |
| <a id="ac-c6-06"></a>AC-C6-06 | Replay the same source sample and repeat after restart. Confirm no duplicate event or delivery for the same material state. |
| <a id="ac-c6-07"></a>AC-C6-07 | Save a custom rule, unit and time window, then edit while paused. Verify exact retained configuration versions and reject ambiguous/nonfinite values. |
| <a id="ac-c6-08"></a>AC-C6-08 | Compare source time in the current card, chart/history and evidence. Distinguish observation time from acquisition and rendering time. |
| <a id="ac-c6-09"></a>AC-C6-09 | Process reversal and official downgrade. Confirm the same development identity, new material revision and stale-review conflict protection. |
| <a id="ac-c6-10"></a>AC-C6-10 | Page through measurements and changes after resolution/restart. Confirm ordering, owner boundaries and stated retention without rewriting old measurements. |

## C7 — Air Quality Watch

Use supported pollutant/station combinations and separate hourly measurements
from rolling-period calculations. Include corrections, withdrawals and incomplete
periods; no stale good value may masquerade as the current reading.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-c7-01"></a>AC-C7-01 | Select a supported location/station and verify catalogue metadata, footprint limits and rejection of unsupported combinations. |
| <a id="ac-c7-02"></a>AC-C7-02 | Select multiple supported pollutants and reopen saved preferences. Each keeps its own metric/unit/period; unavailable metrics cannot be replaced. |
| <a id="ac-c7-03"></a>AC-C7-03 | Store an observation, restart and compare its exact source timestamp in storage and the reader. Later acquisition cannot overwrite that clock. |
| <a id="ac-c7-04"></a>AC-C7-04 | Process new values and a source correction. Compare pinned previous/current evidence and distinguish corrected history from a newly observed value. |
| <a id="ac-c7-05"></a>AC-C7-05 | Replay small fluctuations, duplicates and threshold crossings. Check the actual materiality/hysteresis/cooldown rules and avoid repeated alerts. |
| <a id="ac-c7-06"></a>AC-C7-06 | Inspect hourly versus rolling-period labels, missing hours, unavailable station coverage and stale/withdrawn observations. Limitations must be visible, not inferred away. |
| <a id="ac-c7-07"></a>AC-C7-07 | Review reader, alerts and optional assistant extracts for medical claims. Show environmental evidence without diagnosing personal exposure or illness. |
| <a id="ac-c7-08"></a>AC-C7-08 | Process a relevant material change and locate the same revision in Today. Check owner scope, reason, evidence link and review behavior. |
| <a id="ac-c7-09"></a>AC-C7-09 | Process a supported improvement/recovery after a crossing. Confirm the same development updates; source failure or a withdrawn value cannot imply improvement. |
| <a id="ac-c7-10"></a>AC-C7-10 | Reopen history after resolution and restart, including corrections and reviews. Verify immutable versions, retention and cross-owner denial. |

## B2 — Tender Watch

Use one relevant and one excluded tender, multiple lots, publication corrections,
an explicit deadline, permitted document revisions and an unavailable attachment.
Publication access does not imply permission to read or export documents/Q&A.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-b2-01"></a>AC-B2-01 | Save procurement categories, location, language, scope and exclusions in a company interest profile. Reopen the exact profile revision and verify role/owner boundaries. |
| <a id="ac-b2-02"></a>AC-B2-02 | Ingest a permitted published SIMAP record, process discovery and verify a candidate with publication/lot identity. Embargoed or unavailable source data cannot appear early. |
| <a id="ac-b2-03"></a>AC-B2-03 | Process explicit exclusions and independently labelled negative examples. Check suppression and per-case precision/recall; hand-authored example matches do not establish ranking quality. |
| <a id="ac-b2-04"></a>AC-B2-04 | Open a candidate and compare each reason with the saved profile and exact permitted scope text. AI additions must be visibly separate and independently reviewed. |
| <a id="ac-b2-05"></a>AC-B2-05 | Open the public original and permitted private attachments. Verify hash/version, current access and attribution; unavailable attachments must be explained, not silently omitted. |
| <a id="ac-b2-06"></a>AC-B2-06 | Admit a publication update, duplicate and out-of-order record. Preserve prior versions and reject identity/order corruption without making duplicate opportunities. |
| <a id="ac-b2-07"></a>AC-B2-07 | Move an explicit tender deadline earlier and later. Compare old/new source times, material event and any replaced reminder; unknown dates must not be invented. |
| <a id="ac-b2-08"></a>AC-B2-08 | Add, replace and withdraw permitted documents/Q&A; include changed conditions inside a same-named file and an access failure. Verify exact versions and honest incomplete extraction. |
| <a id="ac-b2-09"></a>AC-B2-09 | Choose Bid, No-bid and Monitor in separate versions; record actor/comment/owner. Confirm internal decision history and no external bid submission. |
| <a id="ac-b2-10"></a>AC-B2-10 | Review, then change deadline/conditions/documents materially. The same candidate reopens while prior decision text stays attached to its original evidence. |
| <a id="ac-b2-11"></a>AC-B2-11 | Reingest identical publications and translations with stable lot identities. Count opportunities and separate lots; source retries must not multiply them. |
| <a id="ac-b2-12"></a>AC-B2-12 | Opt a verified test recipient into the digest, preview new/updated tenders and deliver to the test sink. Recheck current rights/consent/revision after claim; no historical backfill or duplicate send. |

## B7 — IP Watch

Use exact, similar and unrelated marks, goods/services with differing relevance,
publication/register updates and a deadline with verified rule provenance. Results
are candidates for professional review, never infringement determinations.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-b7-01"></a>AC-B7-01 | Register multiple monitored brands and goods/services interests. Reopen the saved revision and verify organisation membership and private/shared responsibilities. |
| <a id="ac-b7-02"></a>AC-B7-02 | Ingest a permitted current Swiss publication with stable register/publication identity. Confirm actual channel coverage and freshness separately from a fixture parse. |
| <a id="ac-b7-03"></a>AC-B7-03 | Supply an exact mark in a supported script/normalization case and an unrelated mark. Check the exact-match reason and preserved original spelling. |
| <a id="ac-b7-04"></a>AC-B7-04 | Use independently labelled similarity pairs with the selected reviewed configuration. Report candidates, unknowns and per-language quality; unapproved calibration cannot claim validated probability. |
| <a id="ac-b7-05"></a>AC-B7-05 | Keep the mark constant and vary goods/services scope. Confirm priority changes only for supported evidence and preserve the reason/rule revision. |
| <a id="ac-b7-06"></a>AC-B7-06 | Open the exact publication snapshot and source link. Verify current permission and immutable original wording; revocation must hide restricted facts. |
| <a id="ac-b7-07"></a>AC-B7-07 | Review all candidate cards, alerts, exports and explanations with a domain reviewer. None may assert confirmed infringement or substitute an AI legal verdict. |
| <a id="ac-b7-08"></a>AC-B7-08 | Compare retained publication date with the authoritative record, including precision/timezone. Acquisition time cannot stand in for publication date. |
| <a id="ac-b7-09"></a>AC-B7-09 | Show explicit and calculated deadline cases, including unknown/ambiguous dates. Calculated deadlines need rule/evidence provenance and a visible verification requirement. |
| <a id="ac-b7-10"></a>AC-B7-10 | Change owner/status/goods or a relevant register field, then reverse it. Retain distinct source revisions and material events without treating formatting refresh as a new legal development. |
| <a id="ac-b7-11"></a>AC-B7-11 | Classify Relevant, Not relevant and Monitor, then process a material update. Check exact evidence-bound decision history, reopening and stale-write rejection. |
| <a id="ac-b7-12"></a>AC-B7-12 | Admit a high-relevance eligible candidate and inspect the Impact Inbox projection. Confirm the same evidence/decision, owner visibility and suppression after current rights are revoked. |

## B8 — Auction Watch

Use multiple lots, supported categories, exact typed prices, an explicit end time,
conditions/documents updates and cancellation. No internal decision places a bid.

| ID | Procedure and required observation |
|---|---|
| <a id="ac-b8-01"></a>AC-B8-01 | Create and reopen category/location/keyword/brand interest profiles with price basis and limits. Verify private ownership and configuration history. |
| <a id="ac-b8-02"></a>AC-B8-02 | Ingest a permitted current official auction through the native collector and process discovery. Verify listing/detail completeness and category coverage; a public link alone is insufficient. |
| <a id="ac-b8-03"></a>AC-B8-03 | Process relevant, excluded and unknown category/location/keyword cases. Confirm explanation and suppression without inventing a missing brand or geography match. |
| <a id="ac-b8-04"></a>AC-B8-04 | Select a price basis and CHF12,000 limit; process CHF8,500 then CHF12,700 and later minor bids. Distinguish starting price, estimate and current bid; missing price is not zero. |
| <a id="ac-b8-05"></a>AC-B8-05 | Open the official auction/lot and permitted retained evidence. Verify source attribution, current rights and distinct lot identity. |
| <a id="ac-b8-06"></a>AC-B8-06 | Restart after collection and reopen current auction state. Preserve raw/normalized binding, source clock, typed prices and completeness indicators. |
| <a id="ac-b8-07"></a>AC-B8-07 | Move the end time and move it back. Record distinct material generations and replacement reminders; the original reminder must no longer send. |
| <a id="ac-b8-08"></a>AC-B8-08 | Admit explicit cancellation and compare it with missing listing/detail data. Only supported cancellation changes status as cancelled; old ending-soon reminders are suppressed. |
| <a id="ac-b8-09"></a>AC-B8-09 | Set a non-default ending-soon interval and explicit test-email consent. Verify the exact deadline revision, once-only delivery, rescheduling and suppression for unknown/stale/cancelled end times. |
| <a id="ac-b8-10"></a>AC-B8-10 | Exercise Bid, No-bid, Inspect and Monitor, then stop/continue following one auction. Check internal history and unchanged discovery for the rest of the profile; no bid is sent. |
| <a id="ac-b8-11"></a>AC-B8-11 | Traverse source and decision versions after cancellation/restart. Retain earlier conditions/documents and typed prices without presenting obsolete evidence as current. |
| <a id="ac-b8-12"></a>AC-B8-12 | Run TI and a clearly synthetic second-canton adapter fixture through admission, discovery, update, review, reminder and cancellation using the unchanged domain workflow. [Normalized adapter conformance](AUCTION_ADAPTER_CONFORMANCE.md) now provides executable fixture evidence beyond rule-only parity; review the run and its source/release limits. No live second-canton rollout is authorized by this check. |

## Audit findings and next implementation work

The existing suites contain substantial native lifecycle and privacy checks, but
the previous traceability table did not point to concrete acceptance procedures.
This document fills that procedural gap without changing criteria or declaring
unrun checks passed. In particular, inspection of
`test_another_canton_adapter_uses_identical_domain_rules` shows TI/ZH **rule-output
parity only**; it does not exercise the full B8 adapter-swap workflow required by
MV2-050. The subsequent [adapter conformance suite](AUCTION_ADAPTER_CONFORMANCE.md)
now covers that complete normalized-output-to-private-workflow fixture boundary.
It does not establish a second native publisher parser or live source rights.

Across the source-dependent rows, capture real permitted acquisition evidence
before closing acceptance. C1's remaining hazard coverage and B2/B7/B8 access,
rights and current nonempty source evidence remain explicit source gates. The
independent matching corpus, target-host capacity, observed human journeys and
exact deployed release remain separate required evidence under MV2-051/054/058.
No completion percentage is inferred from this document's 116 rows.

Document verification, 15 September 2026: 116 unique active procedure anchors
and every local suite/document link resolve; all 126 original criterion texts and
accountability mappings, ten complete deferred C4 rows and 79 supplemental rows
are unchanged. The original specification SHA-256 remains
`a6f4e7da87a9ae30171164512d16ce4be411f2913c22d90ed7bf7e1bc94ece4c`.
Structural evidence: `.tmp/acceptance-protocol-audit.json`. The required backlog
consistency check passed (one test, 0.18s;
`.tmp/acceptance-protocol-backlog.log`). These are document-integrity checks;
no product behavior was retested or accepted by this audit.
