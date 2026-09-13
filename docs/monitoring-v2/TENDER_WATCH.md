# Tender Watch — B2 implementation

**Integrated publication, 13 September 2026:** The owner requested all implemented code be published to main now and all implemented sections enabled. The production defaults and remaining source/acceptance limits are recorded in the [integrated release evidence](evidence/2026-09-13-integrated-publication.md). Earlier dated references to uncommitted or disabled work are historical; the broader task remains IN PROGRESS.


Status: IN PROGRESS, 12 September 2026. The user authorized completion of all
nine active scenarios, with customs/C4 still deferred. Work uses one agent/main;
complete the feature, verify it, then commit and immediately push. No tender
capability is enabled by this document or by isolated contract tests.

## Scope and dependencies

Deliver MV2-042/045 and the tender-specific contributions to MV2-043/044:
private company profile → explained discovery → follow dossier → authoritative
evidence → internal Bid/No-bid/Monitor → material revision → reopened review →
digest. Preserve every AC-B2-01…12. Business ranking must keep hard exclusions
and unknown qualifications explicit; optional semantic ranking cannot supply
unsupported eligibility or override deterministic exclusions.

Existing ownership, membership, consent, source policy, exact document evidence,
jobs/outbox and review primitives are the dependencies. A tender implementation
does not complete their broader shared parent tasks. Source permission for
restricted content is an independent acceptance requirement, not inferred from
public search access. No bidding, interest declaration or Q&A submission is part
of this read-only monitoring feature.

## Current source evidence

- The [official OpenAPI](https://www.simap.ch/api-doc) version 1.5.1 defines
  `/api/publications/v2/project/project-search`, cursor `lastItem`, and public
  publication details linked by project and publication UUIDs.
- Anonymous official requests for search `software` and one returned publication
  detail both returned HTTP 200 on 12 September 2026. Real responses are retained
  in ignored local research files; this establishes public fields only.
- [SIMAP's conditions](https://www.simap.ch/en/about/legal) require third-party
  distribution no earlier than 08:00 Europe/Zurich on publication day; preserve
  original content, distinguish commentary and provide the required notice.
- Public `hasProjectDocuments` is an availability hint, not document permission.
  Authenticated documents and Q&A, a dedicated API client and their permitted
  capture/versioning remain unverified. Registration is prepared using the
  authorized project mailbox. The owner reported completing registration on
  12 September; authenticated API-client/document access is not yet verified.

## Document-set contract work — MV2-044

Implement source-independent immutable observations and reconciliation before
connecting authenticated document fetches. This does not download restricted
content or approve access. Stable provider item IDs identify files/Q&A/conditions;
ephemeral download URLs must not become identities or retained evidence links.
Only permitted stored snapshots can supply content fingerprints and exact links.

Reconciliation must preserve the last known content identity across 403/outages,
distinguish explicit withdrawal from removal established by a complete listing,
and never infer removal from partial pagination. Reordering, polling timestamps
and renewed download tokens do not cause material changes. A replacement during
an access outage must still compare against the last known content once access
returns. Failed OCR is an incomplete comparison, not unchanged requirements.

## Complete feature acceptance

Before publication, verify public and permitted authenticated source samples,
08:00/DST and delayed-publication handling, stable dossier/lot/version identity,
profile preview parity and explained exclusions, private lifecycle/history,
deadline/document/Q&A changes reopening reviewed dossiers, internal decisions,
digest delivery, cross-user/organization denial, five-language accessible/mobile
UI, migrations/jobs/replays, full API Ruff, affected tests, frontend build and
browser journeys. Live activation and human acceptance remain separately recorded.

Without permitted document/Q&A capture and comparison, AC-B2-08 and part of
AC-B2-06 remain open. Public metadata alone cannot complete B2.

## Local verification — 12 September, 18:28 UTC

`simap_sources.py` now provides a bounded anonymous official client and parsing
boundary for search and publication details. The client follows no redirects,
adds no authentication, restricts detail requests to UUID paths, bounds decoded
responses and retains Retry-After cooldowns, including HTTP dates. Nonfinite JSON
numbers and malformed identities fail closed. Search preserves a continuation
when the permitted page is empty, reports when withheld records need reconsideration,
and checks lot-level publication dates before releasing a project. Deadline
parsing preserves source offsets and treats ambiguous/nonexistent local times or
date-only values as unknown rather than inventing a deadline instant.

The implemented client/parser successfully read **20 public search results and
one corrected publication** from the actual official API. The corrected item
retained its dossier UUID and correction reference, and its 16 October 2026
15:00 +02:00 offer deadline resolved to 13:00 UTC. The source did not indicate
documents in this anonymous response; this is not proof that no tender documents
exist or are licensed. [Public source proof](evidence/mv2-042-public-source.json)
contains the exact IDs, clock, scope and response hash, with no credentials.

`document_sets.py` now implements immutable, privately scoped observations and
reconciliation. Content access and withdrawal/removal are independent states.
The last known content snapshot survives an access outage for comparison after
recovery, subject to the eventual reader's current rights. A complete listing can
prove removal; partial pages and denied reads cannot. Baseline capture is silent,
while first visibility after an incomplete baseline is labelled discovery.

**20 document-set tests and 22 SIMAP tests passed**, plus the backlog integrity
test and the full `ruff check services/api deploy/release_manager.py` gate.
The initial backlog index/status mismatch was corrected and its check rerun.
Tests cover document additions/replacements/withdrawal/reinstatement, 403/gaps,
OCR failure, scope isolation, idempotency, publication/DST gates, corrections,
pagination, invalid data, source errors and response bounds.

These are unfinished local components of the whole B2 feature. Private database
persistence, profile/ranking, jobs, document authorization, user workflow, digest,
frontend/browser and live acceptance are still required. No B2 endpoint or UI
has been enabled, no B2 commit has been published, and MV2-042/044 remain
IN PROGRESS rather than DONE.

## Local profiles and dossier persistence — 12 September

`tender_contracts.py` validates private company profiles, exact and explicit
phrase-variant capabilities, CPV interests/exclusions, contract cantons, offer
languages, authority scope, CHF contract ranges and declared qualifications.
Deterministic matching cites exact source locators and distinguishes missing
company qualifications from declared gaps. Neither outcome asserts legal
eligibility. Semantic scoring remains disabled; no default score of 70 is used.

The official CPV search API supplies nested parent edges. Descendant matches and
exclusions use those edges and retain the taxonomy hash; numeric code prefixes
are not treated as proof. Missing taxonomy cannot bypass a CPV exclusion.
`simap_tender_facts.py` separates lots, uses contract addresses rather than an
authority's headquarters, preserves unknown unstructured locations and scopes a
lot-specific award to that lot. Original source JSON remains separate from the
normalized text used for matching and comparison.

The saved real SIMAP publication was successfully projected into **13 separate
lots**, and an explicit Software Engineering phrase matched exactly one lot.
A fresh anonymous official CPV lookup verified the ancestry of 72212000 through
72000000, 72200000 and 72210000. [Projection proof](evidence/mv2-043-lot-projection.json)
distinguishes the retained publication sample from the live taxonomy lookup.
The sample provides project-wide CPV but no explicit lot CPV; the implementation
does not copy the project classification into each lot as confirmed evidence.
The complete discovery UX still needs to expose this project-level context
without inventing lot relevance or silently losing CPV-only candidates.

The additive `e5b7cf26098d` migration introduces private monitors, immutable profile
revisions, stable per-project/lot dossiers, evidence versions and internal
decisions. The central organization guard includes all five models. Repository
operations recheck current membership and owner scope; edits/reviews use version
checks, and exact creation/decision retries do not overwrite later work.
Readers recheck source publication time and stored evidence fingerprints.

Worker-only public observation ingestion retains late evidence without rewinding
the latest source publication, deduplicates exact versions and updates an existing
dossier even when its award/status no longer qualifies for new discovery.
Deadline and published requirement changes reopen review while retaining the
earlier internal decision and its reviewed evidence sequence. Presentation-only
changes keep the review closed. Missing fields are coverage changes, not proof
that requirements were removed. Atomic savepoints prevent partial writes when a
later lot conflicts. No bid, expression of interest or Q&A is submitted.

**153 affected tests passed**, including matching/source boundaries, private
profile/dossier/review persistence, the document-set and transport contracts,
existing Monitoring ownership/migration regressions and backlog integrity. The
full API Ruff gate passed after correcting two import-format findings.

This remains uncommitted whole-feature development. There is no B2 HTTP/UI
activation yet. Durable collection with leases and late-publication recovery,
source-policy integration, current authorized document/Q&A capture, semantic
schema/evaluation under a disabled flag, accessible five-language UI, consented
digest delivery and live/human acceptance are still required. The private
ingestion function is not an HTTP endpoint or a substitute for source approval.

### Followed-publication source checks

The anonymous official project header successfully identified one current
publication shared by all 13 lots. A lot-scoped history request returned the
original 6 August publication behind the 12 September correction. The first
unscoped history request failed; its HTTP status was not captured, so no status
code or access requirement is inferred. For projects with lots, the collector
must use the source's lot UUID when requesting history. These calls perform no
vendor action, subscription, bid or expression of interest.

CPV-only search returned 20 actual projects after omitting the unused optional
`search` parameter; sending an explicit empty `search=` had failed. The client
now omits that parameter for CPV-only discovery. Header/history parsing preserves
publication gates and lot identities, deduplicates a shared publication, rejects
conflicting references and ignores vendor actions/submission fields. Display lot
numbers are not converted into invented UUIDs.

[Follow-source evidence](evidence/mv2-042-follow-source.json) distinguishes the
retained successful header/history responses from the fresh CPV search and
records the unsuccessful probe forms. The expanded source, matching and private
repository set passed **93 tests**; the prior 153-test broader regression set is
recorded above. Durable source jobs and the complete feature remain unfinished.

## Durable public collection — local implementation

`tender_scan.py` and `tender_jobs.py` now implement persisted private checkpoints,
one bounded work item per durable job, source-request leases and retries. The
existing outbox/service executor and scheduler dispatch `tender_refresh` jobs.
Both job listing and direct job read/cancel/retry enforce the monitor's owner,
including peers in the same organization. Job payloads contain only the monitor
version; private profile/search data stays in an organization-scoped collection.

The unpublished additive migration now contains eight tables: the five profile,
dossier and decision tables above, private collection state, a shared source lease
without private content, and a cache of public official CPV ancestry. The source
cache is reverified after seven days. A real simultaneous-writer test proves only
one worker can acquire the initial shared source lease; schema comparison verifies
that the migration agrees with the models.

Discovery uses an explicit **90-day newest-publication window**, rerun from the
first page every six hours rather than advancing a permanent watermark. A cycle
processes at most 100 pages per query, 2,000 pending items and 5,000 deduplication
keys; reaching a bound reports partial coverage. Future publication gates cause
a new overlapping cycle at the permitted instant. Older publications outside the
discovery window are not claimed covered; followed dossiers use their project
header and lot-scoped history independently of discovery query matches.

Search references restrict discovery to the source's latest publication for each
lot. Historical reads cannot create new opportunities, and an older shared tender
publication cannot reopen an already awarded lot merely because another lot is
still open. The queue's apply step is bound to the publication, exact source hash
and requested lot scope; distinct lot scopes of one publication are not collapsed.

The shared request budget permits one request at a time with at least two seconds
between completed requests. This is an application limit, not an asserted official
quota. Source Retry-After values, including a two-day cooldown, take precedence.
Failed requests preserve the cursor. Three failures for one work item record a
coverage gap and let other work proceed; the next overlapping cycle revisits it.
Cancellation preserves the checkpoint. Paused/revised monitors, revoked membership,
disabled source policy and replacement lease tokens prevent an in-flight response
from being applied. Network I/O holds no tenant transaction.

`TENDER_WATCH_ENABLED` and `SIMAP_PUBLIC_SOURCE_ENABLED` both default to **false**.
The latter covers anonymous public publication data only; it does not authorize
documents or Q&A. No production environment or source approval was changed.
This is local implementation, not an activated or completed B2 feature.

A [bounded real-source rehearsal](evidence/mv2-042-durable-source-probe.json) in a
fresh isolated database executed three collector steps: search, publication fetch
and application. It retained one private evidence version and left 22 work items
pending at the deliberate rehearsal boundary. The script terminated normally;
there is no background collection running from that probe. This proves the start
of an actual source-to-storage path, not a completed scan or user acceptance.

The 19 collector tests passed, including real durable service dispatch through the
application, HTTP job privacy, source errors, cursor/gate recovery, same-publication
lot scopes, taxonomy caching, cancellation and concurrent leases. Remaining work
includes the private HTTP/profile/dossier UI, project-level CPV context, optional
disabled semantic schema/evaluation, permitted document/Q&A capture and comparison,
consented digest delivery, retention/current-rights checks, and full live/human
acceptance. These source and persistence components remain uncommitted until the
whole feature is ready.

The final affected regression set passed **128 tests**, including the existing
durable jobs, Air job privacy and additive-migration checks, all tender/source
tests and backlog integrity. Full API Ruff passed. A temporary fixture-import
lint issue and test indentation error were corrected before these final results.

The storage duplication identified at that checkpoint is resolved by the update
below. Retention and current-rights policy remain a separate acceptance gate;
deduplicating a bounded HTTP response alone does not bound lifetime storage.

## Local public journey — 12 September, 20:45 UTC

The unpublished additive migration now creates eleven tender tables. One public
publication snapshot is shared across private lot versions, and content-addressed
normalized fields share common conditions while preserving each version's exact
locator. Private version/field references have tenant-consistent foreign keys.
Readers reject missing or changed field evidence; referenced public evidence
cannot be deleted. Two tenants can reuse a public original while profiles,
dossiers, references, assessments and decisions remain private. No serving
database was migrated; earlier isolated rehearsal databases retain their original
unpublished schemas and must not be reused in place.

`tender-deterministic-v2` retains project CPV context when a publication does not
classify its individual lots. It is explicitly **unverified lot relevance**, never
a lot match or eligibility assertion. Explicit incompatible lot codes do not
inherit the project's match; hard exclusions and unknown exclusion coverage
still take precedence. Source taxonomy is required for descendant context.
An unknown/invitation phase cannot create a discoverable opportunity.
The [retained real 13-lot publication replay](evidence/mv2-043-project-context.json)
produced 13 context-only review candidates for a synthetic CPV-only profile,
zero explicit lot classifications and zero asserted verified lot matches. It
made no new source request and does not represent the user's company profile.

A profile revision can create a new assessment of an unchanged publication.
The source original remains shared, while the private version records its exact
profile revision and reopens review. Older Bid/No-bid/Monitor decisions remain
bound to the evidence sequence that was actually reviewed. Retrying an older
decision does not review new evidence.

`/api/tender-watch` exposes authenticated profile checks, idempotent creation,
draft/paused editing, start/pause/resume/archive/delete, private dossier lists,
following, internal decisions, profile/version history and exact evidence reads.
Normal CSRF, current membership, owner and source switches apply. A shared API
rate bucket bounds reads and mutations independently of resource IDs. Starting
requires the public-source switch and at least one executable discovery query;
the profile check is explicitly not a live source preview. Pause/delete cancel
pending work, and in-flight collectors recheck the monitor version. No endpoint
accepts caller-supplied source evidence, sends a message or submits a bid.

Discovery cards and version indexes query bounded stored projections without
hydrating full publication snapshots or shared terms. Exact source bodies remain
available separately. The five-language `/tender-watch` reader provides settings,
filters, deadline/source/decision review, following and history. Source extracts
are rendered as inert text on demand, with explicit truncation and an original
download. Dates use Europe/Zurich for source deadlines, including a Swiss-format
fallback for Romansh. Changing the active user/workspace remounts private state.
Monitoring Centre includes owner-private tender metadata and a source-gated
entry; the original nine-scenario count and C4 deferral are unchanged.

The SIMAP legal page failed to render during re-verification, so its documented
anonymous `/api/static/v1/pages/about` endpoint supplied the current published
API terms. The required section-5 notice is included verbatim in supplied
languages; Romansh displays the authoritative German notice with `lang="de"`.
Original data and Helvetic Lens assessments remain distinct. This read did not
register an account, accept paid services or establish restricted-content rights.

Verification:

- **159 API tests passed** across public source parsing, matching, private
  storage, collector/jobs, HTTP lifecycle and document-set reconciliation.
- After final profile/centre/UTC changes, **65 affected API tests passed**,
  including the existing Monitoring Centre cases. Exact full API Ruff passed.
- Production Next.js build and TypeScript passed. All frontend prechecks passed;
  the new route's missing contextual guide was added before the final guide gate.
- **4 reader tests passed** for language fallback, bounded large/deep source
  extracts, non-mutation of originals and inert markup.
- The built synthetic browser journey passed profile check/save/start,
  following, decisions, material review, failed-evidence recovery,
  pause/edit/resume, five locales, mobile layout and viewer/source gates.
  Its **7 full-document axe checkpoints** passed all reported violations.
  The existing Centre browser suite passed **8 checkpoints** and its navigation,
  private pagination, revocation and disabled-source checks. Other axe incomplete
  findings remain retained for manual review, not a blanket accessibility claim.
- Browser images and detailed accessibility reports are in ignored local
  `test-results/`; these are synthetic tests, not live production/user acceptance.

This public-data path is still **uncommitted and disabled in production**.
Do not mark MV2-042/043/044/045 DONE or publish a technical substep as the complete
B2 feature. Remaining required work includes retention/current-rights handling,
permitted document/Q&A capture and comparison, consented digest delivery,
semantic schema/evaluation where specified, and live/human acceptance. Source
registration was subsequently completed by the owner, as recorded below. The
pending IPI inquiry was not sent and its automatic-review approval request remains open.

## Local storage and source withdrawal policy — 12 September 2026

The public Tender Watch implementation now has application budgets of 2 GiB
of canonical UTF-8 JSON public payloads and 10,000 private evidence versions per
monitor, configurable through `TENDER_PUBLIC_STORAGE_MAX_BYTES` and
`TENDER_MONITOR_MAX_VERSIONS`. These are application defaults, not SIMAP licence
limits or physical PostgreSQL/WAL/disk capacity estimates. The shared accounting
mutex contains no private owner, query or decision data. Content reused by lots
or tenants is counted once; private version count limits are separate.

Capacity exhaustion rolls back the whole publication, including all lots and
accounting reservations, and preserves the precise collector work/buffer. It
records `storage_capacity` and retries after six hours; increasing capacity lets
the same buffered evidence proceed without a second source fetch. Existing
decisions and all referenced historical originals/fields remain pinned. No
telemetry compaction, age threshold or capacity event deletes those references.

Scheduled cleanup removes at most 100 **unreferenced public payloads** per pass,
and only when captured more than seven days ago. The reference check spans all
tenants, even when called from one organization's session; foreign keys remain
the final guard. This threshold is a local orphan-cleanup policy, not a retention
period imposed by SIMAP and not seven days from the last reference deletion.
Owner deletion continues to remove private rows through normal cascades. This
policy does not claim to bound other domains, backups or all deployment storage.

An operator-only durable restriction registry can deny a project or publication.
It cannot grant restricted document/Q&A access. Detail/original reads, projected
cards/history, decisions, collection before/after I/O and ingestion recheck it.
A newly permitted publication cannot reuse a restricted old original for a diff.
Collection retains its checkpoint and reports `source_rights_unavailable` rather
than silently skipping blocked evidence. Source switches still govern acquisition;
turning a switch back on cannot override a recorded restriction. No public API
can create/lift restrictions. Lifting a restriction or a rights-driven purge
requires separate reviewed operator handling; retained evidence must not be
misrepresented as a substitute for required permitted comparison rights.

The owner reported completing the SIMAP and transport registrations. Transport
sign-in is confirmed. SIMAP's link containing `iss` caused `invalid redirect_uri`
on sign-in; the tab is now on the canonical `/en` page. An automatic approval
rejection stopped the subsequent combined access action; specific authorization
is pending. No SIMAP API client, document/Q&A grant or source credential is claimed.

This is still uncommitted whole-feature development. Permitted document/Q&A
capture, consented digest delivery, semantic evaluation and live/human acceptance
remain required. Capacity and withdrawal handling do not close MV2-055 across
all sources or AC-B2-08's document comparison requirement.

Verification for this local policy change: **59 affected storage, rights,
evidence, collector, repository and HTTP tests passed**. The final indexed
migration refinement passed five storage/upgrade/downgrade tests; exact full API
Ruff, TypeScript no-emit, i18n catalogue and backlog integrity checks passed.
An added HTTP denial test first exposed missing no-store headers on exception
responses; the middleware fix passed the final suite. Public snapshot capture
dates and private source references are indexed for bounded cleanup batches.
These tests use isolated local databases; no production schema or policy changed.

## Local owner-consented email journey — 12 September 2026

Tender email settings are separate from the matching profile. Immutable policy
revisions record explicit consent, the verified recipient address, timezone,
immediate/daily mode and optional overnight quiet hours. A monitor-version CAS
protects settings changes. Viewing a preference or creating a profile never
grants consent. Turning email off suppresses pending intents; turning it on again
does not replay old history. Changing an account address requires fresh consent
for that verified address. An unavailable SMTP service keeps pending intents
without pretending to send them, and the reader identifies that service gate.

New opportunities and material changes to followed lots create private delivery
intents referencing the same exact dossier versions used in the reader. No
source bodies, company profile or recipient address enter shared jobs. Collection
and email use the existing durable job dispatcher; email jobs have one automatic
attempt. The observation and intent commit atomically. Profile reassessments,
late historical evidence and nonmaterial source updates do not create email.

Before claiming and again before SMTP, delivery checks active ownership and
membership, monitor/consent/profile revisions, the verified address, current
source rights, the latest evidence, existing reviews and following. An expired
offer deadline suppresses a new-opportunity email. Reviewing one lot during the
claim/send interval removes that item while preserving other eligible items.
Cancellation heartbeats apply before claim and before sending. Duplicate source
signals across the same owner's monitors are not resent; other workspaces and
owners keep separate notification scope. An in-flight duplicate waits rather
than discarding a possibly still-sendable event.

Both preview and sending use the same eligibility function and expose schedule
deferrals. Email uses current, unreviewed evidence observed in the preceding
48 hours, with at most 50 items per message. A daily mode permits at most one
claimed/sent/uncertain message per local day; remaining items may wait until the
next day and eventually expire from email eligibility. This is a bounded delivery
window, not deletion of dossier evidence and not a guarantee that every retained
development appears in email. The UI states the window, batch limit and source
gaps. The existing scheduler's DST gap, repeated clock and overnight quiet-hour
behavior is reused. Preview sends no email and does not grant consent.

The message identifies opportunities/material updates and links to private
monitor/dossier/evidence versions, with five-language guidance. It does not
redistribute source document text, send a bid, declare interest or post Q&A.
The reader opens a linked dossier, checks that it belongs to the displayed
monitor, and distinguishes a linked earlier original from the current version.
All original downloads still apply owner and current-source-rights checks.

A durable `sending` claim precedes SMTP. Exceptions or an abandoned claim become
`uncertain` and are never automatically retried as a fresh email. The owner sees
uncertainty in delivery settings and can check the mailbox before requesting
operator investigation. This does not claim transactional exactly-once SMTP or
automatic resolution of an uncertain outcome. Production flags remain unchanged;
all messages used in verification were intercepted by fake SMTP.

The unpublished additive migration now includes 15 tender tables, including
private consent policy and delivery rows with owner/tenant/evidence constraints.
No production migration, source credential, activation, real-user consent or live
email acceptance is claimed. Permitted document/Q&A capture/diffs,
specified semantic evaluation and source/live/human acceptance remain open
before the complete B2 feature can be committed and pushed.

## Profile history and combined local verification — 13 September 2026

The reader now exposes immutable profile revisions in ten-row pages, newest
first. Each revision shows all saved search, exclusion and declared qualification
fields, identifies values differing from the current profile, and preserves
unknown versus explicitly empty declarations. The revision number on a tender
can be matched to these settings. Opening history never restores an old profile,
changes monitoring or grants email consent. Data is fetched only while opened;
failed/retried requests do not leave a stale page presented as current. Ownership
and membership remain enforced by the existing private history API. Stored
semantic thresholds do not imply that semantic scoring is enabled.

Verification on the combined local implementation:

- 180 API/source/document-set/tender tests plus backlog integrity passed in the
  single combined run (180 total, 58.84 seconds). This includes consent, real
  durable-job dispatch with fake SMTP, review/permission rechecks and storage.
- The exact API Ruff gate passed. The production Next build, including TypeScript,
  passed after the final history UI change.
- The synthetic browser journey passed 18 full-document axe checkpoints across
  five locales. It verifies profile-history pagination, displayed old settings
  and differences, recovery after a failed history request, no history mutations,
  consent/disable/preview, evidence deep links and mismatched-monitor denial.
  No reported axe violations or prohibited unresolved ARIA issues remain; other
  incomplete automated checks are retained, not an accessibility certification.
- The mobile email screenshot was inspected at 390 pixels: controls and consent
  remain usable without horizontal overflow. Browser history checks cover the
  same width in all five locales.

These are local implementation results. No live SMTP message, source account
credential, production migration, source activation or complete B2 acceptance
was performed. Required document/Q&A acquisition and semantic evaluation still
prevent whole-feature publication; main remains unchanged.

## Exact document text comparisons — 13 September 2026

Local document-set reconciliation now composes with exact parsed-text comparison.
Each side binds the source, dossier, private access scope, provider document ID,
snapshot ID, binary SHA-256 and the recorded parsed-projection SHA-256. The latter
covers original passage text, order, page and locator. A self-consistent replacement
projection with a different fingerprint cannot substitute for recorded evidence.
The reader callback must enforce current permission for each exact original every
time, including when redisplaying a retained comparison. Missing permission yields
unavailable text; operational reader errors propagate. This callback contract is
implemented/tested locally, not yet wired to a production private attachment store.

Comparison preserves case, punctuation, numbers, negation and leading labels.
Only whitespace differences are ignored. It returns literal added/removed/replaced
passage excerpts and original page/locator references; it does not infer that a
number is a deadline or a qualification, nor that a literal change is a new legal
obligation. Paragraph moves can appear as removal/addition. Changed bytes remain
a material file replacement in the manifest even when comparable text is equal.
Different extractor versions, languages, incomplete parsing and mismatched evidence
cannot produce an unchanged verdict. Excerpts and change lists are bounded and
carry explicit truncation and complete hunk counts.

Already-permitted originals can be parsed locally with the existing PDF reader or
strict UTF-8 plain/Markdown text. PDF magic works with octet-stream delivery; other
binary formats are not guessed as text. PDF references use exact extracted page
and block positions, plain text uses original line numbers. Encrypted/broken or
textless PDFs, invalid encodings and unsupported formats retain their content hash
with a failed extraction state. A PDF page without text marks extraction partial.
Complete means the extracted text layer, not diagrams, embedded attachments, OCR
or completeness of legal requirements. Original files remain authoritative.

Bounds: 8 MiB input, 200 PDF pages, 2,000 passages, 2 MiB extracted text, 100 rendered
change hunks, 10 passages per side per hunk and 2,000 characters per excerpt.
These are parser/projection bounds, not a claim of a sandboxed parser process or
a replacement for worker execution limits. ZIP/Office/HTML/Q&A-source adapters,
private storage/retention/read API, source credentials and reader integration still
remain required; no unsupported file has been presented as successfully compared.

Verification: 61 document-set/comparison/parser tests passed (0.50 seconds), including
actual PDF fixture bytes for 3→5 references and 20→27 September, exact page/hash
binding, a new Q&A document manifest entry, denied prior evidence, extractor/language
changes, deliberate projection substitution, whitespace, truncation, encryption,
empty pages and size limits. The exact full API Ruff gate passed. This advances
MV2-044 locally but does not satisfy permitted live capture or AC-B2-08 by itself.

## Private original storage and read API — 13 September 2026

The unpublished migration now contains 17 tender tables. Two new organization-
scoped tables retain an explicit reviewed document-access grant and its private
binary/parsed snapshots. Composite foreign keys bind each snapshot to the same
dossier, organization and access scope. Grants require a retained publication
from that dossier, a source account/policy evidence reference and explicit access
and retention deadlines. Grant creation is an internal operator boundary with
no HTTP route: it requires source-specific permission to capture, retain and let
the owner download documents. Existing public SIMAP access or an app feature flag
does not provide that permission. No real grant was recorded during development.

Worker-only storage checks active monitoring, current grant/publication rights,
private ownership, source identity, actual binary SHA-256 and parsed integrity.
Serialized per-dossier quotas span grant renewals: 64 MiB of original plus parsed
payload and at most 1,000 retained snapshot metadata records. Same-byte/projection
polls reuse their immutable original; permission or capacity failure preserves
previous evidence. Binary and parsed payload columns are deferred, and the paged
metadata index does not load them. These are payload bounds, not a disk/WAL quota.

Private GET routes below enforce current membership, ownership, scope, source
restrictions, grant expiry/revocation, retention and integrity on every read:

- `/api/tender-watch/dossiers/{id}/documents`: cursor metadata pages, explicitly
  retained-only coverage; an empty page does not prove an empty source listing.
- `.../documents/{snapshot_id}/text`: exact parsed passages and extraction status.
- `.../documents/{snapshot_id}/original`: exact bytes as a no-store attachment,
  with nosniff and sandbox headers. Account/policy references are not returned.

Expired or revoked access immediately hides retained originals. The separately
approved retention deadline controls logical payload removal: bounded maintenance
clears binary and parsed columns while retaining IDs/hashes for unavailable links.
The existing tender scheduler runs this maintenance across organizations even if
collection/email is disabled. It does not claim immediate erasure from database
pages, WAL, replicas or backups; those have separate storage lifecycles. Deleting
a monitor cascades through its private grants and document snapshots.

Verification: 260 combined tender/source/document tests passed in 135.58 seconds,
including existing document-summary/history regressions, migration upgrade/
downgrade, cross-tenant reads and cleanup, grant-renewal quotas, immutable restart
deduplication, deferred-payload indexing, corrupted bytes/projections, pause,
revocation and expiry, HTTP attachment/no-store behavior and peer denial. The
full API Ruff gate passed. These local checks used synthetic grants/originals.

Still required before whole B2 publication: private manifest history bound to
dossier versions, automatic material-change reopening/email linkage, document
reader/comparison UI, permitted source collection including Q&A/remaining formats,
semantic evaluation and source/live/human acceptance. Existing public-source
capabilities continue to say documents are not verified; these storage/read routes
alone do not establish production document collection or AC-B2-08 acceptance.

## Document observations tied to review history — 13 September 2026

The unpublished migration now contains 18 tender tables. Private document
observations retain immutable manifest state/deltas, exact snapshot bindings,
sequence and a fingerprint over the complete stored projection. Access grants
keep a separate last-poll identity/hash/clock: unchanged polls need not duplicate
large manifests, exact retries are idempotent, conflicting identities fail, and
late polls cannot rewind current evidence. Manifest bytes share the existing
per-dossier payload budget and their own bounded metadata count. Expired retention
also clears manifest content while preserving unavailable historical references.

A material file-set change creates an immutable dossier revision, even if the
public publication/hash/profile is unchanged. A separate observation key and
composite private reference distinguish it from public ingestion. The revision
reuses public snapshot/section references without putting private documents into
public caches, preserves the earlier decision/reviewed sequence, and reopens a
reviewed dossier. New Q&A and replaced files remain distinct manifest deltas.
Baselines and access/parse metadata have their own history; they do not supersede
pending new-opportunity mail. A newly approved baseline after a revoked private
revision restores readable coverage without asserting a specific material change.

Owner-consented material-update intents reference the resulting exact dossier
revision. Their event identity includes the private observation, so a document
change is not suppressed as a duplicate of an unchanged public publication. Exact
manifest replay or an unchanged reordered poll creates neither another revision
nor another message. Provider-wide normalization of the same private document
event across independently collected monitors remains source-adapter acceptance;
the local observation ID alone does not prove that broader deduplication case.

Current per-file denial masks old retained downloads, titles and text comparisons;
grant/source restrictions and the current changed-item gate also apply before
review or email eligibility. A comparison reads both exact stored originals under
current rights and returns unavailable when either cannot be read. It never
substitutes current text for a missing previous original. Manifest history and
comparison GET endpoints use existing private session/feature/no-store protection:
`.../dossiers/{id}/document-observations/{observation_id}` and its
`/comparison?item_id=...` child. Dossier and version metadata expose the bound
observation ID for the forthcoming document reader.

Local verification includes a baseline → Bid → 3-to-5 reference file replacement
+ Q&A v3 → reopened review → exact-version email intent scenario, unchanged and
stale replay, current denial, renewed grants, pagination, retention, quota rollback,
actual HTTP source excerpts and peer/revocation denial. The integrated 243-test
suite passed in 78.10 seconds before the final changed-item gate; its affected
reader/repository/email tests then passed: 67 tests in 55.08 seconds. Full API
Ruff and the final backlog integrity check passed.

This remains local worker/store/API integration. Required document/comparison UI,
real permitted collection/Q&A/remaining-format adapters, semantic evaluation,
source event normalization and live/human acceptance are still open. No private
source account or document grant was activated in production, no real email was
sent, and the whole B2 feature has not been committed or pushed.

## Private document reader — 13 September 2026

The local five-language reader now opens the exact document observation attached
to a dossier revision, including older revisions selected through history. It
shows paged source-set metadata, separate retained-original history, collection
timestamps, Q&A entries, removed/withdrawn files and incomplete listing coverage.
Repeatedly selecting a historical revision reopens its reader. Original downloads
use the private no-store endpoint; changing scope or closing the reader aborts
pending requests and downloads. Denied downloads clear the selected evidence and
refresh metadata rather than displaying prior evidence as current.

Saved text keeps literal source strings and page/locator references, with bounded
passage pagination and explicit partial/failed extraction states. Comparisons show
both original downloads, exact before/after excerpts, hunk pagination, unavailable
evidence and truncation. They describe literal differences, without asserting a
new legal requirement or automatic qualification. Source text is rendered as text,
including strings that resemble executable HTML. A permission-denied refresh
removes the previous comparison from the evidence panel.

Verification: the production Next.js build passed. The browser scenario passed
30 full-document axe checkpoints across English, German, French, Italian and
Romansh, covering existing profile/review/email flows plus document text,
comparisons, denied evidence refresh and historical reopening. It also checked
51-passage pagination, literal HTML-like source text, original-download endpoint
requests and no horizontal overflow at 390 px. The mobile screenshot was visually
inspected. Browser downloads were denied in the isolated test context; all grants,
accounts and documents were synthetic. Axe results include unresolved non-ARIA
incomplete checks and are not an accessibility certification.

The attachment reader gap is closed locally. Permitted live document/Q&A collection,
remaining-format adapters, source event normalization, changes accumulated since
the last review, semantic evaluation and live/human acceptance remain open. No
production credential, private grant, real email, feature activation or full B2
commit/push resulted from this verification.

## Changes accumulated since the last review — 13 September 2026

The private `/api/tender-watch/dossiers/{id}/review-changes` reader now returns
chronological pages between the last recorded decision and the current dossier
revision. Both boundaries are required in the request. A changed decision or a
new current revision rejects continued pagination with a conflict; cursors cannot
escape the selected window. Unreviewed dossiers start at their first saved
revision. A new decision resets the window without rewriting immutable history.

Each revision retains its own change labels and exact original/document links.
An earlier deadline change therefore remains visible after a document or terms
update. Repeated changes and reversals remain distinct events rather than being
collapsed into an unsupported net interpretation. Existing source, publication,
private grant and per-file gates apply to each entry at read time. Denied evidence
occupies an explicit unavailable slot, with no source details or document pointer;
integrity and operational failures propagate instead of becoming empty history.

The five-language interface separates this review window from complete version
history. It supports chronological pagination, source-original/document links and
unavailable gaps. Refreshing or reopening clears stale displayed evidence while
the current request runs. A conflict tells the user to refresh the dossier before
reviewing a new window; no decision is recorded automatically.

Verification: all ten new repository scenarios passed, including paged deadline
then terms changes, decision/new-evidence invalidation, first review, private file
replacement and reversal before a public update, grant withdrawal, public-source
denial, integrity failure, owner/tenant isolation and invalid cursors. In the
combined run, 44 tests passed and one HTTP test assertion omitted the existing
before/after locator fields. Correcting that assertion produced a passing HTTP
scenario with no-store success/conflict/peer denial. The final Next.js build,
full API Ruff gate, four section-help checks and actual backlog integrity check
passed. The extended browser journey passed 36 full-document axe checkpoints,
including five-language 21-revision pagination and stale-window reopening, with
the same accessibility limitations described above.

These changes complete the local accumulated-review-history gap. Required source
collection, semantic evaluation and real/live/human acceptance remain open; no
complete feature commit, production source grant or activation is claimed.

## Disabled semantic experiments and evaluation — 13 September 2026

`tender_semantic.py` now provides the B2 semantic proposal schema and an explicit
offline assessment entry point. Its default is disabled and makes no model call.
Hard deterministic exclusions skip generation. Missing capabilities, source scope
or an immutable model runtime identity cannot produce a score. The model receives
only bounded public lot fragments and capability phrases; company names, declared
certificates/reference counts and private attachments are not sent. Oversized
UTF-8 inputs are rejected intact rather than silently dropping contradictions.

A proposal contains relevance/abstention, an integer ranking score and bounded
capability facets bound to exact Unicode source spans. Duplicate JSON keys,
nonfinite/coerced scores, unsupported fields/actions, invented capability or
fragment indexes, changed quotes and contradictory duplicate facets are rejected.
Timeouts and model failures preserve deterministic matching. Results bind source,
complete facts, private profile fingerprint, prompt/schema revision, supplied
immutable runtime identity and exact successful response bytes/hash. Cancellation
propagates. No repair loop, bidding, email or production matching integration is
performed. A correct quote can still support an incorrect semantic interpretation;
the proposal remains unapproved even when it passes the contract checks.

`tender_semantic_eval.py` evaluates captured development/validation experiments.
It checks result/input/profile/source/prompt/schema bindings, exact response bytes
and citations before accounting; different runtime identities cannot be pooled.
Repeated source/scope families cannot cross development and validation splits.
Reports separate split/locale metrics, false positives, missed positives including
abstentions, missing/invalid results and coverage. The threshold is explicit and
is not a calibrated probability or production default. Authored development labels
are never counted as independent held-out acceptance, and no report can enable
semantic mode or satisfy MV2-051 by itself.

Reproducible offline command (no model/source/database connection or `.env` load):

```powershell
services/api/.venv/Scripts/python.exe -B scripts/evaluate_tender_semantics.py `
  --dataset <experiment.json> --results <captured-results.json> `
  --threshold <explicit-score> --output <new-report.json>
```

Inputs are bounded strict JSON; the output must be a new file so previous audit
evidence and input files cannot be overwritten. Dataset JSON follows
`Dataset.model_json_schema()`; captures are keyed by case ID and contain the
complete returned assessment object. The report includes dataset/result and
implementation hashes without echoing raw source/profile text.

Verification: 98 semantic contract/evaluator and deterministic tender tests passed,
including actual CLI execution in an isolated directory and refusal to overwrite
a prior report. These use synthetic model outputs to test the safety/accounting
contract, not to claim measured semantic accuracy. A read-only check of the
configured local model-manager runtime path at port 12436 returned HTTP 404;
no identified model was available through that contract. No model was installed,
started or substituted, and no real generation experiment was run. A bounded
actual-model run on authored training/validation cases, independent promotion,
permitted source collection and whole B2 publication remain open.

## DOCX originals and versioned text — 13 September 2026

The local attachment parser now recognizes validated DOCX packages, including
octet-stream delivery identified by ZIP magic and the package's main-document
relationship/content type. It reads paragraph runs, table-cell paragraphs and
referenced header/footer/footnote/endnote stories. Unreferenced stories are not
silently included as current requirements. Text retains whitespace, explicit
tabs/breaks and hyphen markers; locations name the exact package part and XML
paragraph path. Rendered Word page numbers are not invented. Complete describes
the supported text layer, not a full Word layout or legal-completeness judgement.
The package/story structure was checked against [Microsoft's WordprocessingML
documentation](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document).

Fields, numbering, tracked edits, comments, linked content/data bindings, drawings
and other unsupported constructs mark extraction partial. Partial text remains
readable with the existing warning but cannot establish an unchanged or removed
requirement in exact comparison. DOCM/macros, encrypted or malformed packages,
unsupported XML encodings, ambiguous member/relationship names and missing
referenced parts fail extraction while preserving the original-byte fingerprint.
This does not claim support for arbitrary ZIP archives, legacy DOC, spreadsheets,
HTML, OCR, external content or every Office XML feature.

The reader never starts Word, executes macros, follows external relationships or
extracts archive files to disk. Bounds cover 256 members/referenced stories,
32 MiB declared package expansion, 4 MiB per XML part, a 200:1 compression ratio,
50,000 nodes per part, 100,000 cached XML nodes and depth 64. DTD/entities and
non-UTF8 XML are rejected before parsing; XML stories are cached to prevent
repeated decompression of a shared footnotes part. Common document passage/text
bounds still apply. These are parser bounds, not a process sandbox or a claim of
visual completeness; see Python's [ZIP documentation](https://docs.python.org/3/library/zipfile.html)
and [XML security notes](https://docs.python.org/3/library/xml.html).

Validated complete/partial DOCX originals now download through the private API
and browser with a generated `.docx` filename; failed or unrecognized packages
keep a neutral `.bin` filename. The server preserves exact bytes and existing
attachment/no-store/nosniff/sandbox headers. Current source/grant/owner gates
remain in force. A real in-memory DOCX fixture traverses parsing, private storage,
text reading and original HTTP download; peer reads are denied. Literal 3-to-5
reference changes also traverse the existing exact-document comparison engine.

The integrated parser/document-store/history/API run passed 119 tests in 49.57
seconds before the final hyphen-marker handling. The frontend production build
passed. Final affected checks and browser evidence are recorded below; these are
synthetic local originals and grants, not live SIMAP document acquisition.

Final verification after text-marker handling: 88 affected parser/comparison,
private DOCX HTTP and backlog checks passed in 4.56 seconds. The browser passed
36 full-document axe checkpoints across five languages, including a direct check
that the clicked original-download filename retains `.docx`. Isolated browser
downloads remain denied and no fixture was saved to the user's Downloads folder.
The complete API Ruff gate and diff whitespace check passed. This extends local
format coverage; production source rights, live Q&A/document collection, remaining
formats and complete B2 acceptance remain open.
