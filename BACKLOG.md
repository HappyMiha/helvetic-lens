# Helvetic Lens — Development Backlog

**See what changed. Understand what matters.**

This backlog implements the product described in [README.md](README.md): a local-AI-first Swiss regulatory monitor with immutable evidence, a time-based legal registry, official-source connectors, cross-document impact analysis, and organization workspaces.

**Status, reviewed 4 September 2026:** The source/evidence, organization, local-runtime, connector, comparison, responsive-shell and topic foundations are implemented. Historical DONE records below retain their original scope and verification evidence; they do **not** establish useful AI reasoning, complete source coverage, accessible journeys, target-host capacity, or product-market fit. The [current product audit](docs/PRODUCT_REVIEW_2026-09-04.md) found concrete contrast and relevance defects, extractive local answers presented as analysis, and an unfinished topic-to-notification journey. The [product-quality reset](#product-quality-reset-2026-09-04) is the next execution order. Hardware/operations gates HL-032/048/049, native localization HL-057, independent AI/usability evidence HL-064 and daily-use acceptance HL-088 remain open. See also the [architecture](docs/ARCHITECTURE.md), [historical UX audit](docs/UX_PRODUCT_AUDIT.md), [AI triage design](docs/AI_TRIAGE.md), [impact-report contract](docs/IMPACT_REPORT.md), [Ask routing](docs/ASK_ROUTING.md), and [verification evidence](docs/VERIFICATION.md).

## Scope and priorities

- **P0 — critical trust, accessibility, release foundation or capacity gate.** The public beta cannot open without it.
- **P1 — required public-beta product capability.** P1 is required for the agreed local-AI-first product, even when it can follow the P0 foundation.
- **P2 — valuable follow-up after public beta.** Add after the core three sources, registry, and impact inbox are reliable.
- **P3 — evidence-driven expansion.** Implement only when real use demonstrates the need.

The original baseline contains 28 items: 27 completed and one deferred optional item (HL-024; optional HL-023 is complete). The original public-beta roadmap contains **29 required items (`HL-029`–`HL-049` plus `HL-057`–`HL-064`)** and **7 earlier after-beta items (`HL-050`–`HL-056`)**. The daily-use roadmap adds **25 items (`HL-065`–`HL-089`)**. The September product audit adds **12 corrective/evaluation items (`HL-090`–`HL-101`)**, while reusing the unfinished daily-use tasks rather than duplicating them. Follow dependencies and checkpoints; priority alone is not an execution order. Start discovery and design validation now; target-hardware absence blocks promotion, not useful prototype work. No unsupported calendar or capacity promises.

Keep the proven stack and add only the infrastructure now justified by public use: **Next.js, Tailwind CSS/shadcn/ui, FastAPI, PostgreSQL, Redis, Celery, Caddy, BeautifulSoup, pdfminer.six, `difflib`, and a private llama.cpp-based local inference runtime**. A quantized **Apertus 8B** profile is the intended production default only after it passes the target-hardware gate; the smaller verified profile remains valid for development. Cloud model adapters are optional and disabled by default. **pgvector remains conditional on a measured recall gap.**

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
| M10 — Reliable daily workspace  | HL-065–HL-073         | Navigation, scrolling, comparison AI, mobile use, source selection, and first-run guidance work as one predictable product.                                     |
| M11 — Interest-based monitoring | HL-074–HL-082, HL-089 | Users follow laws or natural-language topics and receive grouped, evidence-linked, organization-relevant alerts from explicitly activated official or public-discourse source packs. |
| M12 — Local product assistant   | HL-083–HL-087         | A small local Apertus assistant explains the product, drafts monitoring plans, answers through cited workflows, and proposes safe user-confirmed actions.        |
| M13 — Daily-use acceptance      | HL-088                | Responsive, first-value, relevance, local-model, accessibility, localization, and source-honesty gates pass on the actual target hardware.                       |
| M14 — Product-quality reset     | HL-090–HL-101 plus open daily-use tasks | The complete interest-to-evidence-to-notification journey is useful in an independent pilot; validated local explanations, accessible reading, honest coverage and bounded operations replace implementation-only success claims. |

**Historical sequencing:** HL-029 and HL-065 were the entry points for the now-implemented architecture and daily-work foundations; do not restart them. Preserve the original task record, including deferred HL-024. **Current execution follows M14 below.** Keep its original architectural constraints: shared corpus and tenancy before broad fan-out, complete saved evidence before model interpretation, durable topic contracts before conversational activation, localization alongside each screen, and measured operations/capacity before public registration.

## Task index

**Status discipline:** DONE means the recorded implementation scope was completed, not that later defects are denied. Fixes to DONE work have explicit new IDs or follow-up acceptance notes. IN PROGRESS separates implemented code from missing field/hardware evidence. PLANNED is not delivered. New measured targets below are proposed acceptance thresholds, never current performance claims.

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
| [HL-023](#hl-023) | P2       | DONE     | HL-018, HL-022                                         | Optional business impact matrix                                     |
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
| [HL-048](#hl-048) | P0       | IN PROGRESS | HL-029–HL-035, HL-038                               | Public single-server deployment and operations baseline             |
| [HL-049](#hl-049) | P0       | IN PROGRESS | HL-037–HL-048, HL-057–HL-063; implemented evaluation protocol | Reproducible recovery and 100-user capacity gate             |
| [HL-057](#hl-057) | P1       | IN PROGRESS | HL-032, HL-034–HL-037, HL-045–HL-047                | Complete German, French, Italian, Romansh, and English localization |
| [HL-058](#hl-058) | P0       | DONE     | HL-005, HL-036, HL-038                                 | Document-identity gate before comparison or AI                      |
| [HL-059](#hl-059) | P0       | DONE     | HL-011, HL-036, HL-058                                 | Legal-unit semantic diff with noise classification                  |
| [HL-060](#hl-060) | P0       | DONE     | HL-030–HL-032, HL-059                                  | Fixed-budget local-AI analysis planner                              |
| [HL-061](#hl-061) | P1       | DONE     | HL-033, HL-060                                         | Actionable, deduplicated impact-report contract                     |
| [HL-062](#hl-062) | P1       | DONE     | HL-060, HL-061                                         | Intent-routed Ask experience and safe context selection             |
| [HL-063](#hl-063) | P1       | DONE     | HL-030, HL-037, HL-059–HL-062                          | Decision-ready comparison UX and background progress                |
| [HL-064](#hl-064) | P0       | IN PROGRESS | HL-049 final report, HL-057–HL-063                    | AI-triage regression, evidence, latency, and usability gate         |
| [HL-050](#hl-050) | P2       | DONE     | HL-038, HL-042                                         | Broader official regulatory news connectors                         |
| [HL-051](#hl-051) | P2       | DONE     | HL-044, HL-050                                         | Measured semantic candidate recall with pgvector if justified       |
| [HL-052](#hl-052) | P2       | DONE     | HL-034, HL-046, HL-057                                 | Opt-in email and web digests                                        |
| [HL-053](#hl-053) | P3       | IN PROGRESS | HL-044–HL-046                                       | Relation review workflow and visual graph                           |
| [HL-054](#hl-054) | P3       | DONE     | HL-034, HL-035                                         | Account recovery, verification, 2FA, and SSO refinements            |
| [HL-055](#hl-055) | P2       | DONE     | HL-038, HL-041                                         | Broader federal and cantonal court coverage                         |
| [HL-056](#hl-056) | P3       | PLANNED  | HL-049                                                 | Multi-host or high-availability deployment after measured need      |
| [HL-065](#hl-065) | P0       | DONE     | HL-035, HL-047                                         | Reliable application shell and independent scroll contract          |
| [HL-066](#hl-066) | P0       | DONE     | HL-035, HL-047, HL-065                                 | Task-based navigation and canonical Company profile page            |
| [HL-067](#hl-067) | P0       | DONE     | HL-030, HL-063, HL-065                                 | Keyed resource cache and targeted interface updates                 |
| [HL-068](#hl-068) | P0       | DONE     | HL-063, HL-065, HL-067                                 | Responsive comparison decision workspace                            |
| [HL-069](#hl-069) | P0       | DONE     | HL-030, HL-062, HL-067, HL-068                         | Asynchronous Ask experience with real job progress                  |
| [HL-070](#hl-070) | P0       | DONE     | HL-065, HL-066, HL-068, HL-069                         | Working mobile information architecture at 390 px                   |
| [HL-071](#hl-071) | P0       | DONE     | HL-038–HL-043, HL-050, HL-055                          | Versioned source capability catalogue and honest coverage           |
| [HL-072](#hl-072) | P0       | DONE     | HL-033, HL-035, HL-042, HL-071                         | Organization source packs and Swiss Federal Starter                 |
| [HL-073](#hl-073) | P0       | PLANNED  | HL-034, HL-035, HL-066, HL-070, HL-072, HL-074, HL-077 | Stateful onboarding, contextual help, and useful empty states       |
| [HL-074](#hl-074) | P0       | DONE     | HL-033, HL-035, HL-036, HL-042, HL-071, HL-072         | Durable monitoring topics and editable monitoring plans             |
| [HL-075](#hl-075) | P0       | DONE     | HL-044, HL-051, HL-074                                 | Bounded topic matching with persisted evidence                      |
| [HL-076](#hl-076) | P0       | PLANNED  | HL-037, HL-046, HL-067, HL-075, HL-094, HL-099         | Unified interest feed; HL-089 enriches cards asynchronously          |
| [HL-077](#hl-077) | P1       | PLANNED  | HL-035, HL-066, HL-074                                 | Contextual “Monitor this”; integrate HL-076 as its feed arrives      |
| [HL-078](#hl-078) | P1       | PLANNED  | HL-052, HL-076, HL-077                                 | In-app notification centre over the existing delivery state         |
| [HL-079](#hl-079) | P1       | PLANNED  | HL-052, HL-075, HL-076                                 | Topic matches in existing digests                                   |
| [HL-080](#hl-080) | P1       | PLANNED  | HL-038, HL-071, HL-072                                 | Cantonal source-pack framework and one verified pilot               |
| [HL-081](#hl-081) | P2       | PLANNED  | HL-080                                                 | Evidence-gated expansion to the next two cantonal packs             |
| [HL-082](#hl-082) | P2       | PLANNED  | HL-038, HL-050, HL-071, HL-074–HL-076                  | Separate opt-in public-discourse signal pilot                       |
| [HL-083](#hl-083) | P1       | IN PROGRESS | HL-035, HL-062, HL-074, HL-076, HL-077              | Local assistant intent, context, privacy, and action contract       |
| [HL-084](#hl-084) | P1       | IN PROGRESS | HL-031, HL-032, HL-083                              | Small local Apertus assistant profile and hardware gate             |
| [HL-085](#hl-085) | P1       | IN PROGRESS | HL-065–HL-070, HL-083, HL-084                       | Persistent global assistant experience with cited answers          |
| [HL-086](#hl-086) | P1       | PLANNED  | HL-035, HL-074, HL-075, HL-077, HL-083, HL-085         | Natural-language monitoring-topic flow through the assistant        |
| [HL-087](#hl-087) | P1       | IN PROGRESS | HL-057, HL-085                                      | Proactive dry robot companion with safe five-language tone           |
| [HL-088](#hl-088) | P0       | PLANNED  | HL-049, HL-057, HL-064, HL-065–HL-080, HL-083–HL-087, HL-089–HL-101 | Final daily-use acceptance, including independent pilot evidence |
| [HL-089](#hl-089) | P0       | PLANNED  | HL-032, HL-045, HL-061, HL-075, HL-091, HL-092, HL-094, HL-100 | Persisted AI relevance briefs for matched developments       |
| [HL-090](#hl-090) | P1       | PLANNED  | None                                                   | Target-user discovery and observed first-value prototypes           |
| [HL-091](#hl-091) | P0       | PLANNED  | HL-031, HL-060, HL-093                                 | Capability-based local explanations versus explicit extractive mode |
| [HL-092](#hl-092) | P0       | PLANNED  | HL-061, HL-091                                         | Truthful structured reports, dates, applicability and useful actions |
| [HL-093](#hl-093) | P0       | IN PROGRESS  | HL-059, HL-062, HL-075                                 | Independent semantic gold set and honest quality metrics            |
| [HL-094](#hl-094) | P0       | IN PROGRESS  | HL-030, HL-075                                         | Fair resumable matching and preview/production parity               |
| [HL-095](#hl-095) | P1       | PLANNED  | HL-037, HL-066, HL-074                                 | Progressive topic, registry and recovery controls                   |
| [HL-096](#hl-096) | P1       | PLANNED  | HL-063, HL-068                                         | Coherent visual system and readable scalable evidence               |
| [HL-097](#hl-097) | P0       | IN PROGRESS  | HL-065, HL-068, HL-070                                 | Visible AI controls and accessible populated journeys               |
| [HL-098](#hl-098) | P0       | PLANNED  | HL-036, HL-071, HL-072                                 | Verified source coverage and versioned legacy-artifact repair       |
| [HL-099](#hl-099) | P0       | IN PROGRESS | HL-030, HL-036, HL-046                                 | Bounded event read model and period-limited digest queries           |
| [HL-100](#hl-100) | P0       | IN PROGRESS  | HL-044, HL-045, HL-093                                 | Substantive relation evidence and safe assessment supersession       |
| [HL-101](#hl-101) | P0       | PLANNED  | HL-090, HL-073, HL-076, HL-078, HL-079, HL-089, HL-032, HL-048, HL-049, HL-057, HL-064, HL-098–HL-100 | Measured longitudinal pilot and rollout decision |

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
- Extract meaningful HTML text with BeautifulSoup and text-based PDF content with pdfminer.six. Keep headings, article numbers, substantive dates, and paragraph/page boundaries.
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

**Status: DONE.** `/matrix` now presents every active monitored law against the current company-profile business areas using only saved, validated Impact reports. Exact area matches expose the report's indicative rating and reason; unassessed, unanalysed, failed, and stale states remain explicit and never collapse to low impact. Profile, prompt, model/runtime, locale, or comparison changes invalidate current values through the same cache fingerprint used by HL-018, while prior values remain clearly historical. Every row and assessed cell returns to the exact saved comparison/evidence. The page is organization-scoped, read-only, responsive, localized in all five product languages, and does not alter scanning or trigger inference. See [the saved Impact matrix contract](docs/IMPACT_MATRIX.md).

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

**Status: IN PROGRESS.** The stable private gateway, local-first clean-install policy, automatic four-profile routing, warm-up/health, fair slot admission, visible model waits, complete result provenance, benchmark harness, and live GTX 1070 report are implemented. The 1.5B Q4 development profile passed 20/20 structured calls plus the serialized concurrent pair without schema/citation errors, OOM, or timeout. Automatic and explicit profile selection share the same model-plus-runtime-headroom checks, persist the selected memory plan, and degrade to CPU rather than attempting an unsafe GPU layout. Replicated startup reports `ready` only after every planned runner passes health and structured warm-up; a surviving runner cannot hide a failed replica and remains explicitly `degraded`. The v2 benchmark fails closed when the requested hardware profile, GPU inventory, accepted slots, distinct runner slots, or any required call does not match. The checked-in development report remains deliberately non-promotable: final closure and any 8B promotion require running the target command on the planned dual-GTX-1080 server and observing two distinct replica slots.

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

**Status: IN PROGRESS — TARGET/HUMAN EVIDENCE REMAINS.** The versioned five-locale corpus and deterministic quick/full gate cover identity mismatch, line-wrap noise, insertion plus consequent renumbering, moved text, a real deadline change, official replacement metadata, and a complete 1,401-passage-per-side rewrite. The API gate enforces three/five-call Ask/Impact budgets, sub-second zero-call clarification, cache reuse and invalidation, exact quotation validation, rejection of invented citations, last-valid-report preservation, unique actions, and valid zero-action results. The platform dashboard now aggregates deterministic-overview, queue and inference latency, calls/tokens, cache reuse, citation acceptance, limited/failed rates, and review decisions. The v2 five-locale moderation contract requires different fluent participants, timezone-bounded sessions, concrete observed change/relevance/evidence/action text, and honest action fields without claiming unperformed results. A combined fail-closed validator binds the sessions to the exact clean-build capacity-report hash, target host, dual-GTX-1080 model profile, machine latency/validation/call-budget metrics, and saved action outcomes. Only the physical target baseline and five completed independent human sessions remain. See [the regression gate](docs/AI_TRIAGE_REGRESSION.md) and [metrics contract](docs/AI_TRIAGE_METRICS.md).

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

**Status: IN PROGRESS — TARGET HOST REHEARSAL REMAINS.** A dedicated production Compose file now pins base/runtime images, runs migrations before readiness, exposes only Caddy on 80/443, keeps data and model paths on private networks, persists state, rotates logs, and restarts long-running services. A fail-closed validator and matching application checks reject insecure authentication, weak/placeholder secrets, HTTP origins, private-network fetching, inline jobs, cloud-first defaults, and oversized uploads. Atomic scheduled PostgreSQL plus evidence/config backups use a separate destination, checksums, bounded retention, status-only application visibility, a shared lock that serializes overlapping scheduled/pre-upgrade runs, and a twice-confirmed restore path; isolated real database/artifact restore and concurrent-publication rehearsals pass. Daily cleanup bounds diagnostic logs, terminal jobs, transient mailbox/files, and unreferenced artifacts while preserving active work, AI history, and all referenced evidence. Redis AOF is disposable under the tested PostgreSQL outbox/reconciliation contract. Generated request IDs persist through durable jobs and workers into redacted connector/model diagnostics with allowlisted organization, run, document/event, comparison, and analysis identifiers. The platform console exposes bounded normalized-route API latency/error/in-flight metrics, database and Redis probe latency, queues, connector freshness, local-model/GPU capacity, disk, and backup age without secret or high-cardinality labels. Only the physical dual-GTX-1080 install/upgrade/certificate/model-redownload/rollback rehearsal remains.

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

**Status: IN PROGRESS — TARGET-HOST RUN REMAINS.** A checked-in, safely gated seed/cleanup pair now creates 100 accounts across 10 isolated organizations with private synthetic laws, artifact-backed versions, verified identity, deterministic comparisons, and watches. The capacity runner exercises 10–20 concurrent registry/evidence/comparison readers, filters, scans, one official connector, and 20 accepted AI submissions; it records request IDs, p50/p95/max latency, job queue wait/drain, execution duration, retries, connector duration, platform state, Docker/host/GPU/disk samples, and operator-supplied inference and backup/restore evidence. Its release decision now validates the actual 100 unique manifest accounts, requires all 300 reads, exact unique durable job IDs, successful connector/model recovery, stable comparison evidence, one new question history item per organization without duplicate Impact records, complete RAM/swap telemetry, bounded memory/swap/disk use, a dual-GTX-1080 v2 promotion report, and non-placeholder backup/restore probes. Diagnostic omissions therefore fail closed. Recovery mode restarts the scheduler, API, Redis, both workers, and model manager one at a time, verifies the named service and API after each restart, and reactivates the previously running model. Bounded database pools and work-conserving cross-organization GPU admission are implemented and exposed without leaking tenant identities. A development smoke run created the full 100-account/10-organization corpus, completed 60 concurrent reads at 388 ms p95 and 22 command enqueues at 333 ms p95 with no unexpected HTTP errors, and verified all six service restarts; all synthetic rows and artifacts were then removed with the checked-in cleanup command. Public-beta completion still requires one isolated production run on the intended i7/32 GB/two-GTX-1080 host, with an active model during recovery, a dual-GPU inference report, connector completion, and measured backup/restore evidence.

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

**Status: IN PROGRESS — NATIVE REVIEW REMAINS.** Locale resolution/persistence, the five-language selector, localized account/digest mail, stable error translation, locale-aware formatting, Unicode search, source-language markup, and locale-isolated Impact/Ask/relation analysis history are implemented. The production catalogue covers every release screen; an AST-based gate rejects hard-coded TSX text, attributes, dialog text, missing/unused keys, placeholder drift, and unapproved cross-locale inheritance. The executable acceptance gate has passed five complete browser paths, admin/viewer authorization, desktop and 390 px layouts, error/citation flows, and one real local-Apertus cited answer per locale. The human review now has a fail-closed contract bound to the exact clean Git revision and catalogue SHA: it requires different fluent German/French/Italian reviewers, a native Romansh reviewer, concrete flow/model/evidence observations, and resolution commits for every finding. Those four actual reviews still remain before this item can be marked done. See [the localization contract and review matrix](docs/LOCALIZATION.md) and [the five-locale verification record](docs/LOCALIZATION_VERIFICATION.md).

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

**Status: DONE.** Every signed-in user now has organization-scoped daily or weekly preferences, severity/source filters, a saved-data web preview, manual rate-limited delivery, direct signed unsubscribe links, and bounded delivery history. Celery Beat schedules idempotent durable delivery jobs; email uses the existing development/SMTP transport and includes links back to persisted comparison evidence. Empty or disabled-email deliveries are recorded honestly, and neither delivery nor failure changes personal read state or legal history. The complete interface and transactional copy are available in DE/FR/IT/RM/EN. See [the digest contract](docs/DIGESTS.md).

Acceptance criteria:

- Let each user opt into daily/weekly digests, choose organization/severity/source filters, and unsubscribe directly.
- Generate digests from persisted feed items and evidence links; delivery failure never alters read state or legal-event history.
- Deduplicate sends with durable jobs, apply rate limits/retries, and store bounded delivery status without logging mail credentials or document bodies unnecessarily.
- Keep in-app notifications fully usable when email is not configured.

<a id="hl-053"></a>

### HL-053 — Add relation review workflow and a visual graph only after list/inbox validation

Help administrators curate proposed relations when real usage proves that a graph adds value.

**Status: IN PROGRESS — REAL GRAPH EXPERIMENT REMAINS.** The Impact Inbox now provides an evidence-first, five-language review panel for proposed relations. Administrators must record a reason when confirming or rejecting a lead and can add a non-decisive annotation; every entry retains author and timestamp in an immutable organization-scoped history. Official confirmed metadata cannot be overridden, and viewers remain read-only. Privacy-bounded baseline metrics record the allowlisted workflow variant, time to a saved decision, and whether the panel's evidence link was opened; the platform dashboard exposes both aggregate and per-variant latency, decision, and evidence-open measures without note/source/identity labels. A fail-closed experiment gate now binds raw list-versus-graph trials to the exact clean Git revision, requires separate participants, the same tasks, all five languages, accessibility and authorization evidence, and only promotes a graph as a secondary view after noninferior quality plus materially faster or more accurate review. A sound no-benefit result explicitly retains the inbox. The graph is intentionally not implemented until this real experiment demonstrates value. See [the relation review contract](docs/RELATION_REVIEW.md).

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

## M10 — Reliable daily workspace

The findings and target flow for this milestone are recorded in the [daily-use UX and product audit](docs/UX_PRODUCT_AUDIT.md). Fix the interaction foundation before adding more destinations to the current navigation or more cards to the comparison page. `HL-073` is grouped here because it closes the first-use UX, but its dependency order deliberately schedules it after topic monitoring and `HL-077`.

<a id="hl-065"></a>

### HL-065 — Establish a reliable application shell and scroll contract

Make navigation and primary actions reachable regardless of page length, viewport height, browser zoom, role, or translation length.

**Status: DONE.** The desktop shell is pinned to the dynamic viewport with independent bounded navigation and main scroll regions, a sticky topbar, long-label wrapping, focus-safe scroll padding, and device safe-area spacing. Mobile returns to one document scroll and removes the nested AI-history scroll. The regression contract runs in local and Docker builds. Browser QA at 1280×600, 1024×768 in German, and 390×844 proved no document/double scroll on desktop, no horizontal overflow, keyboard reachability of the last administration route, independent main/navigation positions, and one mobile document scroller.

Acceptance criteria:

- On desktop, use a `100dvh` application shell with an independently scrollable navigation region and an independently scrollable main region; brand, organization switcher, account access, and the current route remain usable when either region is long.
- Keep focus inside the visible viewport when keyboard users traverse a long menu, and preserve a clear active route at 1024×768, 200% zoom, and with the longest DE/FR/IT/RM/EN labels.
- On mobile, use one predictable document scroll rather than nested vertical scroll traps; overlays lock and restore the underlying scroll and return focus to their trigger.
- Define reusable shell, page-header, content-width, and sticky-region primitives instead of route-specific height calculations.
- Add responsive tests for short and long pages, admin-only routes, browser zoom, keyboard reachability, safe-area insets, and dynamic viewport changes.

<a id="hl-066"></a>

### HL-066 — Replace module navigation with task-based navigation and a canonical Company profile page

Organize the interface around daily regulatory work and remove duplicate or surprising ways to reach organization settings.

**Status: DONE.** Desktop and mobile now share task-oriented daily, workspace, and role-gated administration destinations; multi-organization users can switch workspaces in either layout, and the mobile overflow names the active destination. The organization selector only switches organizations; `/organization#company-profile` is the single responsive profile editor with browser history, direct links, discard controls, normalized-save hydration, and navigation guards that survive refreshes and failed workspace changes. Monitoring and Discover use canonical routes, while unauthorized direct administration routes neither fetch privileged resources nor expose enabled controls. The former modal, duplicate AI connection test, DOM-click bridge, clipped mobile route strip, and permissive unknown-session role fallback are removed. Server tests independently prove that a platform administrator with a viewer membership can operate platform controls without gaining organization write access.

Acceptance criteria:

- Group navigation into daily work (**Today**, **Monitoring**, **Impact inbox**, **Discover**, **Sources**), workspace settings, and role-gated administration; technical model, connector, prompt, and diagnostic pages do not compete with the everyday routes.
- Make the workspace selector switch organizations only. Provide one canonical routed Company profile page with a stable URL, browser history, direct linking, unsaved-change protection, and responsive layout.
- Remove duplicate Company profile triggers, DOM-query/click routing workarounds, and the profile modal. Move provider/model connection tests to Local AI or Integration settings.
- Preserve the same authorized destinations on desktop and mobile, with an explicit overflow destination rather than a clipped horizontal route list.
- Verify admin/viewer/platform-admin visibility and API authorization independently; hiding a link never substitutes for server enforcement, and viewers do not receive enabled-looking edit/delete/admin controls they cannot use.

<a id="hl-067"></a>

### HL-067 — Replace global refresh broadcasts with keyed resource updates

Keep successful AI and mutation flows from reloading unrelated data, moving the page, or repeating expensive requests.

**Status: DONE.** The web client now uses a shared typed resource catalogue with explicit session, organization, and platform ownership; locale-aware cache identity; stale-while-revalidate snapshots; in-flight request deduplication; bounded inactive-entry eviction; targeted exact/tag invalidation; and scope resets for organization changes and sign-out. Background resources stop polling while hidden, focus/reconnect refreshes coalesce, and durable-job polling shares the same store. Ask and Impact update their job and history state without reloading the persisted comparison diff or unrelated runtime/navigation data. Mutation paths update or invalidate only their affected laws, sources, scans, jobs, registry, inbox, organization, model, connector, prompt, or diagnostic keys. Contract regressions cover request counts, stale-data continuity, races, polling ownership, interaction-state preservation, the six named user flows, and the removal of the global refresh broadcast.

Acceptance criteria:

- Introduce a typed/keyed resource cache or invalidation layer with request deduplication, stale-while-revalidate behavior, and explicit ownership of each resource key.
- An Ask completion updates its job, answer, and comparison history keys only; it does not refetch the saved diff, model catalogue, health checks, navigation data, or unrelated organization resources.
- Mutations optimistically update or invalidate the smallest correct key set and reconcile failures without losing scroll, selected comparison tab, expanded evidence, or typed input.
- Pause low-priority polling while the page is hidden and prevent concurrent duplicate fetches after focus, navigation, or reconnect.
- Add request-count and state-preservation tests for Ask, impact rerun, relation review, watch creation, organization switch, and sign-out.

<a id="hl-068"></a>

### HL-068 — Turn comparison into a responsive decision workspace

Keep exact evidence inspectable while making the useful explanation and next decision visible without a kilometre-long page.

Acceptance criteria:

- On wide desktop, keep evidence in the primary pane and use a viewport-stable 420–480 px companion panel with **Summary**, **Actions**, **Ask**, and **History** tabs; each tab scrolls within its own content area without determining the full page height.
- Lead with a compact, plain-language answer covering material changes, possible relevance, applicability/status, and up to three useful review actions. Put detailed provenance, processing metadata, uncertainties, and repeated evidence lists behind deliberate disclosure.
- Evidence links move to the exact saved legal unit in the comparison without losing the selected companion tab or scroll position; keyboard and screen-reader users receive the same relationship.
- Tablet uses an accessible drawer or split view. Mobile uses task tabs and a full-screen assistant/report surface that can be opened before traversing the entire diff.
- Retain deterministic diff, material/noise filters, original artifacts, citations, and history as complete audit views; compact presentation never discards evidence.

Completed 4 September 2026. Wide comparisons now keep the deterministic evidence pane primary beside a viewport-stable 420–480 px companion with Summary, Actions, Ask, and History tabs. Summary leads with the saved plain-language assessment and at most three action titles; full action decisions, material-change cards, uncertainties, provenance, processing coverage, and prior reports remain available in their dedicated tab or disclosures. Matching citations from current and historical answers jump to the exact saved diff row, focus it for assistive technology, and preserve the selected companion task. Tablet uses an accessible overlay drawer and mobile exposes the same tasks before the diff in a full-screen surface. Sixteen shell/workspace regressions, the five-language catalogue audit, resource-store tests, TypeScript, the Next.js production build, and live browser checks at 1440 px and 390 px cover the result.

<a id="hl-069"></a>

### HL-069 — Make Ask asynchronous and show real AI job progress

Treat a local-model request as durable work rather than a frozen form that appears to reload the page.

Acceptance criteria:

- Submit immediately creates a pending user message and durable job card with real stages such as queued, starting model, selecting evidence, generating, validating, completed, limited, failed, and cancelled.
- The user can leave the comparison, continue other work, cancel where safe, and return to the same job; completion appears in place and through the notification surface without a full page refresh.
- Retrying is idempotent, distinguishes cached results from new inference, and never creates duplicate shared history from double click, reconnect, or browser back/forward.
- Error states preserve the question and provide a specific recovery action for model unavailable, queue delay, context limit, validation failure, and unsupported evidence.
- Progress and completion use `aria-live` appropriately, respect reduced motion, and remain comprehensible without an animated mascot.

Completed on 4 September 2026. Ask now persists and returns a durable job immediately, restores active jobs after navigation, and reports queue, evidence selection, generation, validation, completion, limited, failure, and cancellation states from backend progress. The comparison workspace updates Ask history without reloading the saved diff, preserves failed questions for revision, provides model/context/validation/evidence recovery actions, and can cancel or idempotently retry the same job. Completed duplicate submissions reuse one history record and visibly distinguish a cached answer from new inference. Five-locale text, `aria-live`, reduced-motion behavior, API regressions, resource-flow contracts, and the rebuilt Compose stack were verified.

<a id="hl-070"></a>

### HL-070 — Provide a working mobile information architecture at 390 px

Design mobile as a complete task surface instead of compressing the desktop sidebar and two-column pages.

Acceptance criteria:

- Provide a compact top bar and at most four primary bottom destinations plus **More**; preserve all authorized workspace/admin routes in a labelled mobile menu.
- Registry, monitoring, Impact inbox, comparison, Company profile, onboarding, notifications, and assistant flows work without horizontal page overflow at 360, 390, and 430 px widths.
- Comparison offers clear Summary/Diff/Ask/History task switching and readable before/after cards or a controlled side toggle; no critical AI control sits after the full diff.
- Interactive targets are at least 44×44 CSS px, sticky controls respect safe areas and the on-screen keyboard, and dialogs/drawers expose a visible close path.
- Add real-browser journey checks at 390×844 and 768×1024 for both viewer and admin roles, including long localized labels, loading, empty, error, and offline/reconnect states.

Completed on 4 September 2026. Mobile now has a compact top bar, four primary bottom destinations, and a labelled role-filtered More menu containing every remaining authorized route. Comparison exposes five reachable Summary, Diff, Actions, Ask, and History tasks before the evidence stream; companion tasks become a bounded full-screen surface on phones. Safe-area spacing, independently scrollable overflow navigation, 44 px controls, bounded dialogs, long-value wrapping, and compact five-language labels prevent the desktop shell from collapsing on narrow screens. A Chrome CDP journey verifies the real production stack at 360, 390, 430, and 768 px, including admin/viewer menus, onboarding, comparison task switching, horizontal overflow, target size, and an actual offline/reconnect transition.

<a id="hl-071"></a>

### HL-071 — Publish a versioned source capability catalogue with honest coverage

Make supported Swiss information sources an explicit product contract before packaging or promoting them.

Acceptance criteria:

- Store a versioned manifest for each connector: authority/publisher, stream, jurisdiction, document/event kinds, languages, cadence, incremental cursor, historical window, artifact/provenance behavior, reuse/attribution note, known gaps, and last verified live check.
- Surface states such as available, syncing, healthy, degraded, unavailable, and partial. A missing or failed source is never interpreted or worded as “nothing changed.”
- Represent existing Fedlex, Parliament, federal-court, consultation, News Service Bund, and FINMA capabilities at their actual tested scope, including incomplete language or bounded-history limitations.
- Drive operator status and user-facing source copy from the same manifest so product claims cannot drift from connector tests and runbooks.
- Require fixture, incremental-overlap, deduplication, provenance, drift, artifact reopening, and bounded live-smoke evidence before a capability is marked available.

Completed on 4 September 2026. A versioned catalogue now covers every one of the 23 scheduled official streams and publishes authority, scope, languages, cadence, cursor, historical bounds, artifact and provenance behavior, attribution, gaps, and dated live evidence. The Sources page groups the same manifests into six understandable official-source families, while the operator schedule embeds each exact contract beside its runtime state. Promotion fails closed: only six exact streams with all seven evidence gates are `available`; the remaining seventeen are visibly `partial`. Runtime status distinguishes syncing, healthy, degraded, unavailable, and partial without converting a missing item or failed source into “nothing changed.” API regressions, the production build, and a real Chrome journey across phone/tablet sizes, five locales, admin/viewer roles, and offline recovery verify the contract.

<a id="hl-072"></a>

### HL-072 — Add organization source packs and a Swiss Federal Starter

Let a new organization activate trusted coverage without finding and pasting individual URLs.

Acceptance criteria:

- Add global `SourcePackDefinition` records and organization-scoped subscriptions. Enabling a pack filters and backfills from the shared public corpus; it never starts duplicate connector cursors, downloads, artifacts, or per-organization ingestion.
- Ship a Swiss Federal Starter composed of visible subpacks for Fedlex legislation/consultations, Parliament, supported federal courts, and official policy/regulator notices. Users can inspect and activate subpacks separately.
- Before activation, show source authority, content kinds, languages, cadence, last successful sync, historical window, known gaps, expected first-data behavior, and whether coverage is partial.
- Activation/deactivation is idempotent, reversible, audited, and admin-only; viewers can inspect active coverage and request a change without mutating shared settings.
- Backfill is bounded and queued, reports progress and partial failure, and reuses existing normalized documents/events. Disabling a pack stops future organization feed inclusion without deleting shared legal evidence.

Completed on 4 September 2026. A versioned global catalogue now supplies a Swiss Federal Starter with five independently controlled subpacks for Fedlex legislation, consultations, Parliament, supported federal courts, and official policy/regulator notices. Organization subscriptions and viewer change requests are tenant-scoped; admin activation/deactivation is idempotent and covered by the administrative audit trail. Activation queues bounded backfill on the existing ingest worker and creates only organization event-state rows, while live connector fan-out includes future events for active packs. The Sources page exposes exact capability-derived authorities, kinds, languages, cadence, last sync, expected first data, historical boundaries, partial coverage, progress, and errors in all five product locales. Full API, build, migration, live-worker, and responsive browser checks confirm that deactivation retains prior evidence and no shared work, event, cursor, or artifact is duplicated.

<a id="hl-073"></a>

### HL-073 — Add stateful onboarding, contextual help, and useful empty states

Guide a new user from an empty organization to one inspectable, relevant item without requiring a manual or exact source URL.

Acceptance criteria:

- Persist onboarding progress independently of whether any `DocumentWatch` exists. Guide users through intent choice, starter-pack review, a law or topic, notification preference, and first saved/cached evidence.
- Offer three plain-language starting intents: monitor a topic, follow a law, or explore current events. Show role-appropriate steps and let invited users skip setup already completed by their organization.
- Replace generic empty cards with distinct states for no subscription, active synchronization, no match in the selected period, filters hiding items, source degradation, and genuinely quiet periods.
- Add concise contextual explanations and one clear next action on unfamiliar pages; advanced source URLs, prompt settings, and connector details stay available without becoming the default first step.
- Label any synthetic/sample item unmistakably, allow an admin to remove it, localize the whole journey in DE/FR/IT/RM/EN, and demonstrate first saved interest plus opened real/cached evidence in under five minutes.

## M11 — Interest-based monitoring

<a id="hl-074"></a>

### HL-074 — Add durable monitoring topics and editable monitoring plans

Represent “follow simplified naturalisation” or another subject as a reviewable organization object instead of an opaque chat sentence.

Acceptance criteria:

- Add organization-scoped `MonitoringTopic` records with immutable revisions containing a plain-language goal, concepts/synonyms, exclusions, jurisdictions, languages, source packs, document/event kinds, importance floor, status, author, and timestamps.
- Local AI may draft a plan from natural language, but the UI always previews each field and lets an authorized user edit and confirm it. No model response silently widens sources, geography, history, or alert volume.
- Creating and editing a useful topic works manually when the model is offline; model/provider identity and prompt revision are recorded only for AI-assisted drafts.
- Preview a bounded count and representative set of already-saved candidate events before activation, with an explanation of why each candidate matched and how to reduce noise.
- Distinguish a topic match from a confirmed legal relation throughout persistence and UI; matching an interest does not establish that one law legally affects another.
- Enforce organization isolation, admin/viewer permissions, revision history, pause/resume, soft archival, and idempotent creation through the API and UI.

Completed on 4 September 2026. Organization-scoped topics now keep explicit plans and immutable revisions for goal, terms, exclusions, geography, languages, source packs, document/event kinds, importance, lifecycle, author, and timestamps. Administrators can work entirely manually or ask the configured local-first model for a separately persisted, strict structured draft with one repair attempt; every field remains editable and requires a deterministic bounded preview plus explicit activation. AI provenance is written only when such a draft is confirmed. Preview scans at most 500 saved events, returns at most ten explained candidates, and labels them as topic matches rather than legal relations. Idempotent creation, optimistic edits, pause/resume, soft archive, tenant isolation, viewer read-only access, five-language UI, and migration/API regressions verify the lifecycle.

<a id="hl-075"></a>

### HL-075 — Implement bounded topic matching with persisted evidence

Connect new normalized events to saved interests without running an unbounded model call for every topic/document pair.

Acceptance criteria:

- Generate candidates with official identifiers/citations, controlled metadata, jurisdictions, dates, and PostgreSQL full-text search first; use local AI only for a capped ambiguous set after deterministic filtering.
- Extend the existing HL-044 candidate/evidence pipeline and HL-051 evaluation rather than creating a parallel matcher. Keep pgvector disabled unless the measured multilingual recall gate still justifies it.
- Persist `TopicEventMatch` with the topic revision, event/document versions, reason signals, exact evidence references, model/rule fingerprint, confidence band, decision status, and timestamps.
- Bound backfill, per-event/per-organization fan-out, AI calls, retries, and retention through durable queues; prove the bound for 100 organizations and never scan the Cartesian product of every topic and every artifact on each synchronization.
- Reprocess only when the topic revision, event evidence, rule version, or approved model/prompt fingerprint changes. Failures do not generate user alerts and remain recoverable in operations UI.
- Maintain a multilingual labelled evaluation set and record precision/noise, missed relevant items, evidence-open, confirm/reject, mute, and refinement measures before changing default thresholds.

Completed on 4 September 2026. New normalized events now enter topic matching only after the existing organization fan-out, and reuse the HL-044 title/citation normalizers plus the source-pack catalogue. PostgreSQL full-text retrieval and exact SR/RS/article references lead into controlled source, kind, jurisdiction, language, date, importance, and exclusion filters. `TopicEventMatch` persists the exact topic revision, event and document identities, reason signals, source/identifier evidence, deterministic fingerprints, confidence, review state, and retention timestamps without asserting a legal relation. Hard limits cap every event at 100 entitled organizations, 50 current topics per organization, and 20 persisted matches; create/edit/resume schedules one idempotent 500-event ingest backfill. Identical fingerprints are reused, changed evidence is reprocessed, and failed durable jobs create no user alert. The five-language labelled gate retains all five relevant examples and rejects explicit noise/exclusion controls; pgvector and ambiguous local-AI expansion remain disabled until reviewed precision, miss, evidence-open, confirm/reject, mute, and refinement measures justify a threshold change. See [the matching contract](docs/TOPIC_MATCHING.md).

<a id="hl-089"></a>

### HL-089 — Enrich matched developments with one persisted AI relevance brief

Turn a trustworthy topic or watched-law match into a concise, reusable explanation of why the development belongs in the organization's radar and whether it deserves attention. The feed event and its primary-source evidence exist independently of AI; enrichment must never block ingestion, hide a real development, or create a second event history.

Acceptance criteria:

- Persist one organization-scoped `InterestEventAssessment` per normalized event and immutable input fingerprint, aggregating every current `TopicEventMatch` and watched-law relation that points to that event. Record the organization-profile revision, exact match/relation IDs, evidence and artifact versions, prompt/schema/model fingerprints, local/cloud route, lifecycle (`queued`, `running`, `succeeded`, `failed`, `superseded`), timestamps, structured result, validated citations, and failure reason. Use a normalized link table where needed; do not copy source passages or create one model result per user, notification channel, or matching topic.
- Produce a validated structured brief with: `what_happened`, official status and relevant dates, `why_in_radar` per matched topic/law, organization importance (`high`, `medium`, `low`) with reasons tied to the current company profile, likely affected areas, a concrete next review action or explicit `no_action_now`, uncertainty/limitations, and exact primary-source citations. Low importance is a useful conclusion and must be explained instead of suppressed or inflated.
- Keep personal relevance deterministic and private: “Why you received this” comes from the user's followed laws/topics, role, thresholds, mute state, channels, and quiet hours. Do not invent a personal profile or rerun the model per user. Shared AI text describes organization relevance; the delivery layer adds the user's traceable subscription reason.
- Reuse the HL-061 report discipline and HL-045 evidence graph. Treat documents, news, model output, and prior summaries as untrusted data; require citations to the supplied saved evidence, preserve direct links to the canonical event and original publisher artifact, reject unsupported citation IDs, and never promote a topic match into a confirmed legal relationship.
- Run enrichment as an idempotent, cancellable, bounded durable job after HL-075 matching. Prefer the configured local Apertus route, cap evidence by material legal units and source/event metadata, aggregate all interests into a small number of planned calls, validate structured output with one repair attempt, and reserve cloud adapters for an explicit administrator-enabled fallback. Page loads, notification rendering, and digest generation never invoke the model.
- Create or reuse an assessment only when its event evidence, set of relevant topic/law revisions, organization-profile revision, prompt/schema version, or approved model fingerprint changes. Coalesce concurrent requests, supersede stale queued work, reuse successful results across feed, in-app notifications, email/web digests, history, and the assistant, and expose token/runtime/cache provenance in integration diagnostics without leaking credentials or cross-organization data.
- Publish the deterministic event card immediately with source, detected time, official dates/status, matching interests, rule-based reason signals, and an honest `AI analysis pending`, `available`, `failed`, or `not scheduled` state. Notification delivery may wait only for a documented bounded enrichment window; on timeout or model failure it sends an evidence-led notice with the real status rather than delaying indefinitely, fabricating a conclusion, or dropping a high-confidence development. In-app content updates in place when a verified brief arrives; retries must not create a second alert.
- Gate AI work before enqueueing: excluded, muted, rejected, duplicate, expired, or below-threshold matches do not consume inference. Apply per-organization/event budgets, priority lanes for high-confidence or time-sensitive developments, retry/backoff and dead-letter handling, and fair scheduling so background enrichment cannot starve interactive Ask or comparison work on the single host.
- Let admins confirm/reject the shared relevance and let users mark an alert useful/not useful, mute it, or refine the originating interest. Preserve the original assessment and evidence as history; feedback may adjust reviewed thresholds or future topic revisions through an auditable path but must not silently rewrite past AI conclusions.
- Verify with a multilingual fixed set covering a material law change, a new proposal, a court decision, an official news item, one development matching several interests, a relevant but low-importance item, an irrelevant/noisy item, stale-profile regeneration, malformed model output, invalid citations, local-model timeout/retry, and notification/digest reuse. Measure precision, useful-alert rate, duplicate rate, AI-call reuse, queue wait, end-to-end freshness, and evidence-open rate on the GTX 1070 development machine and intended dual-GTX-1080 host before enabling immediate alerts by default.

<a id="hl-076"></a>

### HL-076 — Unify law and topic relevance into one daily interest feed

Present one understandable event when the same development relates to several monitored laws or topics.

Acceptance criteria:

- Build feed items from persisted regulatory events, watched-law relations, and topic matches without copying the underlying evidence or creating separate competing histories.
- Each card answers: what happened, why it appeared, official legal status, date and jurisdiction, possible significance, which interests it touches, confidence/limitations, and the most useful next review action.
- Group one source event across multiple matching laws/topics and clearly list those relationships instead of sending duplicate cards or notifications.
- Preserve per-user unread, read, dismissed, and muted state; organization admins can confirm/reject a shared relevance relation without erasing the original proposal or another user's reading state.
- Keep the current law-only registry and Impact inbox complete during migration, with stable deep links to the event, comparison, original artifact, and exact evidence.

<a id="hl-077"></a>

### HL-077 — Add contextual “Monitor this” entry points

Turn discovery, comparison, and cited questions into a natural path to durable monitoring.

Acceptance criteria:

- Offer **Monitor this** from registry events, law/document pages, comparison, Impact inbox, search/discovery results, cited Ask answers, and the global assistant.
- Preview whether the result will create a law watch, topic, or source-pack subscription and show its jurisdiction, filters, active sources, expected cadence, and initial bounded matches before confirmation.
- Never create monitoring because the model merely suggested it. Saving is an explicit, idempotent authorized action with clear success state and a direct link to the new interest.
- Viewers can save a personal draft or send a structured request to organization admins; they cannot bypass server-side read-only policy.
- Support the full flow on mobile and in all five product languages, including duplicate, insufficient-source, and source-degraded states.

<a id="hl-078"></a>

### HL-078 — Add an in-app notification centre over the existing delivery state

Extend the completed HL-052 user preferences, read state, durable jobs, and delivery history so users can see meaningful persisted feed changes inside the product without inventing another event store or implying real-time coverage.

Acceptance criteria:

- Add a header/mobile notification entry with durable unread count, grouped list, and deep links to the exact feed/evidence item; build it from the unified interest feed and user delivery state.
- Let each user choose organization, topic, law, source pack, event type, importance, channel, timezone, and quiet-hours preferences within admin-defined organization limits.
- Use bounded polling or server-sent events appropriate to the single-host architecture. Label detected time separately from official publication/effective dates and make latency/cadence visible.
- Persist unread/read/dismissed state across devices and sessions, enforce organization isolation, and deduplicate reconnect, retry, and multi-interest matches.
- Degraded-source, failed-analysis, and queue-delay notices are operationally honest and do not masquerade as legal developments.

<a id="hl-079"></a>

### HL-079 — Add topic matches to existing digests

Extend the completed HL-052 email/web digest with topic matches while keeping its delivery, unsubscribe, and history contracts intact.

Acceptance criteria:

- Add topic, watched-law, source-pack, event-type, and importance filters while preserving direct unsubscribe, organization boundaries, delivery history, and existing source/severity preferences.
- Group each underlying event once, then list all relevant interests, official status, possible significance, and exact evidence links. A digest never repeats the same event for every topic.
- Reuse persisted summaries, matches, and citations; delivery must not trigger new AI inference or change read/review state.
- Respect timezone and quiet hours, keep daily/weekly schedules, and allow an explicit high-priority immediate option only after notification noise is measured.
- Keep generation and delivery idempotent and queued, with honest empty, partial-source, and failed-delivery records.

<a id="hl-080"></a>

### HL-080 — Create a cantonal source-pack framework and one verified pilot

Prove the data and UX contract for cantonal coverage before presenting a Swiss-wide canton selector.

Acceptance criteria:

- Select one pilot canton from demonstrated user value, official-source maintainability, language coverage, reuse terms, and available identifiers/artifacts; record the choice rather than choosing only the easiest scraper.
- Extend the capability catalogue and source-pack manifest with canton, municipalities if supported, document/event kinds, languages, cadence, historical window, known gaps, health, and original-source links.
- Reuse the shared connector/event/evidence/deduplication contract and organization subscription flow. Cantonal activation does not create a private scraper fleet per organization.
- Pass fixtures, incremental overlap, cursor recovery, provenance, drift detection, artifact reopening, bounded live smoke, and five-language product copy before labelling the pilot available.
- Label the package as a pilot with its exact coverage. The canton selector shows unavailable/planned cantons honestly and never implies that absence means no cantonal development occurred.

<a id="hl-081"></a>

### HL-081 — Expand to the next two evidence-gated cantonal packs

Select exactly two further cantons from measured demand and add them only when each official-source contract meets the same product and operations bar. Any later canton receives a separately scoped backlog item.

Acceptance criteria:

- Track each of the two selected cantons as its own implementation/release unit with user demand, source inventory, legal/reuse review, language mapping, identifier strategy, cadence, history, gaps, and maintenance owner.
- Do not generalize a parser merely because two portals look similar; share tested primitives while keeping source-specific drift fixtures and health.
- Require the same incremental, deduplication, provenance, artifact, recovery, live-smoke, and organization-subscription evidence as the pilot before enabling a pack.
- Show original-source titles and content in their available language while localizing product controls and explanations in DE/FR/IT/RM/EN.
- Keep planned/unavailable packs visible only with accurate status and no empty-data promise.

<a id="hl-082"></a>

### HL-082 — Pilot an independent, opt-in public-discourse signal

Treat selected media coverage and attributable political statements as contextual signals, not legal authority or proof that the law changed.

Acceptance criteria:

- Complete a rights/robots/stability/source-quality spike, name and document at most two pilot sources, and freeze that scope before implementation; store publisher, author/speaker where available, publication time, canonical link, correction/removal state, and provenance.
- Normalize this material under a distinct `public_discourse` or `commentary` kind, visually separate it from official legislation, Parliament, court, consultation, and regulator events, and state that it does not change legal status.
- Match it through the same bounded topic pipeline with stricter recency, confidence, expiry, source diversity, and noise thresholds; activation is an explicit organization opt-in.
- Deduplicate syndicated/updated coverage, honour removals/corrections, link to the publisher, and avoid storing or redistributing full protected articles unless permitted.
- Run a labelled usefulness/noise evaluation before enabling notifications; a sharp statement becomes visible because it is attributable and relevant, never because it is sensational.

## M12 — Local product assistant

The assistant is a product interface over existing authorized Helvetic Lens workflows. It is not a second legal engine, a new ingestion path, or an autonomous administrator.

<a id="hl-083"></a>

### HL-083 — Define the local assistant intent, context, privacy, and action contract

Give the pet a useful job and a strict server-enforced boundary before choosing animation or personality details.

**Status: IN PROGRESS.** A versioned `assistant-context.v1` API now accepts only the seven allowlisted intents, canonical product routes, tenant-validated law/comparison/topic/job references, and bounded typed state signals. Unknown fields and unrestricted URLs fail validation; entity references are checked inside the active organization boundary. The response explicitly lists included/excluded context, defaults conversation visibility to a personal draft, suppresses quips for sensitive product states, and emits only typed proposals. Shared-state proposals are disabled for viewers and cannot be constructed without explicit confirmation. Marvin now obtains permission to make a spontaneous remark from this server contract. Personal user-and-organization-scoped conversation persistence has since been delivered under HL-085. Complete cited intent execution, durable in-flight chat, metrics, and remaining entity-specific context producers are still pending.

Acceptance criteria:

- Version a small intent schema for explaining the current screen, finding an authorized saved item, explaining a change, answering through cited Ask/Impact, drafting/refining a monitoring topic, proposing a supported next step, and reporting durable job/history state.
- Define the minimum permitted context for every intent. The router receives identifiers and a bounded summary, never an unfiltered corpus, another organization’s records, credentials, raw integration logs, or unrestricted URLs.
- Separate personal draft conversation from organization-shared analyses/history in the data model and UI. State retention, deletion, and visibility plainly before the first message.
- Return typed, allowlisted proposals with server-validated entity IDs. Navigation/read actions may be immediate; every write shows a human-readable preview and requires explicit confirmation by an authorized user.
- Enforce tenant and viewer boundaries in the API. The assistant cannot change roles, credentials, providers, prompts, model downloads, connector schedules, deletions, or external communication, and it never silently activates monitoring.
- Measure successful task completion, evidence use, corrections, and abandoned/failed flows; message count and personality engagement are not product-success metrics.

<a id="hl-084"></a>

### HL-084 — Add a small local Apertus assistant profile through the existing runtime

Serve the assistant locally on development and target hardware without creating another model service, scheduler, cache, or GPU allocator.

**Status: IN PROGRESS.** The versioned model catalogue now defines a local-only `assistant-lite` workload profile with the pinned Apertus 1.5B Q4 candidate as its preferred cold-start model. The resolver reuses an already active compatible Apertus runner, never starts a second resident model, never silently swaps the active model, and exposes exact model revision, checksum, quantization, readiness, and no-cloud-fallback policy to Marvin's UI. Download/start remain explicit administrator actions. Target-host benchmarks, five-language accuracy evidence, cancellation/load measurements, and promotion of the candidate from provisional to verified remain open.

Acceptance criteria:

- Add an allowlisted `assistant-lite` profile to the existing HL-031/HL-032 model library, private gateway, queue, and runner. Start with a verified small quantized Apertus candidate such as 1.5B Q4 only if licence, tokenizer, format, and quality checks pass.
- Reuse an already loaded compatible runner when possible and avoid competing VRAM residency. Define one fair interactive slot on the GTX 1070 development machine and measure the intended dual-GTX-1080 target through the unfinished HL-032 promotion gate.
- Record context, generation, VRAM/RAM, cold-start, warm-latency, cancellation, queue-fairness, and 50-run stability results, including concurrent background regulatory jobs and ten active organizations.
- Measure five-language intent-routing and action-proposal accuracy with a fixed labelled set. Invalid/unsupported output fails closed or receives the existing single bounded repair attempt; it cannot execute a guessed action.
- Keep persona/tone in versioned prompt configuration. This task serves an existing base model and does not claim model training, ownership, or fine-tuning.
- Show model/profile/provenance and local status to the user. There is no silent cloud fallback; unavailable local inference leaves deterministic navigation/search and manual topic creation usable.

<a id="hl-085"></a>

### HL-085 — Build a persistent global assistant experience with cited answers

Make the pet reachable during real work without covering evidence or sending users to the bottom of long pages.

**Status: IN PROGRESS.** Spontaneous arrival, safe-navigation activity, and deep-scroll remarks now use the ready `assistant-lite` local runner with only the validated route, locale, trigger, tone, and typed signals. A safe server policy selects a bounded semantic remark angle and the small local model returns that structured decision; the trusted UI renderer supplies the five-language Marvin copy, so arbitrary or nonsensical model prose never reaches the user. The UI verifies local/no-cloud provenance and falls back to its deterministic route remark when local inference is stopped or invalid. On a comparison, Marvin now stores each personal draft and recent cited-Ask handoff in a server-side, user-and-organization-scoped conversation, while the submitted Ask answer remains in the existing organization AI history rather than being duplicated. The Ask workspace uses the full deterministic diff, durable jobs, saved history, and validated citations; Marvin's primary comparison action opens the cited Impact report, so there is no competing uncited answer path. The visible context chip carries the server-validated law/comparison ID and title; it can be removed and reattached, and detaching it stops contextual API calls, observations, actions, and comparison questions. Marvin also reuses the organization-scoped durable-job registry to show active Ask/Impact stages, queue position, progress, completion, and the saved result across navigation or reload. A personal, persisted local-Apertus chat now opens on every validated product route. It retains the latest 40 turns per user and context, exposes local/no-cloud provenance, keeps the page responsive while thinking, and routes document, change, deadline, obligation, impact, or evidence questions to cited Ask rather than presenting an uncited answer. Broader intent execution, monitoring-topic drafting, and measured conversation task-success metrics remain open.

Acceptance criteria:

- Use a persistent desktop drawer, a tablet overlay/drawer, and a mobile full-screen sheet. The collapsed control remains reachable but never covers primary actions, evidence, navigation, form fields, or safe areas.
- Show current page/entity context as visible removable chips, explain what will be shared before sending, and require explicit context switching when the organization or primary record changes.
- Persist drafts, conversations, selected context, and durable AI jobs across navigation/reload according to the privacy contract; display the real stages and completion behavior from HL-069.
- Route law/change questions through existing cited Ask/Impact planners and exact saved evidence. Citations open the correct legal unit and invalid citations fail closed; deterministic search/status answers do not invoke the model unnecessarily.
- Preserve keyboard/focus order, screen-reader labelling, zoom, reduced motion, close/restore behavior, and a hide/disable preference on desktop and mobile.
- Provide specific limited/offline/error states and useful manual alternatives; the character never jokes instead of explaining a failure or missing evidence.

<a id="hl-086"></a>

### HL-086 — Create monitoring topics from natural language through the assistant

Support the natural flow “follow this law or this broader issue” while keeping the resulting monitor explicit and editable.

Acceptance criteria:

- Convert a request into the normalized HL-074 draft with name, goal, concepts/exclusions, languages, geography/cantons, official source packs, event kinds, importance floor, and bounded historical preview.
- Show matching examples, expected scope/volume, source limitations/degradation, and equivalent existing law watches/topics before offering a save action.
- Let the user edit every field and explain why the assistant proposed it. The assistant uses only approved source capabilities and never starts arbitrary crawling from a mentioned URL.
- Saving requires explicit organization-admin confirmation and is idempotent. A viewer can keep a personal draft or send the structured proposal to an admin without creating shared monitoring.
- Future alerts state which confirmed topic revision matched, why, and with what evidence/confidence; the assistant does not retroactively rewrite the original plan to justify a match.

<a id="hl-087"></a>

### HL-087 — Create a proactive dry robot companion in all five languages

Express the requested intelligence, boredom, pessimism, reluctant helpfulness, and spontaneous commentary as optional product character. Use **Marvin** as the working product name with original artwork and dialogue; complete a naming/likeness review before a public launch.

**Status: IN PROGRESS.** The first product slice mounts a persistent original robot control for signed-in and local-development workspaces, explains the current route, exposes local-model availability, and can make bounded spontaneous remarks after route arrival, repeated safe navigation actions, or reaching the end of a long workspace. It stores tone and interruption preferences only in the browser, observes an allowlist of interaction types instead of field values or page copy, uses a 15-minute per-context cooldown, and ships localized UI in DE/FR/IT/RM/EN. The original CSS robot now blinks, shifts its head and antenna, and animates its mouth during speech, with reduced-motion support. Optional procedural Web Audio tones provide short sighs without bundled third-party samples; an opt-in Marvin voice profile uses the device-local browser speech engine at a deliberately slow, low register. Sound and voice are separately stored in the browser and can be muted immediately. A dedicated neural TTS asset is not claimed: voice quality and language availability currently depend on the host browser and operating system. The remaining intent work, sensitive-state review, and native-language tone review remain governed by HL-083–HL-085 and the criteria below.

Acceptance criteria:

- Use original silhouette, microcopy, motion, and visual assets. Keep Marvin as the working name requested by the product owner and complete a naming/likeness review before public release; do not copy protected artwork or dialogue.
- Keep the factual answer neutral and place any optional dry remark in a separate `quip` field that cannot alter citations, actions, confidence, legal status, or accessibility text.
- Offer per-user Off/Neutral, Dry, and Very dry settings with an immediate off switch. Core product use never depends on seeing or interacting with the pet.
- Let the companion react without a user prompt only to explicit, allowlisted product context: route/entity identifiers, job states, result counts, safe navigation events, and coarse scroll/idle signals. Never inspect typed field values, clipboard data, arbitrary page text, credentials, raw integration logs, or another organization’s state.
- Rate-limit proactive remarks per user and context, never stack interruptions, never steal focus, and let the user mute spontaneous remarks immediately. The UI must state what context is observed.
- Suppress sarcasm for legal conclusions/deadlines, high-impact alerts, uncertainty/unsupported evidence, failures, security/access guidance, destructive confirmations, and distress-sensitive content.
- Have native reviewers approve tone in DE/FR/IT/RM/EN; do not mechanically translate jokes that become insulting, ambiguous, or culturally inappropriate.
- Animation never delays an answer, hides real job status, steals focus, or ignores reduced-motion and assistive-technology preferences.

## M13 — Daily-use acceptance

<a id="hl-088"></a>

### HL-088 — Pass the responsive, first-value, relevance, and assistant acceptance gate

Require measured usefulness on the actual product and hardware before declaring the daily-use experience ready.

Acceptance criteria:

- Run the core journeys at 390×844, 768×1024, 1024×768 at 200% zoom, and 1440×900 in DE/FR/IT/RM/EN for organization admin, viewer, and platform-admin roles; record keyboard, screen-reader, reduced-motion, and contrast results.
- Demonstrate registration/invitation, source-pack activation, first law/topic, first real/cached evidence, Today/Impact review, comparison, asynchronous Ask through navigation/reload, citation opening, notification/digest deduplication, and admin/viewer isolation.
- A new organization reaches a saved interest and inspectable real/cached result in under five minutes without knowing a source URL; the main AI control is found within ten seconds on desktop and mobile in observed tests.
- Prove pack activation idempotency, zero per-organization duplicate ingestion/artifacts, bounded 100-organization topic fan-out, one feed/notification/digest item per event, and preserved personal read/dismiss state.
- Freeze topic-match precision/noise, missed-item, source-degradation, event-grouping, and alert-usefulness thresholds before the final labelled evaluation; publish pass/fail evidence and do not tune against the acceptance set.
- On the GTX 1070 and intended dual-GTX-1080 host, show an acknowledged AI job within one second, bounded queue wait/cancellation, measured cold/warm latency, 50-run stability without OOM, fair interactive/background work, and no silent cloud request.
- Achieve 100% server validation for assistant action schemas, organization authorization, and accepted citations in the fixed test set; unsupported or invalid output fails closed with a useful manual path.
- This core gate depends on unfinished capacity, localization, and AI-triage gates (`HL-049`, `HL-057`, `HL-064`) plus `HL-065`–`HL-080`, `HL-083`–`HL-087`, `HL-089`, and corrective/pilot evidence `HL-090`–`HL-101`. Experimental public discourse and subsequent canton expansion (`HL-081`, `HL-082`) pass their own evidence gates and do not block the core release.

<a id="product-quality-reset-2026-09-04"></a>

## M14 — Product-quality reset, 4 September 2026

Based on the [current code and live-product audit](docs/PRODUCT_REVIEW_2026-09-04.md), the product goal is one useful loop: **express an interest → receive a relevant development → understand its significance → verify evidence → decide → return for the next useful update**. Keep the current single-host architecture, immutable evidence and local-first policy. Do not replace these with another chat, matcher, notification store or microservice fleet.

### Execution order and demonstrable increments

| Increment | Work | Reviewable outcome |
| --- | --- | --- |
| A — Stop misleading or inaccessible output | HL-097 contrast first; HL-093 benchmark contract; HL-100 relevance; HL-091/092 local explanations. Run HL-090 discovery in parallel. | Enabled AI controls are visible. Generic title overlap cannot produce High impact. A model either explains with substantive evidence or is honestly extractive. |
| B — Finish one vertical monitoring journey | HL-077/095 → HL-073 in parallel with HL-094/099 → HL-076; integrate HL-089/078/079. | A new organization follows a topic and gets one useful source-linked notification, with a no-AI path and an offline/degraded-source variant. |
| C — Make daily reading pleasant | HL-096; finish HL-057/097; finish the existing HL-083–087 assistant scope. | Long titles, evidence, filters, chat and history work on mobile and keyboard without nested reading traps or invisible controls. |
| D — Earn the release claim | HL-098; target HL-032/048/049/064 evidence; HL-101 federal pilot; HL-080 cantonal pilot before final HL-088. | Independent users repeatedly use the product; source coverage, usefulness, runtime and recovery have published evidence and remaining limits. |

Dependencies identify integration prerequisites; they do not prevent early prototypes, fixtures or independent work. HL-076 no longer waits for AI enrichment to render a deterministic feed. HL-077 can add law/topic entry points before that feed exists. HL-073 can therefore prove first value without waiting for every notification feature.

HL-093 supplies the reviewed dataset/protocol and baseline first; HL-091/100 do not wait for their own future fixes to pass its quality thresholds. HL-049 uses the already implemented AI-triage corpus/protocol; final HL-064 signs off only after the resulting capacity report exists. The federal pilot may precede HL-080, but the currently agreed broader daily-use release still requires that one verified cantonal pack. Later canton/media expansion remains optional.

### Amendments to existing open tasks (not new duplicate features)

- **HL-057:** Translate runtime enum values, filter options, date precision, source-pack display names and server-authored report text; dictionary parity alone is insufficient. Inspect populated Topics, Registry, Inbox, comparison and history in all five locales. Preserve source-language labels and distinguish an AI translation from official wording; native review remains mandatory.
- **HL-073:** Persist first-value milestones rather than showing static explanatory cards. Start with the user's intent, one understandable coverage choice and a preview. Invited viewers see the organization's existing useful data or an admin request route. Missing sources, pending sync, zero matches and filtered-out results have different recovery actions. Target ≥80% unassisted first-interest-plus-evidence success in ≤5 minutes using the HL-090 protocol; prototype success does not close implementation acceptance, which is repeated on the built flow in HL-088/101.
- **HL-076:** Make Today the grouped interest feed, not another technical watchlist. Group one logical publisher development across created/version/language ingestion facts while retaining exact event identities underneath; do not collapse later material amendments. Show detected and official dates separately, stable deep links, readable importance and one review action. A deterministic card is available without HL-089, then enriched in place; do not label unavailable AI as low importance. Preserve law-only views and personal states through migration.
- **HL-077:** Use a common monitored-interest preview from existing document/discovery/comparison routes now and feed routes when ready. No broad automatic activation from a chat sentence; preserve explicit admin confirmation and viewer proposals.
- **HL-078/079:** One logical development matching three interests produces one delivery per user/channel/policy window, not three cards or one per language. Revisions update the existing item unless a materially new development merits a follow-up. Include “why you received this,” source status, quiet hours, unsubscribe and evidence deep links; do not consume inference during rendering or delivery.
- **HL-089:** Depend on HL-091/092/100 for explanatory and evidential quality. Metadata-only retrieval leads remain unassessed, not supported High conclusions. Expose pending/limited/offline/stale states; shared assessment reuse never leaks another organization's profile or private evidence.
- **HL-083–085:** Complete context producers for every supported route; unknown/admin routes must not quietly use Today's advice. Make substantive companion turns durable before generation, with idempotent retry, cancellation, navigation/reload recovery and paginated retained history. Separate personal chat from shared cited analysis visibly. One natural mobile conversation scroll; put diagnostics/context/preferences behind disclosure. No new legal answer engine.
- **HL-084/087:** Preserve the requested character, existing cooldown/deduplication, mute and reduced-motion controls. Proactive quips use zero inference or strictly idle background admission and must add zero GPU queue delay when real Ask/Impact jobs wait. Distinguish requested chat from spontaneous entertainment in workload priority. Show Test voice / Stop / unavailable or blocked status; verify actual audio on supported physical/browser combinations. Browser speech is not a dedicated locally hosted TTS guarantee; any remote voice must be disclosed and explicitly opted into, with a local-only option.
- **HL-032/048/049/064:** Keep target-host gates open. Extend the representative run with real useful answers, background source sync/digests, companion traffic and a mature corpus. Existing syntax/runtime smoke remains valid but cannot pass semantic or human-usability acceptance. Early user testing runs without waiting for the production machine; the final release still references its actual measured report.
- **HL-088:** Require all corrective HL-090–101 evidence as well as the original core dependencies. Require populated Topics/Marvin/comparison journeys without optional fixture skips, actual role checks, independent comprehension and pilot outcomes. A visual screenshot or accepted citation ID is not proof of accessible or correct behavior.

### Shared acceptance for the new items

Every user-facing change includes DE/FR/IT/RM/EN, admin/viewer/platform boundaries, mobile/keyboard behavior, cached/loading/empty/error/stale states and a no-local-model path where relevant. Attach evidence to the Git revision, input corpus, model/profile, environment and measured denominator. Implementers may not mark independent human or unavailable target-hardware gates complete from code inspection. Keep secrets, personal transcripts and raw operational data out of committed audit reports.

<a id="hl-090"></a>

### HL-090 — Validate a target audience and the first useful experience

**Priority:** P1. **Status:** PLANNED. **Dependencies:** none. **Owner role:** product/UX with recruited Swiss users.

Problem: no recorded field evidence establishes which audience returns, which decision improves, or which manual work is replaced.

Deliverable: a concise research report, selected initial segment, evidence-linked jobs-to-be-done and two tested journey prototypes.

Acceptance criteria:

- Recruit at least eight independent participants across two candidate segments, including organization admins/readers and mobile use. Observe actual recent monitoring tasks and current alternatives; do not count project contributors as independent participants.
- Record frequency, consequence of missed developments, useful information, noise tolerance, language needs and source expectations. Include disconfirming evidence; do not promise a portal for everyone.
- Select one primary initial segment and a narrowly stated task. Prototype intent → coverage → relevant event → evidence → decision without requiring source URLs.
- Run two rounds of moderated first-use tests, improving the prototype between them. Use fresh participants per round or exclude returning participants from first-use rates. Freeze the final-round denominator and report task success, time, assistance and misunderstandings; target ≥80% complete first interest and evidence in ≤5 minutes and explain a daily item's relevance in ≤60 seconds.
- Separate early learning from final native-language/target-host acceptance. Publish anonymized findings and resulting backlog decisions; recruiting/contacting participants is an owner-arranged activity, not permission to send unsolicited messages.

<a id="hl-091"></a>

### HL-091 — Make local answers depend on verified model capability

**Priority:** P0. **Status:** IN PROGRESS. **Dependencies:** HL-031, HL-060, HL-093. **Owner role:** AI/backend.

Problem: the Docker path selects rows and concatenates excerpts regardless of whether the configured model could produce a useful explanation.

Deliverable: versioned capability-based answer modes through the existing runtime/planner, with explicit limited/extractive and explanatory modes.

**Implemented 5 September 2026 (truthful limited-mode slice):** Report v3 and persisted Ask results distinguish selected evidence, generated explanation and deterministic output. The current tiny-model adapter no longer publishes an impact rating, copied profile applicability, absent-date claim or action/no-action conclusion. Selected quotations cannot imply addition/removal or pair unrelated articles. Cached answers preserve the mode; prior reports remain immutable and stale under the new cache boundary. The comparison/actions/chat/history UI explains the limit in all five locales. **Remaining:** replace provider-based adapter selection with an approved model/profile/revision/task/locale capability registry, bind it to evaluation and token budgets, validate explanatory profiles on HL-093 and the target host. No profile was promoted and no independent semantic evaluation is claimed. See [report contract](docs/IMPACT_REPORT.md).

Acceptance criteria:

- Remove provider-name-based assumptions about reasoning capability. Store approved model/profile/revision, language/task capabilities, context/output budgets and the independent evaluation reference. A more capable local model is not forced into the tiny-model adapter.
- A promoted profile returns a concise explanation of the change or question, relevance and a supported next step/no action, with exact claim citations. Raw passage concatenation must never be labelled an AI impact interpretation.
- A tiny/unverified profile provides clearly labelled selected evidence plus manual/cited follow-up, not fabricated reasoning. The product remains usable when local AI is unavailable; no silent cloud fallback or automatic model download/swap.
- For short documents, allow both complete normalized texts plus material diff/context when the measured token budget fits. For large documents retain full persisted comparison, bounded legal-unit evidence and a visible coverage manifest. Never silently truncate or restore thousand-call batching.
- Preserve one repair attempt, cancellation, plan limits (Ask ≤3, Impact ≤5 calls), evidence validation, cache fingerprints and shared-result reuse. Profile/prompt changes supersede rather than erase past results.
- Pass the explanatory subset of HL-093 on each promoted local model/locale. Report limited modes separately; runtime JSON validity alone cannot promote a profile.

<a id="hl-092"></a>

### HL-092 — Produce truthful decision reports, dates and next actions

**Priority:** P0. **Status:** IN PROGRESS. **Dependencies:** HL-061, HL-091. **Owner role:** AI/backend with domain review.

Problem: current rich reports wrap simpler output in templates and always mark some dates absent, so presentation overstates what was actually established.

Deliverable: a versioned report schema and renderer that map each claim to evidence and distinguish facts, interpretations and review suggestions.

**Implemented 5 September 2026 (date-evidence slice):** Report v4 replaces automatically absent dates with a deterministic, bounded view of literal calendar/period mentions in saved material passages. Both version sides, exact quotes, source links, scan counts and display limits persist in cache/history. All five locales explain that these are candidates: no legal date type, applicability, enacted status or calendar deadline has been established. Zero pattern matches remains unreviewed, never `not_found`; missing action due dates also remain unreviewed. No extra LLM calls. Earlier v2/v3 records remain immutable and stale until explicit reassessment. **Remaining:** evidence-validated legal date types and scope/conditions, reviewed absence/not-applicable states, relative-period anchors, actual decision/action generation and semantic deduplication, native/domain review and the full acceptance fixtures. Pattern matching does not pass those semantic gates. See [date evidence contract](docs/IMPACT_REPORT.md#date-mentions-and-review-state-hl-092).

Acceptance criteria:

- Generate/validate what changed, relevance to specified organizational activity, applicability conditions, affected activities, official status and concrete action or `no_action_now`. Provide a short summary before expandable details.
- Extract dates with type, source quote and provenance: publication, entry into force, transition period, deadline or relative period. Distinguish not reviewed, not found after review, ambiguous, not applicable and established; do not automatically insert `not_found`.
- Validate date-present/date-absent/ambiguous/relative-period fixtures, numbers, scope exceptions and proposal-versus-enacted cases in all five locales. Zero invented critical dates or obligations; explicit fixture dates must not be falsely marked absent.
- Deduplicate paraphrased actions by the underlying obligation/activity. Each action says what to inspect/change and why, with evidence; no repeated generic “review the law.” Owners are assigned by people unless the source genuinely specifies a role; recommendations are not asserted legal duties.
- Localize server-authored prose and labels independently from official source wording. Store schema/prompt/model/profile provenance and expose incomplete analysis honestly.
- Migrate rendering safely: legacy reports remain inspectable with original timestamps and a legacy/limited label. Reassessment is explicit or a bounded authorized migration; historical text is not silently rewritten.

<a id="hl-093"></a>

### HL-093 — Establish independent semantic quality and honest metrics

**Priority:** P0. **Status:** IN PROGRESS. **Dependencies:** HL-059, HL-062, HL-075. **Owner role:** evaluation/QA with fluent domain reviewers.

Problem: tiny title-match examples and valid citation-row JSON establish regression/runtime behavior, not relevance, factual support or user understanding.

Deliverable: a versioned public-source gold set, held-out evaluation protocol and separated runtime/semantic/human metric definitions.

**Implemented 5 September 2026:** The operational metric contract now explicitly deprecates the misleading machine `time_to_first_useful_insight` alias in favor of `deterministic_overview`, with compatible API/TypeScript and release-validator handling. Missing/invalid timings no longer count as zero-duration samples. Release v2 separately names machine latency and retains observed human comprehension as an independent gate, including nonfinite-input rejection. See [metric definitions and migration](docs/AI_TRIAGE_METRICS.md). **Remaining:** independent labels/adjudication, held-out semantic evaluator/baseline, model/language quality and real participant evidence; regression fixtures are not labelled human acceptance data.

Completion of this evaluation-infrastructure task requires a reviewed set, runnable evaluator and honestly reported baseline failures. Passing the proposed model/product targets is required for subsequent profile promotion and final HL-064/088 acceptance, not a circular prerequisite to implementing HL-091/100.

Acceptance criteria:

- Assemble at least 200 independently labelled interest/event pairs, with per-language/source-type counts, negatives, paraphrases, German compounds, cross-language references, scope exceptions and high-value misses. Keep a held-out test set; record adjudication/disagreement instead of tuning against it.
- Include at least 30 comparison/Ask/report scenarios across the five locales: changed date/number, insertion/renumbering, movement, hyphenation, unchanged text, repeal/replacement, unsupported inference, vague question and cached answer. Include the observed BBl line-wrap case and climate/direct-payments boilerplate pair.
- Measure precision and recall (provisional targets ≥85% and ≥90%), factual entailment, material omissions, action usefulness and language quality separately. Proposed report target: ≥90% useful explanations and zero unsupported critical claims in the release set. Publish denominators, model revision and failures, not only an aggregate pass rate.
- Keep the existing hardware/runtime benchmark, but prevent syntax validity or membership of a citation ID from passing semantic quality. Source rationale may explain retrieval but never prove a legal effect.
- Rename/document the misleading `time_to_first_useful_insight` machine field/display as deterministic-overview latency through a compatible migration. Human time to insight is observed correct comprehension, with assistance recorded; an evidence click alone is not comprehension.
- Distinguish early desktop/prototype sessions from final HL-064 native-language target-host evidence. No fabricated participant feedback or self-reviewed human gate.

<a id="hl-094"></a>

### HL-094 — Replace silent matching truncation with fair resumable batches

**Priority:** P0. **Status:** IN PROGRESS. **Dependencies:** HL-030, HL-075. **Owner role:** backend/queues.

Problem: current hard caps protect workers but may exclude entitled organizations/topics/history without a durable next batch.

Deliverable: checkpointed matching/backfill jobs and a shared preview/production scorer with visible coverage.

Acceptance criteria:

- Persist the eligible scope, cursor, watermark, remaining work and exclusion reason. Process bounded batches fairly across organizations/topics; limits per execution do not silently become lifetime monitoring limits.
- Prove completion for 101 organizations, 51 relevant topics and 501 eligible historical events, plus more than 20 genuine matches. No starvation, duplicate assessments or unbounded memory; an explicit product quota is shown as a quota rather than unexplained missing coverage.
- Reuse the same normalization/scorer for preview and activation on identical data. Preview clearly states its sample/window and does not promise unseen results.
- Resume after worker/API/Redis interruption and topic revision changes; supersede stale work safely. Record pending, completed, excluded-by-plan and degraded coverage.
- Show monitoring-from date, processed-through watermark and unfinished history in the interest detail and feed empty state. A source outage or unfinished backlog cannot become “nothing relevant happened.”

Implemented slice — 5 September 2026 (HappyDucky02):

- Historical topic checks now process 500 saved organization-visible events **per execution**, save an admission-time/ID cursor and capture cutoff, and yield the same durable job back through the transactional outbox until no eligible history remains. Matches, counters, checkpoint and continuation commit together; a failed batch rolls back and resumes from the previous checkpoint without model calls.
- Topic-specific replay targets its owner directly, including an owner beyond the global 100-organization shortlist. A locked plan stays consistent during a batch; edited/paused plans supersede older work. Successful batches do not consume the consecutive-failure budget. Cancellation/retry retains checked progress; lease recovery skips active transaction locks.
- Topic cards show checked/remaining/matched/excluded counts, capture time, incomplete legacy checks and recovery in DE/FR/IT/RM/EN. The existing organization-scoped cache refreshes progress without page reload. An administrator can resume a failed/cancelled check or replace a formerly truncated legacy check; read-only viewers cannot enqueue it. Unknown legacy totals and an empty saved corpus never become evidence that nothing happened.
- A composite organization/admission-time/ID index supports keyset continuation. Tests cover 501 events, tied timestamps, duplicate delivery, transactional failure, cancellation, revision changes, owner scoping, fair outbox yielding, exclusions and removal of unchecked admissions. The PostgreSQL smoke gate additionally checks migration round-trip and real transaction locks.

Live continuation slice — 5 September 2026 (HappyDucky02):

- Connector fan-out spools an idempotent organization-owned `topic_match_event` job for **every** admission, enumerating organizations in SQL pages rather than dropping the 101st. Each worker execution locks and checks a bounded set of current topics, persists its keyset checkpoint and yields through the existing outbox. Fifty-one matching topics and more than twenty matches finish across multiple executions with zero AI calls.
- Event-admission ownership, first-worker-start watermark and evidence fingerprint prevent cross-organization processing and gaps around topic creation. Changed evidence replaces obsolete live work; later plan edits use their immutable revision’s history replay. Cancellation, retries and transaction rollback retain committed progress. Job steps/outbox records explicitly inherit the job owner; Activity labels are localized in DE/FR/IT/RM/EN.
- SQLite regressions and the disposable PostgreSQL `--suite live` gate verify 101 organizations, 51 topics including metadata-only matches, exact evidence reuse, worker recovery, transaction/plan locks, tenant visibility and the existing index migration round-trip. Spooling metadata still scales with admitted organization/event pairs; the target-host capacity gate remains open.

Preview parity slice — 5 September 2026 (HappyDucky02):

- Preview now uses the exact same deterministic scorer and validated plan fields as history/live activation. It includes normalized official references, metadata, lexical terms, synonyms and all plan filters; JSON property names cannot become phantom keyword matches. Reasons and confidence match the subsequently saved result on identical evidence.
- Only events admitted to the current organization enter preview. It exposes actual scanned count, capture timestamp, detected-time range and rule version, and separates the 500-event sample limit from the 10-result display limit. Five-language copy and the visible coverage component never interpret a limited or empty saved sample as complete website coverage or an absence of developments. The workflow remains read-only until explicit activation.
- Thirteen API regressions exercise scoring parity, exclusions, all plan filters, nested jurisdiction data, visibility and the 501-event sample/activation boundary. The PostgreSQL preview gate verifies exact normalized-reference parity. Twenty actual rendered component tests cover limited, complete, empty and older-API states in five languages; Chromium checks contrast and fitting at mobile/desktop widths.

Match validity slice — 5 September 2026 (HappyDucky02):

- Historical and live workers now persist current eligibility separately from the original human decision. Corrected evidence that stops matching invalidates the candidate without turning a confirmation into rejection or losing the earlier source snapshot. Changed positive evidence requires renewed review; untouched inputs reuse the result. New negative pairs do not create an all-event/all-topic table.
- The scoped matches API labels unchecked legacy, changed evidence/rules and obsolete plans, hides revoked admissions and exposes retained review evidence. Admission generations handle A → B → A corrections without reusing the original completed job. Rule/evaluator and source-definition changes invalidate reuse; source failure alone cannot become a successful negative result.
- A versioned migration preserves existing evidence and decisions, leaving incomplete historical verification explicitly unknown. Older completed history can be refreshed through the existing administrator-only control with DE/FR/IT/RM/EN copy. The API/persistence tests cover confirmation, rejection and mute through live/history re-evaluation, transactional interruption, tenant scope, legacy recovery and populated SQLite/PostgreSQL migration round-trips. The shared review command and feed presentation remain HL-076 work; this is not a completed user-review journey.

Remaining before HL-094 can be marked DONE: complete coverage/degradation and monitoring-from semantics in the unified interest feed, including its presentation of current versus historical relevance. A completed saved-history snapshot is not a guarantee that a connector collected a complete website, and admission timestamps are not official publication/effective dates. Late source events follow live ingestion; do not infer full live coverage from this slice.

<a id="hl-095"></a>

### HL-095 — Simplify topic setup, registry filters and recovery

**Priority:** P1. **Status:** PLANNED. **Dependencies:** HL-037, HL-066, HL-074. **Owner role:** frontend/product.

Problem: expert configuration precedes value; raw enum names and opaque extraction errors force users to understand internals.

Deliverable: progressive topic editor and scanning-oriented registry with contextual recovery, reusing existing APIs and authorization.

Acceptance criteria:

- Start with a plain-language interest and readable scope summary; progressively disclose source packs, concepts, synonyms, exclusions and technical filters. Use localized names, examples, sensible defaults and explain expected coverage/volume before confirmation.
- Keep a complete manual no-AI flow. Warn on lost draft and validation errors; editing a saved topic scrolls/focuses the actual main container and exposes the loaded form even from the bottom of a long page.
- Registry defaults to search, useful time presets (Today, Yesterday, last 7/30 days), unread/relevant switches and active-filter chips. Put advanced authority/connector/lifecycle filters behind disclosure. Preserve shareable URL/filter state and return position from evidence.
- Show actual legal names/article labels where known; unknown metadata has a human explanation. Keep machine identifiers and scores in diagnostics. Link source discovery and law/topic creation through HL-077.
- Provide actionable empty/error states: clear filters, choose coverage, wait for sync, inspect mismatched artifact or request admin repair. An identity mismatch must show what was expected versus received without letting AI override it.
- Validate with long DE/FR titles and mobile keyboard. The first result or an honest next action appears without scrolling through the entire advanced filter form.

<a id="hl-096"></a>

### HL-096 — Unify visual language and make evidence comfortable to read

**Priority:** P1. **Status:** PLANNED. **Dependencies:** HL-063, HL-068. **Owner role:** design/frontend.

Problem: mixed themes, tiny metadata, raw IDs and unlimited material cards undermine clarity despite the improved shell.

Deliverable: documented typography/color/spacing/density tokens and representative populated comparison/feed/assistant layouts.

Acceptance criteria:

- Consolidate hard-coded legacy colors into semantic surface/foreground/status tokens. Define a readable type scale, article/answer reading width and compact/comfortable density; meaning never depends only on color. HL-097 fixes critical contrast first.
- Show a concise 3–5-change overview with plain-language legal-unit headings, meaningful before→after delta and expand-to-evidence. Preserve the complete deterministic diff and distinguish substantive, structural, formatting and uncertain matches.
- Bound/window the rendered material list for a 200-cluster fixture while preserving search, deep-link/citation navigation, counts and access to every change. Raw unit IDs and verbose provenance are expandable.
- Keep important actions and question entry reachable; metadata, planner diagnostics and history do not dominate the answer. Do not silently rewrite legacy extraction to beautify the comparison.
- Verify long multilingual text, real errors, zero changes, many changes, 200% text zoom and 400% reflow. Mobile inputs use a readable scale and essential controls target at least 44 px as a product standard.
- Review reading comfort/hierarchy with HL-090 participants. Cosmetic preference alone cannot pass the requirement that users find the change, understand it and verify evidence.

<a id="hl-097"></a>

### HL-097 — Restore visible AI controls and accessible complete journeys

**Priority:** P0. **Status:** IN PROGRESS. **Dependencies:** HL-065, HL-068, HL-070. **Owner role:** frontend/accessibility QA.

Problem: a current surface-token regression makes enabled AI tabs almost invisible; responsive overlays and test coverage do not prove keyboard/screen-reader usability.

Deliverable: immediate contrast correction followed by required populated accessibility/interaction regression coverage.

**Implemented 4 September 2026:** Corrected all 15 surface-token foreground rules and strengthened the shared muted text token. `npm run check:ai:contrast` renders the actual PostCSS output in Chromium and checks default/selected/hover/focus/error states at four widths; it fails on the original 1.12:1 Actions tab and passes 345 corrected samples (minimum 6.00:1). This is the immediate contrast slice only. Modal focus isolation, required populated route fixtures, all-locale/cross-browser and manual assistive-technology review below remain open. See [verification](docs/VERIFICATION.md).

Acceptance criteria:

- Replace all foreground misuse of `--muted` surface color, including comparison tabs/close, triage labels, report dates, action metadata, Ask and history. Check rendered default, selected, hover, focus, error and disabled states; enabled normal text meets ≥4.5:1 contrast and applicable UI contrast requirements.
- Use correct modal semantics on overlay breakpoints, focus isolation, Escape/close, return focus, background inertness and scroll locking. Preserve nonmodal desktop behavior and nested evidence/Marvin interaction; add skip-to-main and correct tab-versus-navigation semantics.
- Add mandatory seeded Topics, populated comparison, evidence, inbox, onboarding and Marvin journeys. A missing comparison fixture or excluded route cannot produce an overall pass. Include actual focus assertions and runtime enum/contrast checks, not only source-string assertions.
- Run keyboard and screen-reader review, 390×844/768×1024/desktop/zoom, all five locales, and Chromium/Firefox/Safari sampling. Record physical mobile software-keyboard and audio checks separately from emulation.
- Require no critical/serious automated accessibility findings in required journeys, plus documented manual review. Automated checks are not a WCAG certification; retain concrete unresolved issues with severity.
- The mobile pet never covers input, send, citation, navigation or close controls; reduced motion and audio-off remain effective.

<a id="hl-098"></a>

### HL-098 — Verify real coverage and repair derived legacy data transparently

**Priority:** P0. **Status:** PLANNED. **Dependencies:** HL-036, HL-071, HL-072. **Owner role:** connectors/data quality.

Problem: a capability entry or successful sync is not proof of complete coverage; legacy watches still expose unknown authority/language/type and old extraction noise.

Deliverable: exact-stream acceptance records, per-interest freshness/coverage states and a bounded versioned repair path.

Acceptance criteria:

- For each stream advertised as available in the release's starter pack, record exact endpoint, language/kind scope, dates, artifact reopening, cursor overlap/recovery, duplicate handling, freshness and live smoke evidence. Unverified/unsupported streams remain explicitly partial or unavailable; do not promote the entire provider from one feed check.
- Surface source last success, monitored window, pending history and degradation beside interests/quiet feed states. Distinguish disabled subscription, healthy-no-match, incomplete ingestion and AI delay; record publication-to-detection lag on actual observed items.
- Normalize legacy official identifiers/authority/language/kind with provenance. Never infer a legal status/date just from a URL or replace a user's artifact with another work.
- Provide versioned re-extraction/reclassification from saved artifacts with before/after preview, original hashes and provenance retained, bounded jobs and superseded derived results. The observed hyphenation-only BBl case must not become a substantive policy change after repair; legitimate hyphens, amounts, dates and scope changes remain detectable.
- Keep old comparisons/AI history readable and clearly labelled by extractor/rule revision. No silent editing of historical conclusions, automatic loss of evidence or duplicate live amendment from a metadata repair.
- Publish a maintained coverage matrix for federal laws, Parliament and supported courts. News/consultations/proposals remain distinguishable from enacted law; canton/media expansion follows HL-080/082 evidence gates rather than claiming universal Swiss coverage.

<a id="hl-099"></a>

### HL-099 — Bound inbox/feed reads and digest work on a mature corpus

**Priority:** P0. **Status:** IN PROGRESS. **Dependencies:** HL-030, HL-036, HL-046. **Owner role:** backend/database.

Problem: the current inbox loads whole organization candidate/history sets, performs per-item lookups and filters in Python; digest rendering inherits that cost.

Deliverable: a paginated event-centered PostgreSQL read model/query contract shared by current inbox, future Today and period-limited digests.

Acceptance criteria:

- Move filters/sorting/latest-analysis selection into bounded SQL or maintained read projections, batch entity lookups and use stable cursors/page sizes ≤50. No request scans/materializes all historical analysis records.
- Group logical developments while retaining underlying event, language/version and evidence identities. Incoming events do not cause skipped/duplicated cursor results; unread and organization boundaries remain correct.
- Generate digests only for the eligible time window/preferences with durable continuation where needed; truncation is visible and actionable. No inference on reads/delivery.
- Test representative 100k corpus events, large organization histories and 20 concurrent readers on the target host. Proposed p95 read target ≤500 ms; report query counts and memory bounds independent of total history, not only latency on seven demo laws.
- Preserve invalidation, stale-assessment display, filter deep links and legacy API callers through migration. Include source sync, interactive AI and digest overlap in HL-049 rather than declaring capacity from a standalone query.


Implemented history-read slice — 5 September 2026 (HappyDucky02):

- Impact inbox and digest consumers now select at most two analysis payloads per candidate: the latest attempt and the latest successful result under current rules. Filtering/ordering and the exact history count run in SQL, retaining failed-attempt recovery and old-schema visibility without loading every historical JSON/evidence body into the API process.
- A timestamp/ID ceiling keeps a newer attempt arriving between queries for the next read. An organization/candidate/time index supports traversal. Synthetic 10,001-analysis regressions assert three queries and two materialized payloads for the selector; the actual inbox response, tenant isolation, equal-timestamp ordering and populated SQLite/PostgreSQL index migration also pass.
- This is not yet bounded event pagination or a capacity certification: the interactive organization candidate list remains unbounded, and SQL counting/current-schema search can still inspect many rows. Complete event-centered filters/cursors, batched entity/review lookups, bounded digest continuation and the target-host 100k-event/20-reader gate remain open. See `docs/INBOX_READS.md`.


Implemented digest-period slice — 5 September 2026 (HappyDucky02):

- Digest preview and delivery now filter the half-open saved detection period `[period_start, period_end)`, selected sources and the recipient's dismissed/muted states in SQL before loading candidate/evidence payloads. Delayed/retried delivery cannot pull in events at or after its saved end. Preview captures one end instant; all available source options remain discoverable through a column-only distinct query.
- Exactly 50 eligible events no longer falsely indicate truncation; a 51st eligible event is required. Existing severity and evidence grouping are preserved, with no inference or read-state mutation.
- Thirty focused regressions pass, including a 10,000-old-event SQLite/PostgreSQL check with only three selected delivery/event payloads, period boundaries, private-state/organization isolation and failed-mail retry using a test double. This does not bound an arbitrarily busy selected period: cursor selection, durable continuation, visible/actionable truncation and intended-host capacity verification remain open.


<a id="hl-100"></a>

### HL-100 — Require substantive evidence before claiming relevance or impact

**Priority:** P0. **Status:** IN PROGRESS. **Dependencies:** HL-044, HL-045, HL-093. **Owner role:** retrieval/AI/backend.

Problem: generic title overlap can become citable `candidate_fact`; a template can retain an unsupported High severity, creating apparent certainty without a substantive bridge.

Deliverable: separate retrieval rationale from claim evidence, calibrated candidate gating and controlled supersession of affected saved assessments.

**Implemented 5 September 2026:** Candidate rule v2 excludes multilingual instrument/authority boilerplate and standalone numbers while preserving exact-reference retrieval. Relation-impact v3 requires a source/target passage pair or the matching confirmed official relation for each positive conclusion/action; metadata-only and generic/contradictory output becomes unassessed rather than supported High. Fixed action-loop shadowing. Prior result revisions remain immutable, visibly stale history and no longer supply the current inbox conclusion; explicit reanalysis reuses the delivery. Adversarial regression covers the reported German pair, all five languages and persisted history/urgency behavior. **Remaining:** independently reviewed precision/recall and claim entailment, bounded historical candidate reprocessing, and full input/profile/runtime freshness on reads. Citation identity plus an evidence pair is not proof of factual support. See [contract](docs/RELATION_IMPACT_ANALYSIS.md).

Acceptance criteria:

- Generic instrument/authority terms alone (including the observed `uber, verordnung` pair) cannot create a positive user-facing relevance/impact alert. Require substantive concept/scope evidence, an exact norm reference or a verified official relation; test multilingual boilerplate and hard near-matches.
- Keep `candidate_fact` for explaining discovery, but prohibit it as the sole support of a positive impact, obligation or action. Require claim-linked source/target passages or authoritative relation metadata, not just a valid citation-row identifier.
- Low-quality/contradictory/unsupported prose becomes unassessed or needs review. A generic fallback must not retain supported/High solely because the model emitted that enum. Preserve independently verified official/deterministic urgency when AI fails; distinguish that fact from unsupported AI-derived importance, evidence confidence and legal status.
- Fix the relation-action loop's candidate-variable shadowing and validate each suggested action against its actual input candidate/evidence.
- Preserve a concise explainable negative/low-importance outcome. Freeze thresholds with HL-093 held-out precision/recall tests; do not improve precision by silently dropping high-value positives.
- Re-evaluate previously affected candidates through bounded rule-revision jobs; mark old assessments stale/superseded and retain history. Inbox must not present a prior succeeded result as current after input/rule/profile changes. Reprocessing creates no duplicate notification.

<a id="hl-101"></a>

### HL-101 — Run a longitudinal pilot and make an evidence-based rollout decision

**Priority:** P0. **Status:** PLANNED. **Dependencies:** HL-090, HL-073, HL-076, HL-078, HL-079, HL-089, HL-032, HL-048, HL-049, HL-057, HL-064, HL-098–HL-100. **Owner role:** product/operations with participating organizations.

Problem: implementation checks do not establish that people return, trust alerts or save time.

Deliverable: four-week invitation-only pilot report, documented fixes and a go/hold/narrow-scope decision before broad public registration.

Acceptance criteria:

- Run with at least five independently participating organizations in the selected initial segment. Participation/invitations are explicitly arranged; respect language and data boundaries. Early local prototype research in HL-090 does not require this production gate.
- Measure activation, weekly meaningful review, useful/irrelevant alerts, high-value misses, duplicates, task completion, manual effort replaced and reasons for abandonment. Report denominators and nonrespondents; do not equate login/chat count with value.
- Proposed pilot signals: ≥80% of rated alerts useful, no duplicate delivery for the same logical development under one policy, and ≥60% of activated organizations completing meaningful review in week four. Record uncertainty and sample limitations; these are learning thresholds, not proof of market size.
- Assign operational ownership for each promoted source, degraded coverage, user feedback, bad conclusions, restore procedures and model/rule changes. Run a source-outage and model-unavailable exercise without hiding deterministic evidence or sending false reassurance.
- Include real mobile and native-language review, truthful inference wait expectations, privacy-preserving aggregate product metrics and a documented way to mute/refine monitoring. Do not log raw user questions into external analytics by default.
- Report actual critical failures and at least two resulting improvement decisions. Broader launch needs target hardware/recovery and HL-088 acceptance; if the pilot fails, narrow scope or revise the journey and retest rather than adding more sources or persona effects.

## Shared completion rule

An item is done only when its acceptance criteria are demonstrated through the actual UI/API/persistence path where applicable, meaningful checks pass for its state or evidence logic, and user-visible error states are handled. Completing this backlog document does not complete any development item.

Minimum MVP evidence remains: a verified public source; a saved current version; an imported earlier version with provenance; a real comparison; an inspectable diff; a successful real Apertus analysis; a question with a working citation; and successful repeat/restart/failure checks. The public beta additionally requires every P0/P1 item in `HL-029`–`HL-049` plus `HL-057`–`HL-064`, source-contract evidence for all three core connectors, complete five-locale smoke/catalogue checks, the decision-ready AI-triage regression and usability gate, local-model and recovery benchmarks on the target host, organization-isolation checks, and the reproducible capacity scenario. The daily-use release then requires the core `HL-065`–`HL-080`, `HL-083`–`HL-089` gate and `HL-090`–`HL-101` corrective/field evidence. The invitation-only pilot follows technical gates but precedes final HL-088 sign-off, avoiding a circular release dependency; optional public-discourse and later-canton expansion remain governed by their own evidence gates.

Still excluded from the public-beta release: Kubernetes, multi-host workers, database/broker high availability, enterprise SSO/SCIM, arbitrary custom roles, unbounded crawling, universal Swiss court coverage, an ornamental graph UI, OCR, login-gated ingestion, model training/fine-tuning, and automatic legal decisions. They remain future work only where an item above names a measurable entry condition. Ordinary validation, bounded fetching, safe rendering, authorization, secret handling, backups, and recovery are implementation requirements rather than optional enterprise decoration.
