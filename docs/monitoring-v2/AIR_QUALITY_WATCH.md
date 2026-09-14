# Air Quality Watch — source contract and implementation scope

## Active whole feature: consented Air digest — 14 September 2026

MV2-035 with scoped MV2-012/022 completes the Digest reuse in §14.8. Reuse the
verified private River consent/delivery pattern, keeping Air's station, pollutant,
period, hysteresis/cooldown and immutable source-version semantics. Deliver verified
owner opt-in/opt-out, immediate/daily/quiet-hour settings with IANA timezone, saved
preview, durable worker delivery and exact private change links in all five locales.
Opening a link never implies review. All nine sections remain enabled and visible.

Before SMTP, require the latest unreviewed post-consent change in the current
configuration and current unmuted condition. Recheck source contract freshness,
observation freshness, period and current input revisions; incomplete 24-hour means,
withdrawn/corrected evidence, worker lag and superseded changes cannot send stale
claims. Preserve hysteresis rather than recalculate a threshold without its state.
No old backfill, implicit consent, repeated local-day digest or uncertain SMTP retry.
Email contains private links rather than copied pollutant readings or health advice.

Acceptance: real HTTP → source projection → durable worker → fake SMTP; tenant,
CSRF/CAS, recipient/membership/review/mute/pause/archive/deletion races; stale source
contract, missing/withdrawn hourly values and corrected 24-hour inputs; migration
preservation, quiet/DST and duplicate suppression; five-language/mobile/viewer
browser journey, exact-reader redaction, root build and exact API lint. Existing
licensed Basel access suffices; Lugano/national access, source operational and human
acceptance remain open. This scope does not close broader shared parent tasks.

Status: the complete Basel feature is implemented and locally verified on
12 September 2026; publication and activation are pending. MV2-034/035 remain
VERIFYING. The initial enabled footprint is the licensed Basel-Binningen station;
Lugano and other areas explicitly show unsupported source coverage. National
coverage and human acceptance are not implied by this scoped implementation.

## Consented digest acceptance — 14 September 2026

The complete scope above is implemented: owner-bound consent, saved preview,
immediate/daily/quiet-hour delivery, durable scheduler and exact private reader.
The reader preserves original measurements and periods, identifies newer or
historical changes and never marks them reviewed on arrival. Known authorization
denials unmount private content, and browser page restoration forces a fresh read.

Delivery rechecks current source-contract and observation freshness, configuration,
mute state, latest review state and source input hashes immediately before SMTP.
An unchanged latest hourly reading cannot hide a correction to an older 24-hour
input. Delivery waits for the stateful projection to catch up, retaining hysteresis
and cooldown semantics. Corrections and missing windows cannot send obsolete
claims. Mail contains exact private links rather than copied pollution readings.
No source access, production consent or real recipient mail was changed.

Verification: the expanded Air/River/Monitoring Centre run passed 89 tests and
exposed one new HTTP-fixture error: a non-hour timestamp was correctly rejected by
the source parser. Correcting that fixture and adding an isolated older-window-input
case produced a final **26/26 Air delivery tests passed**, including the real
HTTP → durable worker → fake SMTP journey. Counts overlap. Migration
`2b08e9a24acd` round-trips without losing source measurements or private changes;
schema comparison passes. Strict consent/CSRF/CAS, source withdrawals/freshness,
tenant/access/recipient/review/mute races, no backfill, daily/quiet/DST and uncertain
SMTP behavior passed. The root production build, changed frontend formatting and
exact API lint passed. The browser journey passed **nine full-document axe
checkpoints without violations**, five locales, mobile/viewer controls, saved
consent/preview/opt-out and exact-link/access-redaction checks. Automated checks do
not claim native-language or human acceptance. MV2-035 remains VERIFYING pending
actual release and applicable source operational/human acceptance.

## Source findings

The [Basel-Stadt dataset 100051](https://data.bs.ch/explore/dataset/100051/)
provides Basel-Binningen air measurements through its public
[Explore API](https://data.bs.ch/api/explore/v2.1/catalog/datasets/100051).
The specific dataset metadata declares **CC BY 4.0**, links its licence, and
publishes hourly O3, NO2, PM10 and PM2.5 fields in micrograms per cubic metre.
Retain the dataset title, publisher as declared, source link, licence link and
an explicit indication of any Helvetic Lens aggregation. The metadata names
MeteoSchweiz; the independently queried air CSV names NABEL. Do not silently
rewrite the provider declaration to hide this distinction.

The [FOEN NABEL data page](https://www.bafu.admin.ch/en/data-query-nabel) links
the public [NABEL query form](https://bafu.meteotest.ch/nabel/abfrage/start/english).
Its station query supports Basel-Binningen and Lugano-Università. Two bounded
read-only queries established the following facts:

- Basel hourly CSV explicitly declares hourly means, fixed MEZ/CET time,
  suburban station type and preliminary current-year values. **144 populated
  pollutant values matched** the cantonal API snapshot at identical source times.
- Lugano daily CSV explicitly declares daily means and, separately, O3's maximum
  hourly mean for the day. Both queried dates contained all four pollutants.
  Lugano is an urban station. This establishes observed coverage, not a licensed
  recurring connector or national coverage.
- CSV station names contain non-UTF-8 bytes compatible with ISO-8859-1, including
  the accented final character of Università. JSON is UTF-8. A HEAD request to the
  form endpoint returns an HTML content type and does **not** establish the POST
  CSV's declared encoding; do not use that HTML header as a CSV contract.

The normalized probe manifest is in
[the retained evidence](evidence/mv2-034-source-probe.json). Raw snapshots stay in
the task's scratch directory; no production collector, user monitor, approval or
email consent was changed.

## Important parser and interpretation cases

The Basel probe contained **11 future empty rows**. The latest populated reading
was 12 September 2026 at 11:00 UTC: O3 110.5, NO2 4.9, PM10 10.1 and PM2.5 4.7
µg/m³. These are dated source observations, never configuration defaults.

Use the timezone-aware API timestamp as identity and preserve it separately from
fetch time. The source's timestamp_text is fixed winter time. Do not interpret
it using Europe/Zurich daylight saving rules. Future empty rows are placeholders,
not forecasts, zero pollution, new observations or evidence of recovery.

An hourly observation is not a daily mean. A locally calculated rolling 24-hour
mean must have its own period/method identity, require all 24 compatible hourly
inputs, and be labelled as a Helvetic Lens calculation from official observations.
No interpolation or filling missing hours with zero. A daily O3 maximum cannot
be compared with an hourly threshold. Retain previous/current values, source time,
period, units, quality, method and correction revision in explanations.

No official categorical scale has yet been established for this contract.
Show numerical observations and explicitly configured user rules until that gate
is satisfied; do not manufacture official categories or personal health advice.

## Implemented feature

Reuse the existing authenticated organization/owner boundary, durable outbox and
deterministic lifecycle patterns. River's release is verified; outstanding
human acceptance remains separate. This implementation does not close the broader
shared parent tasks.

The feature provides supported station search and explicit unsupported-area explanations;
pollutant/period selection; preview and explicit start; threshold/materiality and
cooldown configuration; private current state, previous/current comparison and
evidence; Today changes with reasons; review/reopen; mute pollutant; threshold
editing; pause/resume/archive/delete; measurement and decision history; bounded
recovery, correction handling, staleness and independent missing-pollutant states.
Improvement updates the existing development; minor fluctuations create no spam.
Five-language navigation/forms, English contextual help and mobile/accessibility
checks accompany the reader. Source/review/decision/delivery states and existing
Pollen/River data stay separate. The existing Today page contains a private Air
section with current monitor health, measurement periods, previous/current
evidence, review controls and links back to the exact monitor.

## Source and operational contract

Only the fixed dataset 100051 endpoint is fetched. Metadata is checked at most
daily; observations use two bounded 100-record pages at most hourly, shared by all
users. This is an application budget of at most two observation requests per hour
plus one daily metadata request, not a claim about the provider's unpublished
quota. Durable leases suppress duplicate requests; failures back off from one to
24 hours. Each response is bounded to 2 MB and 30 seconds, without redirects,
ambient credentials or user-supplied URLs. A changed licence, publisher, station
title or unit schema stops new collection. Missing/negative/non-finite, ambiguous
time and duplicate-hour inputs have explicit negative tests.

The collector retrieves up to 96 hours to support 72-hour recovery plus the
preceding 24-hour input window. The mean is labelled as the mean of 24 consecutive
published hourly values; it does not invent an undocumented interval endpoint.
Current coverage becomes stale after six hours. Get requests recompute freshness
even if workers stop. A source withdrawal does not rewind the reader to an older
good hour. Every changed source value retains an immutable reading revision;
existing private explanations retain their original evidence. Corrections affecting
the current rule state, including a 24-hour input correction, are re-evaluated.
Older source corrections remain visible in measurement history.

Thresholds use strictly greater-than. Hysteresis requires improvement to the
threshold minus the configured margin; the cooldown applies to repeated
deteriorations, while improvements remain visible immediately. Repeated unchanged
states create no new event. Improvement retains development identity and new
material changes require renewed review. Muting a pollutant changes a versioned
private setting without clearing other pollutants' state. Unmuting compares the
current observation rather than replaying alerts from the muted interval.

Six additive tables in migration `d4a6be15f87c` follow River's `c395ad04e76b`.
Public latest readings, immutable reading revisions and source cache are separate
from private monitors, settings revisions and developments. Only the owner can
read private entries, including Today, history and jobs, even if another user is
an administrator in the same organization. The existing CSRF, membership, rate
and role boundaries apply. Workers recheck status/version/access after public
network I/O. `AIR_WATCH_ENABLED=false` disables the reader and effective jobs.
Daily cleanup retains public readings for 30 days even with no active monitors;
deleting a private monitor removes its private settings/changes, not shared data.

## Verification evidence

The actual collector passed a read-only probe at **13:48 UTC on 12 September**:
both catalogue and source collection succeeded, retaining 384 public samples and
all four latest Basel pollutants. At source time 12:00 UTC these were O3 116.9,
NO2 3.7, PM10 8.7 and PM2.5 4.3 µg/m³. See
[actual collector evidence](evidence/mv2-034-live-collector.json). The isolated
scratch database contained no accounts or private monitors.

Focused Air suite: **25 passed**, covering actual worker dispatch, migration
roundtrip, Today/privacy, corrections and withdrawals, complete/missing windows,
noise suppression, lifecycle and retention. Existing River suite: **24 passed**.
Affected authentication/jobs/organization/backlog/private-monitoring regression:
**81 passed**. The full frontend build, types, localization and structural checks
pass. The browser journey passed **eight full-document axe checkpoints**, five
locales, mobile layout and viewer restrictions, including preview/save/start,
threshold change, review, history, mute/unmute, Today, pause/edit/resume/archive.
Automated locale checks do not claim native-language review or a human pilot.

Pollen live/delivery/shared-runtime plus the final same-workspace privacy check:
**31 passed**. The global legacy formatting backlog is unchanged; newly created
Air files pass their formatting checks.

| Criterion | Implementation / evidence |
|---|---|
| AC-C7-01 supported station | Manual search; unsupported Lugano/other area explanation; live Basel contract |
| AC-C7-02 pollutant choice | Four pollutants, per-period optional rules and individual mute |
| AC-C7-03 source time | Preserved timezone-aware source timestamp, separate fetch time |
| AC-C7-04 comparison | Immutable previous/current evidence and explicit period/unit |
| AC-C7-05 materiality | Threshold, hysteresis, cooldown, idempotency and recovery tests |
| AC-C7-06 limitations | Provisional quality, station representativeness, missing coverage, derived labels |
| AC-C7-07 no diagnosis | Numerical user rules; no invented medical or official risk categories |
| AC-C7-08 Today | Owner-scoped latest developments, review and exact-monitor links |
| AC-C7-09 improvement | Same development identity with renewed review on subsequent material change |
| AC-C7-10 history | Paginated source revisions, private developments and configuration history |

## Explicit limits and remaining acceptance

1. The provider has not published a numerical quota in the inspected dataset
   contract. Keep the conservative shared budget and source backoff above.
2. Document the exact NABEL CSV reuse/automation grant before enabling Lugano or
   other national stations. The station-geodata licence and Basel dataset licence
   do not automatically license national observation CSVs. Generic federal
   website terms are not a substitute for a dataset-specific grant. Integration
   owns this investigation; no user contact or paid access has been requested.
3. Official categories and daily O3 maxima remain separate unsupported
   interpretations; numerical per-period rules are the implemented fallback.
4. Exact release identity and applicable field/human acceptance remain pending.
   No DONE claim is made merely from local tests or a push.

Keep this feature as one coherent local iteration. Commit and immediately push
main only after the complete feature and required checks are ready.
