# Road Watch — C3 complete-feature contract

**Integrated publication, 13 September 2026:** The owner requested all implemented code be published to main now and all implemented sections enabled. The production defaults and remaining source/acceptance limits are recorded in the [integrated release evidence](evidence/2026-09-13-integrated-publication.md). Earlier dated references to uncommitted or disabled work are historical; the broader task remains IN PROGRESS.


Status: IN PROGRESS, 13 September 2026. Scope: MV2-040/041 and the road-reference
part of MV2-037. This is one of nine active directions. C4/customs and grants
remain deferred. Source discovery is complete enough to begin local contract
implementation; source access and corridor coverage are not approved or active.

## Authoritative source boundary

The [official cookbook](https://opentransportdata.swiss/en/cookbook/road-traffic-cookbook/traffic-situations/)
defines keyed SOAP retrieval of DATEX II situations, updates and revocations.
It recommends one daily full request and subsequent requests with a recent
If-Modified-Since timestamp. There is no history endpoint. Revocations remain
available for 60 minutes. Geographic matching uses versioned TMC/AlertC tables;
the matching topology must be requested from ASTRA. No topology or keyed traffic
sample has been obtained. Cookbook examples are historical, not current coverage.

The [FEDRO terms](https://opentransportdata.swiss/en/tac-fedro/) require registration
and explicit acceptance; ordinary access is limited to six months unless
extended. They prohibit raw machine-readable redistribution to third parties
and require source attribution for published processing results. Acquisition,
retention and any user-visible derived representation need the actual reviewed
grant. A transport API Manager account alone is not evidence of that grant.
No terms were accepted, account plan created, support email sent or API queried
as part of this discovery. TMC access is separate from choosing a road name.

## Inspected developer assets

All four assets were obtained from links on the official cookbook into ignored
task scratch. No original source XML/XSD or traffic data is added to Git.
The files were read in memory; no ZIP paths were extracted or XML entities run.

| Asset | ZIP SHA-256 |
|---|---|
| [DATEX II 2.2.3 schema](https://opentransportdata.swiss/wp-content/uploads/2025/03/DATEXIISchema_2_2_3-with-definitions.zip) | `7bc85136799f28fa106265afcce08425e24988a05dfa58d93737389e6dc35d07` |
| [Creation example](https://opentransportdata.swiss/wp-content/uploads/2025/03/XML_Meldung_IN_338210_DatexII_SOAP_01_Erstellung.zip) | `cf506eab61b78e7f9299532a3f9f2adea549c1e2afaeddc02c057d437c688e11` |
| [Update example](https://opentransportdata.swiss/wp-content/uploads/2025/03/XML_Meldung_IN_338210_DatexII_SOAP_02_Mutation.zip) | `d070366245d74a88fb5b7756802c7dc81613481c6c9a7d313af3c9a2bf65b703` |
| [Revocation example](https://opentransportdata.swiss/wp-content/uploads/2025/03/XML_Meldung_IN_338210_DatexII_SOAP_03_Aufhebung.zip) | `ae20490b43568ccc759b5b4ce07983806bb996182e8359707f10e4a3135ac0b8` |

Inspection found six records in the creation example and three in each later
example. Record version attributes remain zero, so integer version alone cannot
identify changes. The revocation example supplies explicit cancellation. Public
comment containers include an `internalNote`; non-public comments also exist.
These must never enter public explanations merely because of their parent name.
The fixtures reference topology 7.1; that is not a verified current topology.

The XSD distinguishes lane restrictions from road/carriageway closures. Numeric
delay is optional and uses seconds with a floating-point base type. Direction
codes are relative to the topology; they are not inherently compass directions.
Source-derived labels and unknown values must survive normalization without
invented delays or a guessed north/south mapping.

## Implementation and acceptance

1. Create a bounded SOAP/DATEX decoder with explicit namespace/type checks,
   secure XML handling, source-time validation, situation/record identities,
   public instructions, validity windows, cancellation and source capabilities.
   Synthetic fixtures must cover genuine structural patterns above, including
   constant version numbers, record removal in an update, internal-note filtering,
   malformed/oversized XML, namespace spoofing and unsupported extensions.
2. Persist reviewed source permission, expiry/renewal and allowed derived fields.
   A default-off shared collector needs leases, conservative cadence, full/delta
   reconciliation, bounded transfer, rejection/backoff and immediate revocation
   checks. A source outage cannot produce reopening or an all-clear. Record
   both semantic changes and provider evidence without exposing raw XML via APIs.
3. Import licensed, versioned TMC topology and operator-reviewed corridor
   definitions. Prove ordered segment intersection and direction for A2,
   Gotthard and A13. Missing topology is unavailable, not a text-match fallback.
   Different topology versions cannot share an unverified location mapping.
4. Provide private owner-scoped corridor profiles with direction, event types,
   delay threshold and planned-closure preferences. Implement explicit
   preview/start/pause/edit/archive, CAS/idempotency, immutable revisions and
   membership/CSRF/no-store gates using existing Monitoring conventions.
5. Produce low-noise material developments for closure/reopening, lane changes,
   planned rescheduling, accidents and supported congestion. Fifteen minutes
   applies only to a known numeric delay. A full closure is relevant without a
   delay value. Source text is evidence, not an instruction to the application.
6. Complete the five-language reader, Monitoring Centre, Today/history/review,
   major closures in the Impact Inbox,
   and consent-aware delivery where permitted. Recheck source rights, ownership,
   exact version, current preferences and review state before notification.
   Do not auto-enable mail or reuse another direction's consent.
7. Verify complete scenarios, privacy/adversarial failures, exact API lint,
   affected frontend/build checks, browser accessibility, permitted source samples
   and actual activation separately. Commit/push the complete tested feature on
   main, then observe the main-site release. Human acceptance remains explicit.

## Current evidence and remaining dependencies

The source pages and all four linked developer archives were accessible on
13 September. Web reading cannot handle ZIPs, so public documentation files were
downloaded directly without credentials; this did not bypass an access denial.
The Firecrawl CLI and optional lxml package are absent. Inspection used the
standard XML parser after rejecting DTD/entity declarations. Product integration
does not need a Firecrawl account or browser scraping for this documented SOAP
API. The decoder performs bounded structural and semantic checks, not complete
XSD validation. The source-storage migration is local and tested; no production
migration or runtime activation for C3 has occurred.

### Local decoder and reconciliation

`road_feed.py` now decodes the SOAP 1.1 / DATEX II 2.2 contract with UTF-8,
DTD/entity rejection, in-scope namespace resolution, bounded XML complexity,
source clocks, duplicate-field/identity checks and explicit unsupported fields.
It retains supplier/situation/record identity, typed road/carriageway/lane events,
numeric delay in seconds (missing stays unknown), versioned TMC references and
source-relative direction, validity/exception windows, cancellation and end.
Recurring schedules and unsupported extensions remain unavailable capabilities.
The historical `untilFurtherNotice` extension is not silently interpreted.
Only description, warning and location-descriptor public comments are projected;
internal, processing, unknown/other, non-public and restricted/test text is excluded.

Material fingerprints exclude provider receipt/publication/version-only refreshes,
normalize text whitespace and collapse equivalent clauses within one situation.
Original permitted public text and individual record evidence remain separate.
`road_reconciliation.py` provides atomic pure full/delta replacement with an
explicit full baseline, continuity, rollback/conflict and retained-history bounds.
Missing full-feed records or a delta gap mark evidence unavailable; continuous
deltas retain unseen observations without freshening their clock. Only explicit
cancellation revokes a source notice, which is not proof of physical reopening.
This pure state is now persisted by the internal source repository; collector
integration remains unfinished.

The final synthetic decoder/reconciliation suite passed 91 checks, plus the
required backlog/customs-deferral invariant (92 passed, `.tmp/road-contract-final.log`).
Local replay of the three official historical examples produced `created`,
`material_changed`, `revoked`, with 6/3/3 records and preserved topology 7.1.
No raw XML or source comments are committed. The replay is developer-contract
evidence only, not a current feed sample or A2/Gotthard/A13 coverage proof.

### Durable source permission and history

`road_sources.py` and six source-evidence `road_*` tables now persist reviewed permission,
the selected source generation, request evidence, immutable situation versions,
current situation bindings and material changes. Migration `f2ce409d70f4` follows
`e1bd3f8c6fe3`; the road-only downgrade/upgrade preserves accounts and existing
Tender/Commute tables. No actual permission has been recorded or selected.

An explicit policy contains the review reference, attribution, exact supplier,
acceptance/expiry, maximum source age, raw/derived retention, permitted derived
fields and separate notification permission. Policy fingerprints and current
revocation/expiry are checked on reads/writes; an old receipt cannot substitute
for the current permission clock. Recording a grant does not select it or start
acquisition. Selecting a different grant requires a new full baseline and never
transfers old history to it. These are internal operator functions, not HTTP APIs.

Publication uses a locked source generation and request identity to atomically
write evidence, versions, current bindings and material history. Conflicts,
failure during publication, stale source data and storage limits preserve prior
state. Current/history data is decoded from canonical, hash-checked typed JSON;
cross-permission/source version bindings are enforced by composite foreign keys.
Source-only refreshes retain evidence without a new material change. Explicit
reconfirmation can renew retained evidence; unseen deltas cannot do so.

Raw storage may be disabled entirely. Internal notes never enter normalized
versions. Retention cleanup removes expired/denied bytes and history in dependency
order; losing a current or empty baseline increments its generation and requires
a new full snapshot, blocking an in-flight stale writer. No automatic eviction of
unexpired evidence occurs at capacity. Limits are 2 GiB stored content, 64 MiB
current state, 2 MiB per situation, and bounded evidence/version/change row counts.
The cleanup routine is scheduled independently of the source acquisition flags.

The final local run passed 138 checks (`.tmp/road-storage-verified.log`): 30 source
repository cases, 91 decoder/reconciliation cases and 17 affected Commute repository/
migration checks. The tests cover reload, replay, revocation/renewal, field/email
permission, corruption, freshness, retention, empty baseline, reconfirmation,
capacity, atomic rollback and migration compatibility. SQLite cleanup explicitly
fetches affected identities so timezone handling does not depend on cached ORM
objects. No live-source, production-migration or user-acceptance claim follows.

### Shared collector and retention scheduling

`road_acquisition.py` now issues the documented fixed SOAP POST to the official
endpoint, using a bearer key and the exact SOAPAction. Request construction excludes
client cookies, default authentication, private headers and query parameters.
No user's route or identity is sent. XML response transfer is bounded to 32 MiB
on wire and after decompression, with a 45-second total budget, finite HTTP
timeouts, integrity checks and permission/lease guards during streaming.

The seventh road table, `road_source_polls` (migration `a3df51ae81a5` after
`f2ce409d70f4`), provides a shared 60-second request interval, 180-second ownership
lease, durable cooldown/backoff and rejected-source state. The first request, a
daily boundary or an interrupted recent window uses a full snapshot. Subsequent
delta requests overlap the earlier of client request start and provider publication
by ten seconds; a faster client clock cannot advance past source evidence.
Source generation, selected permission, flags, credentials, lease and grant expiry
are checked again before commit. A replaced worker cannot publish or release the
replacement's lease. Failures retain existing observations and require full recovery.

Redirects and a bare HTTP 304 remain blocked as unreviewed response contracts;
the currently implemented source contract requires a DATEX publication. They do
not create an empty snapshot or refresh source clocks. A new explicitly reviewed
and selected permission can recover a credential rejection after its existing
cooldown; changing a key or flag alone cannot clear a rejected contract. Actual
conditional-response behavior still requires permitted live verification.

Celery schedules acquisition and retention checks every 60 seconds. Acquisition
requires `ROAD_WATCH_ENABLED`, `ROAD_SOURCE_ENABLED`, a key and a reviewed selected
permission; all flags default false and credentials empty in both examples and
main production Compose. Retention still runs with acquisition disabled and
disposes its database resources. No serving environment or source flag was changed.

The combined collector/storage/decoder/reconciliation/configuration run passed
155 checks (`.tmp/road-collector-final.log`). A subsequent provider-clock overlap
regression and all affected collector cases passed 33 checks
(`.tmp/road-collector-clock.log`). These use synthetic HTTP and isolated SQLite;
Compose is rendered without a daemon or real secrets. Typed `OverallPeriod`/`Period`
wrappers from the official cookbook are accepted without a false unsupported flag.

### Exact corridor matching and materiality

`road_topology.py` now validates a bounded normalized TMC point/link projection
and resolves operator-labelled corridor flows against its exact country/table/
version and content hash. Reciprocal links, known endpoints and ordered adjacency
are required. Numeric point-code order never determines direction. A reviewed
"northbound" flow may follow negative links; both directions use the same verified
physical extent. Different versions, missing points/distances, malformed extents,
circular ambiguity and path-budget exhaustion remain unknown rather than no-match.
This is not an importer for the still-unseen licensed ASTRA delivery format.

The local official XSD confirms that Method 4 runs from secondary upstream to
primary downstream, with offsets from both ends directed inward. The decoder now
requires integer metre offsets, matching `MetresAsNonNegativeInteger`. Matching
handles trims crossing multiple links, point events, known disjoint roads and
partial corridor extents. Nonzero trims require reviewed along-road distances;
no straight-line/GPS distance is invented. Merely touching endpoints of two linear
spans is not positive-length overlap; explicit point events are handled separately.
Circular extents need the currently unsupported direction-sense capability.

`road_evaluation.py` provides pure temporal/materiality decisions for the future
private workflow. Valid periods are clipped and merged; exceptions override them.
Explicit active/suspended status overrides the schedule, while an overrun means
still in progress. Planned windows, rescheduling, expiration, withdrawal and source
clearance remain distinct. Resolution candidates require previous-event context
and never create a physical all-clear by themselves. Potential/probable source
events retain that distinction; restricted records disclose no schedule.
Fifteen minutes applies only to known numeric congestion delay. Missing delay
does not suppress explicit road/carriageway/lane closures, accidents or roadworks.

The full affected local Road Watch suite passed 211 checks
(`.tmp/road-decisions.log`), including topology, temporal/materiality, decoder,
storage, reconciliation and collector compatibility. All topology is synthetic.
No actual road corridor, topology permission, native delivery parser, persistent
corridor catalogue, private API/reader or user acceptance is claimed by these tests.

### Durable corridor catalogue

`road_catalog.py` now persists immutable reviewed topology revisions, stable
corridor references and version-specific corridor maps. Each topology revision
binds the licensed asset SHA, normalized projection SHA, exact TMC identity,
operator review and separately scoped matching/display/notification permissions.
This internal operator attestation does not acquire a licence or parse an unseen
native ASTRA asset. No real permission or named corridor was published.

Private configurations can retain a stable reference UUID when reviewed mappings
change. Publication checks adjacency and the reference's reviewed flow label,
then advances its generation with a compare-and-swap in the caller's transaction.
Different TMC versions may coexist. Resolution selects the latest explicit map
for the exact country/table/version, rechecks its rights and hashes, and never
falls back to an older grant after revocation or expiry. Reusing a still-valid old
projection requires a new explicit mapping review. Disabled references cannot
resolve. A public description contains permitted labels and attribution only;
the internal resolved graph is not an HTTP response schema.

Retention runs through the existing source cleanup even when acquisition is off.
Expired/revoked topology and mapping bytes are removed while reference UUIDs,
review metadata and hashes remain. Reads deny expired/revoked grants immediately,
without waiting for cleanup. Projection/map sizes and retained row counts are
bounded. Migration `b4e062bf92b6` adds three tables after the existing road poll
migration; the complete road migration roundtrip contains ten tables and preserves
existing product tables. No production database was migrated.

The affected catalogue, storage, collector, topology and materiality tests passed
**148 checks in 17.84s** (`.tmp/road-catalog.log`), including exact-version renewal,
no fallback, distinct use rights, stale edits, disabled references, corrupted
bindings, caller rollback, retention and migration parity. Required API Ruff
passed. These are local synthetic tests, not real corridor or end-user acceptance.

### Private profiles and configuration API

`road_contracts.py` and `road_repository.py` now persist owner/organization-scoped
profiles with one to eight distinct reviewed corridor-direction references,
selected event kinds, a strict numeric congestion threshold and planned-event
preferences. Names, road-name guesses, unsupported IDs, repeated references,
boolean/string thresholds and unsolicited email settings are validated at the
boundary. Saving a draft neither starts processing nor grants consent.

Create retries bind to the original configuration hash. Edits require the current
version and a draft/paused state; each real edit appends an immutable configuration
revision. Reads, pagination, history, archive and removal recheck current owner,
role and workspace membership. Tenant-scoped ORM models and a composite revision
foreign key protect storage boundaries. Deleting a profile cascades its private
history and preserves other profiles and shared corridor data.

The default-off `/api/road-watch` router uses session authentication, CSRF,
bounded input, a shared per-user request-rate bucket, and no-store headers even
on errors. Catalogue and configuration preview require an exact TMC table version
and current display rights. Withheld labels are neither searched nor copied into
private history; the owner's own settings remain readable when a grant expires.
Catalogue pages examine at most twenty references and support empty continuation
pages. A request-local parsed-graph cache has a 32MiB projection budget and never
caches permission decisions. Budget continuation retries the first unread
reference on the next page instead of skipping it. No raw graph/XML is exported.

Migration `c5f173c0a3c7` adds two private tables after the catalogue, bringing the
road migration roundtrip to twelve tables. No production database was changed.
The affected repository/API/catalogue/storage suite passed **73 checks in 42.14s**
(`.tmp/road-private-bounds.log`), including CSRF/owner/feature denials, tenant FK,
save replay, stale edits, rollback, deletion, revoked-label redaction, graph reuse
with immediate revocation/corruption checks, bounded pagination and migration
parity. Required API Ruff and diff whitespace checks passed.

### Private event processing and history

`road_events.py` and `road_jobs.py` now connect saved profiles to permitted shared
source evidence. Explicit start/resume requires the feature/source switches,
selected current source permission, fresh full/delta state, and a usable reviewed
mapping for every selected corridor. One durable private refresh job is queued
per active monitor version; scheduling runs every sixty seconds. Pause, archive,
deletion, owner deactivation and changed versions prevent superseded jobs from
publishing. The processor never calls the provider or sends private selections
upstream. Source acquisition remains the separate shared collector.

The worker locks the current private monitor and writes a material development
and immutable history in one transaction/savepoint. One source situation remains
one event across replacement record IDs and language editions. Fact projections
exclude raw XML, graph geometry and comments. They require event/validity/location
rights; delay-based selection additionally requires delay rights, and lane counts
are included only with lane rights. Congestion uses the configured threshold;
five-minute delay bands suppress one-second prediction jitter in material history
while preserving the exact current permitted delay. Repeated evidence refreshes
the current proof without appending a duplicate material version.

Active/planned changes, rescheduling, partial restrictions, expiry, withdrawal,
source disappearance and explicit `roadCleared` remain distinct. An initial
clearance without prior event context creates no new event. Probable clearance
remains `possible_clearance`; missing, expired or withdrawn evidence does not
become a confirmed open road. Unsupported relevant facts make coverage partial
or unavailable. A stale source preserves historical facts with a stale marker.

Source/configuration/topology expiry is checked again before commit. The durable
dispatcher also checks the running job's current lease, heartbeat, cancellation,
target and tenant in the same transaction, so lease loss rolls back staged event
history without a second-connection SQLite heartbeat deadlock. Scoped job listing,
detail, cancel and retry endpoints hide another owner's road jobs even within
the same organization. No mailbox consent is inferred from starting a route.

Private event/history/review endpoints use normal owner, tenant, CSRF and no-store
gates. Reviews target an exact material sequence/version; new changes stay unread,
and mute does not erase history. Every read rechecks source bytes/permissions and
the exact reviewed mapping permissions, redacting unavailable evidence immediately.
Cleanup removes expired/revoked derived payloads across tenants while preserving
scoped sequence/hash audit metadata. It runs with acquisition disabled. Storage
is bounded per monitor (1000 developments, 10000 versions, 32MiB immutable history,
128KiB event payload) and per processing run (100000 record/corridor evaluations).

Migration `d60284d1b4d8` adds private developments/history and monitor scheduling
fields; the road migration roundtrip now contains fourteen tables. The affected
worker/profile/API/catalogue/source/collector suite passed **125 tests in 99.03s**
(`.tmp/road-worker-final.log`). Final lease/cancellation and possible-clearance
regressions, including actual durable job dispatch and HTTP review, passed all
**23 worker tests in 37.85s** (`.tmp/road-worker-lease.log`). Required API Ruff and
diff whitespace checks passed. Evidence uses isolated databases, synthetic source
data and grants. No real corridor, source enablement, migration or release occurred.

The local five-language `/road-watch` reader now covers reviewed corridor search,
private drafts, preview, explicit lifecycle actions, material event review/mute,
paginated history and settings revisions. Catalogue and preview no longer require
users to enter technical table identities; the server selects the latest reviewed
label while event matching remains exact to the source table version. A revoked
latest label never falls back to older rights. Saved corridor labels and event
attribution are permission checked, separately from private settings. Permission
denials redact the mounted private reader; scope changes and page visibility
transitions abort pending requests. Monitoring Centre includes a gated traffic
filter and owner-private route links. TypeScript and seven reader/help checks
passed. The API/profile/worker/centre suite passed 55 tests; the remaining test
initially confused stable-reference generation with exact-version map generation.
Its corrected assertion and the backlog invariant passed (2 tests in 6.88s,
`.tmp/road-reader-final.log`), covering latest-label revocation without fallback.
Required API Ruff passed. The initial reader browser/build gate was pending at
that checkpoint; the additional evidence below supersedes it for the named flows.

### Today and exact comparisons: local evidence, 13 September 2026

Road Watch now contributes owner-private unread cards to Today. The projection
requires an active current configuration and the selected source permission,
rechecks both current and immutable evidence, and supports bounded sparse pages.
Cursors identify immutable material versions; changed, reviewed or foreign
cursors require an explicit refresh. An urgent card requires a current, certain,
active closure on a verified corridor. Planned, probable, stale, cleared and
missing states do not receive that priority. Advancing the shared source before
private processing marks the previous projection stale.

Links select an exact event and sequence independently of list pagination. The
reader shows the selected immutable change, its immediate predecessor, and the
latest known state separately. Every representation rechecks access and rights;
denied bytes and labels disappear. Opening a link never reviews it. Muting also
preserves the reviewed sequence, so unmuting can restore an unread change.

The Today/jobs/API checks passed 48 tests in 100.45s (`.tmp/road-today.log`).
The final exact-link HTTP and Today cases passed 21 tests in 47.01s
(`.tmp/road-linked-api.log`), including owner isolation, no-store, invalid sequence
bounds, review/mute, sparse pagination, source-generation staleness and revoked
evidence. Six frontend reader/help tests passed. The root web build passed with
an isolated Next output directory; the final heading-level adjustment also passed
the web build (`.tmp/road-today-final-build.log`).

A disposable localhost fixture, with synthetic identity, source facts and grants,
verified the following in Chrome: a historical exact link despite an empty event
list, previous/current comparison, stale data, five-language layout at 390px with
no horizontal overflow, membership denial during a mutation clearing private
content, source denial removing source facts/labels, sparse Today continuation,
and muting removing a Today card without reviewing it. Four full-document axe
checkpoints reported zero violations: Today desktop, exact comparison desktop,
exact comparison mobile, and redacted mobile. The only incomplete contrast node
was the shared `.marvin-body`; it is not counted as a contrast pass. Reports are
local in `test-results/accessibility/road-manual.json`. The fixture was shut down
after testing. It did not contact a real source or send mail.

The access-denial check exposed a lingering loading indicator after private data
was cleared; the reader now suppresses that indicator while access is blocked.
This local evidence does not establish live coverage, a deployed feature, human
translation acceptance, the complete editor/lifecycle browser matrix or all C3
acceptance criteria.

### Consented road email: local evidence, 13 September 2026

Migration `e71395e2c5e9` adds versioned owner email policies and exact-version
delivery attempts, bringing the road schema to sixteen tables. Opt-in requires
the owner's verified current account address and a version-checked explicit
confirmation. It never backfills history, reviews an event or authorizes source
use. Turning email off, pausing or archiving cancels pending delivery. Policies
are bounded to 1000 revisions per route and delivery creation follows the bounded
material history. All new records participate in tenant session scoping.

New material events create intents only when both the source and exact topology
permit notifications. A durable maintenance job claims at most fifty due items,
then rechecks current membership, owner/address, consent revision, source selection,
configuration, event sequence, review/mute, source freshness and both historical
and current evidence before SMTP. No source facts or licensed corridor labels are
copied into mail: the owner's route name and authenticated exact-version links
lead to the permission-checked comparison. Five-language mail and settings copy
are implemented; human language acceptance remains open.

Quiet hours and daily scheduling use the existing timezone/DST-aware scheduler.
A daily digest is attempted at most once per local day. Ambiguous SMTP outcomes
remain uncertain and are never automatically retried. Deduplication uses the
retained material source change and temporal state, rather than every collection
generation, so unchanged refreshes do not resend the same change across the same
owner's routes. Missing retained identity suppresses delivery. Independent owners
retain independent consent and delivery. Email jobs do not prevent fresh road
processing; they share the existing scoped durable job dispatcher.

The delivery/source/worker/migration suite passed 78 tests in 51.63s. The subsequent
API/Today/release-history suite passed 69 tests with one new HTTP test setup error:
the fixture first lacked workspace scope, then counted registration verification
as a road email. After correcting the fixture, the actual HTTP consent-to-durable-
job-to-fake-SMTP test passed in 3.44s (`.tmp/road-email-http-final.log`). The final
delivery suite, including unchanged-source deduplication, passed 32 tests in
31.08s (`.tmp/road-email-dedup.log`). TypeScript, the full root build
(`.tmp/road-email-build.log`) and required API lint passed before the final import
formatting and additional owner-isolation checks. No real mail was sent.

Chrome on a disposable synthetic localhost fixture verified disabled Save without
consent, explicit opt-in, reloaded preferences, read-only exact-link email preview,
and whole-reader redaction after a denied email-preview request. The open email
form's full-document axe audit reported zero violations; only shared Marvin
contrast remained incomplete. It is retained in the local `road-manual.json`
report. The earlier four Today/comparison audit results were observed in tool
output, but their raw report was overwritten by the initial fixture implementation;
the fixture now appends existing audits. Do not claim those earlier raw reports
remain in the current file.

The same browser session verified pause, edit, preview, private draft save,
explicit Start, pause/resume, archive, and deletion with its explicit confirmation.
Request evidence is local in `.tmp/road-email-browser-requests.json`; the fixture
was shut down cleanly. These are synthetic workflow checks, not live source,
complete five-language email/browser acceptance or pilot evidence.

Final delivery verification passed **35 tests in 35.72s**
(`.tmp/road-email-mapping.log`), including the durable HTTP path, independent
owners, deduplication across unchanged source refreshes and a reviewed mapping
changing between claim and SMTP. A current mapping must still be the exact
latest reviewed mapping; otherwise delivery is suppressed until private source
processing catches up. All five final owner-isolation/backlog checks also passed
(`.tmp/road-email-final.log`), and the exact required API Ruff gate passed. The
temporary Next type paths were restored after the isolated browser check.

### Impact Inbox: local evidence, 13 September 2026

The Impact Inbox now includes owner-private, unread, unmuted current closures.
Only certain active road or carriageway closures on a verified corridor qualify;
planned, probable, lane-only, cleared and unavailable events are excluded. Unlike
Today, the Inbox has no 48-hour cutoff: a still-current long-running closure
remains actionable. Current permitted facts can remain visible after an immutable
snapshot expires, while the exact-version reader keeps expired historical bytes
redacted and displays the current state separately.

The read-only API scans bounded sparse pages and checks current ownership,
membership, configuration, selected source, freshness and mapping permissions.
A newer reviewed mapping or a future source timestamp makes old projections
unavailable. Metadata distinguishes missing verification from an empty closure
list; neither means the road is clear. Read and mute actions reuse the exact
event/version checks in Road Watch and Today. The legal filters below this private
section retain their own scope. The page heading and five-language introduction
now describe both kinds of content.

The Inbox/Today/delivery suite passed **73 tests in 79.18s**
(`.tmp/road-inbox.log`). A further HTTP consent, durable fake-mail, Inbox/Today
review and authentication case passed in 3.95s (`.tmp/road-inbox-http.log`). These
include long-running closures, expired snapshots, source/mapping revocation,
future timestamps, owner/tenant isolation and a sparse page of 100 unavailable
events followed by an eligible closure. TypeScript and the initial root build
passed. After adjusting the generic Inbox heading and retaining the legal section
heading, the final root build passed (`.tmp/road-inbox-final-build.log`).

Chrome verified sparse continuation, closure facts and exact links, mute/unmute,
stale-source redaction, an explicit missing-verification warning, and shared read
state with Today. At 390px the controls remained usable without horizontal
overflow. The desktop full-document axe audit reported zero violations; shared
Marvin contrast remained incomplete. The audit was appended to the local
`test-results/accessibility/road-manual.json`; request evidence is in
`.tmp/road-inbox-browser-requests.json`. The synthetic fixture shut down cleanly.
These checks preceded the final heading/copy-only adjustment and do not establish
mobile axe, five-language human acceptance or real source coverage.

Remaining: complete the acceptance matrix and native licensed-table import once
available. Keep the actual FEDRO grant,
TMC version/coverage and permitted notification representation as named external
dependencies. Do not request a topology version inferred solely from historical
examples or treat an unsent request as access approval.

### C3 acceptance audit at this checkpoint

These are local implementation and synthetic evidence mappings. Every row still
requires the applicable real feed/topology, release and human acceptance; none is
marked fully verified in the requirements traceability register.

| Criterion | Local implementation and representative test evidence | Remaining acceptance boundary |
|---|---|---|
| AC-C3-01 saved corridors | `test_road_api.py::test_catalogue_preview_save_edit_history_archive_and_delete`; Chrome editor/lifecycle | Native licensed corridor catalogue and live owner workflow |
| AC-C3-02 closure alert | `test_road_jobs.py::test_saved_profile_to_material_history_and_explicit_clearance_preserves_identity`; Inbox and fake-mail delivery | Current permitted FEDRO closure intersecting actual reviewed TMC coverage |
| AC-C3-03 opposite/unrelated filtering | `test_road_evaluation.py::test_opposite_and_unrelated_corridor_records_are_filtered_with_real_matching` | The test uses the real matching implementation with synthetic topology, not a real licensed table |
| AC-C3-04 previous/current | Exact immutable links, previous/current reader, `test_road_today.py`; Chrome comparison | Permitted live versions and pilot review |
| AC-C3-05 planned changes | `test_road_jobs.py::test_planned_rescheduling_is_material_without_asserting_current_closure` | Actual provider rescheduling examples |
| AC-C3-06 deduplication | `test_road_jobs.py::test_source_record_replacement_and_language_editions_do_not_duplicate_material_events`; delivery owner deduplication | Current provider identity and replacement behavior |
| AC-C3-07 resolution | Explicit source clearance, cancellation, expiry and missing-state distinctions in evaluation/jobs tests | Official live clearance semantics; never infer physical road safety |
| AC-C3-08 evidence | Source/history retention and revocation tests in `test_road_sources.py` and `test_road_jobs.py` | Actual retention/display/notification grant and native TMC rights |
| AC-C3-09 materiality | Profile validation/preview, numeric congestion thresholds, planned preferences and worker band tests | User validation of route/materiality settings |
| AC-C3-10 history | Owner-scoped immutable history and exact links, permission rechecks and sparse cursors | Live history under retention policy and human acceptance |
