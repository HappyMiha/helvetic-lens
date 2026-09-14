# Hazard Watch — C1 complete-feature contract

**Integrated publication, 13 September 2026:** The owner requested all implemented code be published to main now and all implemented sections enabled. The production defaults and remaining source/acceptance limits are recorded in the [integrated release evidence](evidence/2026-09-13-integrated-publication.md). Earlier dated references to uncommitted or disabled work are historical; the broader task remains IN PROGRESS.


Status: IN PROGRESS, 13 September 2026. Scope: MV2-028/029. Implement official
warnings for private named Swiss locations, material history, exact comparisons,
review/reopening, Today/Inbox and explicitly consented delivery. C4 remains
deferred. A protocol implementation does not establish an operational source.

## Source decision

### Native MeteoAlarm feature selected, 14 September 2026

Scope: complete MV2-028/029 weather-warning acquisition and its existing private
workflow, not a standalone Atom parser. Existing CAP journal, private locations,
boundary catalogue, lifecycle, Today/Inbox and consented delivery are dependencies.
Keep all nine sections visible; this channel does not cover civil protection or
power outages. The broader C1 acceptance remains open.

The official [redistribution hub](https://meteoalarm.org/en/live/page/redistribution-hub)
links the public Switzerland Atom feed and describes it as an active-warning
summary. Full warnings are linked CAP resources. Cancel messages are omitted;
their referenced entries disappear. An absent entry must therefore cease being
presented as current without inventing an official cancellation or all-clear.
Initial Updates can lack their earlier publication; missing history must be
identified rather than fabricated. Failed or partial polls must not remove data.

The [current terms](https://meteoalarm.org/en/live/page/terms-and-conditions),
retrieved from the site's public CMS content endpoint on 14 September, permit
Information reuse under CC BY 4.0-equivalent terms with additional conditions:
preserve the unmodified information alongside any transformation, attribute the
Swiss participant, retain issue time, link MeteoAlarm, publish the required delay
disclaimer and maintain operational latency averaging under five minutes and
never exceeding ten minutes. The feed's rights statement explicitly references
these extra conditions. This does not grant a general licence to unrelated site
Content or prove access to the separately restricted EDR/MQTT API.

Acceptance for this complete feature:

1. Bounded shared Swiss Atom and linked CAP acquisition, verified issuer/identity,
   immutable originals, retries/rate limits and no private coordinates on the wire.
2. Atomic complete snapshots, explicit withdrawn/expired/unavailable states,
   exact known predecessor comparisons and clearly unavailable earlier history.
3. Provider-supported weather types and geometry only; no inferred Swiss power,
   civil-protection or other unverified coverage. Start/resume checks actual scope.
4. Existing private events, review/mute, Today/Inbox and opted-in email recheck
   current membership, source snapshot, validity and consent at consumption.
5. Five-language source/status/reader UI, original instructions and source issue
   time, attribution/link/disclaimer, including mobile and unavailable states.
6. Required API lint, affected acquisition/journal/private/delivery tests, frontend
   build/browser checks and public source probe. Publish only the whole feature.
7. Exact production activation and live/human acceptance remain separate evidence.

Discovery evidence: Switzerland Atom returned HTTP 200 with zero entries and
feed update `2026-09-14T08:05:09.601543Z`. An Austrian Atom/CAP example was used
only to inspect the actual transport shape, not to assert Swiss warning coverage.
It included an already-expired warning, confirming that a successful feed request
alone cannot establish warning validity. No production source permission or
private monitor has been changed by this investigation.

Native transport work in progress: `hazard_meteoalarm.py` fetches a bounded shared
Swiss Atom snapshot and deduplicated linked originals without forwarding client
cookies/authentication or accepting arbitrary download URLs. Unsupported feed
structure, wrong issuer/identity, partial failures, redirects and oversized XML
cannot become a successful empty snapshot. Source Retry-After is preserved.
The live route needed standard Accept negotiation fallback (Atom-only returned
406); successful responses still undergo strict MIME and XML validation.
The native probe completed at `2026-09-14T08:49:18Z`, with no current originals
and feed update `2026-09-14T08:35:26.960468Z`. This verifies the empty transport
path only. The 29 synthetic transport tests plus backlog invariant passed
(30 checks, 0.24 seconds), and required API Ruff passed.

Further local implementation, 14 September: the native profile retains original
HTTP source links and translated impact parameters. Atomic complete snapshots
preserve immutable CAP originals, explicitly record missing earlier history,
and track source presence independently of official cancellation/all-clear.
Partial or conflicting batches cannot advance freshness. A durable source lease
enforces the shared polling budget, provider backoff, and in-flight permission,
configuration and lease rechecks. The scheduled collector is wired to Celery.
The private reader exposes native attribution, issue time, link/disclaimer,
incomplete history and precise stale/withdrawn explanations in five languages.

Synthetic verification: journal/profile/source checks passed 128 tests; the
later collector and migration/source checks passed 46 tests in 15.28s. Private
workflow/lifecycle/delivery initially passed 51 checks with one incorrect new
test expectation: stale source status is `unavailable`, whereas a withdrawn
individual warning yields `no_eligible_changes`. Corrected native workflow and
journal/history guards passed 19 tests in 11.61s. The paths include saved-place
start, Today/Inbox, exact reader/review, material updates and consented fake SMTP;
withdrawn/stale originals cannot send or appear as current. No real user mail
or source permission was created. The isolated `hazard-native` root web build
passed after moving the source brand label into the common locale dictionary.
The expanded browser suite passed 59 checks, including all five mobile locales,
native HTTP originals, escaped impact prose, attribution/disclaimer, missing
history and withdrawn/stale current views. Seven axe audits had no violations;
the shared Marvin contrast checks remain incomplete. The new mobile screenshot
was inspected; the disposable fixture and Chrome exited normally. Generated
Next type/config changes were inspected and restored. Final API Ruff, whitespace
and the active-backlog invariant passed (one backlog check in 0.18s).

### Native source activation and complete vertical workflow, 14 September 2026

The normal enabled Celery collector now initializes the reviewed public Swiss
MeteoAlarm contract when no earlier Hazard permission exists and no explicit
permission is configured. It never replaces an explicit source or re-creates,
renews or reactivates an existing/revoked/deselected permission. GET capabilities
and administration diagnostics remain read-only. The initial source review is
valid until 1 January 2027; renewal is an explicit reviewed operation.

MeteoSwiss [describes its weather warning types](https://www.meteoswiss.admin.ch/weather/hazards/how-severe-weather-warnings-are-prepared.html)
and [national remit](https://www.meteoswiss.admin.ch/about-us/legal-mandate.html).
Together with the MeteoAlarm provider directory and Swiss channel, these support
native **wind/thunderstorm** monitoring for verified Swiss places. Only `storm`
has a default jurisdiction record. Other C1 choices remain visible but do not
inherit this coverage. Snow/ice, flooding, forest fire, power outages and civil
protection require their own confirmed source/type coverage. Blowing-snow and
blizzard codes cannot be relabelled as snowfall. A native Snow code can be
recognized without granting snow coverage or activating a monitor.

Reviewed source evidence identifiers (SHA-256 of downloaded public CMS JSON):

- Terms: `7b317929f32b5f7903b574e6c54be822bfe0e30677b3f6155a55d522cc87957c`.
- Redistribution hub: `b84a5d1a50cd2c7824deb46c45e45d1b0b7a6ff66d72a20c75dddf55cf32af4e`.
- Warning providers: `2486a23cf78007848d5aef477d3833a4b353fe756656f404cf8c76403fdd8b04`.

The same worker prepares the pinned January 2026 swisstopo catalogue in the
shared configured data volume. The downloader is bounded, credential-free and
hash-checked; it supports the publisher's observed `application/x.geopackage+zip`
MIME. The installer atomically requires a new catalogue directory. Existing,
revoked, corrupt, expired or interrupted installations are left for the operator,
including a competing installation created during download/decoding. It cannot
silently restore removed geography. The edition review expires 1 January 2027.

Capabilities now report actual completed-source freshness and confirmed types;
the page refreshes that status every minute without starting private monitors.
Source administration reports actual native successes, backoff and failures.
Native consented link emails retain issue time, attribution, MeteoAlarm link and
delay disclaimer. They do not export the original instructions or coordinates.

Final candidate evidence:

- All Hazard modules plus source operations: **360 tests passed in 159.05s**,
  `.tmp/hazard-all.log`. The final snow-code and native diagnostic guards passed
  **34 tests in 10.90s**, `.tmp/hazard-last-guards.log`. Earlier native default,
  geometry, acquisition, lifecycle and delivery checks passed 72 tests in 47.84s.
- The complete isolated `hazard-native-final` root build passed. The expanded
  browser suite passed **60 checks** with seven axe audits reporting zero
  violations; shared Marvin contrast remained incomplete. The mobile image was
  inspected, generated Next files restored, and disposable processes closed.
- A real, isolated first installation validated the official archive checksum,
  loaded **26 cantons / 2,110 municipalities**, and verified Basel municipality
  `2701`. Its GeoPackage hash equals the pinned official edition above.
- At **2026-09-14T09:47:53.945445Z**, a fresh local database initialized the
  reviewed native permission, collected the real Swiss feed, atomically recorded
  its empty complete snapshot and passed the actual Basel storm readiness gate
  against the native geography. Poll evidence SHA-256:
  `033473afd6578399d09105318b48b689a98efd53365f9be79d6d649519425d72`.
  No private monitor, production data, real email or source account was changed.

This completes the native wind/thunderstorm acquisition-through-private-workflow
implementation for publication. It does not complete broader C1: a nonempty
real Swiss CAP event, production activation/operation, additional hazard coverage
and human acceptance are still unverified. MV2-028/029 remain IN PROGRESS.

The [FOCP Polyalert page](https://www.babs.admin.ch/en/polyalert-en) describes
third-party CAP Suisse dissemination as a planned integration by 2027. It links
the [CAP Suisse 1.1 specification](https://www.babs.admin.ch/dam/de/sd-web/H6vSh6NHF65G/Spezifikation%20CAP%20Suisse%201-1.pdf),
dated June 2026. This is enough to implement a bounded, synthetic protocol
contract, but does not prove an available public endpoint, current issuer
coverage, permitted polling or service continuity.

[Alertswiss terms](https://www.alert.swiss/en/home/meta/legal-issues.html) describe
restricted reproduction and noncommercial sharing. Do not treat public website
access as an unrestricted commercial feed grant. No website scraping, account,
application, email, source activation or redistribution is authorized by this
discovery. A source-specific reviewed agreement/channel is still required.

The protocol distinguishes cancellation from all-clear: Cancel removes explicitly
referenced messages; an all-clear uses an Update with Minor severity and AllClear
response. Expiry or a missing message cannot prove safety. References identify
sender, identifier and sent time, and only explicitly named messages are replaced.
Language-only updates and formatting do not create duplicate private alerts.

## Implementation boundary

1. Decode bounded CAP 1.2 / supported CAP Suisse 1.1 fields without fetching
   resources or executing XML entities. Preserve official text, language, severity,
   certainty, instructions, timing and evidence hashes. Reject non-public or
   exercise/test traffic and ambiguous identifiers. Protocol validity is separate
   from trusted issuer/transport verification and use rights.
2. Match permitted geography locally. Coordinate order is latitude/longitude;
   polygons include boundary points and must be closed and simple. Unresolved
   geocodes, altitude restrictions and unsupported geometry remain unknown.
   Never send private Home/Office coordinates to a shared warning collector.
3. Persist current evidence, explicit predecessor references and material history
   transactionally under source permission and retention limits. Geography,
   instructions, severity, effective periods and all-clear changes are material;
   technical refreshes must not reopen review or produce repeat delivery.
4. Provide owner/tenant-scoped location configurations with preview, explicit
   start/pause/resume/archive, CAS and idempotency. Source coverage must explicitly
   identify supported hazards, authorities and geography. Missing power outage or
   cantonal coverage must be visible rather than reported as no hazard.
5. Complete five-language reader, exact previous/current comparison, evidence,
   review/not-relevant/mute-type actions, Today/Inbox and opted-in email. Critical
   official instructions remain visible without AI and are never rewritten by it.
6. Verify AC-C1-01 through AC-C1-10, adversarial/privacy behavior, affected quality
   checks, browser accessibility and separately permitted live/pilot acceptance.
   Commit and immediately push the complete tested feature on main.

## Current external gate

The Alertswiss/CAP Suisse channel still has no verified operational endpoint or
source agreement. The MeteoAlarm weather channel located on 14 September is a
separate source with the scope and conditions above. A real Swiss CAP fixture,
actual provider geometry/type coverage, native journal/private integration and
live acceptance remain open. Feed disappearance cannot provide the missing
official cancellation/all-clear message. CAP Suisse remains a future-compatible
contract, not a claim that Alertswiss already serves it.

## Local protocol, geography and history implementation

`hazard_cap.py` now provides a bounded offline decoder. It checks namespaces,
cardinality, numeric-offset dates, immutable sender/identifier/sent references,
public actual messages, XML size/depth/node limits and supported links. Entity
declarations and unsupported encodings are rejected. Attachments are not fetched;
unprocessed resources, teasers, unknown structures and distinct information
segments remain explicit unsupported states. Source text is retained verbatim;
renderers must treat it as plain text. No signature, issuer or use right is inferred.

`hazard_geometry.py` implements local Swiss-region point containment with included
boundaries, simple closed polygons and kilometre circles. Reversed axes, invalid
rings, unsupported regions, missing geography, unresolved geocodes and vertical
restrictions cannot become definitive outside/no-hazard results. The regional
box is an algorithm bound, not proof of Swiss administrative membership. The
radius matcher and native administrative catalogue added below extend this
initial point-only implementation. Municipal warning-area expansion and runtime
catalogue publication remain unfinished. Ring orientation/start-point and polygon
order do not create changes.

`hazard_reconciliation.py` provides a pure bounded predecessor ledger, not a
deployed collector or database. Current-head replacement requires an exact known
reference; late sibling updates, ancestor cancellations, unverified cross-history
merges and conflicting identity reuse leave the prior state intact. Immutable
messages and latest receipt times are separate. Referenced technical/translation
additions retain evidence without incrementing the material review sequence;
changed instructions override provider minor-update hints. Severity, geometry,
validity and explicit all-clear transitions create material revisions. Cancellation
closes the notice without claiming safety; expiry and feed absence do not resolve
it. Storage is bounded to 2000 messages / 16 MiB per source ledger. Future durable
storage must apply reviewed rights/retention and atomic publication around it.

The first CAP/geometry/backlog check passed 52 tests in 0.45s; the expanded history
suite passed 62 tests in 0.55s (`.tmp/hazard-history.log`). Required API Ruff passed.
The final suite passed **63 tests in 0.54s** (`.tmp/hazard-final.log`), including
repeated-language geometry limits, teaser rejection and superseded-message replay.
Required API Ruff and `git diff --check` passed. A bounded follow-up search of
official MeteoSwiss/OGD warning documentation did not establish another current
permitted warning feed; local forecast datasets are not official hazard messages.
All fixtures are synthetic; these tests do not complete AC-C1-01…10. Durable
source acquisition, private location storage/API/UI, reviews, delivery and live
acceptance remain open. No production setting, source or user monitor changed.

## Private location drafts and reader, 13 September 2026

The owner-private draft workflow is now implemented across storage, HTTP and the
five-language `/hazard-watch` reader. A place has a private name, canton, either
coordinates/radius or an official municipality number, selected hazard types and
minimum importance. These remain declarations until a reviewed geographic
catalogue verifies them. The API cannot accept client-supplied owner, source
approval, geometry verification or email consent. Saving/preview does not start
collection, create jobs or send mail.

Migration `f824a6f3d6fa`, after `e71395e2c5e9`, adds `hazard_monitors` and
`hazard_configuration_revisions`, registered for tenant session scoping. Owner
and current membership checks apply to reads, history, cursors and writes.
Creation is idempotent; edits use CAS and immutable revisions with 100-place /
1000-revision bounds. Caller rollback includes nested savepoints. Archive is
required before version-checked deletion, which cascades private configuration
history. Cross-tenant revision links are rejected by a composite foreign key.

The HTTP routes support capabilities, preview, paged inventory/history, create,
read, edit, archive and delete. Existing authentication/CSRF, grouped rate limits
and no-store responses also cover denials. `HAZARD_WATCH_ENABLED` defaults to false
in settings and both deployment examples/compose; no actual environment changed.
Monitoring Centre includes an honestly gated warning-draft choice and private
inventory links, without exporting coordinates or implying recent source checks.
The total remains nine active choices.

The UI supports both location forms, hazard selection, minimum importance,
preview, save, edit, prior settings, archive and explicit delete confirmation.
Account/workspace/role/visibility changes remount private state and abort pending
requests. Access failures clear the mounted private view. The contextual guide
explains which actions save local settings and why monitoring is not running.
The final breadcrumb names Hazard Watch instead of the default Overview.

Initial repository/protocol/migration verification passed 85 tests with three
new test-fixture errors (wrong DomainError attribute and database context method).
After correcting those fixtures, all **36** private HTTP/repository/authentication/
migration/compose/backlog checks passed in **18.69s** (`.tmp/hazard-http.log`). The
combined new hazard, Monitoring Centre and Road API suite passed **26 tests in
60.00s** (`.tmp/hazard-centre.log`). Required API Ruff passed. The root web build
passed (`.tmp/hazard-private-build.log`) after correcting one JSX unknown-value
condition found by TypeScript. The final breadcrumb-only root build also passed
(`.tmp/hazard-private-final-build.log`). Generated temporary Next type paths were
restored after the builds completed. Browser screenshots preceded this final
breadcrumb-only change; no broader live or human acceptance is claimed.

A disposable fixture served the built product UI with synthetic accounts and
places. A fresh isolated headless Chrome profile verified preview/save of a point,
editing to a municipality, both private revisions, archive, cancel then confirm
deletion, membership denial during a mutation clearing private content, and viewer
read-only controls. All five locale forms fit 390px without horizontal overflow.
Desktop-history and mobile-form full-document axe audits both had zero violations;
the shared Marvin contrast check remained incomplete. Screenshots were inspected.
Local evidence: `test-results/accessibility/hazard-browser-checks.json`,
`hazard-manual.json`, `hazard-desktop-history.png`, `hazard-mobile-form.png`, and
`.tmp/hazard-browser-requests.json`. The fixture/browser completed and closed
cleanly; no real account, location, source or email was used.

This closes the local draft workflow, not the full C1 feature. Native source
acquisition and rights, reviewed municipality/Swiss-border/radius matching,
durable official warning evidence, active lifecycle/review/mute/Today/Inbox,
consented delivery, live release and human acceptance remain unfinished. Existing
CAP/geography/history fixtures do not prove an actual current feed or all C1 AC.

## Native administrative catalogue and radius, 13 September 2026

`match_radius` now intersects a saved 0–50 km spherical radius with supported CAP
circles and polygons. It detects intersections with edge interiors even when all
vertices and the saved centre lie outside. Bounded subdivision uses spherical
distance and a conservative arc-length lower bound along the original linear
latitude/longitude edge; numerical/work-limit uncertainty returns unavailable.
Zero radius preserves point matching. Unresolved geocodes/vertical restrictions
remain unknown, and a known positive member can prove a union intersection.
The combined radius/CAP/history check passed 74 tests in 0.42s.

The [swisstopo product](https://www.swisstopo.admin.ch/en/landscape-model-swissboundaries3d)
supplies separate national, cantonal and administrative-unit layers in LV95.
Its [OGD terms](https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices)
allow use/processing/commercial reuse with attribution. This is a geometry-data
permission, not a warning-feed grant. The public STAC v1 collection returned the
latest edition `swissboundaries3d_2026-01` with no next page on 13 September.
The [official January 2026 asset](https://data.geo.admin.ch/ch.swisstopo.swissboundaries3d/swissboundaries3d_2026-01/swissboundaries3d_2026-01_2056_5728.gpkg.zip)
was downloaded once, without private coordinates or credentials:

- Archive: 37,361,779 bytes, SHA-256
  `68e922353c76fa5db3cef06a32f9711c0198faa6fbd2b5bcde9edc88b0f8999f`,
  matching the STAC SHA-256 multihash (prefix `1220`).
- Sole GeoPackage: 74,231,808 bytes, SHA-256
  `1f122cb7a06f2d312a84b7c0a91116348ba907054d487f0a70b9d2302984e6fc`.
- Attribution: **Federal Office of Topography swisstopo**.

`hazard_boundaries.py` reads exactly hash-checked bytes into a read-only in-memory
SQLite database, closes it explicitly and accepts only the expected native table,
CRS and geometry schema. File/row/geometry/SQL-work bounds apply. It retains
multipart geometry and holes, excludes foreign administrative units and Swiss
non-municipal surfaces from political municipality selection, and requires all
26 cantons plus a unique CH country geometry. It does not repair invalid source
outlines or flatten holes. The caller must supply an edition and explicit review
expiry; stale/unknown municipalities are not replaced by names or old codes.

Local WGS84→LV95 projection uses pyproj with explicit axis order, no ballpark
operation and no remote grid access. Unknown projection accuracy or locations
within the projection/dataset accuracy margin of a border return unavailable.
Shapely/GEOS retains the native topology. A verified centre or municipality does
not prove the configured radius is wholly inside Switzerland or covered by an
official warning source; `radius_coverage_verified` remains false.

`scripts/check-hazard-boundaries.py` provides an explicit offline native check.
Seven probes passed against the checksum-verified file: Basel 2701, Bern 351,
Moutier 6831/JU; Saint-Louis, Vaduz and Busingen outside CH; former Moutier 700
unavailable. It verified 2,110 Swiss political municipalities and 26 cantons.
Evidence is `.tmp/hazard-boundaries-native.json`; the large source files stay
ignored and are not bundled in Git. The check's one-day expiry is a local test
scope, not an approved runtime refresh policy.

The combined catalogue/radius/CAP/history/private-repository suite passed
**107 tests in 4.80s** (`.tmp/hazard-boundaries.log`). Exact required API Ruff and
the native-check script lint passed. This is real administrative-data evidence,
not live warning coverage. Runtime catalogue installation/renewal, municipality
warning intersections, source evidence/lifecycle, review/delivery and the full
user-facing C1 feature remain unfinished and unpublished.

After the dependency update, the private hazard HTTP checks and required backlog
invariant also passed: **5 tests in 14.26s** (`.tmp/hazard-geography-http.log`).
All checks from this geography iteration are terminal. No frontend changed in
this iteration, so the preceding UI/browser evidence remains scoped as recorded.

## Runtime catalogue and private preview, 13 September 2026

The API now resolves private preview locations through `BoundaryStore` under
`<data_dir>/hazard-boundaries`. The operator selection is `current.json`; immutable
objects are `objects/<unpacked-sha256>.gpkg`. HTTP callers cannot nominate paths,
upload geometry or submit proof/approval fields. Every check revalidates the
selection, review time, expiry and asset identity. Changed assets are hash-checked
before decoding. A selection changed during decoding is discarded; missing,
corrupt, revoked, expired or future selections clear the old cache and return
unavailable. Each API process retains at most one public catalogue, not private
location results. No stale-catalogue fallback or remote geocoding is performed.

The read-only preview returns source-attributed municipality/centre proof and
configuration-specific blocking reasons. Valid administrative membership removes
only the location-validation blocker. `hazard_source_not_configured` still blocks
start; a nonzero radius additionally retains an unverified-coverage blocker.
Preview does not create monitors, jobs or delivery, and existing owner/membership,
CSRF, no-store and validation-error redaction still apply.

The five-language reader now displays the matched municipality/code and boundary
edition/attribution, or explains an outside-CH point, canton mismatch, boundary
uncertainty, obsolete municipality or unavailable/expired catalogue. Editing the
form clears the previous proof. Start/source-coverage and email disclaimers remain
visible. This is the saved-location preview, not a claim that C1 is running.

### Explicit operator installation/renewal

`scripts/install-hazard-boundaries.py` is an offline operator tool, not an HTTP
endpoint. It requires the archive, target data directory, reviewed edition, expiry
and **64-character lowercase SHA-256** copied from the official STAC asset (remove
the multihash's `1220` prefix). It verifies bounded ZIP/native contents before any
selection publication. The archive's internal pathname is never extracted.
Existing objects are verified instead of overwritten. A per-directory exclusive
installer lock and an expected-current-selection SHA-256 prevent concurrent or
unreviewed replacement. The new selection is fsynced and atomically published;
objects from earlier editions remain retained.

```powershell
services/api/.venv/Scripts/python.exe -B scripts/install-hazard-boundaries.py <reviewed-archive.zip> --data-dir <explicit-data-directory> --archive-sha256 <official-archive-sha256> --version 2026-01 --expires-on <reviewed-YYYY-MM-DD>
```

An initial install requires no existing `current.json`. For renewal/replacement,
also supply `--expected-selection-sha256` with the exact current file's SHA-256.
Changing only the expiry still requires explicit review and the selection guard.
Withdrawing `current.json` revokes subsequent preview use, without deleting the
retained asset. A lock left by an interrupted installer requires inspection of
that process; it is never automatically treated as stale. This tool does not
enable Hazard Watch, warning-source collection, user monitors or emails.

### Verification and remaining scope

The installation/renewal/revocation/hash/selection-race/private-HTTP/repository
suite passed **50 tests in 14.38s** (`.tmp/hazard-store.log`). Required API Ruff and
installer-script Ruff passed. The root web build passed in the isolated
`hazard-location` output (`.tmp/hazard-location-build.log`); generated temporary
Next type references were restored after completion.

The real official January 2026 archive was installed only into the new ignored
`.tmp/hazard-native-preview` QA data directory with expiry 14 September. The
runtime reader confirmed public Basel coordinates as municipality 2701 and
retained `radius_coverage_verified=false`. Evidence:
`.tmp/hazard-native-install.json`, `.tmp/hazard-native-runtime-proof.json`.
No production data directory, environment or selector was changed.

Isolated headless Chrome verified the confirmed/canton-mismatch/outside/expired/
missing-catalogue states, stale proof clearing on edit, the existing private draft
workflow and all five locale previews at 390px. Desktop-history and mobile-preview
full-document axe audits both had zero violations; shared Marvin contrast remained
incomplete. An initial screenshot showed only the upper form, so the completed
fixture was rerun with targeted preview scrolling; both final desktop-preview and
mobile-preview images were visually inspected. All browser/fixture processes
terminated normally. Evidence: `.tmp/hazard-location-browser-visual.log`,
`test-results/accessibility/hazard-desktop-preview.png`, `hazard-mobile-form.png`,
`hazard-browser-checks.json`, `hazard-manual.json`. All data/identity/source replies
in this browser fixture were synthetic, separately from the native-data check.

Municipality/CAP geocode intersections, coverage of a complete saved radius,
durable official evidence and source rights, active warning history/review/mute,
Today/Inbox, consented delivery and actual live/pilot acceptance remain open.
The full C1 feature is still unpublished and IN PROGRESS.

## CAP municipality/canton matching, 13 September 2026

The CAP Suisse 1.1 specification, pages 29–32, says administrative geocodes can
name only partly affected municipalities/cantons and recommends them for filtering
or lists rather than drawing the affected outline. The new `hazard_matching.py`
therefore does **not** expand a supplied polygon to every address in a named
municipality/canton. It recognizes only the documented names `Swiss official
commune register`, `Cantonabbreviations` and `ISO 3166-1 alpha-2`; postcode aliases,
unknown warning-region schemes and obsolete municipality codes remain unresolved.
Administrative lookup requires the source adapter's explicitly bound catalogue
edition to equal the installed edition. A current catalogue alone does not prove
an old source code's meaning.

A point/radius uses explicit CAP polygons/circles when provided. A matching
administrative-only filter remains a candidate with unavailable precise extent,
not an exact house hit. A whole-municipality watch can match its own explicit BFS
code, retaining `administrative_filter` basis and no fabricated warning outline.
A canton/country-only match cannot confirm that a particular municipality is
affected. Negative filters and explicit geometry remain distinct; unresolved
warning-region codes cannot prove a negative. A known positive area still proves
the union despite another unknown member. Missing geography or airspace altitude
constraints never become outside/no-hazard results.

Municipality watches now also intersect explicit CAP polygons and kilometre
circles with native multipart administrative geometry, preserving interior holes.
The local projector densifies geographic segments (maximum 0.001-degree span and
5 cm midpoint refinement threshold); circle chords start with at most a 5 cm
spherical sagitta. Source geometry is not repaired. A 200,000 projected-point
budget and depth/shape/input bounds return unknown on exhaustion or invalid
projection. The joint dataset/projection accuracy margin treats touching or very
narrow overlaps as uncertain; robust interior overlap matches and separated areas
do not. Administrative-region filters retain native geometry for radius overlap,
so an outside centre does not incorrectly exclude a radius crossing that region.

`BoundaryStore.match_warning` supplies an internal worker entry point with the
same current-selection/expiry/revocation checks as preview. Results carry the
matched basis, boundary edition and hash. This performs no source permission,
category/severity interpretation, collection, evidence persistence or delivery;
those gates still precede any eventual private event. No public matching endpoint
or production/source activation was added.

The initial matcher/catalogue/radius suite passed 61 tests in 1.67s. After adding
the worker revocation check, the full affected matcher/catalogue/radius/CAP/history
suite passed **110 tests in 2.29s** (`.tmp/hazard-matching-final.log`). Required API
Ruff passed. The native checker initially had one import-order lint issue; after
sorting those imports, both operator-script Ruff checks passed as well.

The expanded offline native checker passed the original seven membership probes
plus seven **synthetic warning** scenarios against the checksum-verified real
January 2026 boundaries: named Basel municipality versus unconfirmed exact house,
polygon overlap, exact house inclusion, an outside polygon not enlarged by its
BS dissemination code, a small circle inside Basel and rejection of an unbound
historic code edition. Evidence: `.tmp/hazard-matching-native.json`. These are real
administrative data with synthetic warnings, not a live hazard-feed test. No UI
changed in this iteration; preceding browser evidence remains scoped above.

This closes local geometric matching for the supported subset. Durable source
rights/coverage/category contracts, official evidence and event lifecycle,
review/mute/Today/Inbox, consented delivery and live/pilot acceptance remain open.
The feature remains IN PROGRESS and unpublished.

## Durable CAP source journal, 13 September 2026

`hazard_source_models.py`, `hazard_sources.py` and migration `09b5c714e70b`
(after `f824a6f3d6fa`) now persist permitted public warning evidence independently
of tenant-private places. The five shared tables retain reviewed permission,
selected source generation/cursor, immutable message evidence, exact current
heads and idempotent acquisition receipts. There is no public permission-write
or raw-export route, network collector, real grant or production activation.

The strict reviewed contract binds source key, HTTPS endpoint, sender, grant
reference, attribution, validity, polling/freshness/retention limits, canton and
geocode edition declarations, exact event-code rules and reviewed severity
mapping. Storage, matching, display and notification uses are checked separately.
Only contracts permitting full normalized messages and minimal audit tombstones
are supported. An unknown category/severity is retained as incomplete, never
guessed from official prose. A source declaration does not prove current coverage:
every current-page result explicitly returns `coverage_verified: false`.

Acquisition locks permission before selection and requires both generation and
cursor CAS. Repeated request keys return the original receipt without extending
freshness or retention; a different payload conflicts. A new receipt for the same
immutable message updates last-seen time but preserves first receipt and original
bytes. Replaying an ancestor cannot restore its head. Exact predecessors, material
sequence, translation-only updates, explicit all-clear and Cancel survive session
and engine reload. Missing/late/sibling predecessors cannot partially advance the
cursor. Selecting another grant never copies its evidence; selecting an earlier
grant again requires a fresh receipt before any old head appears in current data.
The caller's rollback includes evidence, head and receipt changes.

Raw and normalized content have distinct immutable deadlines capped by grant
expiry. Zero raw retention or already elapsed raw TTL writes no raw bytes.
Revocation purges both payloads and classification immediately in the caller's
transaction; `purge_content` provides expiry maintenance, retaining only the
explicitly allowed minimal hashes, identities, references and state audit.
Reads recheck rights and deadlines even before physical cleanup. The eventual
collector still needs a scheduled maintenance call when there is no acquisition.
Expired identities cannot be silently rehydrated by the same publication ID.

Current reads distinguish stale receipt, expired CAP period and missing retained
content from resolved/cancelled state. Historic reads can show an unexpired,
permitted exact revision even when it is no longer current. A transport gap or
unrelated message never creates all-clear. Pagination is bounded to 100 heads;
retained reconstruction is bounded to 2,000 messages/16 MiB, raw storage to 64 MiB,
and permission journals to 100,000 evidence rows/200,000 receipts. Byte totals are
checked before loading retained messages and before accepting new payloads.
Exhaustion leaves the previous state intact and requires operator maintenance.

The first source-only run passed 27 tests with two incorrect fixtures (a reused
identifier and a nonexistent table assertion); both fixtures were corrected.
The combined CAP/journal/private repository/API suite then passed **113 tests in
22.45s** (`.tmp/hazard-journal-final.log`). After tightening byte preflight and
adding storage-boundary cases, all **38 journal tests passed in 8.69s**
(`.tmp/hazard-journal-bounds.log`). These cover persisted history, rights expiry
and revocation, retention deletion, replay/cursor conflicts, caller rollback and
final-write failure, cross-permission foreign keys, corruption, unknown mapping,
freshness, bounds and migration upgrade/downgrade with metadata comparison.
Final required API Ruff passed; the backlog invariant passed in 0.26s
(`.tmp/hazard-journal-backlog.log`). All fixtures
are synthetic; native CAP access/rights/current coverage remain unverified.

The next C1 work is private source-bound evaluation/event lifecycle, activation
gates, review/mute, Today/Inbox and consented delivery. Native acquisition,
maintenance scheduling, release and human acceptance remain open. No complete
feature commit, push, live warning feed or delivery is claimed by this journal.

## Private warning events, review and type mute, 13 September 2026

`hazard_events.py` connects a current permitted CAP head to an already active
owner-private monitor. Four tables in migration `1ac6d825f81c`, following
`09b5c714e70b`, store private developments, immutable event revisions, exact-revision
review actions and per-place hazard-type mute settings. All four are registered
in the central tenant policy; monitor deletion cascades the private records.
This internal worker operation neither starts drafts nor certifies source coverage.
The added source-policy flag `private_decisions_allowed` defaults to false:
matching/display permission alone never authorizes persisted private decisions.

Projection binds the configuration revision/hash, permitted source evidence/hash,
source generation and material sequence, and boundary edition/hash. It checks
both source generation/cursor and active monitor version, confirms the exact
current source head and checks native geography again before completing the
savepoint. Source locks precede monitor locks. Decisions contain relevance,
importance, validity and geography evidence; official prose stays in the source
journal and is retrieved only after current permission/retention checks.
No source payload receives private place coordinates.

Only a matched place with a selected, mapped hazard and sufficient importance
gets a new private development. A point outside the source area gets none.
Unknown classification/geography never becomes a positive location claim.
Later removal from the affected area becomes not-relevant, not all-clear.
Exact Cancel/all-clear updates affect only existing private lineage; Cancel
remains distinct from resolved. A missing/stale/expired source cannot synthesize
resolution. Future effective time is represented as planned applicability.

Every changed evidence/proof snapshot has an immutable private revision.
Translation-only changes retain the material sequence and review state. New
instructions, importance or relevant geometry reopen review. Review and
not-relevant actions require both the opened revision and version CAS and retain actor, action, exact event
revision and timestamp atomically with the review state. The minimal private
action audit remains readable without retaining expired official text.

Mute is a separate private preference for a named place and hazard type. It
increments monitor version so stale processing cannot overwrite newer settings,
and neither deletes history nor marks it reviewed. A multi-hazard warning is
muted only if every selected applicable type is muted; muting storm alone cannot
silence an unmuted flood warning. Future Today/Inbox and delivery integration must
check this state immediately before presentation or sending.

The existing gated/no-store/authenticated API now exposes per-monitor event
lists, exact current/historical readers, revision history, review actions and
their history, plus GET/PATCH type-mute settings. Cursors are owner-scoped and
pages are capped at 20. Lists/history omit full official prose; the exact reader
returns the source language/text, attribution, last receipt and proof. A current
source head/configuration/generation change, missing/revoked geography or invalid
rights redacts unconfirmed current evidence. Historic reads retain the exact
version subject to current rights and retained geometry. CSRF and existing role
checks protect mutations; neither source grants nor projection are HTTP writable.

Source retention/revocation maintenance now also erases derived private decision
and proof JSON across all organizations for affected source evidence. Exact
source access is rechecked before every reader response. The implementation is
bounded to 1,000 developments, 10,000 event revisions and 10,000 review actions
per monitor, with 8 KiB maximum decision/proof size. Caller rollback and final
geography failure roll back private evidence and review actions together.

Evidence (synthetic warnings, grants and active-monitor fixtures):

- Initial private/source/repository run: **78 passed in 20.45s**
  (`.tmp/hazard-events.log`).
- First extended API run: 86 passed and one fixture failure because the setup
  omitted its newly registered tenant context. Corrected setup uses that tenant
  without disabling authorization during projection or API calls.
- Corrected event/source/API/repository run: **87 passed in 37.63s**
  (`.tmp/hazard-events-final.log`).
- Final mute/event/source/API run: **65 passed in 35.49s**
  (`.tmp/hazard-mute-final.log`), including migration metadata/roundtrip.
- Additional all-tenant revocation test: **1 passed in 1.89s**
  (`.tmp/hazard-cross-scope.log`). It proves content removal in two private
  organizations without exposing either through another owner's reader.
- Final exact-revision action binding: **24 event/API tests passed in 16.91s**
  (`.tmp/hazard-review-binding.log`). An older historical reader cannot mark new
  instructions reviewed even when it carries the latest development version.
- Required API Ruff and whitespace checks passed. No frontend changed, so no
  repeat UI build is claimed. The HTTP fixture uses the real CAP geometry matcher
  with an explicitly synthetic administrative proof; prior native geographic
  evidence remains separate.
- The active-backlog invariant passed in 0.26s (`.tmp/hazard-events-backlog.log`).

C1 remains IN PROGRESS and unpublished. The next work is the five-language event
UI, Today/Inbox integration, complete activation/pause/resume/archive lifecycle,
source readiness and polling/maintenance, and explicit consented delivery.
Native warning access/rights/current coverage, release and human acceptance are
still open. No real grant, source, user monitor, email or deployment was activated.

## Official warning reader and private actions, 13 September 2026

The five-language C1 UI now exposes the private event API: bounded event and
revision lists, exact historical links, current review/dismiss actions and their
audit, and per-place hazard-type mute settings. Official instructions precede
metadata and saved-place settings. Source text is rendered verbatim and escaped,
with an explicit language selector, attribution, safe HTTPS source link and
publication, receipt and validity times. Source warning level is distinct from
the saved minimum-importance filter. No model or automatic translation is needed.

Malformed or duplicate event/revision parameters never fall back to a current
warning. Historical readers retain their exact text and cannot review a newer
revision. Review sends both the displayed version and revision; new instructions
reopen review while translation additions preserve it. Unavailable evidence hides
official content and actions. Withdrawal, explicit all-clear and missing evidence
remain distinct. Administrative-filter matches do not claim a precise house hit.

Actor, organization, location and URL changes clear request-scoped state and abort
old requests. Delayed responses cannot repopulate another location. Membership
denial removes private workspace content; viewers have no mutation controls.
Mute remains separate from review and preserves history, with monitor-version CAS.

Local evidence uses a disposable Next server, owned headless Chrome and synthetic
source/account fixtures; no real source activation or email request is made:

- Final root build passed with isolated `hazard-reader-final` output
  (`.tmp/hazard-reader-final-build.log`), including TypeScript and the registered
  three event-link/source-URL helper checks. Generated Next config changes were
  restored after inspecting their diff.
- All **22 event browser checks passed in 7.57s**
  (`.tmp/hazard-reader-accepted-browser.log`). They cover exact readers, source
  languages, escaped script text, review/reopening, history, mute, cancellation,
  all-clear, rights redaction, invalid links, role/membership changes, delayed
  responses and all five mobile locales. Desktop and mobile axe report zero
  violations; the shared Marvin color-contrast check remains incomplete.
- The existing draft workflow also passed **19 browser checks in 5.35s**
  (`.tmp/hazard-reader-drafts-browser.log`), including CRUD, preview failures,
  history, role redaction and five locales. Its history selector was narrowed to
  history articles after the event mute section added another heading.
- Visual review found filter labels used for actual event importance; these were
  corrected and the final build/browser run repeated. Final desktop and mobile
  screenshots show Warning level with the actual Warning/Alarm value.
  Earlier harness failures waited too early after navigation or during review
  saving; corrected checks wait for the exact reader and confirmed review state.
- Evidence is in `test-results/accessibility/hazard-events-*` and the bounded
  synthetic request log `.tmp/hazard-events-browser-requests.json`.

MV2-028/029 remain IN PROGRESS and unpublished. Today/Inbox, activation and
pause/resume/archive, polling/maintenance and consented delivery are still open,
as are native source access/rights/coverage, release and human acceptance.

## Private Today and Impact inbox, 13 September 2026

`hazard_today.py` and the gated `/api/hazard-watch/today` and `/inbox` endpoints
now expose owner-private summaries. Today shows unread material changes from the
last 48 hours; translation-only revisions do not renew that window. Impact inbox
shows unread active/planned warnings and alarms, without the 48-hour cutoff.
Explicit source cancellation, all-clear and removal from a selected area leave
that active list and remain distinct changes in Today and retained history.

Every candidate is rechecked through the current event reader, including source
rights, source head, retained evidence, configuration and native geography. Mute,
review and dismissal suppress the card without erasing history. Source changes
that have not been reprojected, stale or revoked evidence and missing geography
cannot enter a summary. A revision arriving during pagination cannot be paired
with the old cursor/detection time. Coverage is always explicitly unverified;
empty, muted and unavailable lists never claim safety.

Pages contain at most 20 items and examine at most 100 candidates. Owner-scoped
revision cursors reject changed/reviewed anchors. An entirely filtered scan can
return an empty page with a continuation rather than scanning all history.
Cards expose a private place name, actual warning state/level, attribution,
receipt/change times and an exact revision link. They omit coordinates, proofs,
source URLs and official prose; the destination reader retrieves the original
instructions under current access checks. Opening a card does not review it.

The five-language Today and Impact inbox components clear request-scoped content
on actor/organization/role changes, browser visibility transitions and refresh.
They abort obsolete requests, refresh visible lists every minute and expose
bounded next/previous controls, retry and explicit unavailable states. Card
actions lead to the exact warning reader; review and type mute remain beside
the complete instructions. Impact inbox wording and its guide now include saved
place warnings and distinguish private cards from the legal filters below.

Evidence is synthetic and does not establish native CAP access or live coverage:

- The first Today/API run passed 20 tests and failed one test setup: assigning
  `Database.organization_id` did not change its request ContextVar. The corrected
  test uses the actual `organization_context` and preserves tenant enforcement.
- The corrected Today/API/private-event suite passed **44 tests in 37.94s**
  (`.tmp/hazard-today-final.log`). The subsequent bounded-snapshot race check and
  full Today suite passed **16 tests in 12.03s** (`.tmp/hazard-today-race.log`).
- Required API Ruff passed. The isolated root `hazard-today` build passed
  (`.tmp/hazard-today-build.log`); generated Next config changes were inspected
  and restored. After correcting the five-language Inbox scope and guide, the
  final root `hazard-today-final` build also passed
  (`.tmp/hazard-today-final-build.log`). These final edits only change scope copy;
  the browser evidence above exercises the same card behavior.
- **38 browser checks passed** (`.tmp/hazard-today-browser.log`), covering the
  existing exact reader plus Today-to-instructions navigation, review/removal,
  reopening, cancellation, mute, empty-page continuation, source/membership
  redaction, retry and all five mobile locales. Four document axe audits report
  zero violations; shared Marvin contrast remains incomplete. Today mobile and
  Inbox desktop screenshots were inspected. Other directions return deliberate
  unavailable fixture responses and are not claimed as verified by these images.
- Browser and fixture processes terminated normally. No source activation,
  email, external user data, real monitor or deployment was used.
- The active-backlog invariant passed in 0.27s
  (`.tmp/hazard-today-backlog.log`); final whitespace checks passed.

MV2-028/029 stay IN PROGRESS and unpublished. Remaining implementation is complete
activation/pause/resume/archive readiness, polling and retention maintenance,
explicit consented delivery and their integration tests. Native source rights,
access/current coverage, release and human acceptance remain independent gates.

## Active lifecycle scope

The next implementation connects explicit start/resume, pause/archive and durable
private processing. Activation must bind the saved configuration, current native
boundary edition, reviewed per-hazard source jurisdiction and a fresh completed
source poll. Source permission or receipt of one warning alone must not prove
coverage. Radius coverage must include the entire saved circle. The default
runtime remains disabled until native source access and evidence are installed.
Stop commands must remain possible after source rights or geography expire.
Every status transition uses owner/tenant/version checks; queued or running old
work cannot publish after pause/archive/configuration changes. Acceptance covers
readiness failures, lifecycle history, job cancellation/leases, rollback,
five-language controls and source-free stopping. Native acquisition remains a
separate gate and no fixture may be described as a real source approval.

## Lifecycle and source readiness, 13 September 2026

Start/resume now require a fresh completed-poll marker bound to the reviewed
permission, generation and cursor, plus unexpired per-hazard jurisdiction proof
covering the entire saved footprint in the current native boundary edition.
One received CAP warning is insufficient. Empty completed polls can establish
channel freshness but never an all-clear. `HAZARD_SOURCE_ENABLED` defaults false;
`HAZARD_SOURCE_PERMISSION_ID` is empty. No native HTTP collector or real grant
has been installed. These controls are independently gated from source access.

Owner/version-checked start, pause, resume and archive keep immutable action
history. Start/resume queue durable private processing; pause/archive cancel old
work even when source permissions or geography expire. Processing rechecks the
source, geography, saved version and job lease before publication. An expired
individual warning cannot prevent an independent fresh warning from processing.
The monitor remains unavailable if any examined warning cannot be verified.
The minute scheduler processes due monitors; separate minute retention cleanup
erases expired/revoked source and derived content even with acquisition disabled.

Five-language controls expose readiness blockers, check times and status history.
Read-only members have no mutation controls; same-organization peers cannot read
or operate another owner's monitor, action history or job. Email consent remains
separate. The current implementation selects one reviewed source permission and
requires it to cover every selected hazard and the complete saved place.

Local evidence (synthetic grants and warnings; no real activation or email):

- Initial lifecycle/source/geography/repository/migration suite: **95 passed in
  22.11s** (`.tmp/hazard-lifecycle-tests.log`). The first HTTP regression run
  exposed lost geography blockers in preview (41 passed, one failed); production
  preview now preserves independent geographic and source blockers. The corrected
  HTTP/worker/lifecycle/Today/Centre suite passed **43 tests in 63.41s**
  (`.tmp/hazard-lifecycle-final.log`).
- Scheduled cleanup with processing disabled and migration metadata/roundtrip:
  **2 passed in 4.41s** (`.tmp/hazard-cleanup.log`). Required API Ruff passed.
- Root `hazard-lifecycle` build passed, including TypeScript and registered
  helper/i18n gates. Inspected generated Next config changes were restored.
  **50 browser checks** passed, with six document axe audits reporting zero
  violations; shared Marvin contrast remains incomplete. Lifecycle desktop and
  mobile screenshots were inspected. Existing draft save/edit/history/archive/
  confirmed-delete and locale regressions also passed against this build
  (`.tmp/hazard-lifecycle-draft-browser.log`). Both fixture runs exited normally.
- Five checks on the official January 2026 native package (SHA-256
  `1f122cb7a06f2d312a84b7c0a91116348ba907054d487f0a70b9d2302984e6fc`)
  verified Basel municipality/100m scope and rejected a 5km circle outside BS,
  a circle crossing the Swiss border and Basel against a ZH-only jurisdiction.
  Jurisdictions were synthetic, geometry real; QA-only installation is unchanged.
  Results: `.tmp/hazard-native-scope.json` at 18:30 UTC.

MV2-028/029 remain IN PROGRESS and unpublished. Next independent work is explicit
verified-owner email consent, quiet-hour/DST scheduling, material-change and
overlapping-place deduplication, and a final source/geometry/mute/review/consent
check before SMTP. Fake-mail tests must prove that expired, superseded or revoked
evidence never sends, uncertain sends are not retried, and receipt is not review.
Native acquisition/rights/current coverage and release/human acceptance stay open.

## Consented warning email, 13 September 2026

Email is off by default. An owner must explicitly opt in with a verified account
address; neither activation nor a location edit grants consent. Immutable consent
revisions bind the recipient and local timezone, immediate/daily mode and optional
quiet hours. Settings use the saved monitor version, cannot redirect to a supplied
address, and can be disabled after source loss, archive or history-cap exhaustion.
Changing preferences suppresses prior pending email without reviewing warnings.

Only new material private warning revisions record delivery intents. Translation
updates do not create another intent, including after a new consent revision.
Pending translation-only changes link the latest original-language revision of
the same material warning. A provider material identity deduplicates overlapping
saved places for the same owner and organization. Organizations remain separate.
Email contains the private place label and authenticated exact-revision links,
not copied warning instructions, coordinates or source proof. The reader keeps
the original instructions visible without AI; receipt never marks them reviewed.

The durable minute scheduler and `hazard_email` worker claim at most 50 due
unreviewed changes from the last 48 hours. Urgent items are ordered first but
respect quiet hours. Daily scheduling uses real timezone instants across DST gaps
and repeated clocks and attempts at most once per local day. Before SMTP, the
worker rechecks consent/recipient verification and membership, active configuration,
current source permission (including notification rights), completed source poll,
whole-place jurisdiction, native geometry, exact current material evidence,
review/dismissal, type mute, deduplication and job cancellation. Unavailable data
cannot produce an all-clear email. Failed/abandoned sends become uncertain and
are never automatically replayed. Outside SMTP mode no real send is attempted.

Five-language settings show explicit consent, verified recipient, quiet hours,
digest clock, uncertain attempts and a read-only preview. Edits clear confirmation
and old previews; conflicts, lost membership, location/actor changes and aborted
requests clear private state. Read-only members cannot change consent. Preview
does not send and links an exact warning revision. The UI shares the existing
delivery vocabulary and scheduling contract with the other private monitors.

Local evidence; all grants, accounts, source warnings and SMTP are synthetic:

- The first migration/behavior run found an incorrect foreign-key target
  (`hazard_event_revisions.sequence`); the model and migration now reference
  `revision`. A subsequent test setup passed the monitor identifier positionally
  to a keyword-only worker parameter; that fixture call was corrected. These
  failed runs were not published. The corrected initial email suite passed
  **19 tests in 18.67s** (`.tmp/hazard-email-behavior.log`).
- Extended email/API/private-event/migration acceptance passed **58 tests in
  60.80s** (`.tmp/hazard-email-integrated.log`), covering pre-send revocation,
  recipient/membership/status/mute/review/geometry changes, overlapping places,
  translation-only revisions, quiet hours, DST, daily delivery, history-cap opt-out
  and source permissions. The exact API Ruff gate passed.
- The root `hazard-email` build passed (`.tmp/hazard-email-build.log`), including
  frontend types, i18n and registered helper checks. Generated Next configuration
  changes were inspected and restored. **19 email browser checks** passed across
  all five locales (`.tmp/hazard-email-browser.log`); two document axe audits had
  zero violations, with shared Marvin contrast incomplete. Desktop/mobile images
  were inspected. The fixture and Chrome exited normally. Browser evidence lives
  in `test-results/accessibility/hazard-email-*` and a separate bounded synthetic
  request log `.tmp/hazard-email-browser-requests.json`.
- The final real API -> durable refresh -> due-email scheduler -> durable email
  worker -> fake SMTP path passed, preserving the exact reader and unreviewed
  Today card. Its first assertion used the internal database field name instead
  of the public job result envelope; the assertion now checks `result.data`.
  Translation after a later consent and disabled production SMTP mode passed
  separately. The corrected full-worker check and active-backlog invariant passed
  **2 tests in 4.23s** (`.tmp/hazard-mail-final.log`); the two additional guards
  passed in `.tmp/hazard-mail-worker.log`. Final required Ruff and whitespace
  checks passed. Main fetch succeeded with HEAD/origin both `8082524`, no drift.

MV2-028/029 remain IN PROGRESS, locally implemented and unpublished. Native CAP
acquisition/channel rights, reviewed current per-hazard coverage, runtime source
installation, production mail operation, release identity and human acceptance
are not established by these checks. The runtime remains disabled by default.
