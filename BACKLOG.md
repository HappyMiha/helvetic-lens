# Apertus RegWatch — Development Backlog

**Know what changed. Know what it means. Know what to do.**

This backlog implements the product described in [README.md](README.md): user-configured websites, tracked laws, imported previous versions, real scans, visual comparisons, and Apertus analysis with verifiable citations.

**Status:** The required MVP workflow is implemented and verified through the browser, real HTTP requests, PostgreSQL, service restarts, and live Apertus inference. Large complete diffs use bounded model requests while retaining every changed passage. See [verification evidence](docs/VERIFICATION.md). Stable `RW-xxx` identifiers remain the task reference.

## Scope and priorities

- **P0 — first working workflow.** Build the real path from a document URL and a previous version to a live comparison and impact analysis.
- **P1 — required to complete the MVP.** Complete website discovery, the dashboard, cited questions, verification, and the repeatable demonstration. P1 items are not optional.
- **P2 — optional after the MVP is accepted.** Impact matrix and retrieval with pgvector, only when justified.

There are **26 required items** and **2 optional items**, including the subsequently requested provider, diagnostics, history, prompt, and local-model work. Follow dependencies and the release checkpoints below; priority alone is not a complete execution order. No calendar estimates are assumed until team capacity, source compatibility, and model access are known.

Keep the agreed stack: **Next.js, Tailwind CSS/shadcn/ui, FastAPI, PostgreSQL, BeautifulSoup, PyMuPDF, and `difflib`**. **Apertus v1.5 8B** is the proposed model target; confirm the actual model identifier and endpoint in RW-017. **pgvector is optional.**

## Release checkpoints

| Checkpoint | Required items | Observable result |
| --- | --- | --- |
| M0 — Ready to build | RW-001–RW-003 | Known test sources and historical inputs; web app, API, and persistent database run locally. |
| M1 — Real sources and laws | RW-004–RW-008 | A user connects a supported site, discovers documents, or adds a law directly; real extracted content is saved. |
| M2 — Historical comparisons | RW-009–RW-013 | A user imports an earlier version, selects two versions, and inspects exact changes and saved evidence. |
| M3 — Live monitoring | RW-014–RW-016 | Scans fetch current content, report actual progress, preserve history, and show useful results on the dashboard. |
| M4 — Apertus explanations | RW-017–RW-019, RW-025 | Model settings persist; impact analysis and questions work against real saved passages with working citations. |
| M5 — Accepted MVP | RW-020–RW-022 | Regression checks, product acceptance, and a repeatable live demonstration pass. |

Start RW-017 as soon as RW-002 and RW-003 are available so model access is checked early. Source fetching, imports, and visual comparisons must remain developable while model access is being resolved. RW-011 can start once snapshots exist; it need not wait for website discovery. Implement regression checks alongside the relevant feature work, then use RW-020 as the completion gate.

## Task index

| ID | Priority | Status | Dependencies | Deliverable |
| --- | --- | --- | --- | --- |
| [RW-001](#rw-001) | P0 | DONE | None | Verified source examples and historical inputs |
| [RW-002](#rw-002) | P0 | DONE | None | Runnable app, API, and database |
| [RW-003](#rw-003) | P0 | DONE | RW-002 | Persistent domain model and migrations |
| [RW-004](#rw-004) | P0 | DONE | RW-001, RW-002 | Real HTML/PDF fetching and extraction |
| [RW-005](#rw-005) | P0 | DONE | RW-003, RW-004 | Immutable snapshots and saved evidence |
| [RW-006](#rw-006) | P0 | DONE | RW-003, RW-004 | Website connection management |
| [RW-007](#rw-007) | P0 | DONE | RW-005, RW-006 | Tracked laws and direct document URLs |
| [RW-008](#rw-008) | P1 | DONE | RW-004, RW-006, RW-007 | Bounded discovery and document search |
| [RW-009](#rw-009) | P0 | DONE | RW-005, RW-007 | Previous-version import |
| [RW-010](#rw-010) | P0 | DONE | RW-007, RW-009 | Version history and baseline selection |
| [RW-011](#rw-011) | P0 | DONE | RW-005 | Shared passage and word comparison engine |
| [RW-012](#rw-012) | P0 | DONE | RW-010, RW-011 | Visual diff with change navigation |
| [RW-013](#rw-013) | P0 | DONE | RW-005, RW-012 | Version-specific evidence viewer |
| [RW-014](#rw-014) | P0 | DONE | RW-007, RW-010, RW-011 | Live scans and historical comparisons |
| [RW-015](#rw-015) | P0 | DONE | RW-014 | Actual progress, partial failures, and recovery |
| [RW-016](#rw-016) | P1 | DONE | RW-006, RW-008, RW-012, RW-015 | Dashboard and scan controls |
| [RW-017](#rw-017) | P0 | DONE | RW-002, RW-003 | Verified Apertus adapter and company context |
| [RW-018](#rw-018) | P0 | DONE | RW-011, RW-013, RW-017 | Cited impact analysis and actions |
| [RW-019](#rw-019) | P1 | DONE | RW-013, RW-017, RW-018 | Ask Apertus with version-specific citations |
| [RW-020](#rw-020) | P1 | DONE | RW-009, RW-014, RW-015, RW-018, RW-019 | Regression checks for state and evidence |
| [RW-021](#rw-021) | P1 | DONE | RW-008, RW-012, RW-013, RW-016, RW-019, RW-020, RW-025 | End-to-end product acceptance |
| [RW-022](#rw-022) | P1 | DONE | RW-001, RW-021 | Setup documentation and repeatable demo |
| [RW-023](#rw-023) | P2 | DEFERRED | RW-018, RW-022 | Optional business impact matrix |
| [RW-024](#rw-024) | P2 | DEFERRED | RW-019, RW-022 | Optional pgvector retrieval |
| [RW-025](#rw-025) | P0 | DONE | RW-002, RW-003, RW-017 adapter code | Settings page with persisted Apertus parameters |
| [RW-026](#rw-026) | P1 | DONE | RW-006, RW-007, RW-017 | Integration diagnostics and controlled deletion |
| [RW-027](#rw-027) | P1 | DONE | RW-018, RW-019, RW-025, RW-026 | Resilient AI calls, saved history, and prompt controls |
| [RW-028](#rw-028) | P1 | DONE | RW-017, RW-027 | Robust citation-row handling and local Docker Apertus fallback |

## M0 — Ready to build

<a id="rw-001"></a>
### RW-001 — Verify initial sources and historical inputs

Select a small, realistic validation set without restricting users to a hard-coded source list.

Acceptance criteria:

- Record 2–3 public regulatory source URLs, including an HTML document, a text-based PDF, and a listing page suitable for discovery. One site may cover multiple formats.
- Record the expected title, content type, relevant content area, language, and any known extraction limitation for each example.
- Obtain at least one earlier document version with recorded provenance. If only a modified example is available, label it synthetic; do not present it as an authentic historical law.
- Prepare a small controlled before/after pair with known changes, including a changed number or deadline. This is for deterministic verification, not a replacement for real source support.
- Keep source and fixture documentation in the repository; do not commit credentials or material without permission to redistribute it. Link to originals when redistribution is unclear.

<a id="rw-002"></a>
### RW-002 — Create the runnable application foundation

Provide one Next.js web app, one FastAPI service, and one PostgreSQL database.

Acceptance criteria:

- Establish a small layout such as `apps/web`, `services/api`, and `docs`; install Tailwind CSS and shadcn/ui without adding unrelated frameworks.
- Document a working local startup procedure. A simple Compose configuration may run the services and a persistent database volume; no cluster or worker fleet is required.
- Include an environment-variable example with placeholders, a database readiness check, and a visible web-to-API connection check.
- Define the initial API conventions for identifiers, validation errors, and asynchronous scan status; expose the FastAPI API documentation.
- Provide basic formatting, lint/type-check, and verification commands appropriate to the code that exists. Keep environment files, downloads, and generated runtime data out of Git.

<a id="rw-003"></a>
### RW-003 — Add the domain model and migrations

Persist the state required to explain what was observed and which versions were compared.

Acceptance criteria:

- Add records for **Source, TrackedLaw, DocumentVersion, Scan**, per-law scan results, and **Comparison**, with analysis attached to a comparison. A scan result may also represent a failed fetch with no new version.
- A tracked law has a current URL, display name, monitoring state, and a reference to its last successfully observed live snapshot. Adding a direct URL must not require prior discovery.
- Versions retain origin, fetch/import time, optional stated version date and its provenance, extraction format/version, text hash, artifact location, and paragraph/page references.
- Comparisons explicitly reference old and new versions of the same law and their mode: ordinary monitoring, historical comparison, or comparison of saved versions.
- Store the single company profile and analysis context needed by RW-017/RW-018. Apply migrations to a clean database and preserve records across service restarts.
- Keep observation history separate from snapshot content so unchanged checks and a return to previously seen content can be recorded without duplicating stored snapshots.

## M1 — Real sources and laws

<a id="rw-004"></a>
### RW-004 — Fetch public documents and extract usable text

Implement one extraction path shared by current documents and imported versions.

Acceptance criteria:

- Fetch supported public HTTP(S) HTML/PDF URLs, retain the original and final URL, and report the actual detected input type.
- Extract meaningful HTML text with BeautifulSoup and text-based PDF content with PyMuPDF. Keep headings, article numbers, substantive dates, and paragraph/page boundaries.
- Normalize whitespace and obvious navigation boilerplate consistently without erasing legal wording, numbers, or punctuation that may carry meaning.
- Return a preview containing title, content type, text excerpt, extraction result, and any limitation before the user saves a document.
- Resolve supported Fedlex ELI law URLs through the official Linked Data metadata into their current or explicitly dated HTML/PDF publication, while retaining the stable ELI URL for later scans and recording resolved provenance.
- Apply practical time, redirect, and download limits; validate public URL targets, including redirects. Report network failures, empty extraction, scanned PDFs, login pages, and unsupported JavaScript pages as distinct failures or unsupported inputs.

<a id="rw-005"></a>
### RW-005 — Save immutable snapshots and evidence

Keep enough original evidence to reproduce a comparison after the live website changes.

Acceptance criteria:

- Persist normalized text, a content hash scoped to the tracked law and extraction rules, stable passage references, and original files or equivalent saved source evidence.
- Store uploaded artifacts in persistent local storage for the initial deployment; no object-storage platform is required.
- Preserve origin, original filename/URL, source-stated or user-supplied version date, and actual fetch/import time separately.
- Reuse an existing matching content snapshot where appropriate while recording each observation/import and its provenance; an imported origin must not erase evidence of a later live observation.
- Treat saved snapshots as immutable. Re-importing an old version or failing a fetch must not replace the current live snapshot.
- Reopen a saved PDF page or text passage successfully after the source changes or the service restarts.

<a id="rw-006"></a>
### RW-006 — Build website connection management

Let the user configure supported websites through the interface.

Acceptance criteria:

- Provide an **Add website** form for a name and public root/listing URL, plus an optional section boundary for discovery.
- **Test connection** performs a real fetch and shows the extracted preview or a useful error. A successful HTTP response with no usable document content is not sufficient.
- Save and edit source configuration in PostgreSQL; display last connection/check status and the configured discovery boundary.
- A newly configured supported website works without changing source code or a hard-coded allowlist of demo sites.
- Explain the difference between connecting a website and selecting individual laws to monitor.

<a id="rw-007"></a>
### RW-007 — Add and manage tracked laws by URL

Make direct document entry the shortest usable path into the product.

Acceptance criteria:

- **Add law** accepts a public HTML/PDF URL, previews its contents, lets the user confirm or edit the title, and saves the tracked law.
- Associate the law with its source where applicable, but do not require the user to run website discovery first.
- Save the first successful live snapshot as **Baseline created**. Do not invent a change when no earlier version exists.
- Allow renaming, pausing, and resuming monitoring. Paused laws are excluded from **Scan all** without losing their history.
- Detect an already tracked document URL and offer the existing law instead of silently creating duplicate watchlist entries.
- Show clear loading, empty, and error states; a failed preview must not create a misleading successful baseline.

<a id="rw-008"></a>
### RW-008 — Discover and search documents within a source

Find candidate laws in a bounded site section and let the user choose what to track.

Acceptance criteria:

- Start at the configured listing page and follow at most one link level, inspecting at most 50 candidate pages per run by default.
- Resolve relative URLs, remove fragments for duplicate detection, preserve meaningful query parameters, and stay within the configured site/section boundary.
- Show candidate title, URL, content type, and extraction preview; support title/keyword filtering over the inspected results.
- Selecting a candidate opens the same law confirmation flow as RW-007. Previously tracked candidates are labeled accordingly.
- Show inspected counts, the limit reached, and per-candidate errors. Never imply exhaustive site coverage.
- Label newly discovered documents separately from changes to previously tracked laws; discovery alone is not evidence of a legal amendment.

## M2 — Historical comparisons

<a id="rw-009"></a>
### RW-009 — Import a previous version

Allow the user to provide an earlier document without waiting for a future live update.

Acceptance criteria:

- Support PDF, HTML, and TXT upload; pasted text; and a direct URL to a historical copy. Reuse the extraction and snapshot pipeline.
- Show the extracted preview and selected law before confirmation. Reject empty or unsupported input with a useful explanation.
- Accept an optional stated version date, retain import time separately, and label a user-entered date as supplied by the user.
- Retain provenance and an explicit synthetic-demo marker when applicable. Uploading a file does not verify it as an official historical version.
- Let the user confirm that the imported document belongs to this law and select it as a comparison baseline.
- Do not change the current live pointer, prior scan results, or stored evidence when importing an older version. A snapshot import alone does not activate live monitoring without a current URL.

<a id="rw-010"></a>
### RW-010 — Show version history and select a baseline

Make it explicit which documents are being compared.

Acceptance criteria:

- The law detail page lists saved versions/observations with origin, available version date, fetch/import time, and the current live snapshot indicator.
- Offer **Last live version**, **Choose previous version**, and **Compare saved versions** as clear comparison choices.
- Old/new selectors accept only versions belonging to the selected law. Do not infer legal chronology solely from upload time or present an unknown date as verified.
- Show historical and synthetic labels before starting the operation and retain those labels on the result.
- Allow repeating a historical comparison without resetting the law or deleting history.

<a id="rw-011"></a>
### RW-011 — Implement the shared comparison engine

Produce deterministic text differences before asking a model to explain them.

Acceptance criteria:

- Use `difflib` to produce added, removed, and modified passage groups, with word-level operations within modified passages.
- Return stable change identifiers, old/new version and passage references, counts, and enough surrounding context for the viewer and Apertus.
- Persist the comparison and its selected version pair/mode; reuse the same engine for live scans, historical comparisons, and saved-version comparisons.
- Identical normalized input produces an unchanged result. Whitespace-only normalization does not create a change, while changed numbers, dates, or legal wording remain visible.
- Keep the deterministic diff independent of model availability. Do not treat a model opinion as proof that text changed.

<a id="rw-012"></a>
### RW-012 — Build the visual diff and change navigation

Let the user see the exact wording that changed.

Acceptance criteria:

- Show old and new text side by side, with red removals, green additions, and word highlights within modified passages.
- Provide a change list, change counts, filters for added/removed/modified content, and navigation to the corresponding passages in both panes.
- Display source, version labels, provenance, available dates, and whether this is a historical comparison or a new monitoring result.
- Make long documents usable by collapsing unchanged context or rendering manageable sections. Provide a text legend and keyboard-accessible navigation in addition to color.
- A controlled change from **30** to **60** is highlighted at the exact location, not represented only by a summary card. Identical versions have a clear unchanged state.

<a id="rw-013"></a>
### RW-013 — Open saved evidence for a specific version

Provide the shared evidence destination used by the diff, impact analysis, and questions.

Acceptance criteria:

- A version/passage reference opens the saved text with the target passage highlighted; a PDF reference opens or identifies the saved page where available.
- Always display the referenced version and its provenance, including imported files. Offer the original source URL separately when it exists.
- Evidence remains accessible if the live URL changes, is unavailable, or now serves a newer document.
- Render extracted text safely instead of executing imported page HTML. Missing or invalid evidence references produce a clear error, not a different passage.
- Both old and new sides of a comparison can be cited independently.

## M3 — Live monitoring

<a id="rw-014"></a>
### RW-014 — Run live scans and explicit historical comparisons

Fetch actual current content, compare the right versions, and preserve monitoring history.

Acceptance criteria:

- **Scan now** handles one law or all active laws. Capture the ordinary comparison baseline before saving a newly fetched snapshot.
- Ordinary scans use the last successfully observed live version. The first successful fetch without a baseline yields **Baseline created**; identical current content yields **Unchanged**.
- A historical selection compares the requested earlier snapshot with current fetched content even when that current snapshot is already stored. Label this result **Historical comparison**, not a newly discovered amendment.
- Record the live observation and the selected comparison mode/baseline separately. Importing or selecting an older snapshot must never make it the current live version.
- Do not create duplicate content snapshots for unchanged checks. If content returns from A to B to A, reuse snapshot A but record the change from B to A and the new observation.
- **Compare saved versions** uses the same comparison engine without a network request and does not advance the live monitoring state.
- Persist successful comparisons even if later analysis fails. Failed fetching/extraction must not overwrite the last good version. Prevent concurrent scans of the same law from racing its baseline update, using a simple single-service mechanism.

<a id="rw-015"></a>
### RW-015 — Expose real progress and recover incomplete scans

Make actual work, partial success, and failures visible.

Acceptance criteria:

- Persist per-law stages such as **Queued, Fetching, Extracting, Comparing, Analysing**, with explicit final comparison and analysis outcomes.
- Provide a status endpoint and simple client polling, or an equivalent small streaming implementation. The interface displays real stages and completed/total counts, not simulated percentages.
- Separate changed, unchanged, baseline-created, and failed document results. A scan may finish with some documents successful and others failed.
- Report model analysis as not configured, pending, succeeded, or failed independently of a valid comparison. Wire the actual model stage through RW-018.
- On restart, mark unfinished runs as interrupted instead of leaving them permanently running or reporting success. Keep completed versions and comparisons intact.
- Offer safe retry of a failed document or failed analysis. Reuse completed work where possible and avoid adding a distributed queue for this scope.

<a id="rw-016"></a>
### RW-016 — Build the dashboard and scan controls

Bring source management, the watchlist, and scan results into one usable interface.

Acceptance criteria:

- Display connected sources, active/paused laws, last check times, latest outcomes, and links to law details and version history.
- Provide **Scan selected** and **Scan all active** actions with actual progress from RW-015 and clear handling of an empty watchlist.
- Keep newly discovered documents, first baselines, unchanged checks, historical comparisons, new live changes, and failures visibly distinct.
- Open the selected comparison directly from a result. Display Apertus impact only when an analysis exists; otherwise show the actual pending, unavailable, or failed state.
- Basic filtering by source and result state works with persisted records. Refreshing the page does not reset the result or fabricate a new scan.

## M4 — Apertus explanations

<a id="rw-017"></a>
### RW-017 — Verify Apertus access and add a small model adapter

Connect to a real Apertus deployment and supply one company profile.

Live verification: the saved Public AI configuration reached `swiss-ai/apertus-v1.5-8b`, returned cited answers and impact analysis, and completed a synthetic 1,406-passage comparison through bounded requests without truncation or HTTP 504.

Acceptance criteria:

- Confirm the reachable endpoint, actual model identifier, authentication method, supported context budget, and a successful real request. Treat **Apertus v1.5 8B** as a proposed target until verified; document any mismatch instead of silently substituting a model.
- Keep endpoint, model ID, credentials, and request limits configurable on the server. Commit placeholder configuration only; do not expose model credentials to the browser.
- Implement one small adapter with bounded requests and explicit timeout/unavailable errors. Report the actual model status, without fabricated model responses.
- Provide one editable, persisted company profile containing the short business description and relevant business areas. No multi-company administration is needed.
- Document setup prerequisites and any access blocker early. Real source fetching and visual comparison continue to work without Apertus; the full model-enabled MVP is not accepted until a real inference call succeeds.

<a id="rw-018"></a>
### RW-018 — Generate impact analysis, actions, and supporting evidence

Explain a selected comparison using the saved source text and company profile.

Acceptance criteria:

- Persist a complete deterministic article/passage diff for the two saved versions and supply every changed old/new passage with explicit change, version, passage, and position identifiers. Treat document content as evidence, not instructions to the assistant.
- Return a concise summary, why it matters, affected business areas, indicative high/medium/low impact with a reason, and 1–3 suggested actions. Attach supporting references to factual conclusions.
- Validate the output shape and evidence references against the supplied passages before displaying citations. Quoted evidence must match the referenced saved text. Invalid JSON/schema/citations receive one constrained repair attempt and are rejected if that also fails.
- Never truncate or retrieval-rank the changed-passage set. Disclose when its size exceeds the configured warning threshold; an upstream context-window failure leaves the complete visual diff available and must not be presented as a successful assessment.
- Save results against the version pair, company-profile revision, model ID, and analysis/prompt version so changed context does not reuse a stale explanation.
- Connect actual analysis status to the scan/dashboard. On model failure, leave the diff available and offer analysis retry without refetching the document or creating another version.
- Show the source evidence and indicate that impact and actions are review aids rather than authoritative legal conclusions.

<a id="rw-019"></a>
### RW-019 — Add Ask Apertus with version-specific citations

Answer questions about the selected law or comparison using inspectable evidence.

Acceptance criteria:

- Provide a question input and answer panel scoped to the selected law/version or old/new comparison. Keep cross-law search and a large chat platform out of scope.
- Use every changed passage from the complete persisted comparison, without embeddings or retrieval ranking. Preserve the deterministic old/new pairing in the model context.
- Answers cite valid version and passage identifiers; citations open the matching saved passage or PDF page through RW-013.
- When changed passages do not support an unrelated answer, explicitly state that limitation. A “what changed?” question must not claim insufficient context when the complete comparison is available. Reject invalid citations instead of displaying fabricated links or silently using the latest live version.
- Follow-up questions retain the selected comparison context. Loading, timeout, and model-unavailable states are visible and leave the diff usable.
- Verify at least one question about changed wording, one about the earlier version, and one that cannot be answered from the supplied documents.

<a id="rw-025"></a>
### RW-025 — Configure Apertus providers through a Settings page

Added at the user's request after implementation began and verified with the live adapter in RW-017.

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

<a id="rw-026"></a>
### RW-026 — Add integration diagnostics and controlled deletion

Added at the user's request after the core monitoring and Infomaniak flows were working.

Acceptance criteria:

- Persist each outbound website, Fedlex, Firecrawl, and OpenAI-compatible model request with provider, operation, method, URL, outcome, HTTP status, duration, request/response sizes, headers, bodies, and an explicit error where applicable.
- Redact authorization, cookies, token/key/password fields, and matching credential values before persistence. Bound large text/JSON payloads and represent binary documents with content type, byte count, and hash so diagnostics cannot make ordinary monitoring unbounded.
- Provide an **Integration logs** page in desktop and mobile navigation. Load lightweight rows first; allow provider/outcome filters, text search, sortable columns, pagination, refresh, and full redacted request/response inspection on demand.
- Allow clearing all diagnostic logs with explicit confirmation. Clearing logs must not change sources, documents, versions, scans, comparisons, analyses, profile, or provider settings.
- Allow removing a website from Sources with confirmation while leaving its tracked documents available as independent monitored documents.
- Allow permanently deleting a monitored document with confirmation. Remove its observations, versions, comparisons, analyses, scan entries, empty scans, and artifact files that are no longer referenced. Block deletion while that document has a queued or running scan.
- Cover redaction, sorting, filtering, detail retrieval, clearing, source detachment, dependency cleanup, artifact cleanup, and active-scan blocking with deterministic API checks.

<a id="rw-027"></a>
### RW-027 — Make AI results resilient, persistent, and configurable

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

<a id="rw-028"></a>
### RW-028 — Recover real provider citations and add local Docker inference

Added after a large Infomaniak comparison returned successful HTTP responses but sometimes used passage positions instead of the requested batch-row numbers, while separate provider connections occasionally closed mid-response.

Acceptance criteria:

- Include an explicit `row_number` as the first column in every batched evidence row and tell the model to cite only that value.
- Accept an out-of-range model reference only when it maps to actual supplied passage positions or numeric passage identifiers; continue rejecting invented citations.
- Include the allowed numeric range in the single repair request and keep exact server-materialized version, passage, quote, page, and evidence links.
- Respect numeric `Retry-After` responses and use bounded exponential delays between interrupted transport attempts.
- Add Local Docker Apertus as a selectable provider whose host/Compose endpoint is derived by the API, whose models load through the OpenAI-compatible `/models` route, and which never receives a saved remote-provider credential.
- Provide and verify a repeatable optional Compose service using the official llama.cpp server image and a compact Apertus instruction checkpoint suitable for local pipeline diagnostics.

## M5 — Verification and demonstration

<a id="rw-020"></a>
### RW-020 — Cover state transitions and evidence with regression checks

Protect the behavior that makes the product reliable. Implement these checks alongside the corresponding tasks, not only at the end.

Acceptance criteria:

- Use controlled HTML/PDF/text inputs to cover first baseline, actual change, unchanged content, normalized whitespace, and a changed number/date that must remain visible.
- Verify repeated historical comparisons against an unchanged current source, duplicate imports, and A → B → A content returning without duplicate snapshots or lost observation history.
- Verify that importing an older document does not move the live pointer, that a failed fetch/empty extraction does not destroy the last good version, and that overlapping scans cannot corrupt their baselines.
- Cover mixed-success batches, interrupted scans after restart, model timeout after a successful comparison, and analysis-only retry.
- Validate old/new citation targets, exact quoted evidence, unavailable evidence, and stale analysis after a company-profile/context change.
- Use deterministic model test doubles only in automated checks and label them as such. They do not replace the real Apertus check required by RW-017/RW-021.

<a id="rw-021"></a>
### RW-021 — Verify the complete product workflow

Exercise the product from the browser through persistence, extraction, comparison, and model output.

Acceptance criteria:

- From a clean installation, connect a website, discover a document, add it to the watchlist, and separately add another law by direct URL without changing code.
- Import an earlier version, choose it as the baseline, run a real fetch, inspect exact changes, read the Apertus analysis, ask a question, and open a citation to the correct version.
- Repeat the historical comparison while current content is unchanged; confirm the correct result label and no duplicate snapshots. Run an ordinary unchanged check separately.
- Restart the app/database services without deleting their volumes; verify sources, paused states, versions, evidence, and scan results are still available.
- Verify visible behavior for unsupported input, an unavailable source, a partial batch failure, and a missing/unavailable model. No failed path appears as successful analysis.
- Compare two saved versions with the network unavailable and confirm the interface does not claim a live scan occurred.
- Automate the deterministic browser path against a controlled local source where practical, then record a manual smoke check against the actual selected public sources and the actual Apertus endpoint. Record limitations honestly; do not mark the full MVP complete on mock-only evidence.

<a id="rw-022"></a>
### RW-022 — Document setup and rehearse a repeatable demonstration

Make the completed workflow usable by another developer or hackathon presenter.

Acceptance criteria:

- Update the README with commands that have actually been verified, required environment variables, migration/setup steps, and the supported source limitations.
- Add a short demo guide covering website connection, direct law entry, historical import, baseline choice, live scanning, visual diff, impact analysis, and a cited question.
- Keep a suitable earlier document or instructions for obtaining it with provenance. Any altered example remains visibly marked synthetic throughout the demonstration.
- Rehearse the same demo twice without changing the external website, deleting history, or replacing real processing with preset cards or simulated progress.
- Document the explicit saved-version fallback for network failure and the model-unavailable behavior; do not present either as a successful live/model run.
- Record the completed acceptance results and remaining known limitations. Mark backlog items done only after their criteria are met; do not bundle enterprise infrastructure into this checkpoint.

## Optional work after acceptance

<a id="rw-023"></a>
### RW-023 — Add the business impact matrix

Provide an additional view over existing evidence-backed analyses.

Acceptance criteria:

- Display changes against the company profile's business areas, with indicative impact and a short reason derived from the saved analysis.
- Each cell opens the relevant comparison and evidence; it does not manufacture an assessment when no analysis exists.
- Unknown/unanalysed impact is distinct from low impact. Profile changes invalidate stale matrix values consistently with RW-018.
- Keep the underlying scan and analysis workflow unchanged. Defer this item if required work is incomplete.

<a id="rw-024"></a>
### RW-024 — Add pgvector only when direct context is insufficient

Improve passage selection only after measuring a real retrieval need.

Acceptance criteria:

- First document a representative query set and the limitation of direct context selection at the intended corpus size. If no material limitation exists, keep this task deferred.
- If justified, add paragraph chunks, embeddings, and pgvector storage in the existing PostgreSQL database; identify the embedding model and its setup explicitly.
- Retrieve within the selected law/version or comparison and preserve exact version, paragraph, and PDF-page references. Never mix unrelated or newer versions into the answer silently.
- Compare answer support, citation correctness, latency, and operational cost against the direct-context baseline before enabling retrieval by default.
- Keep direct context as a usable fallback and do not add a separate vector-database platform.

## Shared completion rule

An item is done only when its acceptance criteria are demonstrated through the actual UI/API/persistence path where applicable, meaningful checks pass for its state or evidence logic, and user-visible error states are handled. Completing this backlog document does not complete any development item.

Minimum release evidence is: a verified public source; a saved current version; an imported earlier version with provenance; a real comparison; an inspectable diff; a successful real Apertus analysis; a question with a working citation; and successful repeat/restart/failure checks. Both **P0 and P1** items are required for the agreed MVP.

Excluded from this backlog: enterprise SSO, multi-tenancy, granular role systems, audit platforms, broad web crawling, scheduled worker fleets, knowledge graphs, autonomous agent orchestration, OCR, login-gated ingestion, model training, and automatic legal decisions. Ordinary input validation, bounded fetching, safe text rendering, and keeping credentials out of Git are basic implementation hygiene, not separate enterprise projects.
