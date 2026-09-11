# Pollen Watch — implementation contract draft v1

MV2-069, 2026-09-11. Product contract for the next implementation slices; not a
completed feature, usability result or permission to activate unaccepted sources.
Uses [MV2-001 extension contracts](EXTENSION_CONTRACT.md) and the separate
[source dossier](POLLEN_SOURCES.md). Basel PBS is the first sample location.

## Journey and acceptance mapping

| Criterion | Required behavior |
|---|---|
| AC-C5-01 | Create Monitor → Personal → Pollen Watch → select a supported public station near the chosen location. Show station name, distance and limits before Start. Avoid storing a home address when station selection suffices. |
| AC-C5-02 | Choose one or several allergens. Preview observation and forecast availability separately for each; seasonal absence remains visible. |
| AC-C5-03 | On explicit Start, store the current official state and immutable evidence immediately, even without a threshold crossing. Show waiting/unavailable/stale when appropriate. |
| AC-C5-04 | Compare categories only under an approved versioned allergen/period scale. A scale change is a revision, not a pollen change. Category labels remain unavailable until source review. |
| AC-C5-05 | User chooses threshold and optional rapid-increase rule; preview explains units, comparison window and reset behavior before Start. Validate finite, nonnegative values; save a rule revision with configuration. |
| AC-C5-06 | Separate cards/series explicitly labelled Measured and Forecast, including observation time or issue + valid time. Forecast revisions never overwrite measurements. |
| AC-C5-07 | Describe environmental concentrations and limits, without diagnosing symptoms or prescribing treatment. |
| AC-C5-08 | Why received identifies selected allergen, station, matched rule and configuration revision. Evidence shows source identity/hash, previous/current values, units, times and attribution. |
| AC-C5-09 | Notify on material transitions, not each poll. Hysteresis/reset and comparable-period rules prevent repeated boundary alerts. Missing data cannot clear a threshold. Quiet hours and opt-in email are independent delivery settings. |
| AC-C5-10 | Preserve revisions and prior decisions. Today → evidence/history → Review / Not relevant / continue; a material new revision may reopen while retaining the old decision. |

Pause stops future matching/delivery without claiming the pollen resolved. Mute
changes delivery only. Resume establishes current state and suppresses historical
backlog floods. Archive/delete/export follow the authenticated personal subject's
permissions and privacy lifecycle. Email is off by default and requires explicit
opt-in; delivery rechecks current permissions and consent.

## Interface boundaries for MV2-070

Use `contract_version=1`, `template_id=pollen-watch`, immutable template/configuration
and rule revisions. The configuration contains public `station_id`, unique selected
allergen IDs, rule settings, timezone and delivery preferences; private workspace
ownership comes from authorization, never a trusted request field.

Keep these source facts independent of that private configuration:

- Observation identity: authority + observation channel + station + allergen +
  aggregation period + observation instant. Corrections append a source revision.
- Forecast identity: authority + forecast channel + model/grid/member/layer +
  cell + allergen + issue instant + valid instant. Corrections append a revision.
- Evidence: immutable source artifact hashes/identities, fetched time, parser version,
  rights version, source units and converted Decimal value; category and scale are
  optional until established. UNKNOWN is a state, never a numeric zero.
- Capability: station/allergen/channel with supported, seasonal-unavailable or
  unverified status and reason. Metadata discovery alone cannot authorize Start.

The source proof JSON is a versioned **capture fixture**, not the final runtime API
schema. Its named observation and forecast fields may inform the adapter; production
models, persistence and UI require MV2-070/030 acceptance. Do not consume this dated
fixture as a live fallback. The broader legal records/feed retain their original API.

## Review protocol still to execute

Create a labelled prototype from the retained sample. Walk through selecting PBS,
choosing birch + grasses, explaining unavailable current forecasts, entering a
threshold/rapid-increase option, inspecting distinct times, why/evidence/history,
pausing and trying an unsupported station. Check keyboard and narrow viewport.
Record actual reviewer, date, findings and fixes; an agent inspection is not a human
session. No review has been performed yet. Native-language, screen-reader and
independent user-testing gates remain assigned to MV2-070/071.
