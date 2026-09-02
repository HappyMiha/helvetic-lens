# Apertus RegWatch

**Know what changed. Know what it means. Know what to do.**

Apertus RegWatch lets users connect regulatory websites, add specific laws or documents to a watchlist, import earlier versions, and run real checks against current source content. It turns detected differences into visual comparisons, plain-language impact summaries, and practical next steps with links back to the evidence.

The MVP must be a functional product with a narrow scope. Sources are configured through the interface, data persists between sessions, and the demonstration uses the same fetching, comparison, and analysis pipeline as everyday use.

> **Project status:** The model-enabled MVP works end to end: source connections, direct URLs, imports, immutable history, live scans, saved comparisons, visual evidence, persisted Apertus settings, impact analysis, cited questions, saved AI history, editable prompts, inspectable integration logs, and controlled removal of sources or monitored documents. Live Apertus checks include a complete 1,406-passage comparison processed without truncation. See [verification notes](docs/VERIFICATION.md).

Development tasks, priorities, dependencies, and acceptance criteria are tracked in [BACKLOG.md](BACKLOG.md).

## Run locally

Use Docker Desktop with Compose for the complete PostgreSQL stack:

~~~sh
git clone https://github.com/HappyMiha/apertus-regwatch.git
cd apertus-regwatch
docker compose up --build -d
~~~

Open [RegWatch](http://127.0.0.1:3000) and the [API reference](http://127.0.0.1:8000/docs). PostgreSQL and saved artifacts use persistent volumes. Migrations run on API startup. Default ports are 3000 (web), 8000 (API), and 54329 (database); stop development processes using those ports before starting Compose.

No model or paid extraction service is required for source monitoring and visual comparisons. Open **Settings → Apertus** to configure your inference endpoint in the app. [.env.example](.env.example) also provides optional server defaults. Never commit .env, credentials, or runtime data.

For development, install Node.js 22+ (tested with 24), Python 3.11+, and uv. Create .env from the example and set DATABASE_URL to the following before starting:

~~~text
postgresql+psycopg://regwatch:regwatch@127.0.0.1:54329/regwatch
~~~

~~~sh
npm ci
uv sync --project services/api --frozen
docker compose up -d db
npm run dev
~~~

The development API stores artifacts under data/. If DATABASE_URL is deliberately left empty, it uses local SQLite for a lightweight trial; Compose always uses PostgreSQL. Do not run both API variants against the same database with different artifact directories.

~~~sh
npm run typecheck
npm run format:check
npm run build
npm run lint:api
npm run test:api
~~~

[Follow the demo guide](docs/DEMO.md) to connect a site, import an older version, fetch current content, and inspect the exact **30 → 60** wording change.

## Connect a real Apertus deployment

The intended model is [Apertus v1.5 8B](https://huggingface.co/swiss-ai/Apertus-v1.5-8B). The served ID depends on your provider. Model weights are not bundled and no alternate model is silently substituted.

Open [Settings](http://127.0.0.1:3000/settings) from the sidebar or mobile navigation:

1. Choose **Infomaniak AI**, **Local Docker Apertus**, or **Other OpenAI-compatible API**. Infomaniak needs its numeric Product ID; the local Compose service is resolved automatically for host or container execution; the custom option needs the API base URL, including /v1 if required. Do not append /chat/completions; RegWatch adds it.
2. Keep the existing credential, replace it, use no credential for an unauthenticated local server, or inherit the server environment value. A saved token/key is never returned to the browser, including in validation errors.
3. Adjust the request timeout, automatic retry count, concurrent batch limit, evidence warning threshold, maximum completion length, temperature, Top P, presence penalty, reasoning effort, and optional JSON mode. RegWatch keeps `stream=false` and `n=1` fixed so structured answers and citations can be validated consistently. The default processes one large-model batch at a time and retries temporary transport, timeout, rate-limit, and 5xx failures twice.
4. For Infomaniak, choose **Load models** to populate the dropdown from the current Product ID. Choose **Test connection** to make an actual request with the form's current values without saving, then **Save settings** to apply them immediately.

For **Public AI**, choose **Use Public AI defaults** to fill `https://api.publicai.co/v1` and `swiss-ai/apertus-v1.5-8b`. This changes only those two draft fields, not the key or other parameters, and does not save automatically. Use an API key created in the provider's developer portal, rather than a chat login credential. RegWatch includes the required User-Agent header. These connection values follow the [Public AI quick start](https://platform.publicai.co/docs).

For **Hugging Face Inference Providers**, choose **Use Hugging Face** to fill `https://router.huggingface.co/v1` and `swiss-ai/Apertus-v1.5-8B:publicai`. Use a [Hugging Face access token](https://huggingface.co/settings/tokens) with Inference Providers permission; it is different from a direct Public AI key. The suffix selects Public AI as the provider through Hugging Face, without changing the requested Apertus model. The preset only edits draft fields and never sends the current key anywhere automatically. This configuration follows the [model card](https://huggingface.co/swiss-ai/Apertus-v1.5-8B) and [Hugging Face provider documentation](https://huggingface.co/docs/inference-providers/providers/publicai); successful inference still requires valid access and available account quota. A Hugging Face model-page URL is not an API base URL.

For **Infomaniak AI**, choose **Infomaniak AI**, enter the numeric Product ID and a product-authorized API token, then choose **Load models**. RegWatch derives `https://api.infomaniak.com/2/ai/{product_id}/openai/v1`, calls the provider's [`/models` endpoint](https://developer.infomaniak.com/docs/api/get/2/ai/%7Bproduct_id%7D/openai/v1/models), and fills the model dropdown with the IDs actually available to that product. Completion requests follow Infomaniak's [OpenAI-compatible chat endpoint](https://developer.infomaniak.com/docs/api/post/2/ai/%7Bproduct_id%7D/openai/v1/chat/completions) and use `max_completion_tokens`. The generated endpoint is read-only in the interface, preventing small URL edits from producing a broken route.

For a local diagnostic fallback on Docker Desktop, run `./scripts/local_apertus.ps1`. It starts the optional `local-ai` Compose profile with the official [`llama.cpp` server image](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md), downloads a roughly 3 GB [BF16 GGUF conversion](https://huggingface.co/MrMeOrYou/Apertus-v1.1-1.5B-Instruct-GGUF) of the official [`swiss-ai/Apertus-v1.1-1.5B-Instruct`](https://huggingface.co/swiss-ai/Apertus-v1.1-1.5B-Instruct) checkpoint into a persistent volume, applies the canonical Apertus chat format, and makes a real structured chat-completion request. Then choose **Local Docker Apertus** and **Load local models** in Settings. RegWatch uses `http://127.0.0.1:12435/v1` when its API runs on the host and `http://local-apertus:8080/v1` from Compose. No remote-provider credential is sent to this local endpoint, and an already saved Infomaniak token is preserved. The compact 1.5B model is useful for connectivity and pipeline tests; use the selected larger hosted model for stronger regulatory analysis.

Connection errors distinguish a rejected key (401), denied model access (403), an incorrect route/model (404), rate limit or quota (429), an unreachable server, and a timeout. Every retry is visible as a separate redacted integration-log entry. Provider response bodies and credentials are not echoed to the browser.

The evidence threshold is a character-based batch target, not the endpoint's exact token window. Large complete diffs are divided on change boundaries and every changed passage is processed exactly once; no passage is retrieval-ranked or truncated. Change-related questions and Impact use this complete deterministic diff. Other questions use the complete extracted text of both saved originals in bounded batches. The original PDF/HTML/TXT artifacts remain downloadable, but RegWatch does not claim to attach raw PDFs to an Apertus chat model: Infomaniak's documented [chat completion contract](https://developer.infomaniak.com/docs/api/post/2/ai/%7Bproduct_id%7D/openai/v1/chat/completions) exposes text and model-dependent image content rather than a PDF-file upload field. The UI reports the batch count and full coverage. Confirm your server's input/output limits and JSON-mode support. Connection success is only a connectivity check; a real cited analysis must still pass acceptance. For Docker, the endpoint must be reachable from the API container; its localhost is not the host machine.

Settings persist in PostgreSQL (or the explicitly selected SQLite trial database) and take precedence over APERTUS_* environment defaults. Keys saved through the app are stored server-side in this local workspace database, so protect its volumes and backups. Nothing is written to Git or browser storage. **Use environment defaults** removes the saved overrides, including a saved key, without changing document history.

Open **Prompt settings** to edit the instructions used for Impact, Ask Apertus, multi-batch synthesis, and the single structured-output repair attempt. Server-controlled schemas, citation checks, complete-evidence rules, and input separation remain fixed. Saving a prompt revision creates a new cache boundary without deleting earlier AI conclusions.

Changing settings through the interface needs no restart. Changes made directly to .env require an API restart, and saved overrides must be removed if those defaults should take effect. Changes to the endpoint, model, evidence warning threshold, or generation parameters mark previous analyses as stale; in-flight requests retain their original settings.

Edit **Company profile** from Settings to supply business context. Impact analysis and Ask Apertus need actual model responses with working evidence links for acceptance. When disconnected or unavailable, the UI says so and keeps the diff usable.

## The value proposition

Teams should not have to reread every regulatory document to find out whether an update matters to them. RegWatch connects three questions in one screen:

- **What changed?** Compare the previous and current versions, with added and removed text highlighted.
- **What does it mean?** Ask Apertus to explain the change and its possible impact on a simple company profile.
- **What should we do?** Get a short, prioritized action list grounded in the source text.

Start by validating 2-3 Swiss public sources and one company profile, but do not hard-code the source list. Users must be able to add another supported website or document without changing application code.

## The main workflow

1. **Connect a website.** Add a public website or a specific regulatory listing page. Preview the connection and the document links it exposes.
2. **Choose laws to monitor.** Search the discovered list by title or keyword, select a document, and save it to the watchlist. Alternatively, add a law directly using its HTML or PDF URL.
3. **Add an earlier version when needed.** Upload a previous PDF, HTML, or TXT file, paste its text, or provide a direct URL to an older copy. Preview it and attach it to the correct law.
4. **Run a check.** Select one law or the watchlist, choose the comparison baseline, and click **Scan now**. The app fetches the current document and shows progress through extraction, comparison, and Apertus analysis.
5. **Inspect what happened.** See which sources were checked, which documents changed, the exact old and new wording, and Apertus's explanation with supporting passages.
6. **Reuse AI history.** Open the saved conclusions and questions attached to the exact before/after comparison. Repeating an identical request with the same settings, prompts, profile, question, and conversation context reuses the stored result without another provider call.
7. **Inspect integrations when needed.** Open **Integration logs** to review the redacted request and response for website, Fedlex, Firecrawl, and model-provider calls, sort or filter the records, and clear the diagnostic history.

Connecting a website and monitoring a law are separate actions: a **source** is a website or listing page; a **tracked law** is a specific document with a current URL; a **version** is a saved snapshot of that document.

## MVP scope

| Feature | What the user can see and do |
| --- | --- |
| **Website connections** | Add, edit, or remove a public source URL or listing page, test extraction, and preview discovered document links. Removing a source detaches its tracked documents instead of deleting their evidence. |
| **Law discovery and watchlist** | Search discovered documents by title or keyword, add selected laws, or add a specific law directly by URL. Name, pause, resume, or permanently delete a tracked document and its saved history through the interface. |
| **Import previous version** | Upload a PDF, HTML, or TXT file, paste text, or fetch a historical copy by URL. Review the extracted text, attach it to a law, and optionally record its stated version date. |
| **Dashboard** | See connected sources, tracked laws, last scan times, changes, and impact indicators. Distinguish newly discovered documents, changed documents, unchanged documents, and failures. |
| **Scan now** | Check one law or the watchlist, with per-document progress and a final summary. A first fetch without a prior version establishes a baseline. A background scheduler is not required. |
| **Version detection and history** | Extract and normalize text, compare a content hash, and preserve version history. Choose an earlier snapshot for comparison without replacing the latest successfully observed version. |
| **Visual diff** | Choose old and new versions and see added, removed, and modified passages. Show side-by-side text, inline word highlights, a list of changes, and links to the saved evidence and original source. |
| **Apertus impact analysis** | Analyse every changed passage in the complete saved comparison; generate a concise summary, why it matters, affected business areas, an indicative high/medium/low impact, and 1-3 suggested actions. Keep supporting passages visible. |
| **Settings** | Choose Infomaniak, the local Docker Apertus service, or another OpenAI-compatible provider; configure Product ID/endpoint, server-side credential handling, an API-loaded model dropdown, timeout, automatic retries, concurrent batch limit, evidence threshold, completion length, temperature, Top P, presence penalty, reasoning effort, and JSON mode. Test unsaved values, save without restarting, restore environment defaults, and edit the company profile. |
| **Prompt settings** | Edit Impact, Ask, synthesis, and repair instructions from the interface. Choose automatic full-document context or changed passages only for general questions. Save revisions without weakening the server-owned JSON schemas, evidence rules, or citation validation. |
| **Integration logs** | Review outbound website, Fedlex, Firecrawl, and Apertus/Infomaniak requests and responses, including HTTP status, duration, payload sizes, and errors. Sort, filter, inspect details, and clear logs. Credentials, cookies, token fields, and matching secret values are redacted before persistence; large payloads are bounded and binary documents are represented by metadata and a hash. |
| **Ask Apertus with citations** | Ask questions about the selected comparison. Questions about what changed use the complete deterministic diff; other questions use every extracted passage from both saved original versions by default. Cite the exact saved version and passage, including a PDF page where available. |
| **AI history and cache** | Keep successful and failed Impact runs, questions, answers, timestamps, model IDs, prompt revisions, coverage, and exact comparison attributes. Reopen citations and original artifacts; reuse an identical successful request without spending more provider tokens. |
| **Optional: impact matrix** | Show changes against business areas such as HR, IT, Legal, and Operations, with an indicative priority and a short reason. Add only if the core demo is complete. |

Impact labels and suggested actions are AI-generated aids for review, not authoritative legal conclusions. Users can check the linked source before acting.

Integration logs are local troubleshooting records, not an enterprise audit system. List responses omit heavy payloads; full redacted request/response details load only when opened. Clearing logs does not alter sources, documents, versions, scans, comparisons, AI history, prompts, or provider settings. Deleting a connected website leaves its documents monitored independently. Deleting a monitored document is permanent and removes its versions, observations, comparisons, Impact analyses, saved questions and answers, scan entries, and unreferenced artifact files; an active scan must finish first.

## Connecting real sources

The first implementation supports public HTML pages, text-based PDFs, and plain text. Discovery fetches one listing page and inspects at most 50 distinct direct links within the configured host/path boundary. Direct PDF/TXT links are prioritised before applying that limit, and common navigation is excluded. Direct document URLs bypass discovery.

Results show extracted titles, actual content types and previews, or an individual error. Filtering covers titles, URLs, and the stored preview text of returned candidates; it is not full-site search. The interface shows inspected/verified/failed counts and any limits reached. Up to three candidates are processed at once, with a 120-second total inspection budget. Unfinished candidates remain visible and can be previewed separately. **Preview & add** confirms a selected document before creating its first live snapshot. A new link is not evidence of a legal amendment.

See [source compatibility notes](docs/SOURCES.md) for real examples. Native extraction does not render arbitrary JavaScript. FINMA's circulars page returns static text, but its dynamic list is not fully available. Fedlex ELI law URLs are handled specially: RegWatch queries the official Fedlex Linked Data endpoint, resolves the latest applicable publication in the selected language, prefers HTML, and falls back to the official display/print PDF. An ELI URL containing an explicit version date or format remains pinned to it. The stable ELI URL stays on the watchlist while each snapshot records the resolved expression, manifestation, version date, format, and file URL. No change to the Add law → Preview document → Add to watchlist flow is required.

Native Fedlex resolution recognises Classified Compilation (`cc`), Official Compilation (`oc`), and Federal Gazette (`fga`) ELI URLs. URLs may end in `de`, `fr`, `it`, `rm`, or `en`; a bare language-neutral work URL deterministically selects German, while an explicit language is preserved. The selected language must actually exist. Other JavaScript routes and search pages still require a supported direct document URL. If Fedlex metadata or its publication file is unavailable, the preview/scan fails explicitly and the last good snapshot remains unchanged. A successful extraction does not establish complete legal coverage.

Source support is layered by platform, not hard-coded one law at a time. Ordinary public HTML and PDF URLs use the generic extractor. A platform adapter is only needed when a publisher exposes a JavaScript shell or a special document registry; the Fedlex adapter covers the supported `cc`, `oc`, and `fga` ELI URL patterns as a group. Adding another law within those patterns requires no code change. A genuinely different publishing platform may need one bounded adapter for that platform rather than a patch for every document URL.

Use reasonable fetch timeouts and download limits. If a page requires unsupported JavaScript rendering, authentication, or OCR, show a clear limitation and allow a direct PDF URL or a manual import where appropriate. An imported snapshot alone does not provide live monitoring: a reachable current document URL is still needed. Never report an empty or failed extraction as a successful check.

Current defaults: 8 MB per document, 25 seconds per source request, 1,000 PDF pages, 1.2 million extracted characters, 6,000 passages, and 25 documents per scan. Whitespace is normalised; changed words, numbers, and dates remain visible. Complex layouts and page headers can create extraction noise, so inspect previews. Optional Firecrawl requires your own server-side key and usable quota; its live path is not validated in this environment.

The API uses one process and one worker. Do not add multiple API replicas or workers: coordination and restart recovery are local to that service. The app binds to loopback and has no user authentication. It is for a local hackathon workspace, not unattended public hosting.

## Previous versions and a reproducible demo

Historical imports are a normal product feature. They let users start monitoring with a known earlier version instead of waiting for a source to change after the first scan.

- Keep the import or fetch timestamp separate from the document's stated version date. A user-entered date is labeled as supplied by the user, not verified automatically.
- Preserve provenance for every snapshot: live fetch, uploaded file, pasted text, or historical URL. Imported content is not automatically an official historical version.
- Let the user confirm that the imported text belongs to the selected law and choose it as the baseline for a comparison.
- Keep snapshots immutable. Importing an older version must not reset the latest successfully observed version or rewrite previous scan results.
- For ordinary monitoring, compare a newly fetched version with the last successfully observed version. With an explicitly selected historical baseline, compare against that baseline instead.
- If today's content is already saved, reuse that snapshot. An explicit historical comparison must still run even when the live content has not changed since the last scan; it must not create duplicate document snapshots.
- Label the result **historical comparison** when appropriate. Differences against an imported baseline must not appear as amendments newly discovered since the last live check.

A complete demonstration uses the real workflow:

1. Add a real current law URL and preview the extracted text.
2. Import an older copy of that law and select it as the comparison baseline.
3. Click **Scan now** to fetch the current source and compare it with the selected earlier version.
4. Watch the actual stages: **Fetching -> Extracting -> Comparing -> Analysing -> Complete**. Show counts and errors from the real run, without simulated progress.
5. Open the changed passages, inspect the before/after wording, and read Apertus's impact and action summary.
6. Ask **"What changed for our company, and which passage supports that?"** and open the cited evidence.

This can be repeated without changing the external website or resetting history. Prefer an authentic older document; if a snapshot is edited for demonstration, visibly label it **synthetic demo data**. If the network is unavailable, offer an explicitly labeled **Compare saved versions** action through the same comparison engine, without claiming a live scan occurred.

## What the user sees

- **Sources and watchlist:** website connection, document discovery, direct law entry, source status, and the next action.
- **Scan activity:** the current stage for each law, completed/total counts, and separate changed, unchanged, baseline-created, and failed results. Analysis failure remains visible even if fetching and comparison succeeded.
- **Law detail and version history:** the current source link, saved versions with provenance and dates, an **Import previous version** action, and old/new version selectors.
- **Comparison view:** a change list, side-by-side old/new text, red removals, green additions, and inline word highlights. Clicking a change moves both panes to the relevant passage. Show version labels and a text legend as well as colors.
- **Apertus panel:** summary, possible business impact, proposed actions, and Ask Apertus. Citations open the relevant saved passage or PDF page so users can verify the analysis.

For example, a clearly synthetic demo could replace **"within 30 days"** with **"within 60 days"**. The interface should highlight **30 -> 60** in the actual document comparison, not merely display a card saying that something changed.

## Proposed stack

| Layer | Choice | Role in the MVP |
| --- | --- | --- |
| Web app | **Next.js** | Source setup, law watchlist, scan activity, version history, diff view, and question interface. |
| Styling and components | **Tailwind CSS + shadcn/ui** | Build a polished, consistent interface quickly. |
| Backend | **FastAPI** | Discover document links, fetch sources, import versions, expose scan progress, compare text, and serve analysis and questions. |
| Database | **PostgreSQL** | Persist sources, tracked laws, immutable document snapshots, scans, comparisons, and saved analyses. |
| Language model | **Apertus v1.5 8B** | Proposed target for impact analysis and cited answers, through one configurable inference endpoint. |
| Content extraction | **BeautifulSoup + PyMuPDF** | Extract text from HTML and text-based PDFs. |
| Diff engine | **Python `difflib`** | Compare normalized passages and produce word highlights for the visual comparison. |
| Optional retrieval | **pgvector** | Consider retrieval only for future corpus-wide questions. It must never replace the complete deterministic diff for a selected comparison. |

The adapter, settings interface, cited analysis, and large-diff batching have been verified against a served Apertus endpoint. Hosting or choosing a model provider remains a separate setup choice, not another product feature.

## Keep the implementation small

Use one Next.js app, one FastAPI service, one PostgreSQL database, and one Apertus endpoint.

The core pipeline is:

```text
User-configured website -> discover documents -> user selects tracked law
Direct law URL --------------------------------------> tracked law

Tracked law -> fetch current HTML/PDF -> extract text -> current snapshot
Earlier file/text/URL ----------------> extract text -> imported snapshot

Selected baseline + current snapshot
  -> compute passage and word differences
  -> show the visual diff
  -> ask Apertus for impact, actions, and cited answers
```

- Keep the initial data model small: **Source, TrackedLaw, DocumentVersion, Scan, Comparison**, and saved analysis attached to a comparison. A comparison explicitly references its old and new version IDs.
- Store source URLs or file provenance, fetch/import times, extracted text, content hashes, and paragraph/page references. Preserve imported artifacts and enough snapshot content to reopen cited evidence after a live page changes; local persistent file storage is sufficient for a single deployment.
- Normalize whitespace and remove obvious navigation boilerplate while preserving substantive dates, headings, article numbers, and legal wording. Show an extraction preview so users can spot unsuitable input.
- A failed fetch or extraction must not replace the last good version. A failed analysis must not hide a valid diff or be reported as a completed analysis.
- Persist a versioned deterministic article/passage diff that covers every passage in both saved versions. Pass every changed old/new passage to Apertus without retrieval ranking or truncation. Validate structured output and citations, then allow one constrained repair request for invalid JSON/schema/citations before rejecting it.
- Attach stable passage references during extraction so displayed citations map to saved evidence. Distinguish source-stated dates from dates supplied by users.
- Save analysis results for each version pair so opening the same change does not regenerate the summary every time.
- Process small scan batches in the FastAPI service and expose actual per-stage status to the interface. Record interruptions as incomplete runs. A separate worker fleet, distributed queue, or orchestration framework is not needed for this scope.

## Build order

- [x] Implement persistent source and law management, including direct document URLs.
- [x] Add real HTML/PDF fetching, extraction previews, and bounded document discovery.
- [x] Add previous-version import, immutable snapshots, and explicit baseline selection.
- [x] Implement live scanning with real progress, version detection, and repeatable historical comparisons.
- [x] Render the version history and visual diff with passage navigation and word highlights.
- [x] Add persisted Apertus settings, a real connection check, and company context in the interface.
- [x] Connect Apertus and display an impact summary with suggested actions and evidence.
- [x] Add Ask Apertus with working citations.
- [x] Verify the complete workflow with real supported sources and an imported previous version, then rehearse the demo through that same workflow.
- [ ] If time remains, add the impact matrix and assess whether pgvector is actually needed.

## Definition of done

- A user can connect a supported website, discover documents, and track a law without editing code. Direct HTML/PDF law URLs also work independently of discovery.
- Sources, tracked laws, version history, and scan results survive an application restart.
- A user can import a previous version, choose it as a baseline, fetch the current source, and inspect exact text changes with an Apertus explanation and a cited follow-up answer.
- Running an explicit historical comparison again works even when the current live snapshot is unchanged; it does not create duplicate snapshots or claim a newly detected live amendment.
- An ordinary scan of unchanged content creates no duplicate document version. A first scan without a baseline is labeled **Baseline created**.
- Failed fetching, unsupported input, empty extraction, and unavailable model responses have clear, distinct outcomes. None silently overwrite the last good snapshot or masquerade as success.
- A citation opens evidence from the actual version used in the answer, including an imported version when relevant.

A dashboard with preset change cards or a scan button that only plays an animation does not meet this definition.

## Not in this MVP

- Enterprise SSO, multi-tenancy, granular roles, audit-log platforms, or compliance certification infrastructure.
- Exhaustive website crawling, universal site compatibility, complex schedules, distributed workers, or a large ingestion platform.
- Knowledge graphs, autonomous agent frameworks, or training/fine-tuning a model.
- OCR for scanned PDFs, login-gated sources, exhaustive jurisdiction coverage, or automatic legal decisions.

Keep website connections, law management, previous-version import, real scanning, and visible comparisons in the core scope. Add infrastructure only when a demonstrated need justifies it.
