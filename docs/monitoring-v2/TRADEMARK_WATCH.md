# Trademark & IP Watch — B7

## Reviewed deadline feature — 14 September 2026

MV2-048 connects explicit private domicile/calendar selection to a reviewed rule
registry, source-specific publication mapping, calendar-month arithmetic, current
candidate/history/Today/Inbox readers and the inspected counsel packet. All nine
sections remain enabled and visible. No production rule, calendar, source approval
or IPI credential is manufactured by this implementation.

The [IPI guidelines](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/d/richtlinien_marken/Richtlinien_Marken_D_2025.pdf)
were checked on 14 September. The filename says 2025 but the cover is dated
1 January 2026. Part 1 §§5.5.2 and 5.5.6 (printed pages 34 and 37) describe
calendar-month arithmetic, non-working-day extension and the exclusion of
day-based suspensions for month-based periods. Part 6 §2.5 (printed page 251)
distinguishes national publication from the relevant international CH-extension
publication in the WIPO Gazette. National publication anchors on the publication
day; international publication on the first day of the following month. Both add
three calendar months, clamping a missing final-month day. Weekend or explicitly
recognized holidays advance to the next working day, with reviewed coverage for
every examined day. The user chooses the relevant party/representative domicile;
device location, profile language and a guessed canton never determine it.

This lookup is implementation evidence, not operational legal approval. A dated
independently reviewed rule must map the actual source/category/office to its
applicable publication event, with reviewer reference and hashed HTTPS citations.
A WO registration event is not automatically a WIPO Gazette CH-extension event.
Missing, ambiguous, future or inapplicable events and missing/expired/revoked/
incomplete calendars produce no deadline. The guidance's two July 2022 examples,
month-end/leap-year cases, successive holidays, Zurich midnight and DST use
synthetic reviewed test inputs. UI and export always require independent legal
verification before filing or paying a fee; neither performs either action.

Immutable rule/calendar payloads and compare-and-set selections live in shared
internal tables. Migration `e7c4a56806e9` adds a registry guard and nullable
reference-only private candidate/event bindings. Old portfolios omit absent
deadline context when serialized, preserving stored hashes and idempotency.
Readers acquire a PostgreSQL shared registry lock before calibration/source locks;
registry changes use an exclusive lock. Rule/calendar/publication changes reopen
review while preserving previous decisions; daily countdown and transport hashes
do not. History pins original versions subject to current source rights and
revocations. Download reconstructs the packet under current rights: changed inputs,
historical revocation or Zurich day invalidate a previously inspected document.

Operational procedure: obtain authoritative publication mapping and complete
recognized-holiday evidence for the actual jurisdiction/date range. Validate
`DeadlineRule` / `DeadlineCalendar` inputs, including reviewer, validity, citations
and document hashes. In a dedicated registry-only transaction use
`trademark_deadlines.retain` then `select_current`, passing the previously observed
selected ID (null for the first selection); commit atomically. Use `revoke` in
an isolated registry transaction when approval is withdrawn. Do not acquire
private-monitor, calibration or source locks before registry writes. These are
internal operator functions; the authenticated public calendar endpoint is
read-only. No production selection was created by this feature.

Verification: 56 combined deadline, workflow/history, export and HTTP checks
passed (71.27s), including metadata comparison and downgrade/re-upgrade preserving
source/portfolio tables. The 60 browser checkpoints passed for the complete
portfolio→review→Inbox→history→export journey, including explicit domicile, saved
configuration, unavailable calendars, source revocation, five languages, mobile
overflow and three axe audits with zero violations. Browser responses are
synthetic; real database tests prove arithmetic and download invalidation. The
isolated root build `trademark-deadline`, exact API Ruff and label synchronization
passed. Broader B7 live-source, independent rule/calendar and similarity-quality
review, release activation and human acceptance stay open. MV2-048 stays
IN PROGRESS in both index and detail.

The final boundary/backlog run passed 22 checks (4.07s), including explicit
boolean-only calendar coverage confirmation. A completed follow-up browser run
captured the actual deadline card at 390px for visual inspection; its 60
checkpoints and three zero-violation axe audits passed. No active test or
deployment was duplicated or interrupted; both owned fixture servers exited.

**Integrated publication, 13 September 2026:** The owner requested all implemented code be published to main now and all implemented sections enabled. The production defaults and remaining source/acceptance limits are recorded in the [integrated release evidence](evidence/2026-09-13-integrated-publication.md). Earlier dated references to uncommitted or disabled work are historical; the broader task remains IN PROGRESS.


## Active scope, 13 September 2026

**Complete review feature scope, 14 September:** MV2-047/048's private
source-backed candidate-to-review journey: source preview/start/pause, bounded
scheduled projection for all portfolio brands, current explained candidates,
immutable internal decisions, retained before/after changes and reopened review,
and owner-private Today/Inbox links. Retain reviewed calibration revisions and
invalidate current decisions when source/profile/evaluation evidence changes.
Exact/owner-interest matching can operate with clearly disclosed unavailable
similarity calibration; missing calibration never becomes a negative clearance
result. Source data remain in the permission-scoped journal. Public writes cannot
grant source rights or invent calibration. Include five-language desktop/mobile
readers, membership/rights/retention/CAS tests, replay/reversion/cursor tests and
the required migration/lint/build gates before publication. Native acquisition,
actual IPI terms/account/traversal/identity evidence, reviewed quality, legal
deadline rules, permitted export/delivery and human acceptance remain separate
open requirements; the full B7 direction is not complete at this feature boundary.

MV2-046/047/048 cover the complete organization-scoped brand portfolio, official
IPI publication/register evidence, explained exact/lexical/phonetic candidates,
goods/services relevance, retained decisions and changes, verified deadline
context, Today/Impact inbox, and explicit counsel-review/export actions. No filing
or external counsel message is sent by a review action. This work proceeds under
the user's authorization to finish all nine active directions; C4 stays deferred.

Dependencies include the shared profile/evidence/review contracts (MV2-043 and
the dependencies listed in each task). Tested user-facing features are published
as complete outcomes while the wider direction stays IN PROGRESS. Native source
rights and human quality/acceptance evidence remain independent gates.

## Private register review journey — 14 September 2026

Implemented source-readiness preview, start/pause and bounded scheduled journal
projection for private multi-brand portfolios. The source and calibration registries
are internal; public requests cannot authorize source use or supply thresholds.
Current exact-name and owner-interest matching can operate with an explicit
similarity-language gap. All five language readers expose the section, readiness,
runtime clocks, candidates, matching methods and explicit goods/service phrases.
Class overlap and a name candidate never establish a legal conflict or clearance.

The owner can mark reviewed/relevant/not relevant/keep monitoring/for counsel.
Each decision checks membership, ownership, current profile/evaluation/source
generation, evidence freshness and decision rights under the monitor lock. A
version/hash conflict cannot silently overwrite another review. Counsel is an
internal marker only: no outreach, filing, export, email or computed legal deadline.
Source payloads remain in the permission-scoped journal, not copied into private
events or decisions. New private tables use organization-scoped foreign keys and
the migration `b4f17235d3b6` follows `a3e06124c2a5`.

Retained material register revisions replay in order, including owner A→B→A
between checks. Changed register facts, profile or calibration reopen the review
while preserving the previous decision. Transport-only hashes do not reopen it.
Missing intermediate evidence is explicitly recorded. Owner-private Today (48h)
and Inbox link the exact event, with independently readable before/at/current
evidence and private decision history. Pagination remains bounded even when all
examined evidence is filtered. Expiry/revocation invalidates current reviews and
redacts source snapshots; visibility/focus/session changes refetch private UI.

Validation: 103 combined source, portfolio, matching, workflow, history, HTTP and
Monitoring Centre tests passed (77.52s). Two focused follow-up checks passed
(4.11s): malformed retained calibration and migration downgrade/re-upgrade
preserving source and portfolio tables. The 32 browser checkpoints cover the
existing multi-brand editor plus the complete start→review→owner change→Inbox
journey, conflict handling, private counsel marker, source revocation, all five
languages at 390px, pause/archive/delete and membership denial. Desktop, mobile
editor and mobile review axe audits reported zero violations. Root build, exact
Ruff and required backlog consistency checks are recorded at publication.
Browser data and calibration are synthetic engineering evidence, not legal
quality or actual IPI acquisition acceptance. No production source grant or email
was created by these checks.

Release activation is independent: the public main site currently reports
`git-f8a4304e658a`. This follow-up is not yet verified active. MV2-046/047/048 remain
IN PROGRESS for real IPI access, approved traversal/identity/coverage, calibrated
quality, legal deadline rules, permitted export/delivery and human acceptance.

## Current official source evidence

### Counsel packet feature — 14 September 2026

MV2-048's next complete user outcome is a permitted, owner-private evidence
packet for counsel review: prepare and inspect the exact packet, then explicitly
download it. Preparation and download independently recheck membership, current
candidate/profile/evaluation/source generation, retention and export rights for
every included source version. The retained preparation stores references and a
content hash, not licensed payload copies. Changed evidence/decision, expired
preparation or revoked rights invalidates download. The UI remains visible with
an explicit unavailable reason when source terms do not permit export. No external
recipient, email, filing or automated sending is added. Five-language desktop/mobile
readers, exact-event/current-only selection, CSRF/tenant/expiry/change tests and
the required migration/lint/build gates form the feature acceptance.

Deadline context remains a separate open part of MV2-048: it needs an approved
applicable rule, verified publication basis, calendar/timezone and calculation
trace. On 14 September the [IPI opposition page](https://www.ige.ch/de/etwas-schuetzen/marken/nach-der-eintragung/ueberwachung-und-verteidigung/widerspruch-einlegen)
and [2025 guidelines](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/d/richtlinien_marken/Richtlinien_Marken_D_2025.pdf)
were checked. National Swissreg publication and international publication must
not be conflated. No operational legal rule or holiday calendar is approved by
this lookup. The packet must preserve official source dates and explicitly state
that the calculated deadline is unavailable and requires verification. Firecrawl
CLI was not present on PATH; official pages were read through the web fallback.

Implemented and verified: explicit preparation, a sandboxed offline HTML preview
and a separate download action, all in the five UI languages. Current-only export
and selected-change export are distinct; the latter rechecks both before/after
versions under their own source permissions. A static downloaded file cannot
update or redact itself, which is explained before download. The source strings
are escaped, the document has a restrictive CSP, and its preview permits neither
scripts nor same-origin access. No source markup becomes executable content.

The private `TrademarkExportPreparation` stores only identifiers, candidate
version, locale, checksum and timestamps. It expires after 15 minutes; no more
than 20 preparations per candidate are retained without expiry cleanup. Idempotent
retries preserve a preparation; conflicting reuse is rejected. The parent lock
serializes prepare/download with review and projection. Every read/download
rebuilds the exact document and verifies its digest, current evidence, membership,
ownership and rights. No licensed packet body is retained on the server. Migration
`c5a28346e4c7` follows `b4f17235d3b6`; private organization registration is included.
Document labels are generated from authored UI translations by
`scripts/sync-trademark-export-labels.mjs`; the root i18n check rejects drift.

Evidence: 54 combined export/API/workflow/history/source tests passed (49.04s),
plus a focused old/new permission test (2.73s). This covers explicit CSRF-protected
download, stale decision/evidence, expiry, wrong hash, idempotency/conflicts,
source rights on every included version, deleted evidence, tenant isolation,
five-language HTML escaping, capacity and migration preservation. The built UI
passed 42 browser checkpoints (8.80s), including byte-for-byte equality between
the inspected preview and the explicitly downloaded test file, current-only
selection, missing rights and revocation between preview and download. The three
application axe audits reported zero violations. The packet iframe is deliberately
sandboxed; these application audits are not an independent legal review of the
document. Root build, exact Ruff, formatting, label synchronization and required
backlog consistency checks are recorded at publication. Tests use synthetic rights
and sources; no real IPI account, source grant, email, filing or counsel contact was
created. The complete B7 direction and approved legal deadline rules remain open.

At this feature boundary the main site's ready endpoint reports `git-3b48a00c92d6`,
which verifies earlier Auction tracking, Centre copy and Auction Today/Inbox.
The later reminders/email, Trademark review and counsel packet activations remain
unverified. No deployment was restarted or duplicated.

On 13 September, the [IPI data-delivery page](https://www.ige.ch/de/uebersicht-dienstleistungen/digitales-angebot/ip-daten/datenabgabe-api)
still requires signed acceptance and account access. The [terms dated 31 October
2024](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/d/Nutzungsbedingungen-Datenabgabe.pdf)
restrict credentials, mailings and downstream raw-data use. No signature,
registration, authenticated request, credential transfer or email is performed
by this implementation. A customer notification/export purpose requires explicit
review; owner/representative contact fields must never become outreach recipients.
Helvetic Lens must identify its derived assessment as its own, not an official
IPI determination or an exhaustive clearance search.

The public [technical documentation](https://www.swissreg.ch/public/apidocs/)
defines bearer-authenticated XML POST requests to
`https://www.swissreg.ch/public/api/v1`. Trademark search is paginated by returned
continuation actions; a page is not a complete acquisition. Responses distinguish
API success from HTTP status and can carry mutable document references. Quota,
concurrency and Retry-After are part of the source contract. The public schema
catalogue is `https://schema.ige.ch/xml/catalog.xml`; Swiss ST.96 extensions must
be interpreted through their actual schema, not a guessed JSON search payload.

References: [requests](https://www.swissreg.ch/public/apidocs/reference/requests.html),
[responses](https://www.swissreg.ch/public/apidocs/reference/responses.html),
[pagination](https://www.swissreg.ch/public/apidocs/getting-started/full-traversal.html),
[limits](https://www.swissreg.ch/public/apidocs/reference/limits.html), and
[schemas](https://www.swissreg.ch/public/apidocs/deep-dive/xml-schemas.html).
Firecrawl Developer located these official documents without credentials; the CLI
is unavailable locally, so the official pages were read using the web tool.

## Implementation and acceptance boundaries

The first local work establishes a bounded versioned portfolio/facts contract and
an explainable candidate engine. Application, publication, registration and
renewal dates remain distinct; missing mark text or goods/services is unknown.
Exact matching uses documented Unicode normalization with original strings kept.
Lexical/transliteration/phonetic features retain their method and language scope.
Similarity promotion requires a reviewed, versioned calibration contract with
training/validation evidence; synthetic thresholds are test fixtures, not measured
quality. No unsupported pronunciation or script is silently treated as a negative.

Goods/services phrase evidence and class overlap are separate. A matching class
alone never proves equivalent goods/services or legal conflict. Candidate output
is always for IP review, including an exact-name match. Independent held-out
evaluation remains MV2-051; data from that split cannot calibrate thresholds.

Required subsequent acceptance: tenant/role isolation; portfolio revisions and
idempotency; official stable IDs and immutable retained source revisions;
correction/owner/status/goods changes reopening review; source-rights rechecks;
rule/version/date-bound deadline calculations with unknown-rule abstention;
all five UI languages; source loss and review history; permitted export and
explicit delivery consent; native and human evaluation. Unavailable acquisition
never implies that no potentially relevant marks exist.

## Local implementation evidence: 13 September 2026

The unpublished implementation now includes bounded portfolio and source-facts
contracts, a deterministic explained candidate engine, owner-private portfolio
persistence and immutable configuration revisions. Migration `4dfa0b58cb4f` follows
`3ce8fa47ba3e`; the migration round trip preserves the existing hazard monitor.
The authenticated, CSRF-protected draft API enforces owner/workspace/role scope,
idempotent creation, compare-and-swap editing, bounded pagination and explicit
archive-before-delete. Its normal and exception responses are no-store. There is
no public route to inject calibration or activate a source.

Exact normalization preserves accents, punctuation and scripts while recording
the Unicode version. Reviewed calibration is required for lexical and whole-word
extension candidates. The initial phonetic method is English single-word Soundex
with a separately calibrated lexical floor; it does not establish support for
other languages, accented names or transliteration. Missing, expired or incompatible
calibration is unavailable. Goods/services evidence retains original language,
statement and phrase references separately from Nice-class overlap. Candidate
assessment never confirms infringement. Application/publication/registration/
renewal/cancellation dates and material source facts have separate fields.

The five-language portfolio UI supports multiple brands, word variants, owners,
Nice classes and goods/services phrases with explicit languages. It saves drafts,
shows revisions, preserves input on a version conflict and redacts private state
after membership denial. Monitoring Centre exposes the private draft and an exact
link only when `TRADEMARK_WATCH_ENABLED` is enabled; the flag defaults to false in
settings, Compose and environment examples. No deployment configuration was changed.
The contextual guide uses the existing English guide catalogue; the form's source,
privacy and assessment explanations are translated into all five product languages.

Verified local evidence:

- Candidate/contract suite: 37 passed (`.tmp/trademark-candidates.log`). Tests cover
  lexical/extension/phonetic examples, five goods-description languages, script and
  calibration uncertainty, comparison budgets, material changes and strict input.
- API/repository/Compose plus predecessor migration regression: 11 passed
  (`.tmp/trademark-integration.log`). An earlier test found exception responses
  missing no-store; the shared middleware now covers the trademark prefix.
- Monitoring Centre regression: 18 passed (`.tmp/trademark-centre.log`), including
  same-workspace peer isolation, disabled metadata and absence of invented polls.
- Exact API Ruff gate passed. Root `npm run build` with isolated output
  `HELVETIC_LENS_CHECK_BUILD=trademark-drafts` passed after adding the missing route
  guide and correcting a nested main landmark (`.tmp/trademark-build-accessibility.log`).
- Disposable synthetic browser fixture: 17 checks passed, including conflict input
  retention and mobile forms in all five locales. Desktop/mobile axe scans report
  zero violations; the existing Marvin contrast node remains an incomplete check.
  Desktop and mobile captures were visually inspected. Evidence is in
  `test-results/accessibility/trademark-browser-checks.json`, `trademark-audit.json`
  and `trademark-{desktop,mobile}.png`. The owned fixture and browser exited.

These are local draft and engine checks, not native IPI acceptance or measured
candidate quality. At this checkpoint, the native XML adapter, source-rights journal, ingestion,
candidate lifecycle/review, deadline-rule trace, register-change reopening,
Today/Inbox integration and permitted delivery/export still require implementation.
Signed access, current coverage, reviewed calibration and independent human
evaluation remain outstanding. MV2-046/047/048 remain IN PROGRESS; no fragment was
committed, pushed or deployed.

## Register journal and native-contract investigation: 13 September 2026

The next unpublished implementation adds `trademark_sources.py` and five shared
permission-scoped tables in migration `5efb1c69dc50` after `4dfa0b58cb4f`. Reviewed
policy fingerprints bind the endpoint, allowed register origins, accepted/expiry
times, acquisition/storage/matching/display/decision/notification/export purposes
and retention. Recording a synthetic policy for tests is not acceptance of IPI terms.
There is no public policy-write, source-ingestion or credential endpoint.

Each accepted record binds complete normalized facts to a raw hash, exact request
endpoint, permission generation, ordered cursor and idempotency receipt. Atomic
savepoints and compare-and-swap prevent partial writes and stale responses. Register
identity combines the supplied official ID with its national/CH-designating origin.
An upstream adapter must still prove the publisher's stable identity; this internal
key does not independently establish it.

Material revisions preserve earlier owner/representative/status/goods/date facts,
including reversions. A transport-only change has a new evidence revision with the
same material sequence. Repeat observations do not extend earlier content TTLs;
reacquisition after expiry creates fresh evidence. Switched/reselected permission
generations do not inherit current records. Historical readers recheck purpose,
expiry, revocation and content hashes. Current pages distinguish stale/unavailable
records and always report coverage unverified. No page is a completed traversal.

Revocation and expiry erase raw/normalized content while retaining approved minimal
hash/sequence/receipt audit. Expired incoming raw bytes are never written; entirely
expired normalized input is rejected. Bounded record sizes, journal rows, receipts
and retained bytes fail closed. A minute cleanup worker runs even with the feature
disabled. Later private candidate projections must join this purge boundary before
they are introduced; no such private event copies exist yet.

Verification: source-journal plus private-repository/migration tests passed **33**
in 10.50s (`.tmp/trademark-source-journal-final.log`), covering immutable changes,
replay/conflicts, generation replacement, purpose denial, expiry/revocation, hash
corruption, database scope constraints, capacity rollback, pagination, stale records
and real cleanup-task execution while disabled. Initial run had 29 passes and one
test-only error (`DomainError.status_code` instead of `.status`); corrected and rerun.
Exact API Ruff passed. No frontend changed in this step.
The authenticated draft API and backlog invariant also passed (3 tests, 5.07s,
`.tmp/trademark-source-api.log`) against the new migration head.

Public protocol evidence is retained locally in `.tmp/ipi-source-contract/`:
official core/common/trademark/Swiss ST.96 schemas, catalogue, and the public
`TrademarkSearch_ReferenceMaterial.zip` field mapping, parsed as `mapping.json`.
These are investigation inputs, not live API responses or redistributed fixtures.
The [TrademarkSearch documentation](https://www.swissreg.ch/public/apidocs/reference/action-trademark-search.html)
requires `Maximal` detail for full goods/services; `Default` omits them. The source
mapping distinguishes application, registration, publication, termination and
protection expiry. Publication history includes reason-specific register changes;
the latest arbitrary publication must not silently become a new-registration date,
and protection expiry must not be labelled a renewal date. The mapping uses `CH`
for national records and `WO` for international registrations designating Switzerland.
Owner information is supplied in ApplicantBag, rather than inferred from licensees.

Remaining work at this journal checkpoint included the actual XML/ZIP adapter, stable native item identity,
publication-event normalization, completed-traversal proof, collection, private
candidate/review/lifecycle/deadline workflows, Today/Inbox, allowed delivery/export,
reviewed calibration and human acceptance. This journal is not a source activation
or a completed B7 feature. All three tasks remain IN PROGRESS and unpublished.

## Offline native codec: 13 September 2026

`ipi_protocol.py` now builds a profile-free ascending full-traversal request with
Maximal detail and embedded items. It decodes a single TrademarkSearch response in
XML or bounded ZIP form, checks both HTTP/action success, request correlation,
counts/offsets, result layout and the NextPage continuation. An empty intermediate
page keeps its continuation. Incomplete, linked-only or ambiguous item data cannot
be reported as an empty successful search. Response/document hashes are distinct;
images/resources are never fetched or extracted. XML byte/node/depth limits and
DTD/entity rejection apply, alongside ZIP count/size/path/duplicate checks.
Retry-After supports both documented forms. Actual collection/poll scheduling is
not implemented by this offline codec, and it never claims verified coverage.

`ipi_trademarks.py` reads the Swiss ST.96 V7_1 document and exact namespace paths,
retaining original names, application/registration numbers, optional goods language,
Nice-class evidence and register publications. It distinguishes CH from the IPI
channel's CH-designating WO records. Multiple official number aliases are returned
to a future durable identity resolver; response-local Data IDs are not accepted as
stable register identities. Selecting a business alias is explicit and validated
against the record. Publication dates are not interchangeable with registration,
action, expiry or cancellation dates; ambiguous new-registration publication dates
remain unavailable. A publication event retains its reason and change text. Renewal
is not inferred from protection expiry. Partial/unlabelled goods and unresolved
parties remain unknown; significant verbal elements are not substituted for a missing
full mark. Unknown/non-Nice classifications are not silently converted to Nice codes.

The facts contract now retains number aliases, publication events, action dates,
expiry date and an optional parent-document hash. That parent hash is provenance,
not a material change. Missing goods language is represented explicitly as unknown
and cannot establish a same-language phrase match. These changes are unpublished;
there are no production B7 source records to migrate.

Evidence:

- Native codec, matcher and journal: 112 tests passed (`.tmp/ipi-native-codec.log`).
  The subsequent parent-hash integration run again passed those 112 tests; its two
  new integration tests initially used a wrong assertion key (`decision_id`). After
  correcting that test key to `decision_sha256`, both passed in 1.93s
  (`.tmp/ipi-native-journal-final.log`). The integration uses real journal storage
  and an explicit synthetic identity alias, not a live collector or identity resolver.
- The two integration cases prove native XML to journal to candidate assessment,
  owner-change history and decision revision, and parent-document refresh producing
  new evidence without a new material candidate. Rights are synthetic fixtures.
- The generated request, native trademark fixture and response were all validated
  against the official cached XSDs using .NET XmlSchemaSet. The custom resolver only
  accepts the locally cached schema URL map and performs no network access. The
  validation helper is `.tmp/validate-ipi-schemas.ps1`; fixture inputs and dependency
  schemas remain in `.tmp/ipi-source-contract/`. This proves schema conformance of
  fixtures, not live endpoint coverage or completeness of every publisher layout.
- Exact API Ruff and whitespace checks passed. No frontend changed or deployment
  was started in this step.

Next required work is durable business-identity resolution, retention-bound parent
response evidence, atomic page/continuation checkpoints and completed-traversal
proof, the permitted HTTP collector, then the private candidate/review/deadline/
lifecycle/Today/Inbox and delivery/export workflows. Source accounts, actual source
approval, calibration and human acceptance remain open. No incomplete feature was
committed or pushed; MV2-046/047/048 remain IN PROGRESS.

## Deadline feature scope — 14 September 2026

Implement the complete MV2-048 review-deadline journey: immutable reviewed rule
and jurisdiction-calendar registries, explicit private domicile-calendar context,
auditable month/end-of-month/working-day calculation, date-based days remaining
in Europe/Zurich, and evidence in candidates, history, Today/Inbox and exports.
Registry updates/revocation must invalidate an obsolete inspected packet and reopen
affected candidate review without sending or filing anything. Missing evidence
must remain visible and unavailable. Old portfolios must retain their identities
and hashes when the new optional context is absent.

Primary-source review on 14 September:
[IPI guidelines](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/d/richtlinien_marken/Richtlinien_Marken_D_2025.pdf),
Part 1 §§5.5.2/5.5.6 and Part 6 §2.5, printed pp.34/37/251. The document's cover
says 1 January 2026 despite its URL filename. National publication and international
CH-extension Gazette publication have different anchors. Month-based periods use
calendar arithmetic; recognized holidays depend on the party/representative
domicile and must not be inferred from a user's browser location. The implementation
will require a reviewed source-field mapping and a complete applicable calendar,
not assume that every IPI WO publication is the Gazette protection-extension event.
No production legal rule or holiday calendar has been independently approved.

Acceptance checks include national/international anchors, leap/end-of-month dates,
weekends/consecutive holidays, incomplete calendar ranges, DST/local-midnight day
counts, changed/revoked rules, publication corrections, historical evidence,
legacy-hash compatibility, private ownership and export revalidation. Five-language
browser presentation and whole-feature API/build checks precede commit and push.

## Native acquisition feature scope — 14 September 2026

Before implementation: finish MV2-046's native IPI ingestion through the existing
private candidate/review journey. This includes durable business aliases, atomic
page admission, retained parent response hashes and bounded licensed payloads,
restartable opaque continuations, source-generation and worker lease checks,
publisher backoff, scheduled permitted HTTP collection and visible acquisition
readiness. Validation must exercise interrupted/replayed pages, bad later items,
identity conflicts, repeated records, permission changes, retention expiry and
native pages reaching private candidates without crossing workspace boundaries.
No backend-only checkpoint is a publishable completed feature.

The official [traversal contract](https://www.swissreg.ch/public/apidocs/getting-started/full-traversal.html)
was rechecked on 14 September. Ascending LastUpdate traversal can repeat updated
records; completion is not a consistent snapshot. Preserve duplicate and changing
total evidence instead of rejecting every legitimate repeated record or claiming
complete Swiss coverage. The [usage limits](https://www.swissreg.ch/public/apidocs/reference/limits.html)
require Retry-After compliance; use one collector request at a time. The cached
common XSD supports explicit timezone-aware LastUpdate bounds, but no incremental
coverage claim is authorized without verified update/deletion semantics.

Dependencies remain the existing journal, native codec, reviewed source permission
and private workflow. Signed IPI access, real credentials, both requested register
origins, production retention capacity, source coverage and reviewed calibration
are unverified. Synthetic grants do not authorize production collection. All nine
sections remain visible and enabled; missing prerequisites appear inside IP Watch.

### Native acquisition implementation and verification

The native collector now connects the official IPI protocol to the existing
private portfolio, candidate, review and material-change journey. It claims one
durable source lease, commits before HTTP, rechecks current rights before and
after network access, and atomically admits the entire decoded page. An invalid
later item rolls back earlier identities, journal records and cursor movement.
Response-local identifiers never identify trademarks. Retained business-alias
hashes resolve stable identities; conflicting identities or a missing previously
selected canonical alias require attention instead of an invented merge.

Parent response bytes and SHA-256 evidence, XML hashes, contiguous offsets,
opaque continuation checkpoints, repeated identities and publisher total changes
are retained. Replayed admission is idempotent; stale leases, changed permission
generations, wrong request IDs and continuation cycles cannot advance the journal.
An expired continuation starts an explicit abandoned state before a fresh traversal.
Finished traversal always remains distinct from verified coverage or a snapshot.
The source link opens Swissreg with the official identifier displayed alongside
the facts; no unverified record deep link is fabricated.

Authentication follows the official
[IPI OIDC contract](https://www.swissreg.ch/public/apidocs/reference/authentication.html):
fixed identity-provider origin, access-token reuse, renewal before refresh expiry
and a new session when refreshed lifetime shortens. Shared tokens are encrypted
with the existing deployment credential cipher, protected by a renewal lease and
purged after expiry. Passwords, tokens and transport bodies never enter status
responses or error messages. No redirect receives a token, password, private brand
query, inherited cookie or injected HTTP-client authentication.

Production configuration enables `IPI_SOURCE_ENABLED` by default. Operators must
provide `IPI_USERNAME`, `IPI_PASSWORD` and a selected
`IPI_SOURCE_PERMISSION_ID` for an actual approved account and reviewed policy.
The full-register query requires permission for both national CH and the IPI
channel's CH-designating international records; checkpoint retention must exceed
the 120-second lease. The collector runs every five seconds, performs at most one
page per tick and obeys durable source/account backoff. Ordinary new traversals
respect the policy's minimum polling interval. Changing local permission
generation does not bypass a publisher waiting period. Sixty-second maintenance
removes expired/revoked parent and continuation bytes even when collection is
disabled, along with expired encrypted token payloads.

The authenticated read-only `/api/trademark-watch/source-status` endpoint and
five-language IP Watch panel expose missing access, retrieval progress, counts,
completion, interruption and next eligible attempt. Refreshing the panel does
not start collection. Source credentials and lease/request bodies are not exposed.
The section and saved private portfolios remain available while access is missing.

Validation:

- The combined protocol/journal/private API/workflow/configuration/backlog run
  passed 120 checks; its one failure was an old exact cleanup-result assertion.
  The final affected acquisition/HTTP/journal run passed all 55 checks in 19.63s,
  including the corrected cleanup contract and a new disabled-worker purge test.
  Additional transport/auth/count/authentication boundary checks passed separately.
  Logs: `.tmp/ipi-feature-final.log`, `.tmp/ipi-affected-final.log`,
  `.tmp/ipi-boundaries-final.log`. Earlier Compose expectation of preview-only
  sections was updated to the already implemented available-to-configure behavior;
  collectors still prove missing inputs do not trigger network requests.
- The real native-page → private candidate → decision → corrected owner →
  reopened review test passed, with peer-user and other-workspace denial.
  Migration `d6b39457f5d8` creates six acquisition/cache tables; metadata and
  downgrade/upgrade checks preserve private portfolios.
- The root build with `HELVETIC_LENS_CHECK_BUILD=ipi-acquisition` passed, including
  i18n, shell, resources, reports, help and web compilation. Generated build-only
  type/tsconfig edits were restored after the owned check terminated.
- The browser journey passed 49 checkpoints, including seven IPI status checks
  and the existing 42 private review/export checks. All five languages and mobile
  layouts were exercised; three application axe audits reported no violations.
  All local fixtures used synthetic responses and terminated after verification.
  Exact API Ruff, changed frontend formatting and whitespace checks passed.

This is implemented acquisition, not real IPI account activation or acceptance of
all B7 requirements. No signed terms, actual credentials, production grant,
full-catalogue sample, independent calibration, approved legal deadline rule or
human pilot acceptance was created. Production volume/retention sizing remains
unverified: the parent-evidence budget is 512 MiB, page payloads are bounded at
32 MiB, a traversal at 100,000 pages and aliases at 4,000,000 per source. Existing
journal revision/receipt/storage limits also apply and fail explicitly. These
limits must be validated against the licensed catalogue before full-coverage
acceptance. Incremental update/deletion semantics remain unverified. MV2-046,
MV2-047 and MV2-048 remain IN PROGRESS.
