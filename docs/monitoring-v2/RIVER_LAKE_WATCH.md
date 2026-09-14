# River / Lake Watch — C6 v1

## Active complete feature: consented River digest — 14 September 2026

MV2-033 with scoped MV2-012/022 delivery completes the Digest reuse in §13.8.
Implement private verified-owner consent, immediate/daily mode, IANA timezone,
quiet hours and a saved-settings preview, followed by bounded durable delivery
through the existing job/SMTP service. No automatic opt-in follows section or
monitor activation. All nine sections remain visible and enabled.

Eligible changes must be new after consent, unread, in the active configuration
and latest for their development. Recheck source freshness, station/metric/rule,
current condition, recipient binding, ownership and consent immediately before
SMTP. Recovery must not send obsolete historical alerts; corrected or superseded
data cannot use an old preview. Email links to the exact private change without
copying measurements. Review, pause/archive, deletion and opt-out suppress work;
uncertain SMTP outcomes never automatically retry.

Acceptance: real HTTP→numeric projection→durable job→fake SMTP, tenant/role/CSRF/
CAS and source/consent/review races, duplicate suppression, daily/quiet/DST,
configuration/measurement preservation through migration, five-language controls,
exact change reader and mobile/browser redaction, root build and exact API lint.
Existing FOEN access is the documented public channel; do not create source keys,
change production consent or infer unsupported station coverage. Human pilot and
source operational acceptance and broader shared parents remain open.

MV2-036 was inspected first but remains PLANNED: a reviewed source-bound geographic
mapping for road TMC references is missing. Complete this mandatory C6 digest
before adopting the cross-source intelligence opportunity from §13.7.


MV2-032/033 deliver private station monitoring through **Monitoring → River / Lake Watch**
(`/river-watch`) on the active main site, helveticlens.ch. The same authenticated account and
workspace boundaries apply. An administrator creates their own monitor; viewers can
read monitors they already own. Other administrators cannot read those private records.

## Complete user journey

Search the official catalogue by station, waterbody or identifier. No location permission
is required. Select water level, discharge and/or temperature, optional official station
danger, and absolute or rise-window thresholds. Preview actual coverage, source time and
validation, save the draft, then explicitly start it. Pausing permits a new configuration
revision; resume, archive and confirmed deletion are available. Configuration changes
invalidate the preview and never silently activate monitoring.

Changes appear in the private web reader with a stable development identity, priority,
source evidence and review decision. A later escalation or downgrade is a new reviewable
version of that development. Measurement history, change history and settings history
are separate paginated views. The owner can additionally opt into immediate or daily
email with quiet hours and an IANA timezone, inspect a saved-settings preview and opt
out again. No section activation implies consent. Broader shared delivery and human
pilot tasks remain open.

## Consented digest acceptance — 14 September 2026

The complete C6 email feature implements the scope above. A private exact-change
reader retains the original evidence, flags newer developments and never marks a
change reviewed merely by opening its email link. Known access denial and browser
page restoration clear private content before a fresh authenticated read.

Freshness and numeric conditions are checked again immediately before SMTP. A
same-clock correction to the current measurement or a rise-window baseline creates
a new development version when the result changes; original evidence remains intact.
An obsolete version cannot send. Paused/archived/deleted monitors, reviewed changes,
revoked membership, opt-out and changed/unverified recipients suppress pending work.
The saved preview never sends mail. Ambiguous delivery is retained for inspection
and never automatically retried. Migration `1af7d89139bc` adds consent/delivery tables
and the email revision; its round trip preserves existing measurements and changes.

Verified locally: **89 passed** across River source/runtime/delivery, Air and IP
delivery regressions plus backlog integrity; **40 passed** in the final River
delivery/Monitoring Centre run, including the added rise-baseline correction test.
These runs overlap and are not a unique-test total. The real HTTP-to-durable-worker
flow used fake SMTP and sent no real email. Daily/quiet-hour/DST, tenant/CSRF/CAS,
final-send races and migration preservation passed. The complete browser journey
passed **eight full-document axe checkpoints with no violations**, including five
locales, mobile/viewer controls, consent/preview/opt-out, exact links and access
redaction. Root production build, changed frontend formatting and exact API lint
passed. Production activation, native-language review and human/source operational
acceptance remain unverified; MV2-033 remains VERIFYING.

## Official source contract and rights

- **FOEN hydrological observations:** [dataset and schema](https://data.bafu.admin.ch/dataproduct-water-observations),
  [API](https://data.bafu.admin.ch/), [licence](https://data.bafu.admin.ch/lizenz-und-quelle).
  The published licence permits commercial and non-commercial reuse with author, title
  and dataset link. These are retained in the reader and sample evidence. Live values
  carry release status 0 and are provisional. The documented live recovery window is
  12 hours, with approximately 9–19 minutes publication delay. Timestamp, station and
  units are checked; missing validation is never promoted to validated data.
- **FOEN LINDAS station danger:** [official distribution description](https://www.bafu.admin.ch/de/aktuelle-hydrologische-daten-beziehen)
  identifies discharge, level, temperature and flood danger as published LINDAS data
  updated every ten minutes. [Published usage terms](https://www.bafu.admin.ch/dam/de/sd-web/5NAitqNKub6m/allgemeine_bedingungenfuerdasherunterladenaktuellerhydrologische.pdf)
  permit commercial and non-commercial use and specify downloading no more frequently
  than ten minutes. The application uses the public endpoint, never a private account.
  Only the explicit `dangerLevel` field is used. It is the official station state, not
  a regional forecast or an application-derived interpretation of water level.
- Fixed public endpoints, bounded response bodies, no redirects or user URLs, no source
  credentials. A shared database lease permits one fetch per channel per ten minutes;
  the catalogue refreshes daily. Failures retain evidence and back off to six hours.
  [FOEN rate limits](https://data.bafu.admin.ch/rate-limits) allow 500 requests per five
  minutes per client IP and reject queries above 10,000 rows. One station query remains
  below 1,000 rows per field; catalogue/danger responses at the limit fail closed.

## Verified source behavior, 12 September 2026

A bounded public probe at **11:46:41 UTC** returned **243 supported live-range stations**.
Station **2289, Rhein — Basel, Rheinhalle**, supplied live W and Q at **11:30 UTC**:
244.866 m above sea level and 403.426 m³/s, both provisional. LINDAS independently
published danger level 1 at the same source time. Water temperature was absent and is
shown as UNKNOWN, not zero. These values are dated verification evidence, not defaults.

The probe also established that aggregate values lagged by almost three hours. The
connector therefore uses `data_live` for rules. `data_10min_mean` supplies native unit
metadata for the same station only; aggregate values never become live rule inputs.
The catalogue API rejected string range filters, so the implementation reads the bounded
active catalogue and validates the documented four-digit live range locally.

Retained normalized probe evidence is in [the source evidence JSON](evidence/mv2-032-source-proof.json).
Source response SHA-256 values identify the exact inputs. This was an independent scratch
database; it created no user monitors and changed no production state.

## Numeric and operational semantics

Water level is station elevation in `m ü.M.`, bound to that station's reference; it is
not water depth. Discharge uses m³/s and temperature °C. Unknown units fail closed.
Absolute rules use strictly greater-than. Rise rules compare exact window endpoints
in the same metric, station, unit, reference and method; water-level rises may use cm.
Windows are 10–1,440 minutes in multiples of ten. Missing endpoints or a gap exceeding
the source's five-to-ten-minute cadence returns UNKNOWN; nothing is interpolated.
Longer windows become available only after enough compatible live history accumulates.

Official danger escalation receives priority 1 independently of custom threshold events
(priority 2). Repeated identical states create no duplicate changes. Downgrades and
threshold reversals retain the development identity. New monitors establish a current
baseline; subsequent recovery evaluates unseen source times in order. A gap beyond
live recovery remains visible, and current danger history starts from retained snapshots.

Durable outbox jobs recheck membership, ownership, active state and configuration version
after network I/O. A pause, revocation, edit or deletion prevents stale work from writing
private events. `RIVER_WATCH_ENABLED=false` disables the reader and new/effective runs.
Source data stays public and independent of private monitor deletion. Measurement views
cover 30 days; cleanup runs during collection and daily even without active monitors.
Private revisions/decisions remain until their owner deletes the monitor.

## Acceptance evidence

| Acceptance | Evidence |
|---|---|
| AC-C6-01 station/waterbody selection | Official catalogue, manual search, HTTP/browser creation flow |
| AC-C6-02 official measurement storage | Real FOEN probe and normalized durable source rows |
| AC-C6-03 previous-state comparison | Deterministic ordered evaluation with a persisted watermark |
| AC-C6-04 threshold change | Absolute crossing and rise-window tests |
| AC-C6-05 official escalation priority | Independent danger field and priority override tests |
| AC-C6-06 no duplicate alerts | Repeated refresh and recovered crossing/reversal tests |
| AC-C6-07 custom threshold | Unit/window validation and editable revisioned form |
| AC-C6-08 source timestamp | Preview, current state and both histories retain source time |
| AC-C6-09 downgrade same development | Stable development identity and renewed review tests |
| AC-C6-10 historical access | Separate private changes/settings and public measurement pagination |

The focused suite currently passes **24 tests**, including actual durable worker dispatch,
cross-user job/history denial, CSRF, source attacks, retention and pause-during-fetch.
Affected auth/release/backlog regression: **135 passed**. Pollen, shared runtime/jobs and
organization regression: **271 passed**. The normal frontend build and structural checks
pass. The browser journey passed seven full-document axe checkpoints across five locales, mobile layout and viewer restrictions, including save/start/review/history/pause/edit/resume/archive. Exact public release identity remains pending;
these tasks remain VERIFYING until release evidence is available. Native-language review
and broader pilot acceptance are not claimed by automated locale/accessibility checks.

Migration `c395ad04e76b` adds only five River tables after `b2849cd3f65a`. It changes no
existing Pollen, legal, account or organization tables. The existing Pollen feature,
private Basel configuration and consent are preserved.

The repository-wide format check still reports 184 existing checkout warnings (83 baseline formatting issues and 101 line-ending differences), including legacy i18n and global CSS. This feature does not reformat the whole application. New River files and the touched navigation/help components pass their formatting checks; functional build, type, localization and accessibility gates pass.
