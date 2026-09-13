# Transport Watch — C2 implementation gate

**Integrated publication, 13 September 2026:** The owner requested all implemented code be published to main now and all implemented sections enabled. The production defaults and remaining source/acceptance limits are recorded in the [integrated release evidence](evidence/2026-09-13-integrated-publication.md). Earlier dated references to uncommitted or disabled work are historical; the broader task remains IN PROGRESS.


Status: IN PROGRESS, 13 September 2026. Scope: MV2-037's public-transport
reference subset plus MV2-038/039. Road corridors remain MV2-040/041 work.
No transport feature is published or enabled. Finish one complete feature before
commit and immediate main push; source preflight alone is not delivery.

Production Compose now passes the Tender/Commute controls, credentials,
permission IDs, redirect origins and quotas through the common API environment.
Both environment examples retain false/empty defaults for these unreleased
features. Existing Air/River true defaults are preserved and their explicit
disable controls now reach the containers. Twelve read-only Compose/application
deployment tests passed in 5.55s with synthetic values, including effective
source disablement despite configured keys and absence of transport settings
from web/other non-API services. The migration container shares the API runtime
environment. No actual environment file, container or deployment was changed.

## Source gate

The [official Trip Updates cookbook](https://opentransportdata.swiss/en/cookbook/realtime-prediction-cookbook/gtfs-rt/)
requires a registered API key, binary production responses and redirects. The
feed's `feed_version` selects its static timetable; a newer download must not
replace that mapping early. The documented horizon is three hours. An explicit
zero delay is an on-time observation; absence is not. Only departure forecast
changes trigger the described source updates. These constraints must be checked
against an authenticated sample before a live capability claim.

The [Service Alerts cookbook](https://opentransportdata.swiss/en/cookbook/event-cookbook/gtfs-sa/)
documents a separate keyed binary feed. Selectors include agency, stop, route and
direction; trip selectors are not used in this Swiss alert profile. The documented
effect is UNKNOWN_EFFECT, so a generic alert cannot be relabelled as a structured
cancellation, replacement bus or restored service from that field. Keep the
official multilingual text and source identity. Trip Updates must supply any
claimed structured cancellation/delay capability independently.

Both cookbooks say two requests/minute; the [limits page](https://opentransportdata.swiss/en/limits-and-costs/)
still says five. This contradiction remains unresolved. Proposed application
budget: one shared request per feed per minute, with leases, bounded redirects,
backoff and Retry-After; it is not a confirmed provider grant. Do not probe limits
aggressively. Never forward the authorization header to an unverified redirect
origin. A sample must establish the actual redirect destinations first.

The [Open Data terms](https://opentransportdata.swiss/en/terms-of-use/)
allow file-based data without registration; service access requires registration.
They require source attribution, regular data updates and analyses identified as
the user's work. FEDRO road terms are separate. The user subsequently authorized
free account registration using the project mailbox. The owner completed the
registration on 12 September and the authenticated API Manager session was
verified. GTFS-SA and GTFS-RT each list five requests per minute and unlimited
total quota. An application request named **Helvetic Lens Monitoring** is
prepared for GTFS-SA. Automatic approval review rejected submission and adding
the GTFS-RT plan, requiring specific authorization for credential/access creation.
That confirmation is pending; no token has been generated or stored by this agent.

At **14:37:09 UTC**, two anonymous live-feed probes returned **401**. The CKAN
`package_show` endpoint returned **403**; this does not establish that public ZIP
downloads require a key. The public catalogue page lists timetable resources,
but no authenticated response or actual static↔realtime match has been obtained.
See [probe evidence](evidence/mv2-037-source-preflight.json). No transport/OJP/GTFS
key name was found in the development environment or its local configuration.
User was asked whether an API Manager account with both API products exists;
never request the secret value in chat or retain it in evidence/Git.

### Verified static archive, 12 September 2026

The public catalogue download succeeded without authentication. The earlier
CKAN API denial therefore does not block static files. The official resource is
`fe5f2e22-156a-4375-9373-031ecdd7e72c`, filename
`gtfs_fp2026_20260909.zip`, 247,376,208 bytes, SHA-256
`8d625f4236f30bc8ae1ec742025b5e29d36af9602c6d7055c219a918d49e7a6a`.
Its actual `feed_info.txt` version is `20260909`, timetable range
2025-12-14 through 2026-12-12. Source:
[official GTFS catalogue](https://data.opentransportdata.swiss/de/dataset/timetable-2026-gtfs2020).
The ZIP includes UTF-8 BOM CSV tables and a 3,074,774,637-byte `stop_times.txt`.
Keep this import off request paths; stream the archive in a background operation
and persist resolved references once, rather than rescanning it per monitor poll.

`transport_static.py` resolves up to 32 explicit trip/date/sequence selections in
one import, checks calendars and exceptions, validates route/agency/direction,
ordered segment stops and actual parent station rows, and retains the archive
hash. It rejects unsupported frequency departures, conditional boarding,
unmapped identities, mismatched versions, malformed archives and conflicting
calendars. Verified outputs can now be persisted through the internal catalog
boundary described below; no worker or UI activation has been performed.

The real archive resolved BVB route 1, trip `.ojp-91-1.1.TA.1.j26`, from
Basel MParc to Basel Münchensteinerstrasse, sequences 1→2, on its **historical
service date 2025-12-31**, at 05:42→05:43 UTC. The same trip does not operate on
2026-09-14; an attempted import correctly rejected it. These are static reference
checks, not current departures, live delays or a completed C2 scenario.
**35 reference/import tests passed**, including DST, overnight travel, calendar
additions/removals, version mismatches, directions, exact segments, archive paths,
unknown parents and conditional boarding. The full API Ruff gate passed.

## Local contract work

Implement independent, fail-closed time and identity checks while access is
unavailable. [GTFS Schedule](https://gtfs.org/documentation/schedule/reference/)
defines elapsed service time from local noon minus twelve hours, including values
above 24 hours. Saved commute weekday/time windows instead use local wall time.
These are distinct on DST changes. Unknown static versions and unmapped IDs must
remain unavailable; a city name is not a journey intersection.

Local `transport_reference.py` now implements elapsed service-time conversion,
overnight weekday windows, explicit spring-gap rejection and autumn repeated-hour
coverage, half-open overlap and exact conjunctive agency/route/direction/stop/trip
matching against a supplied verified snapshot. Parent stops must be explicitly
mapped; names and identifier prefixes do not imply equivalence. This pure module
has no API, data importer or worker and is not a live transport feature.

Verification: **13 reference tests plus the backlog integrity check passed**;
the full API Ruff gate passed. Fixtures cover both DST transitions, service times
above 24h, invalid times, opposite direction, outside-leg stops, wrong agency,
unknown timetable versions and different trip service dates. No real-source E2E
claim follows from these isolated checks.

[GTFS Realtime](https://gtfs.org/documentation/realtime/reference/)
defines FULL_DATASET as replacement of the prior snapshot. DIFFERENTIAL semantics
remain unspecified, so reject that mode until an explicit provider contract
exists. Deletion is not valid in FULL_DATASET. Disappearance, expiry, missing
realtime and explicit recovery must preserve distinct event states and history.

## Complete-feature acceptance before publication

### Local implementation evidence, 13 September 2026

`commute_contracts.py` validates private catalog reference selections, weekdays,
Zurich wall-time windows, explicit threshold/reset values and the outside-window
policy. Its pure evaluator preserves source outages and last-known conditions,
uses exact planned-leg/time intersections, suppresses small delay changes, and
supports pause today, mute, priority cancellation and one candidate across selected
legs. A digest candidate is not email consent. Spring gaps, overnight weekday
ownership and conflicting/stale/future observations are covered by fixtures.

The checkpoint retains skipped boarding/alighting stop IDs. A later zero boarding
delay does not restore a skipped alighting stop without an explicit scheduled
prediction at that stop. Partial improvement retains the disruption episode until
recovery is evidenced. Catalog ownership and persistence are still caller gates;
these functions do not expose an API or start a monitor.

`transport_feed.py` now decodes actual binary fixtures through the
[official Python bindings](https://gtfs.org/documentation/realtime/language-bindings/python/).
The lock adds `gtfs-realtime-bindings==2.2.0` and `protobuf==7.36.1`, without other
dependency upgrades. It bounds input to 32 MiB, 50,000 entities, 2,000 stops per
update, 100 alert selectors/periods, and 20 bounded language editions per text.
Original response SHA-256 and canonical entity fingerprints are distinct.

Invalid binary, missing required fields, unknown fields/enums, mixed entity kinds,
duplicate trip instances, invalid periods and FULL_DATASET deletion reject the
replacement atomically. Replay, older snapshots, conflicting timestamps, static
version switches and disappearance have separate outcomes. Trip developments use
trip/service-date/start-time identity while retaining the provider entity ID, so
renaming the latter does not create a new commute disruption.

The static importer retains exact segment stop sequences. Projection checks both
sequence and ID, maps explicit cancellation and skipped endpoints, and reads only
the selected boarding departure prediction. Absolute predicted departure time
takes precedence over a conflicting delay number; absent data remains unavailable.
Trip measurement timestamps remain old when the enclosing feed is refreshed.
No upstream stop-delay propagation or trip-level delay propagation is claimed.
Trip start-time variants, changed trip properties and assigned-stop changes return
explicit mapping-required reasons. Source alert text/language and open/disjoint
active periods remain evidence; unsupported selector constraints are never dropped
to broaden coverage. Alert effects do not become structured cancellation claims.

Verification: the preceding contract/reference/import run passed **64 tests**.
Binary, transition, import and reference regression passed **108 tests**, including
zero-versus-absence, renamed entity IDs, stale measurement timestamps, disjoint
alert periods, unsupported stop changes and evidence of resumed stop service.
The exact full API Ruff gate passed. These are synthetic protocol fixtures,
not authenticated source samples, source permission or live acceptance.

Still required: permitted real binary samples and static matches; shared bounded
HTTP acquisition/leases/redirect authorization; verified interchange data,
scheduled catalog renewal; Today/outbound digest integration and the
five-language UI/browser journey. No production migration, source grant or activation
was performed for C2. An unsuccessful response must never be decoded as an empty
snapshot. The caller must recheck source permission and freshness before applying
snapshot differences. Whole-feature publication and all AC-C2 criteria remain open.

### Private catalog and configuration integration, 13 September 2026

The additive `f6c8da371a9e` migration adds four tables: shared leg references and
dated verified legs, plus private monitors and immutable configuration revisions.
It follows the currently unpublished Tender Watch migration. The migration chain
must be reviewed in publication order; no serving database was changed.

The internal `publish_legs` boundary accepts bounded importer results, preserves
archive/date/version/sequence proof and rejects conflicting replacement evidence.
Recurring references bind route, direction, exact ordered stops and local departure
time; a different dated trip may serve the same reference only with matching
identity. Readers check payload hashes, dated keys and the reference identity.
Catalog rows have no owner/query information. Catalog publication has no HTTP route.

The default-disabled `/api/commute-watch` routes now provide authenticated catalog
search, exact-date/timetable preview, private draft create/list/read/edit/delete,
configuration history, archive and pause commands. Scope derives from current
membership and the authenticated owner, never submitted organization/user IDs.
Requests require normal CSRF; all success and denial responses use `no-store`.
The API has one shared per-user request budget across IDs and paths.

Creation is idempotent within owner/workspace; quotas cap 100 monitors per owner
and 1,000 revisions per monitor. Compare-and-swap versions prevent stale edits,
deletes and lifecycle actions. Edits require draft/paused state and return the
monitor to draft. Private deletion cascades revisions while preserving public
catalog data. Pause-today uses the Zurich date. Active-state cases remain synthetic
fixtures: start/resume now require current recorded source permission, fresh stored
feeds and an eligible dated journey. Enabling `COMMUTE_WATCH_ENABLED` alone cannot
create an active monitor. Preview checks exact static identity and cached source
readiness; it does not fetch the provider. Source permission is not granted through
this API. Connected multi-leg activation still requires verified interchange data.

Verification: **128 integrated tests passed** for private HTTP/repository,
catalog, binary projection and existing commute/reference/import rules. A separate
**21-test run passed** for private API/repository, organization isolation and the
earlier migration chain. The new migration's upgrade/downgrade preserves accounts
and existing Tender Watch schema; ORM metadata matches all four tables. Regression
covers foreign-owner cursors, membership removal, inactive users, viewer write
denial, rollback, replay, CAS, archived deletion, composite tenant foreign keys,
literal wildcard search, disabled/unknown references, wrong-version previews and
rehashing a wrong-route payload. Full required API Ruff passed. No frontend or
live-source acceptance is claimed by this backend integration.

### Durable source/event processing, 13 September 2026

The additive `a7d9eb482baf` migration adds source permissions, latest feed state,
private developments, immutable event versions and private review signals. It also
adds poll scheduling timestamps, with a constant UTC backfill that preserves saved
drafts. Generated changes to unrelated existing tables were removed before use.
The C2 schema now has nine tables; private additions join the normal tenant scope.

`commute_sources.py` accepts only bounded binary data under an explicit internal
permission record and keeps one latest original response per source. It rejects
older/conflicting replacements and checks hash, timestamp, version, current rights
and freshness when reading. Replay cannot freshen the source timestamp. Credential
material is not stored in these tables. No HTTP permission-write route exists;
all positive permission/activation examples so far are synthetic fixtures.

`commute_jobs.py` is wired into the existing durable job/outbox dispatcher and a
30-second scheduler. Start/resume enqueue processing only after source and dated
journey checks. Pause/archive/delete cancel pending work and review candidates;
superseded jobs cannot update a changed monitor. Membership is checked again by
the worker. These jobs process stored shared feeds and do not fetch a provider.
An empty feed produces `waiting_for_predictions`, not a claim of on-time running.

`commute_events.py` stores per-leg checkpoints, material history and at most one
private review candidate per development version in the same transaction. Minor
delay changes do not create repetitive history/alerts; explicit cancellation,
improvement/restoration, outages and official notice changes retain one service-day
development. Disappearance/staleness never proves recovery. A replay comparison
bug caused by tuple/list JSON normalization in source language editions was found
and fixed by persisted-worker tests. Capacity failures roll back checkpoints,
history and candidates together (1,000 developments, 10,000 versions and 32 MiB
history per monitor; 128 KiB per version). These signals are not email consent or
SMTP delivery. Normalized field evidence includes the exact static leg/archive
proof and original feed/entity hashes; full original historical feeds are not
retained, and the API labels this evidence as normalized source fields.

Private event/history/review/mute routes now recheck ownership and current source
rights. Exact sequence/version review leaves subsequent changes unread; mute does
not falsely mark evidence reviewed. Source revocation hides historical evidence.
Readers mark stale/expired values without waiting for another worker tick and
preserve the original immutable history. Generic job list/read/cancel/retry routes
also enforce the private commute owner, including other admins in the same workspace.

Verification includes actual durable service dispatch and authenticated HTTP event
review with synthetic source grants/feeds, replay, low-noise thresholds, cancellation
and restoration, missing/stale feeds, revocation/renewal, history fingerprints,
rollback on capacity failure, empty feeds, source clock rollback, source languages,
same-workspace job isolation and upgrade over a populated private draft. The
final worker/source-clock/static-proof regression passed **145 tests in 27.00s**,
including the backlog integrity check; required API Ruff passed.
No source registration, credential creation, live acquisition, real email, source
grant or production activation occurred in that iteration. Interchange/catalog
renewal, Today/digest delivery and the five-language UI remain
required before whole-feature publication and user acceptance.

### Shared HTTP acquisition, 13 September 2026

`commute_acquisition.py` now connects the official binary endpoints to the stored
feed/private worker through a separate minute Celery task. The collector is disabled
unless both `COMMUTE_WATCH_ENABLED` and `COMMUTE_SOURCE_ENABLED` are true. Operators
must supply separate secret `COMMUTE_GTFS_RT_KEY` / `COMMUTE_GTFS_SA_KEY` values and
the corresponding `COMMUTE_GTFS_RT_PERMISSION_ID` / `COMMUTE_GTFS_SA_PERMISSION_ID`
from actual reviewed source grants. Configuration never creates a source grant.
These are deployment environment values, not fields requested from end users.
No real keys were created, obtained, transmitted or installed in this iteration.

Migration `b8ea0c593cb0` (after `a7d9eb482baf`) adds one shared poll/lease row per
source. Conditional database claims serialize collection across organizations and
workers; a crashed worker has a 120-second lease, and an expired worker cannot
capture a response or release a replacement's lease. The application requests a
new chain no sooner than 60 seconds after completion. This is an application budget,
not resolution of the provider's conflicting published quota. Private commute
routes, owner IDs and workspace data are never included in provider requests.

HTTP has no ambient proxy configuration or browser cookies, bounded connection/read
timeouts and a 45-second total deadline checked at each request/chunk boundary.
Gzip and zlib deflate decoding cap both wire and expanded content at 32 MiB.
Incomplete streams, concatenated compression members, oversized content, malformed
binary and conflicting source timestamps never replace the last good snapshot.
Replay does not refresh source observation/receipt time. The source parser remains
strict; actual provider samples must establish supported wire fields and versions.

Redirect chains stop after three redirects and reject loops, insecure or unreviewed
origins. `COMMUTE_FEED_REDIRECT_ORIGINS` is an operator-reviewed JSON array of exact
HTTPS origins for public/signed object downloads; it defaults to empty. No actual
redirect destinations have yet been verified. The API bearer key never leaves the
fixed API origin, including for explicitly reviewed storage origins. Every request
and final capture rechecks the grant and lease; a revocation during acquisition
prevents capture and further redirects. Failures store fixed codes, not error bodies,
credentials or destination URLs. Exponential backoff and Retry-After apply globally;
401/403 suspends automatic retries until a new reviewed permission is configured.
Other blocked configuration/redirect cases require operator review; credential
renewal does not bypass them. Retry-After beyond one day suspends automatic polling
and retains a bounded long cooldown instead of retrying after the ordinary backoff.

The isolated acquisition suite passed **28 tests in 2.71s**: flags/grants, cross-tenant
rate sharing, inflight claims, expired/replaced leases, redirects/auth/cookies,
compression expansion/truncation, timeouts, HTTP failures, Retry-After, revocation,
replay and actual collected-feed-to-private-cancellation evidence. The earlier
acquisition plus repository/migration run passed **37 tests in 5.47s**. Required
Ruff passed. After the last cooldown refinement, the combined acquisition,
private worker/API, binary/static/reference, organization isolation, migration
and backlog regression passed **173 tests in 29.74s**. Required Ruff and
`git diff --check` passed. All feeds, grants and HTTP responses were synthetic;
no live-source or user-acceptance claim follows from these checks.

Read-only browser inspection now shows **Log in** on both API Manager and SIMAP;
the earlier authenticated API Manager tabs are no longer in the available tab list.
Registration alone does not establish an active API plan/token or permission to
acquire restricted SIMAP documents. Previous access-creation approval remains
pending; no attempt was retried and no source or production deployment was activated.

### Private journey interface, 13 September 2026

The local `/commute-watch` page now supports dated catalog search with pagination,
ordered selection of up to eight verified legs, a private name, weekdays and Zurich
time window, delay/hysteresis thresholds, event categories and outside-window
policy. It has separate preview and save operations. Catalog pagination cannot
submit the draft. Preview no longer asks the user for an internal archive version:
the server selects a fresh permitted feed's exact version or one unique common
dated catalog mapping, and rejects ambiguous archives instead of choosing the newest.
Saved monitor/configuration-history responses provide friendly journey labels.

The page implements explicit start, pause/resume, pause today/continue today,
pause-before-edit, archive and deletion with an inline confirmation. Source
unavailability disables start in the UI and remains enforced by the API. Connected
journeys still require verified interchange data. The Monitoring Centre now includes
the private commute inventory/filter and a gated link; nine active choices remain,
with customs/C4 excluded. No feature/source switches have been enabled in production.

Private events show the exact source condition, availability, observation time,
reported delay and official language editions. HTML-like source text remains literal.
History pages retain normalized-source labeling and feed hashes, and distinguish
settings revisions. Exact-version review and mute remain separate actions. Missing,
expired and stale observations keep an explicit last-known-state message. Refresh
reads saved data. Today is now connected by the later update below; actual
email/digest delivery is not connected yet.

Account/workspace/role and selected monitor boundaries reset the page state and
abort requests on unmount. Pagination and refresh hide old payloads before a new
request resolves. Access-denied history clears the visible event evidence. A late
response cannot replace a newly selected editor. Lifecycle conflict feedback
survives reload; event-review conflicts clear evidence and retain a refresh notice.
The controls have English, German, French, Italian and Romansh copy, responsive
layout and contextual help using the product's shared reviewed English guide system.
Two pre-existing Tender document captions also moved into the five-locale copy map
to satisfy the repository-wide locale gate; no document acquisition behavior changed.

Verification: authenticated API/repository/worker/Monitoring Centre tests passed
**54 tests in 60.61s**, including automatic version choice, revoked-feed fallback,
owner isolation, feature-off metadata and settings labels. The first browser run
found an invalid test-harness response for unrelated shell APIs; correcting it to
the existing unavailable-response contract allowed the full journey to pass.
The built browser then passed catalog paging/preview/save/start, review/mute,
history revocation, pause/edit/restart/archive/delete, stale-response and role/source
gates, with **11 full-document axe checkpoints** across desktop/mobile and all five
locales. The complete root `npm run build` gates passed after adding route help and
the locale fixes. The final browser run, including event-conflict feedback, passed
all **11 full-document axe checkpoints** again. The combined C2 API/source/worker,
private inventory, migration, organization isolation and backlog suite passed
**193 tests in 63.31s**. Required API Ruff and `git diff --check` passed. The final
root web build also passed i18n, shell/resource/report/help checks and Next build;
the new frontend tests verify Zurich date boundaries and literal language fallback.
All accounts, grants, timetable legs and feeds in browser/API tests are synthetic.
Real-source matching, provider onboarding and human language/usability acceptance
remain unverified; no whole C2 release or completion is claimed.

### Private Today and exact event links — 13 September 2026 (local)

Today reads the existing private transport signals without creating another read
state or delivery queue. It keeps only the latest pending signal per development
for the current owner, workspace, active configuration and non-paused day. Review,
mute, archive, changed settings and a handled newer signal suppress old cards.
The reader checks current source permission and immutable evidence hashes on every
request. It scans at most 100 candidates and advances a sparse-page cursor without
exposing denied titles. Stable timestamp/ID ordering supports bounded pages; an
invalidated cursor asks for a refresh. Signals older than 48 hours are omitted.

Cards include journey labels from saved static evidence, service day, source,
observed delay/time and explicit reasons. Current missing, expired or stale data
is shown as last known; an old cancellation is never styled as a current urgent
alarm when its observation is unavailable. Outside-window candidates remain
identified as saved candidates, without implying an email was sent.

Each card links to its exact development and sequence. The authenticated detail
endpoint verifies the expected monitor and independently loads the requested
immutable snapshot, even outside the first events page. Older links retain their
original labels and observations beside a separately labeled latest known state;
opening one does not mark it read. Revoked review/history access clears the whole
linked presentation, including the previously shown historical snapshot.

Today and the reader have five-language copy. Account/workspace/role boundaries,
page replacement, focus refresh, periodic refresh and pagehide clear/abort protect
private content. The Today block is omitted when unavailable or empty; disabling
the feature also clears pagination state. The normal Today refresh remounts it.

Verification so far: **23 passed** API/HTTP/privacy tests, including ownership,
cross-workspace isolation, exact history, current rights and corruption, no new
jobs/read state, sparse and tied-time pages, missing/stale cancellation, lifecycle
suppression, middleware authentication and feature/no-store gates. Full root web
build passed, including a test that saved labels/observations do not mutate source
evidence. The combined transport, inventory and backlog suite passed **252 tests
in 72.18s**, and the exact API Ruff gate passed. The browser attempt has not
produced new acceptance evidence: its isolated Chrome exited before the first
checkpoint while the harness waited for its local server. Automatic approval
review rejected stopping the two verified test processes under AGENTS.md's rule
against interrupting active checks; explicit user authorization is pending.
A bounded startup request timeout has been added for the next run, not applied
to the already-running process. The earlier 11-checkpoint UI result above does
not verify this new Today integration. No live feeds, account credentials,
real messages, release or human acceptance are claimed.

### Exact timetable renewal — 13 September 2026 (local)

The new background `commute_renewal` boundary can renew one to 32 saved
reference/date pairs against an already acquired, pinned static archive. It
finds current trip IDs using exact agency, route, direction, selected ordered
stops, Zurich departure wall time and service-day offset. A changed source trip
ID or stop-sequence numbering can therefore preserve the saved reference UUID.
Renumbering is verified from the new archive, never copied from an old version.
Source labels or city similarity do not establish a match. Timetable changes
that alter these saved meanings remain unresolved and require user review.

Candidate collection streams the archive with bounds of 50,000 candidate trips,
200,000 endpoint rows and 32 exact candidate legs. The final strict static reader
verifies the complete selected segment, source names, boarding permissions,
agency timezone and calendar. Calendar exceptions are shared with the original
static reader. An ambiguous exact match, unavailable date, frequency template
or changed segment is reported explicitly rather than selecting a nearby trip.
Exceeding a bound fails the batch without publishing partial mappings.

Only unique matches are published, under a transaction, using the existing
immutable reference/date/version records. Existing private monitor settings,
configuration revisions and old timetable evidence are unchanged. A conflicting
already-pinned mapping cannot be overwritten. This boundary does not fetch
archives, create source permission, enable the feature or send alerts.

An operator can preview the mapping using the configured database and an already
acquired archive:

```text
python -B scripts/renew_commute_catalog.py --archive <archive.zip> --version <feed_version> --sha256 <archive_sha256> --reference <saved_reference_uuid> --date 2026-09-14
```

Repeat `--reference` and `--date` for at most 32 distinct pairs. The default is a
transactional dry run: the JSON report has `applied: false`, and no mapping is
retained. After inspecting it, `--apply` commits unique matches. Both modes
verify the exact archive SHA-256 and feed version. The command performs no schema
migration or network request. A successful process exit is not proof that every
pair mapped: inspect each `status` in the report.

Verification: **58 tests passed in 6.74s** across renewal, static archive parsing,
catalog/private configuration and the backlog invariant. Tests cover changed
trip IDs, new exact stop sequences with unsorted CSV rows, immutable old/new
versions, dry-run rollback, checksum rejection, candidate bounds, calendar
removals/additions, overnight times and GTFS elapsed-time behavior at both DST
transitions. CLI `--help` and exact API Ruff passed. Fixtures are synthetic ZIPs;
no production database or source archive was imported. Scheduled archive
discovery/acquisition/renewal and live-feed matching remain unfinished.

### Shared static archive acquisition boundary — 13 September 2026 (local)

`commute_static_acquisition.py` now selects an exact version from an already
obtained CKAN resource document. It verifies dataset/resource UUIDs and the
official unsigned download path; display names and newer filenames are not
substitutes for the requested version. Multiple matching resources are ambiguous,
and missing/denied catalog data remains unavailable. The selector bounds resource
count to 1,000. It does not itself fetch the catalog.

The binary downloader uses an isolated public GET with explicit headers and no
authorization, cookies or private workspace fields, including when an injected
client has default credentials. Redirects require exact reviewed HTTPS origins,
at most three hops; signed redirect URLs are neither returned nor persisted.
No wildcard object-storage allowlist is installed. HTTP access denial blocks;
throttling retains Retry-After and network errors expose only fixed codes.

ZIP bytes stream to a unique staging file with actual and declared size bounds
of 512,000,000 bytes, identity content encoding and a 240-second HTTP total
deadline. Guards run before requests, during streaming and before publication.
The completed file must match any expected checksum and pass the existing
StaticArchive structure/feed-version/date validation. Publication uses a
content-hash filename and an atomic no-replacement link. A pre-existing artifact
is verified; corrupt entries are preserved for investigation rather than
overwritten. Staging files are removed on failure. The returned record contains
the clean resource URL, SHA-256, size and actual feed validity dates.

Verification: **71 tests passed in 3.37s** across static acquisition, existing
live-feed acquisition and ZIP parsing. Final static retrieval checks passed
**23 tests in 0.24s**, including credentials on redirects, truncation/oversize,
encoding, exact version/hash, cancellation, cache conflicts, deadline, sanitized
network errors, resource ambiguity and catalog bounds. Exact API Ruff passed.
All HTTP and ZIP tests are synthetic. The official catalog was read again on
13 September; it still listed the 20260909 resource. A web-tool download attempt
did not retrieve the signed object, and no alternative request retried that
blocked redirect. No archive was downloaded into production.

This was the low-level boundary before the shared collector below. Its historical
verification does not prove live source access. The preceding successful frontend
build is unchanged by these backend modules.

### Durable shared static collector — 13 September 2026 (local)

`collect_commute_static` is scheduled every minute, with an independently
persisted 15-minute acquisition cooldown and a 30-minute lease. It is disabled
unless `COMMUTE_WATCH_ENABLED`, `COMMUTE_SOURCE_ENABLED` and the new
`COMMUTE_STATIC_ENABLED` are all enabled. `COMMUTE_STATIC_DATASET_ID` must be a
canonical operator-configured UUID. No production setting was changed.

Both live feeds must be fresh, hash-consistent and covered by current reviewed
permissions, and must agree on one explicit static version. A worker claims
the global lease with an atomic conditional update. Source permission and lease
ownership are checked throughout acquisition and before recording the archive;
a late worker cannot release a replacement lease or publish a binding. No
database transaction stays open during provider requests. Private journeys,
users and organization identifiers are not sent to the provider.

The public CKAN `package_show` request is bounded to 2 MiB and 30 seconds, with
declared/actual length checks and sanitized parser/network failures. Redirects
and access denial suspend the collector; it does not fall back to scraping a
login page or borrowing a browser session. The actual earlier CKAN 403 remains
unresolved. ZIP redirects still require exact operator-reviewed origins in
`COMMUTE_STATIC_REDIRECT_ORIGINS`; none were installed.

Migration `e1bd3f8c6fe3` adds two shared tables: the lease/cooldown and immutable
version bindings. Each binding retains the original dataset/resource/unsigned
URL, SHA-256, size and feed dates. Cached files are revalidated before reuse;
missing files can only be reacquired with the original resource and checksum.
Corrupt files remain untouched and suspend automatic retry. There is no HTTP
operation that clears a blocked collector; access/cache conflicts require
operator investigation and deliberate recovery. Ordinary transient errors use
persisted exponential backoff, respecting provider Retry-After.

`COMMUTE_STATIC_CACHE_MAX_BYTES` defaults to 2 GiB and reserves room for one
maximum-sized staging file. Only exact hash-named, database-owned archives unused
for more than seven days may be removed to make space. Bindings and private
history remain intact. Unknown files, including abandoned staging files from a
crashed process, count toward quota and are never automatically deleted. A full
cache reports unavailable until space is restored. Version bindings are bounded
to 512; reaching that limit suspends acquisition rather than discarding evidence.

Verification: **92 tests passed in 11.78s** across the shared collector, static
retrieval, neighboring live-source polling, catalog persistence and schema
round-trip/ORM parity. Coverage includes shared reuse across organizations,
no network-held database locks, fresh-source disagreement/revocation, lease
takeover, corrupt/missing cache files, immutable checksums, quota retention,
access denial, throttling and malformed/truncated/oversized catalog responses.
Exact API Ruff passed. The initial test attempt could not use Windows' default
pytest temporary directory; the successful run used a new isolated directory
inside the development workspace. No production database was touched.

Automatic dated-reference/connection renewal is integrated in the next section.
It does not change a private configuration or start sending alerts. Live source
access, static/feed compatibility and complete C2 browser,
release and human acceptance remain open. On the latest browser check, both
SIMAP and API Manager showed **Log in**; no API key or access plan was created.

### Automatic cached-catalogue renewal — 13 September 2026 (local)

The shared static collector now retains its lease after recording the archive
binding, runs one bounded catalogue-renewal batch, and then releases the lease.
This also prevents cache GC from removing an archive while the automatic worker
uses it. No private monitors, memberships, email settings or personal route
queries enter the catalogue scan. It considers only enabled imported public
references and previously imported ordered connection pairs.

`CommuteStaticPoll.renewal_state` persists a keyset cursor, exact static version,
local-date anchor, current date offset and bounded outcome counts. Each batch
contains at most 16 work units / 32 unique reference-date targets. The pass
covers eight upcoming Zurich departure dates, converting them to exact GTFS
service dates using the saved departure-day offset. Night services therefore
do not default to the wrong calendar day. Pairs carry both references together
even when standalone-reference work falls on another page. Unrelated units are
never concatenated into a journey.

A new feed version or a new day after pass completion starts a fresh pass.
Expired departure dates are skipped; new catalogue entries behind a cursor are
picked up on the next pass. A completed pass means every selected unit was
attempted, not that every journey was matched. Missing, ambiguous, outside-feed
and unsupported-frequency results remain explicit. Existing preview/start gates
continue to reject unmapped dates and unusable connections while a pass proceeds.
The cursor provides bounded eventual coverage, not an instantaneous network-wide
refresh guarantee.

Renewal now has preparation, resolution and publication phases. The background
worker snapshots identities in a short transaction, closes it, and scans the
archive without holding a database connection. Parser checkpoints periodically
revalidate lease/source permission; the scan has a 20-minute budget. Publication
locks and rechecks current feed versions/permissions, lease ownership, reference
identities and known connections. It atomically records new mappings, connection
proofs and cursor progress. Failure before commit leaves progress and mappings
unchanged; the immutable cache binding may remain for a subsequent retry.
Private configurations, existing mappings, historical proof and consent are
never rewritten. Updated transfer minima can prevent start even when both new
trip IDs match the saved route exactly.

Verification: **125 tests passed in 24.98s** across automatic and operator
renewal, interchange rules, static parsing, shared collection, catalogue and
migration behavior. The final automatic-worker suite passed **10 tests in
7.47s**, including no database connection during file scans, unchanged private
choices, correct overnight dates, invalidated connections, source revocation,
feed-version change, lost leases, disabled references, scan deadline, persisted
pagination and publication rollback followed by a cache-only retry. Exact API
Ruff passed. One initial worker test expected an internal readiness error from
the lifecycle API; it was corrected to the existing generic API contract while
retaining the specific interchange-state and unchanged-configuration assertions.

The unpublished additive static-cache migration now includes the small JSON
cursor column; ORM parity and downgrade/upgrade remain covered. No production
migration, credentials, source access, source request, actual mail or activation
occurred. No frontend changed. The existing browser test handle was polled and
is still running without new acceptance output; it was not interrupted or
duplicated. Actual source compatibility, browser evidence and pilot acceptance
still prevent whole C2 completion.

### Dated connection renewal — 13 September 2026 (local)

Renewal of an already imported journey now rechecks its known ordered connection
pairs when both endpoint references are included for the requested date. It
resolves rules from the newly pinned archive, rather than copying a prior
connection decision. New trip identifiers must satisfy the new source selectors;
changed minimum times, later arrival, explicit prohibitions and missing rules
produce fresh independent outcomes. If either leg cannot be uniquely mapped,
the connection report says `mapping_unavailable` and creates no dated proof.
Older legs, proofs and private configuration revisions remain unchanged.

The bounded batch resolver verifies up to 32 unique dated legs and 32 pairs,
reading the full stop-times and transfer tables once per connection batch.
It does not concatenate unrelated requested pairs into one journey. The existing
eight-leg ordered journey importer uses this same rule resolver. Pair/date
expansion or graph bounds fail the transaction; they do not silently truncate
coverage. Mapping and connection publication share a savepoint, and the normal
operator dry run rolls both back. Applying renewal records newly verified or
explicitly unusable source outcomes; it does not create consent or activate feeds.

`scripts/renew_commute_catalog.py` now includes `interchanges` alongside `items`.
Request every saved leg for the target date and inspect both collections before
`--apply`. A mapped leg alone does not imply a usable connected journey. This
extends the internal/operator path. The automatic cached-catalogue worker above
now invokes the same resolver through separate preparation/publication phases;
permitted live discovery and acquisition still need source acceptance.

Verification: **100 tests passed in 11.78s** across connection renewal, individual
renewal, interchange import, static parsing and catalog/migration behavior.
Cases include changed trip IDs, minimum times and arrival gaps, absent/prohibited
rules, missing endpoints, idempotency, preservation of historical proofs,
dry-run/apply, all-or-nothing bounds and one-pass batch table reads. Exact API
Ruff passed. No frontend behavior or schema changed in this renewal update; the
preceding successful web build remains applicable. No source request, live import,
production change or new browser completion is claimed.

### Verified interchange rules — 13 September 2026 (local)

The internal importer now resolves adjacent pairs of two to eight exact ordered
legs from the same pinned archive and service day. It implements the route/trip
specificity order in the [GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/#transferstxt),
including endpoint station-to-child expansion. Equal maximal rules remain
ambiguous. Explicit prohibition, insufficient elapsed time and absent rules do
not authorize a connection. Recommended and timed connections retain their source
meaning; minimum-time rules require an explicit non-negative minimum. Continuing
on contiguous segments of the same trip is distinguished from changing routes.
Linked-vehicle types 4/5 remain unsupported until their vehicle continuation is
verified. No nearest-stop, station-name or accessibility-path inference is used.

The parser verifies both full legs against the archive, reads at most one million
transfer rows and retains at most two maximal candidates per pair. Source rule,
CSV row number, endpoint IDs, scheduled gap, minimum time, exact leg hashes and
archive hash are retained. The additive `d0ac2e7b5ed2` migration follows
`c9fb1d6a4dc1`, adding the shared `commute_interchanges` table (13 C2 tables total).
Composite foreign keys bind both dated legs. Import is idempotent and rejects
conflicting pinned evidence. Downgrade removes these proofs, retaining existing
accounts, journeys and email consent; multi-leg processing then requires proofs
to be imported again. No production migration or import was executed.

Preview shows the connection rule and elapsed/minimum seconds in five languages,
with an explicit distinction between the timetable and actual travel conditions.
Start checks each eligible dated connection. Processing and pre-send email
eligibility recheck the exact current evidence; missing or corrupt proof prevents
new notifications. Immutable material-event history includes the interchange
evidence used at processing time. The generic multi-leg prohibition is replaced
only for connections with usable imported proof; source permission/freshness,
owner consent, role and window gates remain enforced.

Operator dry run, against an already acquired archive and configured database:

```text
python -B scripts/import_commute_journey.py --archive <archive.zip> --version <feed_version> --sha256 <archive_sha256> --date <YYYY-MM-DD> --leg <first_trip_id> <boarding_sequence> <alighting_sequence> --leg <second_trip_id> <boarding_sequence> <alighting_sequence>
```

Repeat `--leg` in travel order, at most eight. Dry run rolls back all catalog and
proof writes. Inspect every `interchanges[].state` before using `--apply` to
retain the results. `applied: true` records catalog publication, not source
activation, private-monitor creation or a successful connection. This command
does not fetch archives or create source grants. Automatic archive acquisition
and renewal of these dated connections remain unfinished.

Verification: **120 tests passed in 65.17s** across interchange parsing, catalog,
migration, jobs, mail, HTTP and Today. Final focused checks passed **33 tests in
2.86s**, including dry-run/checksum/apply, endpoint parent scope, specificity,
ambiguity, prohibition, invalid inputs/bounds, exact minimum, DST service dates,
same-trip continuation, two-leg start/worker history and suppression of prepared
mail after proof removal. An incorrect synthetic SMTP field name in an additional
test was corrected; no production mail configuration was changed. Exact API Ruff,
CLI Ruff/help and the full root web build passed. All feeds and accounts are
synthetic. The browser harness now expects 25 full-document axe checkpoints,
including a two-leg preview; this extension has not been run because the earlier
stalled browser process remains active with stop approval pending. These checks
do not establish actual Swiss transfer coverage or live/human acceptance.

### Consent-aware transport email backend — 13 September 2026 (local)

Transport event processing now records email intents atomically with a new
material event only when the owner has already explicitly enabled delivery to
their verified account address. Email consent has its own immutable revisions;
it does not rewrite journey configuration or Today review state. Enabling email
does not backfill old signals. Disabling it cancels pending email work while
preserving private source checks and unread Today cards. Outside-window saved
candidates create mail intents only under daily-digest opt-in.

The additive `c9fb1d6a4dc1` migration adds two private tables and a default-zero
email revision to existing commutes. Foreign keys bind the organization, owner,
monitor, consent revision and exact development sequence. Downgrading this new
migration removes its new consent/delivery history; accounts, journeys and
transport event history are retained, and upgrading again does not restore an
email opt-in. No production migration was executed.

Authenticated, owner-only GET/PUT `/api/commute-watch/monitors/{id}/email` use the
normal no-store/session/CSRF guards. PUT requires a current monitor version,
validated preferences and a strict explicit consent boolean matching the chosen
mode. GET `/email-preview` shows at most 50 due eligible exact links, with quiet
hours/daily-attempt/unavailable status. A feature switch alone cannot create
verified-address consent or source permission.

The existing durable dispatcher and a 60-second scheduler handle immediate or
daily delivery, using the established timezone/DST and quiet-hours calculations.
Pending work is bounded to 50 updates per message and the latest applicable
unreviewed event versions within 48 hours. Original cancellation candidates have
queue priority; stale immediate observations are suppressed. Daily mail points
to saved updates rather than declaring an old disruption to be a live alarm.
Signals from the same provider event, observation time and pinned static version
are deduplicated across the same owner's monitors within their workspace.

Before SMTP, the worker rechecks source rights and exact evidence integrity,
ownership/membership, verified recipient and consent revision, active/current
journey settings, pause today, mute/review and newer event versions. It claims
delivery state before sending and repeats these checks at the send boundary.
SMTP timeouts and abandoned claims become uncertain and are not automatically
resent; durable email jobs have one attempt. The user can see an uncertainty
count in email settings. A successful mail does not mark the event reviewed.
Five-language text/HTML messages use escaped journey names and authenticated
exact-version links; raw source notices are not copied into mail.

The backend is exercised with synthetic accounts, grants, feeds and a fake mailer,
including a real HTTP consent/start flow through the service's durable dispatch.
The initial 31 existing catalog/worker/migration checks and 32 mail/API checks
passed. The complete delivery suite subsequently passed 32 checks including
cross-workspace rows, populated migration rollback, localized escaping and job
cancellation. The combined regression passed **89 tests in 60.46s** after adding
the static version to the deduplication identity. The final delivery suite passed
**34 tests in 19.93s**, including daily overflow rescheduling and exclusion of
already queued monitors from scheduler candidate pages. A SQLite ORM in-memory
date comparison failure in rescheduling was fixed by disabling session evaluation
for that bulk update. Exact API Ruff and `git diff --check` passed.

The saved journey now has a five-language email settings panel. It exposes
off/immediate/daily modes, digest time, IANA timezone and optional overnight quiet
hours. Enabling delivery requires a new explicit checkbox confirmation; changing
preferences clears that confirmation. Unverified addresses cannot enable mail,
viewers cannot write, and archived journeys can only disable delivery. Source or
SMTP unavailability is visible without representing saved consent as activation.
Preview explicitly uses saved settings and sends nothing; daily-attempt, quiet
hours, uncertain outcome and the 50-item limit have separate explanations.
Each preview link identifies the exact private event, sequence and service day.

Requests abort when the panel, account scope or selected journey is replaced.
Save uses PUT and the current monitor version, then refreshes the parent monitor.
Conflicts and denied previews clear the stale form and private links until an
explicit refresh. The panel clears previews on focus and private state on page
exit; a restored browser page reloads preferences. Invalid equal quiet-hour
endpoints remain editable. Email changes do not edit the journey configuration.

The full root web build passed after adding the panel. The existing isolated
browser harness now includes consent/opt-out, exact preview, conflict/denial,
unverified address, readonly and five-language mobile email cases, increasing
expected full-document axe checkpoints from 18 to 24. These new browser cases
have **not run to completion**: the earlier active harness remains stalled and
its scoped stop approval is still pending. Syntax checks are not browser proof.
Live SMTP, real-source acceptance and full browser acceptance remain open.
Keep the complete C2 feature unpublished until the user-facing flow is ready;
this backend evidence is not a whole-feature completion or activation claim.

### Remaining release acceptance

- Verified permitted binary Trip Updates and Service Alerts samples; pinned
  matching static version, stable stop/route/trip/service-day identities and
  explicit unsupported capability reporting.
- Private verified journey or explicit-leg selection; weekdays and local window;
  threshold; preview, explicit start, pause today, mute event and full lifecycle.
- Relevant cancellation/partial interruption, material delay, reviewed updates,
  explicit improvement/restoration, Today reasons, official evidence and history.
- No alerts from opposite directions, unrelated routes or outside the selected
  window; no minor-delay spam or fabricated recovery from feed disappearance.
- Five-language accessible/mobile UI, real-source acceptance, privacy/migration,
  worker/replay tests, full lint/build and browser journey.

All ten AC-C2 criteria remain unverified as a complete scenario. General shared
parents, road reference data and human pilot acceptance are not closed by C2.
