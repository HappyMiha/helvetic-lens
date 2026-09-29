# Completed Monitoring release commentary

Archived verbatim from the active backlog on 28 September 2026 to keep its
validated 512 KiB reader bound. The active queue and task acceptance remain in
[BACKLOG_MONITORING_V2.md](BACKLOG_MONITORING_V2.md); these are historical results.

## Research continuation — 1.37 conservative local rejection

DONE within uncertainty repair, evaluation and verified publication; recorded before code. MV2-002/020/023/051: preserve uncertain
candidate decisions, develop a versioned local Laya rejection guard, and measure
its extra review burden against reduced false exclusion. Existing provider,
worker, cumulative budgets and public NoMIRACL cache only; no private dossiers or
paid calls. Development uses dev hash offsets 12–13, validation uses test offsets
42–43, two questions per relevance subset/language (EN/DE/FR), all judged
candidates; verify no overlap with prior project query IDs. Development is capped at 121 and validation at 120 local calls; each has
240 seconds / 12 seconds per call (total 241 / 480). This pre-inference size
correction retains one development query with 11 candidates; no labels/results
were used to alter sample selection.
Raw source passages stay outside Git. Threshold candidates are fixed before calls:
0.50, 0.65, 0.80, 0.90, 0.95. Only low-score unrelated → uncertain is permitted;
never auto-admit uncertain records or label confidence as accuracy.
Selection: zero development positive exclusions, retain at least half the baseline
negative exclusions, extra uncertainty <=20% of all cases, retain most negative
exclusions, then lowest threshold. If no candidate qualifies, no promotion.
Freeze selection before opening validation labels/results. Validation promotion:
complete matched inputs/model, positive exclusions <= baseline and <=5% of positive
labels, retain >=50% of baseline negative exclusions, extra uncertainty <=20%,
at least one low-score rejection deferred. A failure prevents production promotion.
Independently preserve final uncertain review events instead of calling them rejected.
Acceptance: deterministic privacy/budget/uncertainty tests; frozen development and
fresh validation receipts; exact API/script lint, affected tests, native publication.
Clients stay at verified 1.36 unless a user-visible reader change is required.
No threshold passed development; validation stays unopened and no guard is
promoted. Worker activity now distinguishes uncertain/unavailable from rejected;
raw provider scores and policy version are retained. 65 affected cases pass.
Core git-09ab8bcfff5f is verified live; both clients retain verified 1.36 assets.
Native health, 25 module hashes, five containers, nine routes and schema passed.
See [scope](docs/PRODUCT_RESEARCH_GATE_POLICY.md). Parents and professional quality OPEN.



## Product decision — 1.29 domain-aware dossier setup

DONE within verified 1.29 scope; recorded before implementation on 28 September. Scope, dependencies,
source readiness and acceptance are in [PRODUCT_DOMAIN_SETUP.md](docs/PRODUCT_DOMAIN_SETUP.md).
MV2-002/020/023: server-selected LegalPack/PharmaPack for common profile suggestions,
refinement, source advice and honest discovery capabilities; visible saved direction
in both clients. Full target architecture and broader parent gates remain open.



## Owner priority — 1.30 readable dossier

DONE within verified 1.30 implementation/release scope; recorded before code
on 28 September. The owner requested a document-like dossier before further
architecture work. Human usability and broader parent gates remain open. See
[PRODUCT_DOSSIER_CLARITY.md](docs/PRODUCT_DOSSIER_CLARITY.md) for MV2-002/020/024
scope, dependencies, unchanged source readiness and acceptance. Separate reading,
human discussion, AI research and original sources while preserving every workflow.



## Architecture continuation — 1.31 structured dossier context

DONE within the bounded 1.31 scope; recorded before code on 28 September.
C03/C33 and MV2-002/020/023 now include optional, versioned Legal/Pharma subject
fields on the common dossier with existing roles and audit. Both clients and the
shared Core are published and verified; 105 API checks and 173 tests per client passed. See [scope and acceptance](docs/PRODUCT_STRUCTURED_CONTEXT.md).
This does not establish entity resolution, applicability or source coverage.



## Architecture continuation — 1.32 versioned dossier templates

DONE within the bounded 1.32 scope; recorded before code. C33/C44/C48 and
MV2-002/020/023 now include optional versioned template selection and retained
guidance on the existing shared dossier. Core and both products are published
and verified; 116 API checks and 179 client tests each passed. See [scope and acceptance](docs/PRODUCT_DOSSIER_TEMPLATES.md).
This does not complete source readiness or the Market Access proving journey.



## Research continuation — 1.38 captured-source relationships

DONE within the verified source-provenance scope; recorded before code. MV2-002/020: explain matching captured content,
same-address versions and unknown source independence beside exact paired quotes
in Changes over time. Capture time is distinct from publication/effective time.
Reuse existing comparisons, source snapshots, visibility, review and client basis
rendering. No provider call, schema change or automatic claim merge. See
[scope, source readiness and acceptance](docs/PRODUCT_SOURCE_RELATIONSHIPS.md).



## Research continuation — 1.39 reviewed entity identity

DONE within verified pair-review/publication scope; recorded before code.
61 affected Core checks and 203 tests/lint/types/build per client passed. Core
git-5b03c488e5bf and both existing Sites 39 are live; 38 HTTP/access checks and
47 exact assets per client plus native runtime/schema verified. MV2-002/020/024: exact cited cross-run entity
suggestions and explicit reversible editor decisions in the same dossier/audience.
Reuse original mentions, sources and native review/visibility contracts. Existing
captured identifiers only; no source acquisition or model call. See
[scope, dependencies and acceptance](docs/PRODUCT_ENTITY_IDENTITY.md).
Full canonical registry, professional quality and broader parent acceptance OPEN.



## Research continuation — 1.35 bounded evaluation

DONE within bounded evaluation/publication scope. MV2-002/020/023/051 reuse the pinned public
NoMIRACL cache, existing local Laya adapter, 1.34 gate instructions and saved
controlled-worker traces. Freeze a disjoint sample and explicit call/time budgets;
measure three-way relevance outcomes and deterministic citation/follow-up integrity.
Publish IDs/hashes/metrics only. No paid probes or private production records.
[Scope, readiness and acceptance](docs/PRODUCT_RESEARCH_EVALUATION.md).
Live hosted/full-workflow quality and all broader parent gates remain OPEN.



## Owner priority — 1.34 iterative dossier research

DONE within the verified 1.34 scope; scope defined before implementation. MV2-002/020/023 and the new
[Investigation Engine specification](docs/INVESTIGATION_ENGINE_SPEC.md), sections
42–43. [Architecture audit, dependencies, readiness and acceptance](docs/PRODUCT_ITERATIVE_RESEARCH.md)
record the current gaps and additive vertical slice: question-first creation,
planner, candidate gate, cited claims/entities/edges, persistent open questions,
a real second search updating existing evidence, budgets and readable UI.
Core and both clients are published and verified. 64 API checks and 189 tests per
client passed, alongside exact runtime/assets and anonymous access checks. Legacy
monitoring/source rights remain intact. Full specifications and live quality remain OPEN.



### Legal product rename — 1.27 DONE within scope

Owner-confirmed addition on 28 September 2026: **Helvetic Lens Legal**,
`legal.helveticlens.ch`, `HappyMiha/helveticlens-legal`. Public names, navigation,
search, metadata, guide and source URLs are updated with compatibility for the
existing `loyer` API/storage identity and old domain. The same Sites project,
dossiers, roles, publication choices and Apache-2.0 repository history remain.
See `docs/PRODUCT_LEGAL_RENAME.md`. Verified evidence includes alias idempotency,
private/public/guest/CSRF boundaries, exact production assets and renamed remote
identity. This addition does not complete the full investigation/visual specs.


## Product decision — 1.28 evidence read recovery

DONE within verified 1.28 scope; recorded before implementation on 28 September. Scope and acceptance
are in [PRODUCT_READ_RECOVERY.md](docs/PRODUCT_READ_RECOVERY.md): native comparison
and snapshot retry with server-authoritative result recovery; both product clients
cancel and fence obsolete reads. This contributes to MV2-002/020 and preserves
current source rights, nine directions and full-specification open gates.


## Owner priority — 1.36 research reader repair

DONE within verified client repair/publication; recorded before implementation. MV2-002/020/023/024: repair repeated
saved-evidence forms shown in the owner's Legal mobile screenshots and make
transient platform errors actionable. EvidenceSearch and ClaimEvolution currently
shared one sibling React key; changes in preceding conditional children could strand
old search components. The 16:42 UTC-offset-adjusted report also overlaps native
API/tunnel quiescence during the 1.35 release; exact failed request is unavailable.
Dependencies: existing shared clients, native authorization and Sites projects.
No new sources or model calls. Acceptance: actual reconciliation regression for
error/loading/recovery transitions, one search and one history block, stable
search state; status-aware API errors without automatic write/model retries;
existing access isolation preserved; both clients tested, pushed and verified.
Both clients passed 197 tests plus lint/types/build and are live as version 38;
33 HTTP/access checks and 47 exact assets passed per product.
See [scope and evidence](docs/PRODUCT_RESEARCH_REPAIR.md). Parent tasks stay open.


## Research continuation — 1.40 human claim review

DONE within verified review/publication scope; 52 affected Core checks and 209 tests/lint/types/build per client passed; recorded before code. MV2-002/020/024: explicit source-pinned
accept/dismiss/needs-more-evidence on the existing DossierClaim, separate from
machine support. Reuse native evidence, roles, visibility and publication consent;
no new source access or inference. See [scope, dependencies, source readiness and
acceptance](docs/PRODUCT_CLAIM_REVIEW.md). Full architecture/human acceptance OPEN.


## Research continuation — 1.41 reviewed saved-evidence search

DONE within verified search/publication scope; 100 Core and 216 client checks passed; recorded before code. MV2-002/020/023/024: current human review
alongside original machine status/citations in all private saved-search modes;
separate bounded freshness fence, no ranking/inference promotion. Reuse current
review/source/auth/cache contracts; retained evidence only. Scope, dependencies,
source readiness and acceptance: [reviewed search](docs/PRODUCT_REVIEWED_SEARCH.md).
Full target and human acceptance remain OPEN.



**Saved document context and exact source links — 28 September 2026:
DONE (scoped production contribution / release 1.27).** Scope: MV2-002/020/024.
Make the exact saved source legible inside owned-document comparisons and both
product document-history readers: full version identity, capture fingerprint,
file/format, actual retained counts and distinct capture/document dates. Keep
synthetic/import and selected-article provenance explicit. Improve text measure,
spacing, narrow-screen reader layout and disclosure controls using Brandbook v1.0.
Native report provenance and passage links must identify the full saved version
and encode complete passage IDs, including query/hash characters.

Dependencies: existing ComparisonView/Version/VersionCard/ReportProvenance,
SourceReading helpers/copy, product DocumentHistory/SavedPageVersion, installed
primitives and revision-pinned source readers. Source readiness: version_summary,
product_document_history METADATA and evidence_pages already provide the required
fields under current authorization; no API/schema/model/provider/credential or
source-right change is required. Native comparison jobs, identity decisions,
material classification, review actions, companion tabs and Ask remain in place.
The existing client history/error/refresh/revision behavior stays authoritative;
no query, collection, paid research, publication or notification is started by
opening context. The separate native baseline workflow completed in 1.26 stays
unchanged. A broader legacy comparison resource/job-cache refactor is not part
of this presentation and exact-link outcome and is not claimed complete.

Acceptance: full old/new IDs in saved report provenance; exact escaped native
version/passage destinations; true saved passage/character totals with unknown
separate from zero; valid capture timestamps, stated/official/supplied date
provenance, original files, recorded hashes, selection scope and synthetic labels
remain distinct. Product original-source actions retain legacy HTTP(S) support
while rejecting unsafe or credential-bearing URLs. Both readers preserve exact
quoted text, source language, page offsets, revision mismatch/withdrawal handling,
explicit current-revision reload and retained AI-note context. Five native locales,
actual SSR/helper behavior cases, required frontend tests/lint/types/builds,
affected existing API contracts, backlog smoke, value scans, immediate main pushes
and exact existing Sites/native production proof precede scoped DONE. No browser
or private-production-record probes; human/professional/full-spec gates stay open.
Evidence: docs/PRODUCT_VERSION_CONTEXT.md.



**Saved comparison clarity and selection safety — 28 September 2026:
DONE (scoped production contribution / release 1.26).** Scope: MV2-002/020/024.
Make native saved-version comparison and both product saved-page change readers
clear about the exact pair, capture identities, real retained counts and preview
limits. Separate the editor's unsaved baseline selection from the persisted
comparison. Retain a local choice across background reads; if its source revision
changes, require an explicit return to the current saved choice before another
write. After a committed mutation, withhold the old comparison until the server receipt is acknowledged by a current read. Hide retained source text when its current read fails.

Dependencies: existing NativeComparisonWorkspace, native_comparison_views and
revisioned native selection writes; both MonitoringTriggerRow/PageChange readers,
DocumentHistory's expected_revision links, installed primitives and release 1.25
source metadata helpers. Source readiness: current native API already returns
saved version IDs/times, material counts, comparison identity, paged exact text
and stale/unselected states. Existing product page payload already returns exact
old/new revisions, hashes, full saved-text character counts and bounded excerpts;
matched_at is the watched page version's capture time. No new API/schema/provider,
model, credential, source rights, publication or delivery change is required.

Acceptance: distinguish the saved pair from a draft; revision conflicts cannot
silently rebase a choice, and a committed write cannot display an older result
as its new comparison. Preserve explicit clear/save, read-only roles, current
source withdrawal, exact passage/source/PDF readers, candidate/result paging,
registry return and account boundaries. Show actual counts, with unknown distinct
from zero; partial previews never imply complete changes or legal/factual impact.
Both clients expose source version/revision/capture/fingerprint details and exact
revision-pinned full-reader actions. Reuse neutral Brandbook typography, readable
measure and responsive paired text; no synthetic Lens or truth score. Cover five
native locales, pure selection and actual SSR behaviors, required client tests/
lint/types, native checks/types, final builds, backlog smoke, protected-value scan,
immediate main pushes and exact existing production/runtime verification.
Browser/human language/visual and professional/full-spec acceptance stay separate.
Evidence: [Saved comparisons](docs/PRODUCT_SAVED_COMPARISONS.md): 403 native
frontend cases, 147 per client, exact API Ruff and 71 API cases, all builds
and scans; both Sites 29, 131 origin checks and 47 exact assets each, exact
native comparison activation/assets and 60-module runtime proof. Full
specifications and broader MV2-002/020/024 remain IN PROGRESS.

**Source reading and inspectable provenance — 28 September 2026:
DONE (scoped production contribution / release 1.25).** Scope: MV2-002/020/024.
Give the native saved/corpus evidence reader a clear source-first hierarchy,
readable retained-text measure, distinct source and capture dates, actual saved
record counts and inspectable capture identity. In both product clients, make
captured excerpts, source usage and preservation boundaries legible in the same
source card/reader journey. Keep unknown classification/publication dates honest.

Dependencies: existing native EvidenceView/evidencePage and product SourceCard/
SourceMetadata/SourcePreview, installed UI primitives, shared Brandbook themes
and completed global Ask. Source readiness: authorized retained versions and
investigation snapshots already returned by existing APIs; current access and
source withdrawal remain backend decisions. Inspection found that the bounded
native evidence-page projection omits the already stored content hash. Return
that scalar under the same existing authorization query, without hydrating full
versions or making another request. No acquisition, provider, account, secret,
schema, publication, model or notification change is required. The existing
product HTTPS-only source-link policy remains in place; native legacy HTTP(S)
references retain their existing scheme policy while rejecting user-info URLs.

Acceptance: source origin is a safe HTTP(S) reference without embedded credentials;
saved capture time and stated/publication date stay separate; true zero counts
remain distinct from unknown; only real SHA-256 identities are labelled as such;
retained excerpts are not represented as a complete original. Preserve exact
passage targets, PDF page/source anchors, original downloads, previous/next pages,
source language, synthetic/import notices, permission/error states and current
registry return position. Show context and provenance without a new widget grid
or simulated Lens. Reuse semantic themes, accessible disclosure and responsive
reading layout, with complete five-locale native copy. Run helper/real SSR cases,
existing frontend/localization/types/format and both client lint/tests/types,
final native/Sites builds, exact API Ruff gate and affected bounded-reader/auth/
document-history cases, backlog smoke, protected-value scans, immediate main
pushes and exact production readiness/origin/asset/runtime verification. Browser,
human language/visual and professional/full-spec gates remain separate.
Evidence: [Source reading](docs/PRODUCT_SOURCE_READING.md): native 391 frontend
cases, 142 per client, exact API Ruff and 55 API cases, all builds and scans;
both Sites 28, 130 origin checks and 47 exact assets each, exact native reader
activation/assets and 58-module runtime proof. Full specifications and broader
MV2-002/020/024 remain IN PROGRESS.

**Global Ask/Search and retained command drafts — 28 September 2026:
DONE (scoped production contribution / release 1.24).** Scope: MV2-002/023/024.
Deliver a persistent native global entry, including login/history routes, with
Cmd/Ctrl+K, accessible dialog focus, useful saved-source and explicitly public
Pharma/Loyer knowledge results, and a local draft handoff into existing Marvin
context. Preserve existing conversation/comparison drafts; paused or detached
context is never silently enabled. Preparing a question never submits AI work.
Both product clients retain their typed command on dismissal and share safe
shortcut behavior; route/account/dossier changes clear scoped transient state.

Dependencies: completed 1.23 themes, native AuthGate/I18n/Marvin and existing
registry/public-knowledge APIs, existing Radix/Base UI dialogs and shared
product destinations. Source readiness: current authorized registry records and
author-published knowledge only. This native entry does not add internet/model
coverage; open-web investigation stays available through the existing product
journeys. No new provider, account, secret, model, schema, API, publication,
source-permission or external-delivery change is required.

Acceptance: one globally available entry; explicit submit only; bounded real
results with exact safe links, accurate partial/failure/empty/pagination state;
current account/route context and cancellation/late-result fences; retained
question on dismissal, cleared state on authority/context transition; conflict-
safe local Marvin draft preparation without auto-activation or overwrite;
composition/repeat/nested-dialog-aware shortcuts and focus restoration; five
native locales and responsive Brandbook light/dark/forced-color/reduced-motion
styles. Run meaningful helper/adapter/SSR behavior checks, all native frontend/
localization/types/build/format gates, both client tests/lint/types/portable
builds, final backlog smoke, provider-value scans, immediate main pushes and
exact native/Sites/origin/asset verification. Browser/human/professional and the
remaining full-spec acceptance stay open. Evidence: [Global Ask/Search](docs/PRODUCT_GLOBAL_ASK.md): native 380 cases,
135 tests per client, final builds, protected-value scans and backlog smoke;
both Sites 27, 129 origin checks and 47 exact assets each, plus exact corrected
native activation/assets and unchanged runtime proof. Full specifications and
broader MV2-002/023/024 remain IN PROGRESS.

**Native reading themes and shared preference resilience — 28 September 2026:
DONE (scoped production contribution / release 1.23).** Scope: MV2-002/024.
Deliver dark/light/system reading themes across the existing native page
surfaces, forms, tables, source/evidence readers, dialogs, login and all nine
Monitoring directions. Reuse the existing Brandbook shell and both product
clients' theme controls, with one device-local preference contract. Preserve
user drafts and mounted research context when themes change. The initial theme
is Brandbook dark; explicit light/system preferences remain available per origin.
Do not equate this palette migration with native universal Ask/Search, full visual
redesign, human acceptance or completion of the dynamic dossier specification.

Dependencies: delivered 1.22 navigation/identity; existing root layouts, native
I18n/AuthGate/Marvin, client ResearchEnvironment and installed accessible UI
primitives. Source readiness: repository-owned UI only; no source-rights,
model/provider, API, schema, authentication, publication or external-delivery
change. The current tracked-source inventory has 24 CSS/TSX files containing
639 color literals; legitimate semantic statuses and artwork require review,
not blanket color inversion. Existing tokens and helpers are extended; no new
framework or dependency is required.

Acceptance: actual persisted/invalid/blocked-storage preferences, in-memory
choice under system changes, cross-tab updates and listener teardown; early
paint and hydration-safe global controls in both clients and native five locales;
semantic light/dark surfaces, text, status, focus and selection with authored
contrast evidence; print/forced-colors/reduced-motion behavior; existing nine
navigation directions and context/auth/draft gates. Run native frontend,
localization/types/build/format, both client tests/lint/types/portable builds,
final backlog smoke and protected-value scans; immediately push tested main,
exact native and existing Sites publication, origin/auth/compiled-asset checks.
No browser/human visual or language acceptance is implied by this background
cycle. Both parent tasks and full specifications remain IN PROGRESS. Detailed
implementation and exact production acceptance are recorded in
[Reading themes](docs/PRODUCT_READING_THEMES.md): native 367 cases, 129 client
tests each, all builds, 84 authored contrast pairs, corrected native production
git-8ea723c934b8 with 40 assets/43 HTTP checks, and both Sites 26 with 125 origin
checks/47 assets each. The final backlog smoke and protected-value scans pass.


## Archived overview entries, 29 September 2026 — before research-first

## Research continuation — 1.43 reviewed claim kinds

Reviewed claim kinds 1.43 DONE within verified scope. Reuse ClaimReview, DomainPack and current evidence/access pins; retained captures only. Explicit versioned editor classification, unknown legacy type, source/user/AI separation, stale-search/answer protection. [Scope, dependencies and acceptance](docs/PRODUCT_CLAIM_INTERPRETATION.md). Full target/human acceptance OPEN.

## Research continuation — 1.42 consented claim synthesis

Consented claim synthesis 1.42 DONE. Reuse current claims, citation/review pins, private access and research preview. Retained eligible captures only. Explicit versioned consent, bounded complete contradiction groups, exact quotes, stale-answer and hidden-source protection; legacy input unchanged. Scope/dependencies/source readiness/acceptance: [PRODUCT_CLAIM_SYNTHESIS.md](docs/PRODUCT_CLAIM_SYNTHESIS.md). Full target/human acceptance OPEN.

## Research continuation — 1.41 reviewed saved-evidence search

DONE within verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Research continuation — 1.40 human claim review

DONE within verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Product decision — 1.28 evidence read recovery

DONE within verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Product decision — 1.29 domain-aware dossier setup

DONE within bounded verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Owner priority — 1.30 readable dossier

DONE within bounded verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Architecture continuation — 1.31 structured dossier context

DONE within bounded verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Architecture continuation — 1.32 versioned dossier templates

DONE within bounded verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Research continuation — 1.39 reviewed entity identity

DONE within bounded verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Research continuation — 1.38 captured-source relationships

DONE within bounded verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Research continuation — 1.37 conservative local rejection

DONE within its verified scope. No threshold passed; no guard enabled; validation
remains unopened. The exact predeclared protocol and results are retained in
[release history](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md) and
[scope and evidence](docs/PRODUCT_RESEARCH_GATE_POLICY.md).

## Owner priority — 1.36 research reader repair

DONE within verified scope; [complete release commentary](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Research continuation — 1.35 bounded evaluation

DONE within scope. Full recorded overview is preserved verbatim in
[release history](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Owner priority — 1.34 iterative dossier research

DONE within scope. Full recorded overview is preserved verbatim in
[release history](BACKLOG_MONITORING_V2_RELEASE_HISTORY.md).

## Architecture continuation — 1.33 readable source coverage

DONE within verified 1.33 scope. Recorded before code: C14/C23/C24 and MV2-002/020/024.
99 API checks and 185 client tests each passed, with lint/types/Sites builds.
Compose saved page/topic/source-pack/public-search state as a calm dossier reader.
Missing or unsupported selected sources stay visible; collection is not a complete
per-dossier scan. See [scope and acceptance](docs/PRODUCT_DOSSIER_COVERAGE.md).
Existing source rights and full parent/human acceptance gates remain unchanged.

<!-- End of archived overview entries. -->


## Evidence-directed reinterpretation — 1.53

DONE within verified scope: Core and existing public Sites 52 active. Cited reinterpretation drives actual bounded follow-up research; 49 Core checks and 263 client tests each passed. [Scope and acceptance](docs/PRODUCT_ADAPTIVE_ORIENTATION.md).

## Early source-backed orientation — 1.52

DONE within verified scope: Core and both public Sites 51 active; one bounded early cited interpretation while research continues, retained history and pause/correction. [Scope, dependencies, source readiness and acceptance](docs/PRODUCT_EARLY_ORIENTATION.md). No new monitoring authority.

The two completed overviews above were archived verbatim from the active backlog on 29 September 2026 during scope recording for 1.55.
