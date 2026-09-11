# Pollen Watch complete feature: operating and pilot review

This is a reviewable runbook, not a record of completed human/source acceptance.
The complete feature is implemented across MV2-069/070/030/031/071; parent tasks
remain open until their individual source, human and release gates are met.

## Activation and isolation

Only Monitoring v2 may expose this workflow. Its exact workspace/template/version
grant is read from `MONITORING_V2_ROLLOUT`; the source decision is separately read
from `POLLEN_SOURCE_POLICY`. Both default to `{}` in the Monitoring Compose
override. API, CPU worker and scheduler receive the same values. Do not set an
approved channel because a download or synthetic test succeeded. Draft preferences
and imported backups never grant email consent.

The private decoder uses pinned native/Python ecCodes 2.47.0 and canonical COSMO
v2.47.0.2. It has one CPU, 1 GiB RAM, a read-only filesystem, bounded tmpfs, no
published ports, credentials, database or source volume. Only the CPU worker joins
its private internal network. The main product Compose configuration is unchanged.
The existing release controller builds its established images before activation;
Compose builds the decoder dependency on first use. A cold native build is inside
the controller's bounded startup/rollback step. No serving controller or checkout
was modified to bypass its gates. Verify first activation and rollback on the
actual candidate before calling the deployment accepted.

## Source decision to review

Each approved channel must identify a retained review SHA-256, immutable version,
source/method, station set, allergen set, period, UTC validity interval, freshness,
poll interval, retention days and explicit raw-export permission. Ambiguous
overlapping admissions fail closed. Raw export defaults off even for an approved
display channel. Category rules also require one approved method/period/allergen
scale; there are no invented built-in cutoffs.

- Hourly: `meteoswiss:ogd-pollen`, `meteoswiss-automatic-hourly-v1`,
  `observation_hourly`, station `h_now` CSV. Twenty-minute refresh is a download
  schedule, not proof of a new measurement every twenty minutes.
- Daily: the same source, `meteoswiss-automatic-daily-v1`. Official `d1` is
  00–00 UTC; `d0` is 06–06 UTC on the following day. Only completed intervals
  from the automatic method (2023 onward) are admitted. The interval end identifies
  validity. Daily means and their category scales never become hourly categories.
- Forecast: `meteoswiss:icon-ch2`,
  `icon-ch2-control-nearest-lowest-layer-v1`, `forecast_instant`. The initial
  scheduling contract selects the explicit 00 UTC issue and tomorrow's current
  UTC hour, plus the exact same-issue rapid-change baseline when supported.
  Control member, lowest layer 80, model grid, nearest cell within 5 km, issue and
  valid time remain distinct from observations. The distance limit is an
  implementation bound, not accuracy or home-level exposure.

The implementation retains exact artifact hashes, source row hashes and forecast
conversion provenance. Public downloads validate every HTTPS redirect, supplied
checksums, byte limits and a 210-second cumulative fetch budget below the shared
five-minute lease. Jobs heartbeat and honor cancellation between bounded I/O
steps. Errors use bounded codes without signed URLs or source bodies. Retries
back off to at most one day; unavailable values never become zero. Expired source
admission withholds current/history values and raw downloads.

Public normalized samples and raw files have recorded retention deadlines.
Cleanup removes at most 100 expired artifacts and 1,000 expired public rows per
run; renewal serializes on artifact metadata. Private configuration, review and
material evidence remains until owner/workspace deletion and stays subject to
current source access rules. Deletion cascades the monitor's private runtime,
reviews, delivery intents and history; queued work is cancelled. It does not
delete the shared public source data used by other monitors. JSONL history export
contains a manifest, configurations, activity and every review revision. It is
paginated internally and checks current ownership/membership on every page. Only
the final `complete` record certifies a completed download; this is a history
export, not an importable live monitor or database backup.

## Functional walkthrough for independent reviewers

1. Use an isolated authorized workspace and verified sources. Create a multi-
   allergen monitor, choose a named station, check observation/forecast coverage,
   choose exact threshold/reset or rapid/category rules, and preview. Verify
   that unavailable sources and unsupported category scales explain blocked Start.
2. Start explicitly. The initial official state must not invent an earlier
   crossing. Confirm separate measurement, forecast issue and forecast-valid
   times, exact evidence values, attribution and the environmental-data limitation.
3. Confirm a real permitted material transition in Today and in the monitor.
   Open why/previous/current/baseline/source evidence. Review it, mark not relevant,
   or continue; verify the decision history survives reload and later distinct
   material changes reopen without erasing the earlier review.
4. Exercise absent/allergen coverage, stale data, provider outage, corrected
   source revision, recovery and duplicates. Unknown never means low pollen,
   resolved review or a fabricated measurement. A new model issue rebaselines.
5. Pause; change station/rules while paused; resume. Initial state is refreshed
   without replaying old alerts. Archive preserves history. Delete removes private
   records. Download a history export and verify the final completeness marker.
6. Separately opt in to email with the saved schedule. Test immediate/digest,
   Zurich DST transitions and overnight quiet hours. Turn email off; pause and
   resume without consent; revoke membership/source access before sending. An
   uncertain SMTP acceptance is visible and never automatically resent. Actual
   registration/Pollen delivery and recipient approval need independent evidence;
   no real email was sent by isolated feature tests.
7. Use another owner and workspace, a viewer, revoked membership and a restored
   browser page. No private monitor, history, export, artifact or job may leak.
   Verify five-language keyboard/mobile and screen-reader operation, not just axe.
8. Rehearse candidate migration, restart, database backup/restore and rollback
   with isolated resources. Record actual release SHA and user-visible behavior;
   a push or successful build is insufficient.

## Remaining acceptance evidence

Retain permitted official birch and grass forecasts; the September ragweed proof
does not substitute. Complete operational FSDI/CSCS usage, lifecycle/freshness,
period-specific category and retention/export review. Independently review the
five translations, screen-reader journey and scoped CORE-20/C5 criteria with real
users. Measure the declared pilot workload and limits. Record recipient-approved
live email and actual deployment/rollback identity. No invitation, paid source,
new credential or production policy activation is implicit in this document.

## Pilot protocol and decision record

Decision: **HOLD — not yet ready to invite real users.** Engineering publication
with rollout/source gates closed does not change this decision. Assign a named
pilot owner and support contact before admission; neither is assigned here.
Recruitment/messages require explicit authorization and have not been performed.

After source and release gates pass, recruit at least five consenting representative
participants. Record aliases, not personal data, in the repository. Cover all five
UI languages with independent fluent reviewers; include screen-reader, keyboard-only
and mobile touch journeys. Record reviewer identity/role, locale, browser/device,
UTC date and exact public release SHA.

Observe the functional walkthrough without coaching. Record completion, time,
assistance, errors and the participant's explanation of: monitored station,
measured versus forecast value, why a change appeared, what source failure means,
and how to stop email. Exercise all four review decisions, later reopening, two
identical monitors, pause/edit/resume, export and deletion. A duplicate signal must
appear once in Today and yield at most one email per owner. Another owner's review
must remain independent.

Record support issues with severity, reproduction, expected/actual behavior and
SHA. Privacy/consent failures, false zero/resolution claims, unexplained measured/
forecast confusion, duplicate delivery or blocked core journeys keep HOLD. Retain
failed attempts as well as successes. Rerun affected steps after fixes. Independent
reviewers must sign off CORE-20/C5 scope before READY; this protocol does not claim
those outcomes or replace any stronger backlog criterion.

Declare pilot workspace/user/monitor/channel counts and cadence before measuring.
Capture queue age, source freshness/failures, decoder duration, CPU/RAM, API latency,
notification outcomes and recovery time during normal refresh, outage and recovery.
Compare with backlog budgets; do not extrapolate a small synthetic rehearsal to
an unmeasured workload.

For the first authorized live email, retain consent action, recipient approval,
provider outcome and observed receipt/unsubscribe. Never automatically retry an
uncertain SMTP outcome. Capture controller candidate/activated SHA, health and
rollback, independently comparing public readiness and visible Pollen behavior.
Rollout removal preserves private history. Source decisions retain their review
hash, scope and validity interval. No production policy is approved by this packet.
