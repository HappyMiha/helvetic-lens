# River / Lake Watch — C6 v1

MV2-032/033 deliver private station monitoring through **Monitoring → River / Lake Watch**
(`/river-watch`) on both application instances. The same authenticated account and
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
are separate paginated views. This C6 slice delivers in the web reader; it does not enable
email or infer consent. Broader shared delivery and human pilot tasks remain open.

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
