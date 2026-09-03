# Helvetic Lens — Development Backlog

**See what changed. Understand what matters.**

This backlog implements the product described in [README.md](README.md): a local-AI-first Swiss regulatory monitor with immutable evidence, a time-based legal registry, official-source connectors, cross-document impact analysis, and organization workspaces.

**Status:** The hackathon MVP (`HL-001`–`HL-031`, `HL-033`–`HL-047`, `HL-050`–`HL-051`) and decision-ready comparison work (`HL-058`–`HL-063`) are implemented and verified through the API, browser build, migrations, and regression tests. Five-language product localization (`HL-057`) is in progress. `HL-032` awaits its physical dual-GTX-1080 acceptance benchmark. The remaining public-beta/local-AI-first roadmap is planned. See the [target architecture](docs/ARCHITECTURE.md), [decision-ready AI triage design](docs/AI_TRIAGE.md), [impact-report contract](docs/IMPACT_REPORT.md), [Ask routing](docs/ASK_ROUTING.md), [localization contract](docs/LOCALIZATION.md), and [verification evidence](docs/VERIFICATION.md). Stable `HL-xxx` identifiers remain the task reference.

## Scope and priorities

- **P0 — release foundation or safety/capacity gate.** The public beta cannot open without it.
- **P1 — required public-beta product capability.** P1 is required for the agreed local-AI-first product, even when it can follow the P0 foundation.
- **P2 — valuable follow-up after public beta.** Add after the core three sources, registry, and impact inbox are reliable.
- **P3 — evidence-driven expansion.** Implement only when real use demonstrates the need.

The completed baseline contains 28 items, including two deliberately deferred optional items. The public-beta roadmap contains **29 required items (`HL-029`–`HL-049` plus `HL-057`–`HL-064`)** and **7 after-beta items (`HL-050`–`HL-056`)**. Follow dependencies and checkpoints; priority alone is not an execution order. No calendar estimates are assumed until the dual-GTX-1080 benchmark and connector contract spikes are complete.

Keep the proven stack and add only the infrastructure now justified by public use: **Next.js, Tailwind CSS/shadcn/ui, FastAPI, PostgreSQL, Redis, Celery, Caddy, BeautifulSoup, PyMuPDF, `difflib`, and a private llama.cpp-based local inference runtime**. A quantized **Apertus 8B** profile is the intended production default only after it passes the target-hardware gate; the smaller verified profile remains valid for development. Cloud model adapters are optional and disabled by default. **pgvector remains conditional on a measured recall gap.**

## Release checkpoints

| Checkpoint                      | Required items        | Observable result                                                                                                                                               |
| ------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M0 — Ready to build             | HL-001–HL-003         | Known test sources and historical inputs; web app, API, and persistent database run locally.                                                                    |
| M1 — Real sources and laws      | HL-004–HL-008         | A user connects a supported site, discovers documents, or adds a law directly; real extracted content is saved.                                                 |
| M2 — Historical comparisons     | HL-009–HL-013         | A user imports an earlier version, selects two versions, and inspects exact changes and saved evidence.                                                         |
| M3 — Live monitoring            | HL-014–HL-016         | Scans fetch current content, report actual progress, preserve history, and show useful results on the dashboard.                                                |
| M4 — Apertus explanations       | HL-017–HL-019, HL-025 | Model settings persist; impact analysis and questions work against real saved passages with working citations.                                                  |
| M5 — Accepted MVP               | HL-020–HL-022         | Regression checks, product acceptance, and a repeatable live demonstration pass.                                                                                |
| M6 — Local-first foundation     | HL-029–HL-035         | One server has durable queues, managed local models, organization data, login, and enforced read-only users.                                                    |
| M7 — Swiss legal registry       | HL-036–HL-043         | Normalized events from Fedlex, Parliament, the Federal Supreme Court, and their official notices appear in a time-grouped registry.                             |
| M7A — Decision-ready comparison | HL-058–HL-064         | Verified document identity, legal-unit changes, bounded local inference, useful actions, and an evidence-first review experience replace noisy passage batches. |
| M8 — Impact intelligence        | HL-044–HL-046         | Evidence-backed relations connect new events to monitored laws and appear in an actionable organization inbox.                                                  |
| M9 — Public beta                | HL-047–HL-049, HL-057 | Five-language UI/AI/history, admin/operations UI, Internet-facing single-host deployment, recovery, and the reproducible 100-user gate pass.                    |

Preserve `HL-001`–`HL-028` as the completed MVP record. For public beta, implement `HL-029` first, establish the `HL-057` internationalization conventions immediately, then run durable-job, local-model, organization, and translation work in parallel where their dependencies allow. Complete tenancy and the shared-corpus split before adding broad connectors; otherwise source records would need a second migration. Complete `HL-058`–`HL-064` before treating AI output as a product decision aid: the exact diff stays available for audit, while the default flow must identify material legal-unit changes and produce bounded, validated results. Localize each screen as it is built instead of translating the finished product at the end. Finish operations and the measured capacity gate before exposing registration publicly.

## Task index

| ID                | Priority | Status   | Dependencies                                           | Deliverable                                                         |
| ----------------- | -------- | -------- | ------------------------------------------------------ | ------------------------------------------------------------------- |
| [HL-001](#hl-001) | P0       | DONE     | None                                                   | Verified source examples and historical inputs                      |
| [HL-002](#hl-002) | P0       | DONE     | None                                                   | Runnable app, API, and database                                     |
| [HL-003](#hl-003) | P0       | DONE     | HL-002                                                 | Persistent domain model and migrations                              |
| [HL-004](#hl-004) | P0       | DONE     | HL-001, HL-002                                         | Real HTML/PDF fetching and extraction                               |
| [HL-005](#hl-005) | P0       | DONE     | HL-003, HL-004                                         | Immutable snapshots and saved evidence                              |
| [HL-006](#hl-006) | P0       | DONE     | HL-003, HL-004                                         | Website connection management                                       |
| [HL-007](#hl-007) | P0       | DONE     | HL-005, HL-006                                         | Tracked laws and direct document URLs                               |
| [HL-008](#hl-008) | P1       | DONE     | HL-004, HL-006, HL-007                                 | Bounded discovery and document search                               |
| [HL-009](#hl-009) | P0       | DONE     | HL-005, HL-007                                         | Previous-version import                                             |
| [HL-010](#hl-010) | P0       | DONE     | HL-007, HL-009                                         | Version history and baseline selection                              |
| [HL-011](#hl-011) | P0       | DONE     | HL-005                                                 | Shared passage and word comparison engine                           |
| [HL-012](#hl-012) | P0       | DONE     | HL-010, HL-011                                         | Visual diff with change navigation                                  |
| [HL-013](#hl-013) | P0       | DONE     | HL-005, HL-012                                         | Version-specific evidence viewer                                    |
| [HL-014](#hl-014) | P0       | DONE     | HL-007, HL-010, HL-011                                 | Live scans and historical comparisons                               |
| [HL-015](#hl-015) | P0       | DONE     | HL-014                                                 | Actual progress, partial failures, and recovery                     |
| [HL-016](#hl-016) | P1       | DONE     | HL-006, HL-008, HL-012, HL-015                         | Dashboard and scan controls                                         |
| [HL-017](#hl-017) | P0       | DONE     | HL-002, HL-003                                         | Verified Apertus adapter and company context                        |
| [HL-018](#hl-018) | P0       | DONE     | HL-011, HL-013, HL-017                                 | Cited impact analysis and actions                                   |
| [HL-019](#hl-019) | P1       | DONE     | HL-013, HL-017, HL-018                                 | Ask Apertus with version-specific citations                         |
| [HL-020](#hl-020) | P1       | DONE     | HL-009, HL-014, HL-015, HL-018, HL-019                 | Regression checks for state and evidence                            |
| [HL-021](#hl-021) | P1       | DONE     | HL-008, HL-012, HL-013, HL-016, HL-019, HL-020, HL-025 | End-to-end product acceptance                                       |
| [HL-022](#hl-022) | P1       | DONE     | HL-001, HL-021                                         | Setup documentation and repeatable demo                             |
| [HL-023](#hl-023) | P2       | DEFERRED | HL-018, HL-022                                         | Optional business impact matrix                                     |
| [HL-024](#hl-024) | P2       | DEFERRED | HL-019, HL-022                                         | Optional pgvector retrieval                                         |
| [HL-025](#hl-025) | P0       | DONE     | HL-002, HL-003, HL-017 adapter code                    | Settings page with persisted Apertus parameters                     |
| [HL-026](#hl-026) | P1       | DONE     | HL-006, HL-007, HL-017                                 | Integration diagnostics and controlled deletion                     |
| [HL-027](#hl-027) | P1       | DONE     | HL-018, HL-019, HL-025, HL-026                         | Resilient AI calls, saved history, and prompt controls              |
| [HL-028](#hl-028) | P1       | DONE     | HL-017, HL-027                                         | Robust citation-row handling and local Docker Apertus fallback      |
| [HL-029](#hl-029) | P0       | DONE     | HL-028                                                 | Single-host local-first architecture and capacity contract          |
| [HL-030](#hl-030) | P0       | DONE     | HL-029                                                 | Durable PostgreSQL jobs with Redis/Celery execution                 |
| [HL-031](#hl-031) | P0       | DONE     | HL-029, HL-030                                         | Local model library, downloads, and runtime manager                 |
| [HL-032](#hl-032) | P0       | IN PROGRESS | HL-030, HL-031                                      | Local-first inference routing, GPU fairness, and hardware benchmark |
| [HL-033](#hl-033) | P0       | DONE     | HL-003, HL-029                                         | Shared public corpus and organization-aware migration               |
| [HL-034](#hl-034) | P0       | DONE     | HL-033                                                 | Registration, login, sessions, and onboarding                       |
| [HL-035](#hl-035) | P0       | DONE     | HL-034                                                 | Organization membership and enforced admin/viewer access            |
| [HL-036](#hl-036) | P0       | DONE     | HL-005, HL-011, HL-033                                 | Normalized regulatory documents, dates, and events                  |
| [HL-037](#hl-037) | P1       | DONE     | HL-035, HL-036                                         | Time-grouped monitoring registry and document timeline              |
| [HL-038](#hl-038) | P0       | DONE     | HL-030, HL-036                                         | Versioned incremental connector contract                            |
| [HL-039](#hl-039) | P1       | DONE     | HL-038, existing ELI resolver                          | Fedlex federal-law catalogue connector                              |
| [HL-040](#hl-040) | P1       | DONE     | HL-038                                                 | Swiss Parliament initiatives and bills connector                    |
| [HL-041](#hl-041) | P1       | DONE     | HL-038                                                 | Swiss Federal Supreme Court decisions connector                     |
| [HL-042](#hl-042) | P1       | DONE     | HL-030, HL-039–HL-041                                  | Scheduled synchronization, deduplication, and watch fan-out         |
| [HL-043](#hl-043) | P1       | DONE     | HL-038, HL-042                                         | Official notices and source-linked news events                      |
| [HL-044](#hl-044) | P1       | DONE     | HL-036, HL-039–HL-043                                  | Evidence-backed relation graph and candidate generation             |
| [HL-045](#hl-045) | P1       | DONE     | HL-032, HL-044, HL-060, HL-061                         | Local-AI potential-impact analysis                                  |
| [HL-046](#hl-046) | P1       | DONE     | HL-037, HL-045, HL-063                                 | Impact inbox and monitored-law cross-links                          |
| [HL-047](#hl-047) | P1       | DONE     | HL-031, HL-035, HL-042                                 | Platform and organization admin console                             |
| [HL-048](#hl-048) | P0       | PLANNED  | HL-029–HL-035, HL-038                                  | Public single-server deployment and operations baseline             |
| [HL-049](#hl-049) | P0       | PLANNED  | HL-037–HL-048, HL-057–HL-064                           | Reproducible recovery and 100-user capacity gate                    |
| [HL-057](#hl-057) | P1       | IN PROGRESS | HL-032, HL-034–HL-037, HL-045–HL-047                | Complete German, French, Italian, Romansh, and English localization |
| [HL-058](#hl-058) | P0       | DONE     | HL-005, HL-036, HL-038                                 | Document-identity gate before comparison or AI                      |
| [HL-059](#hl-059) | P0       | DONE     | HL-011, HL-036, HL-058                                 | Legal-unit semantic diff with noise classification                  |
| [HL-060](#hl-060) | P0       | DONE     | HL-030–HL-032, HL-059                                  | Fixed-budget local-AI analysis planner                              |
| [HL-061](#hl-061) | P1       | DONE     | HL-033, HL-060                                         | Actionable, deduplicated impact-report contract                     |
| [HL-062](#hl-062) | P1       | DONE     | HL-060, HL-061                                         | Intent-routed Ask experience and safe context selection             |
| [HL-063](#hl-063) | P1       | DONE     | HL-030, HL-037, HL-059–HL-062                          | Decision-ready comparison UX and background progress                |
| [HL-064](#hl-064) | P0       | PLANNED  | HL-057–HL-063                                          | AI-triage regression, evidence, latency, and usability gate         |
| [HL-050](#hl-050) | P2       | DONE     | HL-038, HL-042                                         | Broader official regulatory news connectors                         |
| [HL-051](#hl-051) | P2       | DONE     | HL-044, HL-050                                         | Measured semantic candidate recall with pgvector if justified       |
| [HL-052](#hl-052) | P2       | PLANNED  | HL-034, HL-046, HL-057                                 | Opt-in email and web digests                                        |
| [HL-053](#hl-053) | P3       | PLANNED  | HL-044–HL-046                                          | Relation review workflow and visual graph                           |
| [HL-054](#hl-054) | P3       | DONE     | HL-034, HL-035                                         | Account recovery, verification, 2FA, and SSO refinements            |
| [HL-055](#hl-055) | P2       | DONE     | HL-038, HL-041                                         | Broader federal and cantonal court coverage                         |
| [HL-056](#hl-056) | P3       | PLANNED  | HL-049                                                 | Multi-host or high-availability deployment after measured need      |

## M0 — Ready to build

<a id="hl-001"></a>

### HL-001 — Verify initial sources and historical inputs

Select a small, realistic validation set without restricting users to a hard-coded source list.

Acceptance criteria:

- Record 2–3 public regulatory source URLs, including an HTML document, a text-based PDF, and a listing page suitable for discovery. One site may cover multiple formats.
- Record the expected title, content type, relevant content area, language, and any known extraction limitation for each example.
- Obtain at least one earlier document version with recorded provenance. If only a modified example is available, label it synthetic; do not present it as an authentic historical law.
- Prepare a small controlled before/after pair with known changes, including a changed number or deadline. This is for deterministic verification, not a replacement for real source support.
- Keep source and fixture documentation in the repository; do not commit credentials or material without permission to redistribute it. Link to originals when redistribution is unclear.

<a id="hl-002"></a>

### HL-002 — Create the runnable application foundation

Provide one Next.js web app, one FastAPI service, and one PostgreSQL database.

Acceptance criteria:

- Establish a small layout such as `apps/web`, `services/api`, and `docs`; install Tailwind CSS and shadcn/ui without adding unrelated frameworks.
- Document a working local startup procedure. A simple Compose configuration may run the services and a persistent database volume; no cluster or worker fleet is required.
- Include an environment-variable example with placeholders, a database readiness check, and a visible web-to-API connection check.
- Define the initial API conventions for identifiers, validation errors, and asynchronous scan status; expose the FastAPI API documentation.
- Provide basic formatting, lint/type-check, and verification commands appropriate to the code that exists. Keep environment files, downloads, and generated runtime data out of Git.

<a id="hl-003"></a>

### HL-003 — Add the domain model and migrations

Persist the state required to explain what was observed and which versions were compared.

Acceptance criteria:

- Add records for **Source, TrackedLaw, DocumentVersion, Scan**, per-law scan results, and **Comparison**, with analysis attached to a comparison. A scan result may also represent a failed fetch with no new version.
- A tracked law has a current URL, display name, monitoring state, and a reference to its last successfully observed live snapshot. Adding a direct URL must not require prior discovery.
- Versions retain origin, fetch/import time, optional stated version date and its provenance, extraction format/version, text hash, artifact location, and paragraph/page references.
- Comparisons explicitly reference old and new versions of the same law and their mode: ordinary monitoring, historical comparison, or comparison of saved versions.
- Store the single company profile and analysis context needed by HL-017/HL-018. Apply migrations to a clean database and preserve records across service restarts.
- Keep observation history separate from snapshot content so unchanged checks and a return to previously seen content can be recorded without duplicating stored snapshots.

## M1 — Real sources and laws

<a id="hl-004"></a>

### HL-004 — Fetch public documents and extract usable text

Implement one extraction path shared by current documents and imported versions.

Acceptance criteria:

- Fetch supported public HTTP(S) HTML/PDF URLs, retain the original and final URL, and report the actual detected input type.
- Extract meaningful HTML text with BeautifulSoup and text-based PDF content with PyMuPDF. Keep headings, article numbers, substantive dates, and paragraph/page boundaries.
- Normalize whitespace and obvious navigation boilerplate consistently without erasing legal wording, numbers, or punctuation that may carry meaning.
- Return a preview containing title, content type, text excerpt, extraction result, and any limitation before the user saves a document.
- Resolve supported Fedlex ELI law URLs through the official Linked Data metadata into their current or explicitly dated HTML/PDF publication, while retaining the stable ELI URL for later scans and recording resolved provenance.
- Apply practical time, redirect, and download limits; validate public URL targets, including redirects. Report network failures, empty extraction, scanned PDFs, login pages, and unsupported JavaScript pages as distinct failures or unsupported inputs.

<a id="hl-005"></a>

### HL-005 — Save immutable snapshots and evidence

Keep enough original evidence to reproduce a comparison after the live website changes.

Acceptance criteria:

- Persist normalized text, a content hash scoped to the tracked law and extraction rules, stable passage references, and original files or equivalent saved source evidence.
- Store uploaded artifacts in persistent local storage for the initial deployment; no object-storage platform is required.
- Preserve origin, original filename/URL, source-stated or user-supplied version date, and actual fetch/import time separately.
- Reuse an existing matching content snapshot where appropriate while recording each observation/import and its provenance; an imported origin must not erase evidence of a later live observation.
- Treat saved snapshots as immutable. Re-importing an old version or failing a fetch must not replace the current live snapshot.
- Reopen a saved PDF page or text passage successfully after the source changes or the service restarts.

<a id="hl-006"></a>

### HL-006 — Build website connection management

Let the user configure supported websites through the interface.

Acceptance criteria:

- Provide an **Add website** form for a name and public root/listing URL, plus an optional section boundary for discovery.
- **Test connection** performs a real fetch and shows the extracted preview or a useful error. A successful HTTP response with no usable document content is not sufficient.
- Save and edit source configuration in PostgreSQL; display last connection/check status and the configured discovery boundary.
- A newly configured supported website works without changing source code or a hard-coded allowlist of demo sites.
- Explain the difference between connecting a website and selecting individual laws to monitor.

<a id="hl-007"></a>

### HL-007 — Add and manage tracked laws by URL

Make direct document entry the shortest usable path into the product.

Acceptance criteria:

- **Add law** accepts a public HTML/PDF URL, previews its contents, lets the user confirm or edit the title, and saves the tracked law.
- Associate the law with its source where applicable, but do not require the user to run website discovery first.
- Save the first successful live snapshot as **Baseline created**. Do not invent a change when no earlier version exists.
- Allow renaming, pausing, and resuming monitoring. Paused laws are excluded from **Scan all** without losing their history.
- Detect an already tracked document URL and offer the existing law instead of silently creating duplicate watchlist entries.
- Show clear loading, empty, and error states; a failed preview must not create a misleading successful baseline.

<a id="hl-008"></a>

### HL-008 — Discover and search documents within a source

Find candidate laws in a bounded site section and let the user choose what to track.

Acceptance criteria:

- Start at the configured listing page and follow at most one link level, inspecting at most 50 candidate pages per run by default.
- Resolve relative URLs, remove fragments for duplicate detection, preserve meaningful query parameters, and stay within the configured site/section boundary.
- Show candidate title, URL, content type, and extraction preview; support title/keyword filtering over the inspected results.
- Selecting a candidate opens the same law confirmation flow as HL-007. Previously tracked candidates are labeled accordingly.
- Show inspected counts, the limit reached, and per-candidate errors. Never imply exhaustive site coverage.
- Label newly discovered documents separately from changes to previously tracked laws; discovery alone is not evidence of a legal amendment.

## M2 — Historical comparisons

<a id="hl-009"></a>

### HL-009 — Import a previous version

Allow the user to provide an earlier document without waiting for a future live update.

Acceptance criteria:

- Support PDF, HTML, and TXT upload; pasted text; and a direct URL to a historical copy. Reuse the extraction and snapshot pipeline.
- Show the extracted preview and selected law before confirmation. Reject empty or unsupported input with a useful explanation.
- Accept an optional stated version date, retain import time separately, and label a user-entered date as supplied by the user.
- Retain provenance and an explicit synthetic-demo marker when applicable. Uploading a file does not verify it as an official historical version.
- Let the user confirm that the imported document belongs to this law and select it as a comparison baseline.
- Do not change the current live pointer, prior scan results, or stored evidence when importing an older version. A snapshot import alone does not activate live monitoring without a current URL.

<a id="hl-010"></a>

### HL-010 — Show version history and select a baseline

Make it explicit which documents are being compared.

Acceptance criteria:

- The law detail page lists saved versions/observations with origin, available version date, fetch/import time, and the current live snapshot indicator.
- Offer **Last live version**, **Choose previous version**, and **Compare saved versions** as clear comparison choices.
- Old/new selectors accept only versions belonging to the selected law. Do not infer legal chronology solely from upload time or present an unknown date as verified.
- Show historical and synthetic labels before starting the operation and retain those labels on the result.
- Allow repeating a historical comparison without resetting the law or deleting history.

<a id="hl-011"></a>

### HL-011 — Implement the shared comparison engine

Produce deterministic text differences before asking a model to explain them.

Acceptance criteria:

- Use `difflib` to produce added, removed, and modified passage groups, with word-level operations within modified passages.
- Return stable change identifiers, old/new version and passage references, counts, and enough surrounding context for the viewer and Apertus.
- Persist the comparison and its selected version pair/mode; reuse the same engine for live scans, historical comparisons, and saved-version comparisons.
- Identical normalized input produces an unchanged result. Whitespace-only normalization does not create a change, while changed numbers, dates, or legal wording remain visible.
- Keep the deterministic diff independent of model availability. Do not treat a model opinion as proof that text changed.

<a id="hl-012"></a>

### HL-012 — Build the visual diff and change navigation

Let the user see the exact wording that changed.

Acceptance criteria:

- Show old and new text side by side, with red removals, green additions, and word highlights within modified passages.
- Provide a change list, change counts, filters for added/removed/modified content, and navigation to the corresponding passages in both panes.
- Display source, version labels, provenance, available dates, and whether this is a historical comparison or a new monitoring result.
- Make long documents usable by collapsing unchanged context or rendering manageable sections. Provide a text legend and keyboard-accessible navigation in addition to color.
- A controlled change from **30** to **60** is highlighted at the exact location, not represented only by a summary card. Identical versions have a clear unchanged state.

<a id="hl-013"></a>

### HL-013 — Open saved evidence for a specific version

Provide the shared evidence destination used by the diff, impact analysis, and questions.

Acceptance criteria:

- A version/passage reference opens the saved text with the target passage highlighted; a PDF reference opens or identifies the saved page where available.
- Always display the referenced version and its provenance, including imported files. Offer the original source URL separately when it exists.
- Evidence remains accessible if the live URL changes, is unavailable, or now serves a newer document.
- Render extracted text safely instead of executing imported page HTML. Missing or invalid evidence references produce a clear error, not a different passage.
- Both old and new sides of a comparison can be cited independently.

## M3 — Live monitoring

<a id="hl-014"></a>

### HL-014 — Run live scans and explicit historical comparisons

Fetch actual current content, compare the right versions, and preserve monitoring history.

Acceptance criteria:

- **Scan now** handles one law or all active laws. Capture the ordinary comparison baseline before saving a newly fetched snapshot.
- Ordinary scans use the last successfully observed live version. The first successful fetch without a baseline yields **Baseline created**; identical current content yields **Unchanged**.
- A historical selection compares the requested earlier snapshot with current fetched content even when that current snapshot is already stored. Label this result **Historical comparison**, not a newly discovered amendment.
- Record the live observation and the selected comparison mode/baseline separately. Importing or selecting an older snapshot must never make it the current live version.
- Do not create duplicate content snapshots for unchanged checks. If content returns from A to B to A, reuse snapshot A but record the change from B to A and the new observation.
- **Compare saved versions** uses the same comparison engine without a network request and does not advance the live monitoring state.
- Persist successful comparisons even if later analysis fails. Failed fetching/extraction must not overwrite the last good version. Prevent concurrent scans of the same law from racing its baseline update, using a simple single-service mechanism.

<a id="hl-015"></a>

### HL-015 — Expose real progress and recover incomplete scans

Make actual work, partial success, and failures visible.

Acceptance criteria:

- Persist per-law stages such as **Queued, Fetching, Extracting, Comparing, Analysing**, with explicit final comparison and analysis outcomes.
- Provide a status endpoint and simple client polling, or an equivalent small streaming implementation. The interface displays real stages and completed/total counts, not simulated percentages.
- Separate changed, unchanged, baseline-created, and failed document results. A scan may finish with some documents successful and others failed.
- Report model analysis as not configured, pending, succeeded, or failed independently of a valid comparison. Wire the actual model stage through HL-018.
- On restart, mark unfinished runs as interrupted instead of leaving them permanently running or reporting success. Keep completed versions and comparisons intact.
- Offer safe retry of a failed document or failed analysis. Reuse completed work where possible and avoid adding a distributed queue for this scope.

<a id="hl-016"></a>

### HL-016 — Build the dashboard and scan controls

Bring source management, the watchlist, and scan results into one usable interface.

Acceptance criteria:

- Display connected sources, active/paused laws, last check times, latest outcomes, and links to law details and version history.
- Provide **Scan selected** and **Scan all active** actions with actual progress from HL-015 and clear handling of an empty watchlist.
- Keep newly discovered documents, first baselines, unchanged checks, historical comparisons, new live changes, and failures visibly distinct.
- Open the selected comparison directly from a result. Display Apertus impact only when an analysis exists; otherwise show the actual pending, unavailable, or failed state.
- Basic filtering by source and result state works with persisted records. Refreshing the page does not reset the result or fabricate a new scan.

## M4 — Apertus explanations

<a id="hl-017"></a>

### HL-017 — Verify Apertus access and add a small model adapter

Connect to a real Apertus deployment and supply one company profile.

Live verification: the saved Public AI configuration reached `swiss-ai/apertus-v1.5-8b`, returned cited answers and impact analysis, and completed a synthetic 1,406-passage comparison through bounded requests without truncation or HTTP 504.

Acceptance criteria:

- Confirm the reachable endpoint, actual model identifier, authentication method, supported context budget, and a successful real request. Treat **Apertus v1.5 8B** as a proposed target until verified; document any mismatch instead of silently substituting a model.
- Keep endpoint, model ID, credentials, and request limits configurable on the server. Commit placeholder configuration only; do not expose model credentials to the browser.
- Implement one small adapter with bounded requests and explicit timeout/unavailable errors. Report the actual model status, without fabricated model responses.
- Provide one editable, persisted company profile containing the short business description and relevant business areas. No multi-company administration is needed.
- Document setup prerequisites and any access blocker early. Real source fetching and visual comparison continue to work without Apertus; the full model-enabled MVP is not accepted until a real inference call succeeds.

<a id="hl-018"></a>

### HL-018 — Generate impact analysis, actions, and supporting evidence

Explain a selected comparison using the saved source text and company profile.

Acceptance criteria:

- Persist a complete deterministic article/passage diff for the two saved versions and supply every changed old/new passage with explicit change, version, passage, and position identifiers. Treat document content as evidence, not instructions to the assistant.
- Return a concise summary, why it matters, affected business areas, indicative high/medium/low impact with a reason, and 1–3 suggested actions. Attach supporting references to factual conclusions.
- Validate the output shape and evidence references against the supplied passages before displaying citations. Quoted evidence must match the referenced saved text. Invalid JSON/schema/citations receive one constrained repair attempt and are rejected if that also fails.
- Never truncate or retrieval-rank the changed-passage set. Disclose when its size exceeds the configured warning threshold; an upstream context-window failure leaves the complete visual diff available and must not be presented as a successful assessment.
- Save results against the version pair, company-profile revision, model ID, and analysis/prompt version so changed context does not reuse a stale explanation.
- Connect actual analysis status to the scan/dashboard. On model failure, leave the diff available and offer analysis retry without refetching the document or creating another version.
- Show the source evidence and indicate that impact and actions are review aids rather than authoritative legal conclusions.

<a id="hl-019"></a>

### HL-019 — Add Ask Apertus with version-specific citations

Answer questions about the selected law or comparison using inspectable evidence.

Acceptance criteria:

- Provide a question input and answer panel scoped to the selected law/version or old/new comparison. Keep cross-law search and a large chat platform out of scope.
- Use every changed passage from the complete persisted comparison, without embeddings or retrieval ranking. Preserve the deterministic old/new pairing in the model context.
- Answers cite valid version and passage identifiers; citations open the matching saved passage or PDF page through HL-013.
- When changed passages do not support an unrelated answer, explicitly state that limitation. A “what changed?” question must not claim insufficient context when the complete comparison is available. Reject invalid citations instead of displaying fabricated links or silently using the latest live version.
- Follow-up questions retain the selected comparison context. Loading, timeout, and model-unavailable states are visible and leave the diff usable.
- Verify at least one question about changed wording, one about the earlier version, and one that cannot be answered from the supplied documents.

<a id="hl-025"></a>

### HL-025 — Configure Apertus providers through a Settings page

Added at the user's request after implementation began and verified with the live adapter in HL-017.

Acceptance criteria:

- Provide a Settings page reachable from desktop and mobile navigation, with provider, Product ID or endpoint, model, credential handling, timeout, evidence warning threshold, maximum output tokens, temperature, Top P, presence penalty, reasoning effort, and JSON-mode controls.
- Test the current form with an actual adapter request without implicitly saving it; make unavailable, invalid, and successful connection states explicit.
- Offer the documented direct Public AI and Hugging Face router address/model as draft defaults, preserving the key and other parameters. Explain which provider credential each route needs, and authentication, access, route/model, and quota failures separately.
- Offer a native Infomaniak mode that derives its OpenAI-compatible URL from the numeric Product ID, loads the product's available models from `/models`, and presents them in a dropdown. Map completion length to `max_completion_tokens`, request one non-streaming response, and verify the live adapter with an actual available Apertus model.
- Save valid settings in the workspace database and apply them to new requests immediately. Preserve them across service restarts.
- Keep an existing key when editing other fields; allow explicit replacement, removal, and environment inheritance. Never return keys through the API, including validation errors.
- Retain environment defaults and offer an explicit reset without affecting documents, versions, or scans. Document that saved keys are held server-side in the local database and its backups.
- Mark previous analyses as stale after relevant model/context/generation changes. In-flight work retains the configuration it started with.
- Expose the existing company profile editor from the Settings page. Do not add account administration or a model-hosting platform.

<a id="hl-026"></a>

### HL-026 — Add integration diagnostics and controlled deletion

Added at the user's request after the core monitoring and Infomaniak flows were working.

Acceptance criteria:

- Persist each outbound website, Fedlex, Firecrawl, and OpenAI-compatible model request with provider, operation, method, URL, outcome, HTTP status, duration, request/response sizes, headers, bodies, and an explicit error where applicable.
- Redact authorization, cookies, token/key/password fields, and matching credential values before persistence. Bound large text/JSON payloads and represent binary documents with content type, byte count, and hash so diagnostics cannot make ordinary monitoring unbounded.
- Provide an **Integration logs** page in desktop and mobile navigation. Load lightweight rows first; allow provider/outcome filters, text search, sortable columns, pagination, refresh, and full redacted request/response inspection on demand.
- Allow clearing all diagnostic logs with explicit confirmation. Clearing logs must not change sources, documents, versions, scans, comparisons, analyses, profile, or provider settings.
- Allow removing a website from Sources with confirmation while leaving its tracked documents available as independent monitored documents.
- Allow permanently deleting a monitored document with confirmation. Remove its observations, versions, comparisons, analyses, scan entries, empty scans, and artifact files that are no longer referenced. Block deletion while that document has a queued or running scan.
- Cover redaction, sorting, filtering, detail retrieval, clearing, source detachment, dependency cleanup, artifact cleanup, and active-scan blocking with deterministic API checks.

<a id="hl-027"></a>

### HL-027 — Make AI results resilient, persistent, and configurable

Added after live Infomaniak runs exposed intermittent transport failures and inconsistent structured response envelopes.

Acceptance criteria:

- Retry interrupted connections, timeouts, rate limits, and temporary 5xx responses with a configurable bounded attempt count. Log every attempt separately and process large-model batches sequentially by default.
- Accept a valid structured answer inside common provider wrappers or encoded JSON strings, validate it against the fixed schema and exact saved citations, and make at most one explicit repair request when validation fails.
- Persist every Impact run and Ask request with its date, model, prompt revision, evidence coverage, selected comparison, status, error, question, conversation context, answer, and citations. Display the unified history on the comparison and monitored-document pages.
- Reuse a successful result only when its comparison, company profile, provider/model settings, prompt text, question, and supplied question history match. Show reuse counts and make zero provider requests on a cache hit.
- Use the complete deterministic diff for change questions and Impact. For other questions, process every extracted passage from both saved original versions in bounded batches by default; keep changed-passages-only as an explicit lower-cost option.
- Keep original version artifacts available for inspection and download. Do not claim raw PDF upload support when the configured OpenAI-compatible chat endpoint does not document a PDF attachment contract.
- Provide a **Prompt settings** page for Impact, Ask, synthesis, repair, and question-context instructions. Preserve server-controlled schemas, evidence separation, exact citation checks, and one-repair limits regardless of editable wording.
- Cover retries, wrapped/double-encoded output, full-version context, cache reuse, failed-request history, prompt cache boundaries, history cascade deletion, browser rendering, and a live Infomaniak Ask/Impact run.

<a id="hl-028"></a>

### HL-028 — Recover real provider citations and add local Docker inference

Added after a large Infomaniak comparison returned successful HTTP responses but sometimes used passage positions instead of the requested batch-row numbers, while separate provider connections occasionally closed mid-response.

Acceptance criteria:

- Include an explicit `row_number` as the first column in every batched evidence row and tell the model to cite only that value.
- Accept an out-of-range model reference only when it maps to actual supplied passage positions or numeric passage identifiers; continue rejecting invented citations.
- Include the allowed numeric range in the single repair request and keep exact server-materialized version, passage, quote, page, and evidence links.
- Respect numeric `Retry-After` responses and use bounded exponential delays between interrupted transport attempts.
- Add Local Docker Apertus as a selectable provider whose host/Compose endpoint is derived by the API, whose models load through the OpenAI-compatible `/models` route, and which never receives a saved remote-provider credential.
- Provide and verify a repeatable optional Compose service using the official llama.cpp server image and a compact Apertus instruction checkpoint suitable for local pipeline diagnostics.

## M5 — Verification and demonstration

<a id="hl-020"></a>

### HL-020 — Cover state transitions and evidence with regression checks

Protect the behavior that makes the product reliable. Implement these checks alongside the corresponding tasks, not only at the end.

Acceptance criteria:

- Use controlled HTML/PDF/text inputs to cover first baseline, actual change, unchanged content, normalized whitespace, and a changed number/date that must remain visible.
- Verify repeated historical comparisons against an unchanged current source, duplicate imports, and A → B → A content returning without duplicate snapshots or lost observation history.
- Verify that importing an older document does not move the live pointer, that a failed fetch/empty extraction does not destroy the last good version, and that overlapping scans cannot corrupt their baselines.
- Cover mixed-success batches, interrupted scans after restart, model timeout after a successful comparison, and analysis-only retry.
- Validate old/new citation targets, exact quoted evidence, unavailable evidence, and stale analysis after a company-profile/context change.
- Use deterministic model test doubles only in automated checks and label them as such. They do not replace the real Apertus check required by HL-017/HL-021.

<a id="hl-021"></a>

### HL-021 — Verify the complete product workflow

Exercise the product from the browser through persistence, extraction, comparison, and model output.

Acceptance criteria:

- From a clean installation, connect a website, discover a document, add it to the watchlist, and separately add another law by direct URL without changing code.
- Import an earlier version, choose it as the baseline, run a real fetch, inspect exact changes, read the Apertus analysis, ask a question, and open a citation to the correct version.
- Repeat the historical comparison while current content is unchanged; confirm the correct result label and no duplicate snapshots. Run an ordinary unchanged check separately.
- Restart the app/database services without deleting their volumes; verify sources, paused states, versions, evidence, and scan results are still available.
- Verify visible behavior for unsupported input, an unavailable source, a partial batch failure, and a missing/unavailable model. No failed path appears as successful analysis.
- Compare two saved versions with the network unavailable and confirm the interface does not claim a live scan occurred.
- Automate the deterministic browser path against a controlled local source where practical, then record a manual smoke check against the actual selected public sources and the actual Apertus endpoint. Record limitations honestly; do not mark the full MVP complete on mock-only evidence.

<a id="hl-022"></a>

### HL-022 — Document setup and rehearse a repeatable demonstration

Make the completed workflow usable by another developer or hackathon presenter.

Acceptance criteria:

- Update the README with commands that have actually been verified, required environment variables, migration/setup steps, and the supported source limitations.
- Add a short demo guide covering website connection, direct law entry, historical import, baseline choice, live scanning, visual diff, impact analysis, and a cited question.
- Keep a suitable earlier document or instructions for obtaining it with provenance. Any altered example remains visibly marked synthetic throughout the demonstration.
- Rehearse the same demo twice without changing the external website, deleting history, or replacing real processing with preset cards or simulated progress.
- Document the explicit saved-version fallback for network failure and the model-unavailable behavior; do not present either as a successful live/model run.
- Record the completed acceptance results and remaining known limitations. Mark backlog items done only after their criteria are met; do not bundle enterprise infrastructure into this checkpoint.

## Optional work after acceptance

<a id="hl-023"></a>

### HL-023 — Add the business impact matrix

Provide an additional view over existing evidence-backed analyses.

Acceptance criteria:

- Display changes against the company profile's business areas, with indicative impact and a short reason derived from the saved analysis.
- Each cell opens the relevant comparison and evidence; it does not manufacture an assessment when no analysis exists.
- Unknown/unanalysed impact is distinct from low impact. Profile changes invalidate stale matrix values consistently with HL-018.
- Keep the underlying scan and analysis workflow unchanged. Defer this item if required work is incomplete.

<a id="hl-024"></a>

### HL-024 — Add pgvector only when direct context is insufficient

Improve passage selection only after measuring a real retrieval need.

Acceptance criteria:

- First document a representative query set and the limitation of direct context selection at the intended corpus size. If no material limitation exists, keep this task deferred.
- If justified, add paragraph chunks, embeddings, and pgvector storage in the existing PostgreSQL database; identify the embedding model and its setup explicitly.
- Retrieve within the selected law/version or comparison and preserve exact version, paragraph, and PDF-page references. Never mix unrelated or newer versions into the answer silently.
- Compare answer support, citation correctness, latency, and operational cost against the direct-context baseline before enabling retrieval by default.
- Keep direct context as a usable fallback and do not add a separate vector-database platform.

## M6 — Local-first public foundation

<a id="hl-029"></a>

### HL-029 — Ratify the single-host local-first architecture and capacity contract

Turn the public-server assumptions into an implementation contract before changing the runtime or data model.

**Status: DONE.** [The accepted architecture contract](docs/ARCHITECTURE.md) fixes one physical host and one Compose deployment, private service boundaries, `local_only`/`waiting_for_model` behavior, measured GTX 1070 and dual-GTX-1080 profiles, explicit 100-user queue semantics, release objectives, and the accepted availability limits of a single server.

Acceptance criteria:

- Adopt [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) as the target: one physical Linux host and one repository/Compose deployment, with separate web, API, worker, scheduler, PostgreSQL, Redis, model-manager, and llama.cpp processes.
- Keep only Caddy ports 80/443 public. PostgreSQL, Redis, workers, model management, and inference endpoints remain on private Docker networks; development access binds to loopback.
- Define `local_only` as the clean-install inference policy. A missing or stopped model yields `waiting_for_model`; it never triggers a hidden cloud request.
- Publish hardware profiles for one 8 GB GTX 1070 and two 8 GB GTX 1080 cards. State clearly that the public target is 100 ordinary users through queues, not 100 simultaneous generations.
- Define measurable public-beta objectives for API latency, queue admission, GPU slots, memory, recovery, and connector freshness. Do not select model size, context, or concurrency by name alone.
- Record the accepted single-host risks: one server is a failure domain, maintenance causes downtime, and Redis/PostgreSQL persistence does not provide high availability.

<a id="hl-030"></a>

### HL-030 — Replace process-local background work with durable PostgreSQL jobs and Redis/Celery execution

Make scans, connector synchronization, parsing, comparisons, AI work, and maintenance survive service restarts.

**Status: DONE.** Long-running scans, Impact analysis, and Ask commands now enter PostgreSQL-backed jobs and steps through a transactional outbox. Redis/Celery runs six explicit queues with separate CPU and AI workers plus Beat; the Activity and comparison views expose persisted progress, queue position, cancellation, retry, errors, and result links. Automated and live Compose checks prove idempotent claims and recovery after API, worker, scheduler, and Redis restarts.

Acceptance criteria:

- Add PostgreSQL `Job` and `JobStep` records with organization, type, target, priority, idempotency key, state, progress, attempts, lease/heartbeat, bounded error details, and result links.
- Use a transactional outbox or equivalent durable dispatcher so creating a domain command and making it eligible for Redis delivery cannot diverge.
- Add Redis and Celery workers/Beat in the same Compose deployment with separate `interactive`, `ingest`, `parse_diff`, `ai_interactive`, `ai_background`, and `maintenance` queues.
- Make every worker task idempotent. At-least-once delivery, retry, a stale lease, or a worker restart cannot duplicate versions, events, comparisons, or analyses.
- Return a job ID quickly from long-running commands. The UI shows real stage, position or wait state, progress, retry, cancellation, and a link to the persisted result.
- Keep completed immutable evidence after cancellation. Move exhausted jobs to an inspectable failed/dead-letter state and allow an administrator to retry them safely.
- Demonstrate recovery after restarting API, worker, scheduler, and Redis; PostgreSQL reconstructs eligible work even when the broker loses its transient queue state.

<a id="hl-031"></a>

### HL-031 — Add a local model library, verified downloads, and a private runtime manager

**Status: DONE.** Implemented as a private allowlist-based model-manager container, dedicated model volume, durable maintenance jobs, and the Local models platform screen. The GTX 1070 live check adopted the cached 1.5B Q4 artifact, verified its pinned SHA-256, started the pinned CUDA llama.cpp runtime, and returned valid structured JSON. Replicated/split dual-1080 benchmarking and the stable fair inference gateway remain explicitly in HL-032.

Let a platform administrator choose, download, validate, start, stop, and inspect local models without editing Compose files.

Acceptance criteria:

- Store a versioned allowlist of model entries with family, upstream repository, immutable revision, GGUF file, quantization, SHA-256, size, license/acceptance state, chat template, resource requirements, and verified hardware profiles.
- Probe CUDA devices, VRAM, RAM, disk, and runtime support. Mark a model/profile `compatible`, `unverified`, or `incompatible` with a plain-language reason before download or activation.
- Download into a `.part` file with progress, pause/cancel, safe resume, available-disk checks, checksum verification, and atomic activation. A failed verification never replaces a valid artifact.
- Expose `available`, `downloading`, `verifying`, `starting`, `ready`, `stopped`, `degraded`, `incompatible`, and `error` states in a platform-admin model screen.
- Run llama.cpp behind a narrow private model-manager API. The public web/API containers do not receive the Docker socket and cannot execute arbitrary model URLs or commands.
- Pin the llama.cpp runtime image/binary and record it with every deployment. Prevent removal of an active model or of an artifact referenced by retained analysis provenance.
- After a cached download, prove that version comparison, Impact, and Ask work without Internet access; deterministic registry and diff features remain usable before a model is installed.

<a id="hl-032"></a>

### HL-032 — Make local inference primary and validate GPU routing on the target hardware

**Status: IN PROGRESS.** The stable private gateway, local-first clean-install policy, automatic four-profile routing, warm-up/health, fair slot admission, visible model waits, complete result provenance, benchmark harness, and live GTX 1070 report are implemented. The 1.5B Q4 development profile passed 20/20 structured calls plus the serialized concurrent pair without schema/citation errors, OOM, or timeout. The checked-in report deliberately records `profile_matched: false`: final closure and any 8B promotion require rerunning the same benchmark on the planned dual-GTX-1080 server and observing two distinct replica slots.

Give the application one stable inference interface while the runtime chooses a measured safe GPU layout.

Acceptance criteria:

- Route application calls through one private OpenAI-compatible local gateway. Local inference is selected by default; Infomaniak and custom compatible providers remain explicit per-organization options.
- Implement `dev-1070`, `dual-1080-replicated`, `dual-1080-split`, and `cpu-degraded` profiles. GPU use is enabled by default; a CPU-only path is a diagnostic/degraded option.
- Try one quantized Apertus replica per GTX 1080 when model weights, KV cache, and safety headroom fit on one 8 GB card; otherwise use one layer-split runner across both cards and reduce concurrency to one.
- Never advertise full BF16 Apertus 8B or Apertus 70B as defaults for this host. Promote a quantized Apertus 8B profile only after it passes; keep a smaller verified Apertus profile available when it does not.
- Add warm-up, health, slot ownership, fair per-organization admission, interactive-over-background priority without starvation, timeout, retry, and degraded-single-GPU behavior.
- Persist backend, model revision/hash/quantization, runtime version, hardware profile, context, generation settings, queue wait, inference duration, token counts when available, and validation/repair outcome with each result.
- Benchmark at least 20 representative structured calls and two concurrent calls in replicated mode. Record tokens/second, load time, peak VRAM/RAM, maximum stable context, accepted slot count, schema validity, citation validity, and OOM/timeout results.

<a id="hl-033"></a>

### HL-033 — Split the shared public corpus from organization-owned monitoring data

Fetch each official Swiss document once while keeping watchlists, profiles, prompts, private inputs, and AI history inside one organization.

Acceptance criteria:

- Add organizations and organization ownership where appropriate; separate canonical public documents/versions from an organization's `DocumentWatch` and selected baseline.
- Reuse one immutable official artifact, extraction, deterministic diff, and general relation result across organizations. Do not duplicate a Fedlex version because ten organizations monitor it.
- Keep company profiles, prompt revisions, provider credentials, quotas, questions, company-specific impact conclusions, feed state, and custom sources scoped to the active organization.
- Mark uploaded, pasted, or otherwise private documents with `owner_organization_id`; never expose them through the shared public corpus.
- Migrate every existing record into a default legacy organization without changing evidence IDs, artifact keys, comparison pairs, or AI-history links.
- Replace global URL uniqueness with canonical-document identity plus organization watch uniqueness, so several organizations can monitor the same official document.
- Add isolation checks proving that guessed cross-organization IDs, search, exports, integration logs, jobs, and evidence routes disclose nothing and return `404` or the authorized shared-public representation.

Delivered: canonical public documents, extracted live versions, and deterministic public comparisons now use nullable corpus ownership, while `DocumentWatch` owns each organization's display name, active state, selected baseline, and scan outcome. Fedlex URLs reuse one canonical row and one live artifact across organizations; uploaded, pasted, historical, synthetic, and custom-source material remains private. Session-level query criteria enforce the boundary for evidence, comparisons, scans, jobs, logs, AI history, profiles, prompts, and provider settings. Prompt revisions, quota records, and connector cursor state have organization-owned tables ready for the following features. The migration creates a legacy organization and preserves existing law/version/comparison/history identifiers and artifact keys. Cross-organization regression tests cover guessed IDs, logs, jobs, profiles, private baselines, public reuse, and safe removal of a watch without deleting the shared corpus.

<a id="hl-034"></a>

### HL-034 — Add simple registration, login, sessions, and first-run onboarding

**Status: DONE.** Registration and login now create Argon2id-backed accounts, isolated personal or named organizations, random revocable PostgreSQL sessions, CSRF-protected cookie mutations, Redis-backed abuse limits, minimal security events, and a short first-run path. Production configuration fails closed when anonymous mutation or insecure cookies are enabled; the explicit local-development mode preserves the existing demo workspace.

Make the public instance easy to enter without introducing an external identity platform.

Acceptance criteria:

- Registration asks for email, password, person name, and optional organization name; an empty organization name creates a personal organization.
- Normalize email safely, hash passwords with Argon2id, and use random revocable PostgreSQL-backed sessions in `Secure`, `HttpOnly`, `SameSite` cookies. Do not store bearer tokens in browser storage.
- Protect cookie-based mutations against CSRF and apply Redis-backed limits to registration, login, fetch, scan, invitation, and AI-submission paths.
- The first user of a newly created organization becomes its organization administrator. Typing an existing organization name never grants membership.
- Provide login, logout, expired/revoked-session handling, and a short onboarding path that leads to the registry or first monitored law.
- Preserve the present local developer flow behind an explicit development-only setting; public deployment refuses to start with anonymous mutation enabled.
- Record only the minimum login/security events needed for support and abuse control, without putting passwords, cookies, or credentials into integration logs.

<a id="hl-035"></a>

### HL-035 — Enforce organization invitations, membership, and administrator/viewer roles

**Status: DONE.** Organization administrators can issue, list, revoke, and copy seven-day single-use email-bound invitation links; new or existing accounts can join and switch workspaces. Membership lists, role changes, explicit handover, last-administrator protection, removal with session revocation, API-wide viewer read-only enforcement, and matching hidden UI controls are implemented. A separate idempotent CLI manages and audits platform administrators without granting implicit organization access.

Let an organization share one workspace while making non-admin members read-only.

Acceptance criteria:

- Support two organization roles for public beta: `organization_admin` and `viewer`, plus a separate deployment-wide `platform_admin` flag/role.
- An organization administrator can create a single-use expiring email invitation, list pending invitations, revoke one, and remove another member. Joining requires the invitation token.
- Every organization member sees the same watchlist, sources, registry items, versions, comparisons, AI history, prompts, profile, and organization feed.
- A viewer can inspect all organization data and manage only personal read/dismiss state. Add/edit/delete, scan, Ask, reanalyse, prompt, provider, profile, invitation, and membership controls are absent.
- Enforce the same rules in FastAPI; a viewer's direct mutation call returns `403`. A platform administrator does not gain organization data access unless explicitly added to that organization.
- Refuse to remove or demote the last organization administrator and support an explicit handover before that administrator leaves.
- Provide an idempotent CLI command to list/promote/demote platform administrators, log the change, and refuse to remove the last one. Do not require manual database edits or expose public self-promotion.

## M7 — Swiss legal registry and official connectors

<a id="hl-036"></a>

### HL-036 — Normalize Swiss regulatory documents, expressions, versions, dates, events, and relations

**Status: DONE.** The shared corpus now separates authority-level works, identifiers, language expressions, immutable version descriptors, precision-preserving date facts, evidence-backed events, versioned relations, and explicit legacy mappings. Deterministic merge rules deduplicate connector retries and multilingual expressions, reject conflicting identifiers, and keep organization-owned provisional URL records isolated. Existing laws, artifacts, comparisons, and IDs remain readable; the migration backfills them without inferring lifecycle events.

Create a common corpus model before importing whole official catalogues.

Acceptance criteria:

- Represent canonical acts, ordinances, parliamentary business, initiatives, bills, court decisions, and official notices separately from language expressions and immutable document versions.
- Store authority-scoped identifiers such as ELI URI, SR/RS number, parliamentary business ID, court docket, and stable official URL without treating a mutable URL as the sole identity.
- Keep `detected_at`, `published_at`, `version_date`, `effective_from`, `effective_to`, decision date, and fetch time as distinct optional fields with provenance and precision.
- Model `created`, `new_version`, `amended`, `repealed`, `replaced`, `status_changed`, `decided`, and `notice_published` events without inventing lifecycle facts from disappearance or fetch failure.
- Store versioned evidence-backed relations including `amends`, `repeals`, `replaces`, `implements`, `cites`, `interprets`, and `potentially_impacts`, with provenance method and confirmed/proposed/rejected state.
- Add database constraints and merge rules so a connector retry or a second language expression does not create a duplicate canonical work or event.
- Keep all existing direct-URL laws and comparisons readable throughout the migration; provide an explicit mapping for records that cannot yet be matched to an official identity.

<a id="hl-037"></a>

### HL-037 — Build the time-grouped monitoring registry and document timeline

Make recent Swiss legal activity understandable before a user opens a comparison.

**Status: DONE.** The Registry page now reads the saved organization corpus in two views, preserves server-side filters and cursor state in the URL, groups detection timestamps using Europe/Zurich calendar boundaries, and keeps official legal dates visibly separate. Law detail includes one saved-data timeline for identifiers, expressions, versions, events, comparisons, relations, monitoring state, and provenance. See [the registry contract](docs/REGISTRY.md).

Acceptance criteria:

- Provide `My monitored documents` and `All discovered events` views with server-side search, cursor pagination, stable sort, loading/empty/error states, and saved filters in the URL.
- Group by Europe/Zurich `detected_at` into non-overlapping Today, Yesterday, Last 7 days, Last 30 days, Older, and Custom range sections; test midnight and daylight-saving boundaries.
- Display detection time separately from official publication, version, decision, and effective dates, including `unknown` rather than copying the fetch time into a legal-date field.
- Filter by authority, connector, document kind, language, lifecycle state, impact, watched/unwatched, read state, and connector health.
- Each row states what happened, the document and authority, why it appears, which monitored laws are linked, analysis state, and the next evidence/timeline/comparison action.
- Document detail shows identifiers, current lifecycle, immutable versions, events, comparisons, incoming/outgoing relations, monitoring state, and source provenance in one timeline.
- Keep registry reads responsive while synchronization and AI work are queued; do not require a live connector or model request to render saved data.

<a id="hl-038"></a>

### HL-038 — Introduce a versioned, incremental, observable connector contract

Share ingestion, deduplication, recovery, and diagnostics across every official source instead of adding URL-specific patches.

**Status: DONE.** All official adapters now share six versioned operations, a host-allowlisted bounded HTTP transport, normalized corpus writes, extracted artifact persistence, global cursor/page checkpoints, idempotent receipts, per-item recovery records, and observable contract health. Fixture probes cover Fedlex, Parliament, and the Federal Supreme Court. The 3 September 2026 live probes passed for all three contracts. An initial Parliament denial was correctly reported as `degraded` without advancing a cursor; its contact user agent and compressed-response handling were then corrected and covered by regression tests. Concrete catalogue semantics follow in HL-039–HL-041. See [the connector contract](docs/CONNECTOR_CONTRACT.md).

Acceptance criteria:

- Define connector operations for `discover_since`, metadata, expressions/versions, official artifact fetch, explicit relation extraction, and health/source-contract status.
- Normalize every result to a stable external identity, authority, document type, language, known dates/status, canonical URL, artifact hash, raw provenance reference, and connector/schema version.
- Store connector cursors and page checkpoints in PostgreSQL. Advance only after the page or safe partial boundary is persisted; repeating the same cursor is harmless.
- Apply common URL/redirect validation, content limits, artifact storage, extraction, hashing, retries with jitter, rate limits, per-item errors, and redacted integration diagnostics.
- Detect source-contract drift such as a missing field, HTML template change, or implausible empty result and surface `degraded` instead of silently marking all documents unchanged or repealed.
- Include a fixture-backed contract test and one bounded live smoke test for each connector. Fixtures never replace the official-source smoke check.
- Attribute and date reused source data as required by the authority and retain its canonical official link on every imported record.

<a id="hl-039"></a>

### HL-039 — Expand native Fedlex ELI support into a federal-law catalogue connector

Discover and monitor federal acts and their official lifecycle without requiring one manually pasted law URL at a time.

**Status: DONE.** The native adapter now exposes DE/FR/IT RSS discovery with a two-day overlap and bounded keyset SPARQL reconciliation for `cc`, `oc`, and `fga`. It preserves ELI work, dated language expression, manifestation/file metadata, the current applicable official artifact, SR/RS as a secondary identifier, official dates/status, basic-act, citation, and legal-resource-impact provenance. Direct Add law records bind to the same catalogue work. Missing metadata degrades the stream without inferring repeal. The read-only live smoke passed against RSS and SPARQL on 3 September 2026. See [the Fedlex connector contract](docs/FEDLEX_CONNECTOR.md).

Acceptance criteria:

- Build on the working direct-URL resolver; use the bounded DE/FR/IT official RSS feeds for fast discovery and the Fedlex Linked Data/SPARQL service for authoritative backfill/reconciliation of Classified Compilation, Official Compilation, and Federal Gazette collections.
- Preserve ELI work → language expression → dated/format manifestation identity, including available languages, official files, consolidation/version date, and source metadata.
- Treat SR/RS number as a searchable identifier rather than the primary key; canonical identity follows ELI because an SR number can be reused after a total revision.
- Bootstrap in bounded pages, then use RSS/watermarks with overlap plus mandatory scheduled SPARQL reconciliation because the feeds retain only a recent window; if a collection has no reliable update field, run an honest bounded sweep.
- Import JOLux citations and legal-resource impacts before model proposals, combining the official business-status, mutation, and consolidation history needed to interpret them. Detect lifecycle and cross-reference events only when supported by official metadata/artifacts.
- A missing row, timeout, or SPARQL error never proves repeal. Keep the last good version and cursor, mark the run partial/degraded, and retry from a safe checkpoint.
- Maintain Add law → Preview → Monitor for individual ELI URLs and deduplicate those records with catalogue discovery without changing the UI flow.
- Respect the official robots policy by dereferencing ELI/content-negotiated resources instead of directly crawling blocked `/filestore/*` paths; use low concurrency and backoff because no public numeric limit is documented.
- Verify several `cc`, `oc`, and `fga` identities, more than one language, a dated version, one JOLux relation, one feed item recovered by reconciliation, and at least one lifecycle case against saved official provenance.

<a id="hl-040"></a>

### HL-040 — Add a Swiss Parliament initiatives and bills connector

Track parliamentary business before it becomes enacted law.

**Status: DONE.** The isolated `parliament-webservice-v2` adapter now provides complete catalogue, recent-tail, and known-active streams in bounded slices. It retains stable/short IDs, actual DE/FR/IT/EN availability, localized source text and summaries, type/state, authors, committees, sessions, descriptors, official artifacts, dates, retrieval provenance, and required attribution. Status-only updates emit a lifecycle event without a text version; substantive records and linked documents remain immutable. Exact official identifiers become evidence-backed relation candidates. Fixture and live checks passed on 3 September 2026. See [the Parliament connector contract](docs/PARLIAMENT_CONNECTOR.md).

Acceptance criteria:

- Use the official Parliament web service for affairs and related summaries, types, states, descriptors, committees, people, documents, sessions, and votes needed by the product; retain actual DE/FR/IT/EN availability because substantive English fields can be incomplete.
- Retain stable and short business identifiers, title/summary per available language, type, state/stage, authors, committees, updated/publication dates, official URL, and official artifacts.
- Complete a source-contract spike for 50-row paging, ID ordering, and update filters. Since older affairs can change and the list is not ordered by `updated`, perform a complete lightweight bootstrap, frequently revisit new/current-year and known non-final affairs, and periodically reconcile every `(id, updated)` page.
- Create a status-change event without manufacturing a new text version when only metadata changes; create an immutable version when an official draft/message/report artifact changes.
- Extract exact SR/RS, ELI, Fedlex, article, and parliamentary references as deterministic relation candidates. Title similarity alone remains proposed and requires evidence.
- Preserve the required source attribution `Parlamentsdienste der Bundesversammlung, Bern`, a visible retrieval date, and the unmodified official record wherever reused data is displayed or exported; keep Helvetic Lens summaries separately labelled.
- Isolate the adapter contract because the authority says the current older API remains available until further notice while a replacement is planned.
- Verify a new/updated business, a state change, a related official document, multiple pages, more than one language, a partial-item failure, and an idempotent rerun.

<a id="hl-041"></a>

### HL-041 — Add a Swiss Federal Supreme Court decisions connector

Surface new court decisions that cite or interpret monitored federal law.

**Status: DONE.** The connector uses the official latest/date index with a five-date overlap and a bounded current/previous-year insertion-date reconciliation stream. Source review corrected the earlier sitemap assumption: the sitemap declared by the court covers website pages, not decision records, so no invented `lastmod` feed is used. Exact Aza/docket identity, distinct decision and insertion dates, actual-language HTML, descriptors, immutable artifacts, exact citation candidates, two-second pacing, source-contract health, safe partial recovery, and idempotent corpus writes are implemented. See [the connector contract](docs/FEDERAL_COURT_CONNECTOR.md).

Acceptance criteria:

- Limit the first release to the Swiss Federal Supreme Court official latest/date index, databases, and official decision HTML; broader courts are HL-055. Treat the declared website sitemap only according to its observed contents.
- Complete a source-contract, terms, and robots review; enforce the published two-second crawl delay. No undocumented third-party aggregator may be the authority of record.
- Store stable Aza/docket identity, court/chamber, decision date and insertion/publication date separately, language, descriptors/norms when exposed, official JumpCGI/source URL, artifact hash, and immutable extracted HTML.
- Poll the latest/date index with an overlap and reconcile the current and previous years through bounded official insertion-date pages by stable identity. Avoid repeatedly downloading the giant all-decisions RSS snapshot.
- Do not fabricate a source PDF: free official decisions are generally HTML, so store/reopen the authoritative representation that actually exists.
- Template drift, challenge pages, a crawl-delay violation, or an implausible empty interval sets connector health to degraded without advancing past uncertain coverage.
- Extract cited acts/articles and official identifiers as evidence-backed `cites`/`interprets` candidates. Never describe a judgment as amending the wording of a statute.
- Isolate per-decision failures so one bad decision does not lose the rest of a page; retain a retryable item error and safe checkpoint.
- Verify at least one newly listed decision, repeated overlap, multilingual metadata where available, a cited norm, original artifact reopening, and idempotent rerun.

<a id="hl-042"></a>

### HL-042 — Schedule incremental synchronization, deduplicate official work, and fan out watch events

Run the core connectors continuously without fetching the same public evidence once per organization.

**Status: DONE.** Eleven persisted streams now run through Celery Beat, the PostgreSQL outbox, and the bounded ingest worker. Platform administrators can inspect health and history, edit interval/jitter/Swiss-time windows, pause/resume, and run a stream immediately. Shared official events fan out idempotently to organization watches, including durable retry after a worker disappears between persistence and fan-out. See [synchronization operations](docs/SYNCHRONIZATION.md).

Acceptance criteria:

- Use the durable scheduler to enqueue each connector according to a persisted schedule, per-source rate limits, overlap policy, jitter, maintenance window, and manual `Sync now` control.
- Lock one connector/checkpoint safely across workers while allowing bounded per-document processing; a scheduler restart cannot enqueue an unbounded duplicate run.
- Deduplicate canonical documents, artifacts, versions, and regulatory events before creating organization feed work. Store one shared ingestion result and fan it out to matching watches.
- Show last success, current cursor/watermark, next run, duration, new/changed/failed counts, freshness lag, partial coverage, and health in the admin UI.
- Allow pause/resume and retry from the last safe checkpoint without deleting saved corpus data or organization history.
- Apply backpressure when parsing, disk, or AI queues are saturated; ingestion does not exhaust RAM or starve interactive registry reads.
- Prove that two organizations watching the same Fedlex act receive their own event/feed state while the official artifact and deterministic comparison are stored once.

<a id="hl-043"></a>

### HL-043 — Ingest official notices and source-linked news from the three core authorities

Capture relevant official context around laws, parliamentary business, and decisions without claiming broad web-news coverage yet.

**Status: DONE.** The stable Parliament press-page OData feed now runs as an incremental scheduled stream, persists five official language expressions and immutable extracted bodies, emits one contextual `notice_published` event per source revision, and derives only exact ELI, SR/RS, and affair relations. Fedlex Federal Gazette coverage remains in its legal connector to avoid duplicate manifestations; the Federal Supreme Court press area is documented as lacking a reliable machine watermark, so its healthy decision connector was not widened into a fragile crawl. See [docs/OFFICIAL_NOTICES.md](docs/OFFICIAL_NOTICES.md).

Acceptance criteria:

- Discover stable official notices, press items, or publication feeds exposed by Fedlex/federal authorities, Parliament, and the Federal Supreme Court when their source contract permits reliable incremental ingestion.
- Normalize an item as `official_notice` with authority, title, dates, language, official URL, immutable body/artifact when available, and precise provenance.
- Extract direct document identifiers and citations into deterministic candidates; send only bounded unsupported candidates to later impact analysis.
- Deduplicate syndicated or multilingual manifestations without merging substantively distinct notices; preserve each official language expression.
- Make clear in the registry that a notice is contextual information, not a statute, enacted amendment, or court holding.
- If a core authority has no stable official notice interface, document that limitation and keep its connector healthy for supported legal records rather than adding a fragile unbounded crawl.
- Defer broader Federal Council, department, regulator, consultation, and general news monitoring to HL-050.

## M7A — Decision-ready comparison and AI triage

This checkpoint replaces passage-volume-driven AI work with the product contract in [docs/AI_TRIAGE.md](docs/AI_TRIAGE.md). Exact saved evidence remains the audit layer. The default experience identifies material legal-unit changes, explains why they may matter, and produces a small review plan within a fixed inference budget.

<a id="hl-058"></a>

### HL-058 — Verify document identity before comparison, monitoring, or AI

Prevent a plausible-looking analysis of two artifacts that are not versions of the same legal work.

**Status: DONE.** Artifact identity and evidence are persisted, pair decisions are cached with an identity fingerprint, unknown assignments require an audited confirmation, official conflicts cannot be overridden, and mismatches are quarantined before comparison or AI. The recovery flow exposes both originals, version selection/import, and safe removal of a mistaken non-current import.

Acceptance criteria:

- Persist detected authority, canonical work identifier such as ELI/SR/RS or docket, document kind, title, language, version/publication date, source URL, extraction method, and identity evidence for every artifact.
- Resolve identity through connector metadata and official identifiers first; title/content fingerprints may support an `unknown` or `probable` result but cannot override a contradictory official identifier.
- Classify a proposed pair as `verified`, `probable`, `unknown`, or `mismatch`. Block automatic comparison and AI for `mismatch`; require an explicit, audited user decision for `unknown` without relabelling either saved artifact.
- Explain a failed gate in product language and offer concrete recovery: attach the artifact to the correct document, select another version, inspect both originals, or remove the mistaken import.
- Recheck identity when extraction rules, connector metadata, or artifact assignment changes. A previous AI result remains historical and is visibly invalidated rather than silently reused.
- Add a regression where the monitored record names a naturalization decree while an artifact identifies itself as SR 910.13; no comparison, Impact report, or Ask job may start.
- Keep identity validation independent of the model. AI may help propose a match for review but cannot mark a legal-work identity as verified.

<a id="hl-059"></a>

### HL-059 — Build a legal-unit semantic diff above the exact audit diff

Show changes to legal meaning without turning one insertion, renumbering, page wrap, or moved section into hundreds of apparent amendments.

**Status: DONE.** Diff schema v6 preserves complete exact passage coverage while projecting source text into a title/chapter/section/article/paragraph/littera/number hierarchy. Each alignment records its stable-label/content/neighbour/parent score, reason, and ambiguity. Deterministic semantic classifications and stable amendment clusters keep movement, renumbering, repeated layout, and safe line-wrap repair out of the default material AI set without changing stored evidence.

Acceptance criteria:

- Parse a version into a hierarchy such as title/chapter/section/article/paragraph/littera/number while preserving the original page, passage, text, artifact, and exact diff references.
- Normalize comparison-only noise including Unicode variants, whitespace, line/page breaks, repeated headers/footers, and safe end-of-line hyphenation. Never mutate stored source evidence or normalize away legally meaningful punctuation, numbers, or wording.
- Match units by official/stable identifiers first, then bounded label, content, neighbour, and parent-context signals. Record the algorithm/version, match reason, score components, and ambiguity.
- Classify each result as `substantive`, `added`, `removed`, `moved`, `renumbered`, `formatting_only`, or `uncertain`; keep severity/applicability out of the deterministic classifier.
- Group a coherent amendment into one stable change cluster with old/new units and surrounding context. A moved or renumbered unchanged unit does not become a substantive change.
- Make **Material changes** the default data set for AI while keeping uncertain units visible and separately reviewable. **All exact changes** remains complete, immutable, and reopenable for audit.
- Add fixtures for a single inserted article that renumbers every following article, line-wrap and split-word changes, a moved unchanged section, a real obligation/deadline edit, and a complete replacement. Assert both material-change recall and noise classification.

<a id="hl-060"></a>

### HL-060 — Plan every local-AI analysis within a fixed call and context budget

Use the model for semantic explanation and triage, not as a slow passage-by-passage diff engine.

**Status: DONE.** Impact and Ask now save an explicit pre-inference `AnalysisPlan` with selection decisions, reusable semantic-change fingerprint, profile-aware context fingerprint, token estimates, fixed context/output limits, expected calls, and coverage. Impact is capped at five provider calls and Ask at three; formatting/structural-only comparisons use zero model calls. Completed and failed records retain actual calls, queue/inference timing, provider token counts, validation/repair results, and a result link, shown compactly in the comparison and AI-history interfaces. See [docs/AI_ANALYSIS_PLANNER.md](docs/AI_ANALYSIS_PLANNER.md).

Acceptance criteria:

- Persist an `AnalysisPlan` with task/intent, selected change IDs, context fingerprint, model/context limits, estimated input/output tokens, call budget, coverage, and reason for each included or excluded unit before inference begins.
- A comparison with no material or uncertain change returns a deterministic `no substantive change detected` result with zero model calls. A small complete change set uses one model call when it fits the verified runtime context.
- For larger sets, cluster related legal units and use at most **five total generation calls for an Impact report**, including synthesis and any repair. Platform configuration may lower this bound but cannot silently raise it per document.
- Sending both complete saved versions in one request is allowed only when the actual serialized prompt plus reserved output fits the benchmarked model context. Otherwise use the complete semantic change set; never create one generation request per passage or page.
- If all material/uncertain units cannot be reviewed within the budget, preserve the complete deterministic result, mark AI coverage as limited with reviewed/total units, and offer targeted follow-up. Never claim a complete AI assessment.
- Reuse a shared general change explanation before organization-specific applicability. Local inference remains the default; a budget failure never causes silent cloud fallback.
- Run through HL-030 durable jobs and expose the plan, call count, queue wait, inference time, tokens when available, validation/repair outcome, and result link in bounded diagnostics.

<a id="hl-061"></a>

### HL-061 — Return an actionable, deduplicated regulatory impact report

Turn evidence into a review plan that helps an organization decide what to inspect next.

Acceptance criteria:

- Return a validated report with headline, materiality, material changes, organization applicability, affected business areas, important dates/obligations, uncertainties, evidence coverage, and zero to five suggested review actions.
- Every change explanation identifies the old/new legal units and cites exact saved evidence. Unknown applicability, effective date, deadline, or responsibility remains explicitly unknown rather than being invented.
- Separate potential severity from evidence strength. Present `confirmed`, `supported`, `possible`, and `needs_review` evidence grades using deterministic provenance and citation validation rather than an unqualified model confidence number.
- Structure each action with action type, verb/object title, rationale, proposed owner role, affected area, priority, due basis/date or `not_found`, applicability condition, related change IDs, and citations. Label it as a review suggestion, not a confirmed legal obligation.
- Permit zero actions. Do not require filler text when a change is editorial, outside the profile, or lacks enough evidence for a concrete recommendation.
- Generate a stable normalized `action_key`; merge duplicate actions across batches/changes, combine their citations, and reject a final result containing duplicate keys. Three copies of the same generic review instruction can never be displayed.
- Cache only on matching comparison, semantic-diff fingerprint, organization/profile revision, prompt/schema revision, model/runtime fingerprint, and output locale. Keep all successful and failed attempts; a new valid report supersedes but never overwrites history.

<a id="hl-062"></a>

### HL-062 — Route Ask by user intent and select only the context the intent needs

Make free-form questions a useful drill-down after the report instead of an invitation to read two entire documents for every sentence.

Acceptance criteria:

- Classify input before document-context assembly as `explain_changes`, `organization_impact`, `actions`, `specific_unit`, `whole_document`, `vague`, or `off_topic`; the router receives no raw document body and has a separately bounded cost.
- Canonical intents reuse the current validated report where possible. Offer localized prompts such as **Explain the changes simply**, **Does this affect us?**, **Show new obligations or deadlines**, and **Create a review checklist**.
- A vague conversational phrase such as `Ничего не понятно но очень интересно` returns a useful clarification and intent choices, optionally with the saved TL;DR, in under one second and with zero full-document/batch inference calls.
- Every change-related question uses the complete semantic change set and its uncertainty records, never passage retrieval. Specific-unit questions use the selected unit plus bounded parent/neighbour context.
- A whole-document question may use both complete versions only when they fit the measured context; otherwise use explicit targeted retrieval over saved originals and state its scope. This exception must not weaken complete-diff handling for change questions.
- Set a fixed **three-call maximum per Ask job**, including repair/synthesis. If the answer cannot be supported within that scope, explain what evidence is missing and offer a narrower question rather than scanning indefinitely.
- Either pass prior validated answers and citations needed for a follow-up or present each saved question as independent. Do not render a chat metaphor whose backend remembers only prior question text.
- Persist intent, scope, selected evidence/change IDs, coverage, latency, model/runtime, locale, answer, citations, and cache use with the exact comparison.

<a id="hl-063"></a>

### HL-063 — Redesign comparison review around material changes, meaning, and action

Let a user understand a new version without scrolling through thousands of red/green passage rows.

**Status: DONE.** The comparison now opens on deterministic semantic clusters and five plain-language counts while retaining every exact passage/word change behind **All exact changes**. One validated current report presents what changed, why it may matter, a review plan, exact evidence jumps, coverage and complete profile/model/runtime/prompt/locale provenance. PostgreSQL-backed inference survives navigation and exposes real queue, group-analysis, validation and terminal states without blocking the diff. Organization administrators can append accept/assign/schedule/dismiss/not-applicable decisions with actor, time, rationale and organization scope; legal evidence and prior reports stay immutable. Stable classification, evidence, job and decision states have non-colour labels and the comparison-specific five-language mappings ready for the HL-057 product-wide catalogue. See [the comparison review contract](docs/COMPARISON_REVIEW.md).

Acceptance criteria:

- Lead with counts for **Material**, **Added/removed**, **Moved/renumbered**, **Formatting only**, and **Needs review**. Default to material/uncertain clusters; place the complete current passage/word diff behind **All exact changes**.
- Each material-change card shows what changed in plain language, before/after legal units, possible organization relevance, important dates/obligations, evidence grade, assumptions, and a one-click exact-evidence view.
- Present one current **What changed / Why it may matter / Review plan** report with generated date, versions, profile/model/prompt/locale provenance, coverage, and a compact link to prior reports.
- Let authorized users accept, assign, schedule, dismiss, or mark a suggested action not applicable without changing shared legal evidence. Preserve actor, time, rationale, and organization scope.
- Submit inference as an HL-030 background job and keep the screen usable. Show `queued`, queue position/estimate when known, `preparing changes`, `analysing n/N groups`, `validating evidence`, `ready`, `limited`, `failed`, and `cancelled` from real persisted state.
- Navigation or refresh does not lose the job. Notify the user when it finishes and reopen the saved result; stream status or individually validated cards, never unverified legal prose.
- Render a deterministic change overview immediately while AI is offline, queued, or failed. Avoid a ten-minute blocking spinner as the only value on the screen.
- Apply HL-057 localization and accessible non-colour labels to every classification, state, evidence grade, action, and error.

<a id="hl-064"></a>

### HL-064 — Pass the AI-triage regression, evidence, latency, and usability gate

Prove that the redesigned flow saves review time and cannot regress to thousands of low-value requests.

Acceptance criteria:

- Check in a labelled multilingual corpus covering identity mismatch, formatting-only revisions, split-word/page-wrap noise, insertion plus mass renumbering, moved text, one true obligation/deadline change, repeal/replacement, and a large rewritten document.
- For the insertion fixture, report the intended material change while grouping consequent renumbering separately; retain the complete exact audit diff and do not show hundreds of material changes.
- For a 1,400-plus-passage or equivalent 3,600-plus-evidence comparison, an automatic Impact report respects the five-call cap. An Ask job respects the three-call cap. No path creates one inference call per passage.
- The vague-question fixture completes clarification under one second without document inference. Repeating an identical valid request returns the saved result without a provider call; changed dependencies produce a new version and mark the old result stale.
- Validate 100% of displayed legal quotations against saved evidence and reject out-of-range references. A failed or partial analysis cannot replace the last valid current report.
- Assert zero duplicate normalized action keys, allow zero justified actions, and human-review action specificity, owner/due-state honesty, evidence links, and separation of severity from evidence strength.
- Measure time to deterministic overview, queue wait, AI completion, total calls/tokens, cache reuse, citation acceptance, limited/failed rate, action accept/dismiss rate, and time to first useful insight on the target local hardware.
- In moderated testing across the five supported locales, a user can identify the main material change, possible organizational relevance, evidence, and next review step within two minutes without opening **All exact changes**. Record failures and revise the gate before public beta.

## M8 — Evidence-backed impact intelligence

<a id="hl-044"></a>

### HL-044 — Generate an explainable relation candidate set for every new regulatory event

Find which monitored laws could be affected without comparing every new item with every law.

**Status: DONE.** Every committed connector run now reuses confirmed official relations and performs a bounded PostgreSQL full-text/deterministic second-stage search over watched works. Shared candidates retain source/target versions, score components, reasons, rule revision, status, expiry, and provenance; organization delivery rows enforce independent limits without duplicating the general relation. Similarity-only results remain explicitly proposed and candidate-only. The labelled regression fixture covers the required event classes and unrelated controls. See [docs/RELATION_CANDIDATES.md](docs/RELATION_CANDIDATES.md).

Acceptance criteria:

- Create confirmed relations directly from official metadata and exact identifiers/citations, preserving the supporting metadata field, passage, page, or artifact.
- Generate a bounded second-stage candidate set with normalized titles, authority/type metadata, article/norm references, and PostgreSQL multilingual full-text search.
- Store why each watched law became a candidate, the rules/index revision, source and target versions, score components, and candidate expiry/status.
- Enforce per-event and per-organization limits and reuse the same general candidate relation for all watching organizations before personalizing impact.
- Evaluate recall and noise on a labelled set containing enactment/repeal, parliamentary proposals, decisions, notices, exact references, and unrelated controls.
- Do not use similarity as evidence or show a relation as confirmed merely because it ranked highly. Keep unsupported/title-only matches proposed.
- Add embeddings/pgvector only through HL-051 if the labelled benchmark proves a material recall gap that deterministic and full-text methods cannot close.

<a id="hl-045"></a>

### HL-045 — Analyse candidate effects with local Apertus and exact saved evidence

Turn a candidate relation into a useful, reviewable potential-impact conclusion for each affected organization.

**Status: DONE.** Each organization relation candidate can now start a durable `ai_background` job with lower priority than interactive Ask work. One fixed-budget local-first dossier combines the exact event/version, monitored-law lifecycle and passages, deterministic retrieval facts, organization profile, and any confirmed official relation. Structured output is validated with at most one repair; citations are materialized from persisted rows, invalid references are rejected, actions are deduplicated and capped at five, and unsupported conclusions remain explicitly unsupported. Successful and failed attempts are retained, while cache reuse requires identical evidence/version, profile, prompt, model/runtime, and schema fingerprints. Confirmed official relations remain separate immutable facts. See [the relation-impact contract](docs/RELATION_IMPACT_ANALYSIS.md).

Acceptance criteria:

- Queue background relation analysis on the local backend by default and let higher-priority interactive Ask jobs pre-empt new background batches without cancelling completed work.
- Supply the exact new event/version evidence, relevant monitored-law passages/current lifecycle, deterministic relation facts, and organization profile; treat all source text as evidence rather than instructions.
- Reuse the HL-061 report/action contract with supported/unsupported, proposed relation type, potential severity, evidence grade, concise explanation, affected business areas, zero to five deduplicated review actions, and evidence-row numbers.
- Materialize citations from supplied rows on the server, allow one constrained repair, and reject invalid JSON/schema/out-of-range citations. Never display an unsupported AI relation as fact.
- Keep official repeal/replacement/amendment metadata authoritative and visually distinct from AI-proposed potential effects; a model cannot overwrite a confirmed relation.
- Cache only when event/target versions, evidence, organization profile, prompt, model/runtime fingerprint, and analysis schema all match. Preserve successful and failed history.
- Use the HL-060 fixed-budget planner within measured local context and GPU limits, expose queued/running/limited/coverage states, and leave registry/evidence usable when the model is offline or backlogged.

<a id="hl-046"></a>

### HL-046 — Add an organization impact inbox and cross-links on monitored laws

Give users one place to understand why a new law, proposal, decision, or notice matters to what they monitor.

**Status: DONE.** `/impact` now groups all affected monitored laws under one saved source event, shows the five explicit analysis/relation states, severity and coverage, and links to source, evidence, timeline, comparison, and preserved analysis history. Read/dismiss/mute state is private per user. Forced reanalysis always adds history while the last valid result remains current. Official replacements expose reciprocal predecessor/successor links and administrators can monitor the successor without removing predecessor history. Organization review decisions are separate from immutable official metadata, and viewer permissions allow only personal inbox state changes. See [the impact inbox contract](docs/IMPACT_INBOX.md).

Acceptance criteria:

- Create one organization feed item per source event and group every affected monitored law beneath it, rather than producing duplicate cards for the same event.
- Distinguish `Confirmed relation`, `Possible impact`, `Awaiting analysis`, `Analysis failed`, and `No supported impact` with source, date, severity, and evidence coverage.
- Explain why the item appears, show the potential effect and suggested next step per watched law, and open the source artifact, relation evidence, document timeline, and comparison.
- When an official act replaces a monitored act, show reciprocal successor/predecessor links and let an organization administrator add the successor to monitoring without losing the predecessor's history.
- Support source/severity/type/watched-law/read-state filters plus per-user unread, read, dismissed, and muted state; these actions never delete the shared event or another user's state.
- Reanalysis creates a new history record and updates the current presentation only after a valid result. Existing evidence and prior conclusions remain inspectable.
- A viewer can read and manage personal read state but cannot confirm/reject a proposed relation, run analysis, change monitoring, or edit shared data.

## M9 — Public beta operations and acceptance

<a id="hl-047"></a>

### HL-047 — Build separate platform and organization administration surfaces

Expose the controls needed to operate one public installation while keeping organization administrators inside their own workspace.

**Status: DONE.** `/admin` now provides a bounded installation control room for services, connectors, durable queues, failures, local-model/GPU slots, benchmark readiness, disk/retention, backup presence, resources, and administrative outcomes, with links to the existing detailed controls. `/organization` provides the active workspace's members/invitations, watchlists/sources, company profile, prompt override, local-or-cloud AI mode, saved AI usage, and quotas. All `/api/admin/*` reads and writes require platform-admin authority when authentication is enabled. Organization prompts inherit editable platform defaults until overridden. Provider tokens are write-only AES-256-GCM ciphertext keyed by `HELVETIC_LENS_CREDENTIAL_KEY` (or a persisted local-development volume key), and legacy plaintext is migrated at startup. Every non-auth API mutation records bounded actor/scope/time/result metadata without request bodies. See [docs/ADMINISTRATION.md](docs/ADMINISTRATION.md).

Acceptance criteria:

- Platform admin pages cover local model catalogue/downloads/deployments, GPU/runtime health and benchmark, global connectors/schedules, queues/jobs/dead letters, disk/retention, backup status, global prompt defaults, and service health.
- Organization admin pages cover membership/invitations, watchlists/custom sources, company profile, organization prompt overrides, quotas/usage, and optional cloud-provider opt-in/credentials.
- Keep credentials write-only and encrypted with a deployment key; show replacement/removal/test status without returning secret values to the browser or logs.
- Every sensitive action has API authorization, validation, an actor/time/result record, and a confirmation step only where the action is destructive or sends data to a newly enabled cloud destination.
- Clearly label global versus organization scope and local versus cloud execution. No organization administrator can start arbitrary binaries, edit another organization, or access the Docker socket.
- Provide a compact system-status view with queue age, connector freshness, model slots, GPU/RAM/disk, recent failures, and backup age, with links to bounded diagnostics.
- The CLI remains the bootstrap/recovery path for platform-admin assignment when the web admin surface is unavailable.

<a id="hl-048"></a>

### HL-048 — Ship a reproducible public single-server deployment and operations baseline

Make the i7/32 GB/two-GTX-1080 server safe and recoverable enough for a public beta.

Acceptance criteria:

- Provide one documented production Compose/override command with Caddy TLS, fixed image versions/digests, startup migrations, health/readiness checks, restart policies, private networks, and named volumes.
- Publish only ports 80/443. Refuse insecure production defaults such as anonymous mutation, placeholder session/deployment keys, public databases/Redis/llama.cpp, or unbounded uploads.
- Configure PostgreSQL backups plus document/evidence/configuration backup to a separate destination; treat downloaded models as reproducible artifacts unless explicitly retained.
- Configure Redis AOF `everysec` and `noeviction`, while proving PostgreSQL job recovery after Redis loss. Document the single-host outage and data-loss boundaries honestly.
- Add bounded retention/cleanup for integration diagnostics, job attempts, temporary downloads, and orphan artifacts without deleting immutable evidence or user-selected AI history unexpectedly.
- Add structured correlation across request, job, connector run, document/event, comparison/analysis, and organization; expose metrics for API, DB, Redis, queues, connectors, model/GPU, disk, and backup age without high-cardinality secret labels.
- Rehearse install, upgrade with pre-migration backup, certificate renewal, model re-download, database/artifact restore, and rollback limits from the runbook.

<a id="hl-049"></a>

### HL-049 — Pass recovery, fairness, and the reproducible 100-user capacity gate

Measure the public claim on the actual target host and tune shipped limits to what it can sustain.

Acceptance criteria:

- Check in a reproducible scenario with 100 accounts across several organizations, 10–20 concurrent registry/evidence readers, concurrent filters, scans, connector work, and 20 accepted AI submissions.
- Meet registry/detail read p95 below 500 ms, command validation/job enqueue p95 below 1 second, and HTTP error rate below 1%, excluding intentional validation/rate-limit responses.
- Keep database connections, API/worker memory, CPU parse concurrency, queue size, and disk growth bounded; the host does not thrash swap and the GPUs do not OOM.
- Apply fair organization admission so one large comparison cannot indefinitely block another organization's short interactive request. Report active GPU slots and honest estimated/waiting state.
- Kill/restart API, CPU worker, AI worker, Redis, model runner, and scheduler during the scenario; queued work recovers without duplicate versions/events/comparisons/analyses or false success.
- Record CPU, RAM, VRAM, disk/network, model load time, context, input/output throughput, queue wait/drain, connector duration, failure/retry counts, and backup/restore duration.
- If the desired Apertus 8B profile fails, ship one split runner or a smaller verified model and update the capacity contract. The measured result overrides the desired model name.

<a id="hl-057"></a>

### HL-057 — Internationalize the complete product in five Swiss-market languages

Make German, French, Italian, Romansh, and English first-class product languages without changing or silently translating official evidence.

**Status: IN PROGRESS.** Locale resolution/persistence, the five-language selector, localized account mail, stable error translation, locale-aware formatting, Unicode search, source-language markup, and locale-isolated Impact/Ask/relation analysis history are implemented. The shared catalogue currently covers access, onboarding, navigation, registry, Impact, and AI history; remaining release screens, human language review, five complete browser paths, and five real local-Apertus samples remain before this item can be marked done. See [the localization contract and review matrix](docs/LOCALIZATION.md).

Acceptance criteria:

- Support the explicit locale set `de-CH`, `fr-CH`, `it-CH`, `rm-CH`, and `en-CH`, with their native language names in a keyboard-accessible language selector on public, authenticated, mobile, and desktop screens.
- Select locale in this order: authenticated user preference, pre-login cookie, supported browser `Accept-Language`, then a documented deployment default. Switching language applies immediately and persists per user without changing the organization's shared data.
- Use one maintained, namespaced translation catalogue and ICU-style parameter/plural formatting for every user-visible string. Do not concatenate translated sentence fragments or translate stable API fields, enum values, database identifiers, evidence IDs, or URLs.
- Localize registration/login, onboarding, navigation, registry/timeline, sources, comparisons, Impact/Ask, AI history, notifications, organization/admin/model/connector screens, loading/empty/error states, validation, destructive confirmations, and transactional email/digests when those features exist.
- Return stable machine-readable error codes plus typed parameters from FastAPI and translate them at the presentation boundary. Do not persist a rendered English error as the only explanation of a failed job.
- Format dates, times, relative groups, numbers, file sizes, and plural counts with locale-aware CLDR/`Intl` rules while keeping Europe/Zurich grouping semantics. Avoid ambiguous numeric legal dates and preserve the source's exact stated date/provenance.
- Treat product locale and document language as separate fields. Model official DE/FR/IT/RM/EN expressions explicitly, show which languages actually exist, and never imply that a missing Romansh or English source version is available.
- Keep official passages and citations in their original language. Any machine-generated translation or explanation is separately labelled, links to the unchanged source evidence, and never becomes an official `DocumentVersion`.
- Ask local Apertus for analysis in the user's selected/requested language, store `output_locale` with the result, and include it in cache/idempotency fingerprints. Reusing a German answer for an otherwise identical French request is forbidden; prior answers remain visible with their language label. A language failure is retryable and never silently falls back to cloud or another output language.
- Make search Unicode- and diacritic-safe for German umlauts, French/Italian accents, and Romansh text; retain an explicit document-language filter and do not silently search a machine-translated corpus as if it were source text.
- Store recipient locale for invitations and later digests. Use it for localized subjects/plain-text/HTML and locale-preserving links, with a documented organization/deployment fallback. Organization-shared content remains one record while each user sees localized controls and personal notification text.
- Set the page `lang` attribute and the language of quoted source blocks correctly. Verify keyboard/focus behavior and both 390 px and desktop layouts with the longest translations; no essential control may clip or depend on translated text length.
- Add a catalogue-completeness check that fails CI on missing/unused production keys, placeholder/plural mismatches, or unapproved hard-coded user-facing English, plus a pseudo-locale or equivalent layout stress check. No release screen may fall back silently to a mixed-language interface or expose a raw translation key.
- Run one browser smoke path per locale covering login, registry/filter/search, comparison/citation, local-AI history, an error state, and admin/viewer authorization. Record one real local-Apertus cited answer per language and human-review its language and source/evidence labels.
- Keep translation files in the repository and document the contributor workflow, terminology glossary, reviewer status, and fallback behavior; no external translation-management platform is required for public beta.

## Work after public-beta acceptance

<a id="hl-050"></a>

### HL-050 — Add broader official regulatory news and consultation connectors

Extend beyond source-linked notices only after the core Fedlex, Parliament, and court connectors are reliable.

**Status: DONE.** The shared connector pipeline now ingests the official News Service Bund search, multilingual FINMA RSS feeds, and the Fedlex JOLux consultation catalogue. It retains canonical HTML or original SPARQL JSON, labels notices and consultations as context/proposals rather than enacted law, records exact declared Fedlex impacts, and exposes bounded schedules and diagnostics. See [the source contracts and verification design](docs/BROAD_OFFICIAL_CONNECTORS.md).

Acceptance criteria:

- Prioritize official Federal Council, department, regulator, and consultation APIs/feeds/publication lists; document source contract, attribution, cadence, and coverage for each.
- Reuse HL-038 ingestion and HL-044 candidate generation; do not introduce a parallel crawler, evidence model, or notification store.
- Label news/consultation status precisely and preserve official artifacts; never present commentary or a proposal as enacted law.
- Add a connector only after its incremental behavior, deduplication, drift detection, and bounded live verification pass.

<a id="hl-051"></a>

### HL-051 — Add pgvector only if a labelled candidate-recall benchmark justifies it

Improve multilingual relation discovery without weakening exact evidence requirements.

**Status: DONE — pgvector remains disabled.** The checked-in multilingual gate measures deterministic identifiers plus the production full-text/scoring path at 100% recall and 100% precision on 15 labelled pairs, with zero additional disk or embedding calls. It fixed exact cross-language SR/RS retrieval and safe German legal-title suffix matching. Similarity remains candidate-only evidence. See [the benchmark, measurements, and reopen threshold](docs/RELATION_CANDIDATE_BENCHMARK.md).

Acceptance criteria:

- Compare deterministic identifiers plus PostgreSQL full-text candidates against a labelled relation set and document the specific missed cases and required recall gain.
- If justified, store versioned embeddings in the existing PostgreSQL database, record the embedding model/revision/language behavior, and bound indexing/reindexing work through the queues.
- Measure recall, precision/noise, latency, disk/RAM, and downstream citation correctness before enabling semantic candidates by default.
- Keep embeddings as candidate-generation signals only; every displayed relation still needs official metadata, exact saved passages, or a validated local-AI evidence result.
- Leave the feature disabled and close the task with evidence if it provides no material benefit.

<a id="hl-052"></a>

### HL-052 — Add opt-in email and web digests

Summarize the existing impact inbox without turning notification delivery into a second source of truth.

Acceptance criteria:

- Let each user opt into daily/weekly digests, choose organization/severity/source filters, and unsubscribe directly.
- Generate digests from persisted feed items and evidence links; delivery failure never alters read state or legal-event history.
- Deduplicate sends with durable jobs, apply rate limits/retries, and store bounded delivery status without logging mail credentials or document bodies unnecessarily.
- Keep in-app notifications fully usable when email is not configured.

<a id="hl-053"></a>

### HL-053 — Add relation review workflow and a visual graph only after list/inbox validation

Help administrators curate proposed relations when real usage proves that a graph adds value.

Acceptance criteria:

- Provide evidence-first confirm/reject/annotate actions with reviewer, timestamp, reason, and versioned history; never erase the original model/rule proposal.
- Show graph nodes/edges only for the user's authorized corpus and make confidence/provenance/status accessible without relying on color.
- Keep the timeline/list/inbox as complete alternatives; no essential action requires manipulating a graph.
- Measure whether the graph improves review time or correctness before making it a primary navigation surface.

<a id="hl-054"></a>

### HL-054 — Add account recovery, verification, 2FA, or SSO only as public-use needs mature

Strengthen identity workflows without blocking the deliberately small first registration experience.

**Status: DONE.** Registration now issues a 24-hour email-verification link, the Organization page shows verification status and resend action, and sign-in includes a non-enumerating 30-minute password-reset flow. Both links are random, hashed at rest, replace older pending links, expire, and work once. Resetting a password revokes every active session. Separate request/completion rate limits and minimal security events cover abuse and audit needs. Development delivery uses a private, self-pruning mailbox while production requires configured SMTP; the privacy and operator recovery boundaries are documented in [the account recovery runbook](docs/ACCOUNT_RECOVERY.md). TOTP and SSO remain deliberately deferred until measured need.

Acceptance criteria:

- Prioritize verified-email and expiring password-reset flows with non-enumerating responses, hashed one-time tokens, rate limits, and session revocation.
- Add TOTP 2FA or an external identity provider only after a documented user/operations need; never create a custom SSO protocol.
- Preserve organization invitations, last-admin protection, CLI platform-admin recovery, and API authorization in every new flow.
- Update privacy/retention and recovery runbooks before enabling any new identity data or provider.

<a id="hl-055"></a>

### HL-055 — Expand court coverage after the Federal Supreme Court connector is stable

Add further federal or cantonal courts source by source rather than implying universal Swiss coverage.

**Status: DONE.** The Federal Criminal Court is now the second court source. Its bounded official latest-decision list feeds normalized dockets, hierarchy, decision dates, DE/FR/IT language, court-linked original PDFs, cited norms, source health, and an explicit latest-window coverage warning into the shared corpus. Fixture tests cover overlap, deduplication, drift, provenance, and evidence reopening; the bounded live check observed 50 decisions and successfully reopened one 217-page PDF. See [the connector contract](docs/FEDERAL_CRIMINAL_COURT_CONNECTOR.md).

Acceptance criteria:

- Select each court from demonstrated user value and a maintainable official source contract, not from scrape convenience alone.
- Map its identifiers, hierarchy, dates, languages, artifacts, cited norms, coverage limits, and reuse terms into HL-036/HL-038.
- Keep source-specific health and coverage visible; absence from one database never means absence of a decision.
- Pass fixture/live smoke, incremental overlap, deduplication, drift detection, provenance, and evidence reopening before declaring support.

<a id="hl-056"></a>

### HL-056 — Split services across hosts or add high availability only after measured need

Keep a documented scale-out path without paying its operational cost in the first public deployment.

Acceptance criteria:

- Use HL-049 measurements and outage history to identify the actual bottleneck or availability requirement before changing topology.
- Preserve the same PostgreSQL job contract, connector cursors, artifact identities, model fingerprints, and authorization boundaries across hosts.
- Add shared/object artifact storage, externalized PostgreSQL/Redis, remote GPU routing, or replicas only with explicit consistency, backup, TLS, and failure-recovery tests.
- Do not call a multi-host deployment highly available until database, broker, artifacts, ingress, and model routing all have tested failure behavior.

## Shared completion rule

An item is done only when its acceptance criteria are demonstrated through the actual UI/API/persistence path where applicable, meaningful checks pass for its state or evidence logic, and user-visible error states are handled. Completing this backlog document does not complete any development item.

Minimum MVP evidence remains: a verified public source; a saved current version; an imported earlier version with provenance; a real comparison; an inspectable diff; a successful real Apertus analysis; a question with a working citation; and successful repeat/restart/failure checks. The public beta additionally requires every P0/P1 item in `HL-029`–`HL-049` plus `HL-057`–`HL-064`, source-contract evidence for all three core connectors, complete five-locale smoke/catalogue checks, the decision-ready AI-triage regression and usability gate, local-model and recovery benchmarks on the target host, organization-isolation checks, and the reproducible capacity scenario.

Still excluded from the public-beta release: Kubernetes, multi-host workers, database/broker high availability, enterprise SSO/SCIM, arbitrary custom roles, unbounded crawling, universal Swiss court coverage, an ornamental graph UI, OCR, login-gated ingestion, model training/fine-tuning, and automatic legal decisions. They remain future work only where an item above names a measurable entry condition. Ordinary validation, bounded fetching, safe rendering, authorization, secret handling, backups, and recovery are implementation requirements rather than optional enterprise decoration.
