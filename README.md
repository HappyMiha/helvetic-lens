# Helvetic Lens

**See what changed. Understand what matters.**

Helvetic Lens lets users connect regulatory websites, add specific laws or documents to a watchlist, import earlier versions, and run real checks against current source content. It turns detected differences into visual comparisons, plain-language impact summaries, and practical next steps with links back to the evidence. The next public release expands that proven workflow into a Swiss legal registry that discovers official laws, parliamentary business, court decisions, and their evidence-backed possible effects on monitored documents.

The MVP must be a functional product with a narrow scope. Sources are configured through the interface, data persists between sessions, and the demonstration uses the same fetching, comparison, and analysis pipeline as everyday use.

> **Project status:** The model-enabled MVP works end to end: source connections, direct URLs, imports, immutable history, live scans, saved comparisons, visual evidence, persisted Apertus settings, impact analysis, cited questions, saved AI history, editable prompts, inspectable integration logs, and controlled removal of sources or monitored documents. Scans and AI work now use durable PostgreSQL jobs with Redis/Celery workers, persisted stages, cancellation, retry, result links, and restart recovery. The current triage layer keeps the complete exact comparison for inspection, separates likely material wording from formatting and renumbering noise, blocks obvious document mismatches, and gives AI a fixed-size evidence dossier instead of starting one request per passage. See [verification notes](docs/VERIFICATION.md) and the [AI triage contract](docs/AI_TRIAGE.md).

> **Public-beta direction:** Local AI becomes the default and cloud providers become explicit optional adapters. The target remains one physical i7/32 GB/two-GTX-1080 server and one Compose deployment. Durable jobs, managed quantized models, account sessions, enforced organization roles, the normalized regulatory corpus, time-grouped registry, three official-source connectors, and persisted scheduled synchronization are implemented; complete German/French/Italian/Romansh/English localization, official notices, and an impact inbox follow in the backlog. See the [architecture decision](docs/ARCHITECTURE.md) and `HL-029`–`HL-049` plus `HL-057` in [BACKLOG.md](BACKLOG.md).

Development tasks, priorities, dependencies, and acceptance criteria are tracked in [BACKLOG.md](BACKLOG.md).

## Run locally

Use Docker Desktop with Compose for the complete PostgreSQL stack:

```sh
git clone https://github.com/HappyMiha/helvetic-lens.git
cd helvetic-lens
docker compose up --build -d
```

Open [Helvetic Lens](http://127.0.0.1:3000) and the [API reference](http://127.0.0.1:8000/docs). PostgreSQL, Redis, and saved artifacts use persistent volumes. Migrations run on API startup. Default loopback ports are 3000 (web), 8000 (API), 54329 (database), and 63799 (Redis); stop development processes using those ports before starting Compose.

Local development keeps the existing anonymous workspace when `APP_ENVIRONMENT=development` and `ALLOW_ANONYMOUS_DEV=true`. Set `APP_ENVIRONMENT=production`, `ALLOW_ANONYMOUS_DEV=false`, and `SESSION_COOKIE_SECURE=true` for an internet-facing deployment. Production startup rejects anonymous mutation or insecure session cookies. Registration creates an isolated organization even when another user types the same organization name; an empty name creates a personal workspace. Passwords use Argon2id, sessions are random, revocable, PostgreSQL-backed cookies, and browser mutations require the matching CSRF cookie/header. Registration issues a 24-hour email-verification link; the sign-in page provides a non-enumerating 30-minute password-reset link that works once and revokes all active sessions. See [authentication notes](docs/AUTHENTICATION.md) and the [account recovery runbook](docs/ACCOUNT_RECOVERY.md).

Open **Organization** to invite a viewer or another administrator with a seven-day, single-use link bound to the invited email. Viewers can inspect the complete shared workspace but cannot add, edit, delete, scan, ask AI, reanalyse, or change settings. Promote another administrator or use the explicit handover action before removing the current administrator. Platform-wide model controls require a separately assigned platform administrator.

```sh
docker compose exec api helvetic-lens-admin list
docker compose exec api helvetic-lens-admin promote owner@example.ch
docker compose exec api helvetic-lens-admin demote owner@example.ch
```

The CLI is idempotent, writes a minimal security event, and refuses to remove the last platform administrator. It only changes platform duties; the account must still be an explicit member to access an organization's data.

The rebrand keeps existing PostgreSQL data, local SQLite history, document artifacts, and the downloaded local Apertus model. Legacy storage and environment aliases are accepted only for upgrade compatibility; new configuration uses the `HELVETIC_LENS_*` names shown in [.env.example](.env.example).

No model or paid extraction service is required for source monitoring and visual comparisons. Open **Settings → Apertus** to configure your inference endpoint in the app. [.env.example](.env.example) also provides optional server defaults. Never commit .env, credentials, or runtime data.

For development, install Node.js 22+ (tested with 24), Python 3.11+, and uv. Create .env from the example and set DATABASE_URL to the following before starting:

```text
postgresql+psycopg://helvetic_lens:helvetic_lens@127.0.0.1:54329/helvetic_lens
```

```sh
npm ci
uv sync --project services/api --frozen
docker compose up -d db
npm run dev
```

Set `JOB_EXECUTION_MODE=inline` for this lightweight two-process development command. The development API stores artifacts under data/. If DATABASE_URL is deliberately left empty, it uses local SQLite for a lightweight trial; Compose always uses PostgreSQL and durable workers. Do not run both API variants against the same database with different artifact directories.

```sh
npm run typecheck
npm run format:check
npm run build
npm run lint:api
npm run test:api
```

[Follow the demo guide](docs/DEMO.md) to connect a site, import an older version, fetch current content, and inspect the exact **30 → 60** wording change.

## Current MVP inference options

The current MVP can use local Docker, Infomaniak, or another compatible endpoint. The public-beta target makes a managed local quantized Apertus deployment the normal path; cloud use remains an explicit organization-level opt-in and is never a silent fallback. The intended larger model is [Apertus v1.5 8B](https://huggingface.co/swiss-ai/Apertus-v1.5-8B), subject to the measured GTX 1080 compatibility gate. The served ID depends on the runtime/provider. Model weights are not bundled and no alternate model is silently substituted.

Open [Settings](http://127.0.0.1:3000/settings) from the sidebar or mobile navigation:

1. Choose **Infomaniak AI**, **Local Docker Apertus**, or **Other OpenAI-compatible API**. Infomaniak needs its numeric Product ID; the local Compose service is resolved automatically for host or container execution; the custom option needs the API base URL, including /v1 if required. Do not append /chat/completions; Helvetic Lens adds it.
2. Keep the existing credential, replace it, use no credential for an unauthenticated local server, or inherit the server environment value. A saved token/key is never returned to the browser, including in validation errors.
3. Adjust the request timeout, automatic retry count, concurrent batch limit, evidence warning threshold, maximum completion length, temperature, Top P, presence penalty, reasoning effort, and optional JSON mode. Helvetic Lens keeps `stream=false` and `n=1` fixed so structured answers and citations can be validated consistently. The default processes one large-model batch at a time and retries temporary transport, timeout, rate-limit, and 5xx failures twice.
4. For Infomaniak, choose **Load models** to populate the dropdown from the current Product ID. Choose **Test connection** to make an actual request with the form's current values without saving, then **Save settings** to apply them immediately.

For **Public AI**, choose **Use Public AI defaults** to fill `https://api.publicai.co/v1` and `swiss-ai/apertus-v1.5-8b`. This changes only those two draft fields, not the key or other parameters, and does not save automatically. Use an API key created in the provider's developer portal, rather than a chat login credential. Helvetic Lens includes the required User-Agent header. These connection values follow the [Public AI quick start](https://platform.publicai.co/docs).

For **Hugging Face Inference Providers**, choose **Use Hugging Face** to fill `https://router.huggingface.co/v1` and `swiss-ai/Apertus-v1.5-8B:publicai`. Use a [Hugging Face access token](https://huggingface.co/settings/tokens) with Inference Providers permission; it is different from a direct Public AI key. The suffix selects Public AI as the provider through Hugging Face, without changing the requested Apertus model. The preset only edits draft fields and never sends the current key anywhere automatically. This configuration follows the [model card](https://huggingface.co/swiss-ai/Apertus-v1.5-8B) and [Hugging Face provider documentation](https://huggingface.co/docs/inference-providers/providers/publicai); successful inference still requires valid access and available account quota. A Hugging Face model-page URL is not an API base URL.

For **Infomaniak AI**, choose **Infomaniak AI**, enter the numeric Product ID and a product-authorized API token, then choose **Load models**. Helvetic Lens derives `https://api.infomaniak.com/2/ai/{product_id}/openai/v1`, calls the provider's [`/models` endpoint](https://developer.infomaniak.com/docs/api/get/2/ai/%7Bproduct_id%7D/openai/v1/models), and fills the model dropdown with the IDs actually available to that product. Completion requests follow Infomaniak's [OpenAI-compatible chat endpoint](https://developer.infomaniak.com/docs/api/post/2/ai/%7Bproduct_id%7D/openai/v1/chat/completions) and use `max_completion_tokens`. The generated endpoint is read-only in the interface, preventing small URL edits from producing a broken route.

Open **Local models** to inspect the host, accept a model license for an exact immutable revision, and download, pause, resume, verify, start, stop, or remove an allowlisted Apertus GGUF. Transfers run in the durable maintenance queue, use `.part` files, check free space and SHA-256, and activate atomically. The private manager owns the pinned CUDA llama.cpp runtime and model volume; the public API receives neither a Docker socket nor an arbitrary model URL/command. Local inference is the clean-install default. Infomaniak and custom OpenAI-compatible providers are explicit settings, never silent fallbacks. The current catalogue includes a measured 1.5B Q4 development profile for the GTX 1070 and an 8B Q4 candidate that remains blocked until it passes the dual-GTX-1080 benchmark.

For a terminal smoke test, run `./scripts/local_apertus.ps1`. It starts the manager, adopts a compatible cached artifact when available (otherwise resumes its pinned download), verifies its hash, starts it on GPU, and checks an actual structured `{"status":"ok"}` response. Every application request uses the stable gateway at `http://127.0.0.1:12436/openai/v1` on the host or `http://model-manager:8090/openai/v1` inside Compose. Runner ports stay private inside the model container and can change when the manager selects `dev-1070`, `dual-1080-replicated`, `dual-1080-split`, or `cpu-degraded`. AI jobs wait visibly while a verified local model starts or warms up.

Connection errors distinguish a rejected key (401), denied model access (403), an incorrect route/model (404), rate limit or quota (429), an unreachable server, a timeout, and a request that exceeds the model context window. Context-limit failures are not retried unchanged. Every useful retry is visible as a separate redacted integration-log entry. Provider response bodies and credentials are not echoed to the browser.

The evidence threshold is a character-based request target, not the endpoint's exact token window. Helvetic Lens always preserves the complete deterministic comparison as the inspectable audit layer. Before inference, it saves an inspectable fixed-budget plan with selected change IDs, inclusion reasons, context fingerprint, token estimates, coverage, and expected calls. Interactive AI receives a bounded dossier that prioritizes likely material or uncertain changes and excludes detected formatting and renumbering noise. Impact can make at most five provider calls and Ask at most three, including repair/synthesis; formatting/structural-only comparisons use zero model calls. Small documents may fit in one request; large comparisons use a small fixed number of coherent batches and report limited AI coverage honestly. General document questions use both complete saved versions only when they fit, otherwise they use question-matched passages with adjacent context. Vague comments return immediate clarification choices without sending the document to the model. See [the planner contract](docs/AI_ANALYSIS_PLANNER.md).

Existing snapshots stay immutable. A comparison created from an older extractor can be re-diffed with the new classifier, but it cannot recover PDF line breaks that were not retained in that snapshot. Re-import the historical artifact and run a fresh scan to receive the v3 PDF line-wrap repair on both sides.

The original PDF/HTML/TXT artifacts remain downloadable, but Helvetic Lens does not claim to attach raw PDFs to an Apertus chat model: Infomaniak's documented [chat completion contract](https://developer.infomaniak.com/docs/api/post/2/ai/%7Bproduct_id%7D/openai/v1/chat/completions) exposes text and model-dependent image content rather than a PDF-file upload field. Sending the extracted structure also keeps citations tied to exact saved evidence. The UI reports which material items entered the dossier, what was suppressed as technical noise, and how many planned model calls were used. Confirm your server's input/output limits and JSON-mode support. Connection success is only a connectivity check; a real cited analysis must still pass acceptance. For Docker, the endpoint must be reachable from the API container; its localhost is not the host machine.

Settings persist in PostgreSQL (or the explicitly selected SQLite trial database) and take precedence over APERTUS_* environment defaults. Keys saved through the app are stored server-side in this local workspace database, so protect its volumes and backups. Nothing is written to Git or browser storage. **Use environment defaults** removes the saved overrides, including a saved key, without changing document history.

Open **Prompt settings** to edit the instructions used for Impact, Ask Apertus, multi-batch synthesis, and the single structured-output repair attempt. Server-controlled schemas, citation checks, complete-evidence rules, and input separation remain fixed. Saving a prompt revision creates a new cache boundary without deleting earlier AI conclusions.

Changing settings through the interface needs no restart. Changes made directly to .env require an API restart, and saved overrides must be removed if those defaults should take effect. Changes to the endpoint, model, evidence warning threshold, or generation parameters mark previous analyses as stale; in-flight requests retain their original settings.

Edit **Company profile** from Settings to supply business context. Impact analysis and Ask Apertus need actual model responses with working evidence links for acceptance. When disconnected or unavailable, the UI says so and keeps the diff usable.

## The value proposition

Teams should not have to reread every regulatory document to find out whether an update matters to them. Helvetic Lens connects three questions in one screen:

- **What changed?** Compare the previous and current versions, with added and removed text highlighted.
- **What does it mean?** Ask Apertus to explain the change and its possible impact on a simple company profile.
- **What should we do?** Get a short, prioritized action list grounded in the source text.

AI is used as a regulatory triage assistant, not as a more expensive line-diff renderer. Deterministic code establishes which saved documents are being compared, preserves every exact difference, and removes changes that are clearly page layout or numbering. Apertus then explains the compact set of meaningful changes, tests their possible relevance against the organization profile, and proposes a review action only when the evidence supports one. Free-form questions are a drill-down after this report; unclear input is turned into useful choices instead of triggering a full-document run.

For a very small law, placing both extracted versions in one request is reasonable. A large Swiss act can exceed the local model's context by orders of magnitude, so attaching two PDFs does not make the analysis complete or reliable. The scalable unit is a cited article or change cluster, with the two original files always one click away for verification.

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

| Feature                           | What the user can see and do                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Website connections**           | Add, edit, or remove a public source URL or listing page, test extraction, and preview discovered document links. Removing a source detaches its tracked documents instead of deleting their evidence.                                                                                                                                                                                                                                                                |
| **Law discovery and watchlist**   | Search discovered documents by title or keyword, add selected laws, or add a specific law directly by URL. Name, pause, resume, or permanently delete a tracked document and its saved history through the interface.                                                                                                                                                                                                                                                 |
| **Import previous version**       | Upload a PDF, HTML, or TXT file, paste text, or fetch a historical copy by URL. Review the extracted text, attach it to a law, and optionally record its stated version date.                                                                                                                                                                                                                                                                                         |
| **Dashboard**                     | See connected sources, tracked laws, last scan times, changes, and impact indicators. Distinguish newly discovered documents, changed documents, unchanged documents, and failures.                                                                                                                                                                                                                                                                                   |
| **Scan now**                      | Submit a durable job for one law or the watchlist, with queue position, persisted per-document progress, cancellation/retry, and a final result link. A first fetch without a prior version establishes a baseline.                                                                                                                                                                                                                                                    |
| **Version detection and history** | Extract and normalize text, compare a content hash, and preserve version history. Choose an earlier snapshot for comparison without replacing the latest successfully observed version.                                                                                                                                                                                                                                                                               |
| **Visual diff**                   | Choose old and new versions and see added, removed, and modified passages. Show side-by-side text, inline word highlights, a list of changes, and links to the saved evidence and original source.                                                                                                                                                                                                                                                                    |
| **Apertus impact analysis**       | Preserve the complete exact comparison, exclude detected layout/renumbering noise from inference, and analyse a fixed-budget dossier of likely material changes. Generate a concise summary, possible relevance, affected business areas, an indicative high/medium/low impact, and up to five distinct evidence-backed review actions. Zero actions is a valid result.                                                                                               |
| **Settings**                      | Choose Infomaniak, the local Docker Apertus service, or another OpenAI-compatible provider; configure Product ID/endpoint, server-side credential handling, an API-loaded model dropdown, timeout, automatic retries, concurrent batch limit, evidence threshold, completion length, temperature, Top P, presence penalty, reasoning effort, and JSON mode. Test unsaved values, save without restarting, restore environment defaults, and edit the company profile. |
| **Prompt settings**               | Edit Impact, Ask, synthesis, and repair instructions from the interface. Choose automatic full-document context or changed passages only for general questions. Save revisions without weakening the server-owned JSON schemas, evidence rules, or citation validation.                                                                                                                                                                                               |
| **Integration logs**              | Review outbound website, Fedlex, Firecrawl, and Apertus/Infomaniak requests and responses, including HTTP status, duration, payload sizes, and errors. Sort, filter, inspect details, and clear logs. Credentials, cookies, token fields, and matching secret values are redacted before persistence; large payloads are bounded and binary documents are represented by metadata and a hash.                                                                         |
| **Ask Apertus with citations**    | Ask questions about the selected comparison. Change questions use the deterministic material-change dossier; small general questions can use both complete versions, while large ones use a bounded relevant passage set with neighbours. Vague input returns suggested intents with zero model calls. Cite the exact saved version and passage, including a PDF page where available.                                                                                |
| **AI history and cache**          | Keep successful and failed Impact runs, questions, answers, timestamps, model IDs, prompt revisions, coverage, and exact comparison attributes. Reopen citations and original artifacts; reuse an identical successful request without spending more provider tokens.                                                                                                                                                                                                 |
| **Organizations and roles**       | Register an isolated workspace, invite members with expiring one-time links, share watchlists and evidence, switch memberships, and enforce administrator or read-only viewer access in both API and UI. Platform model administration remains a separate audited assignment.                                                                                                                                 |
| **Normalized regulatory corpus**  | Keep one authority-level work across languages and immutable versions, retain ELI/SR/RS/business/docket identifiers, preserve official-date precision and provenance, record only evidence-backed lifecycle events, and version confirmed or proposed cross-document relations. Existing direct-URL monitoring remains compatible through explicit provisional mappings.                                                      |
| **Regulatory registry**           | Browse monitored documents or all discovered events in stable Europe/Zurich time groups, search and filter the saved corpus, distinguish detection time from official legal dates, and open evidence, comparisons, or the complete document timeline without waiting for a connector or model.                                                                                                                       |
| **Official connectors**           | Run Fedlex, Parliament, Federal Supreme Court, and Federal Criminal Court adapters through the same versioned discovery, metadata, expression, artifact, relation, and health boundary. The two court adapters preserve their actual official HTML or PDF evidence, stable case identifiers, dates, language, hierarchy, and exact legal references. Each source reports its own coverage limits and degrades on drift without inventing legal state. |
| **Source synchronization**        | Schedule all 23 official connector streams through durable PostgreSQL jobs and the Redis/Celery ingest queue. Platform administrators can inspect health, cursors, freshness and run counts, edit intervals, jitter and Swiss-time windows, pause/resume a stream, or choose **Sync now**. Backpressure bounds active runs, pending ingest work, and minimum free artifact space. |
| **Optional: impact matrix**       | Show changes against business areas such as HR, IT, Legal, and Operations, with an indicative priority and a short reason. Add only if the core demo is complete.                                                                                                                                                                                                                                                                                                     |

Impact labels and suggested actions are AI-generated aids for review, not authoritative legal conclusions. Users can check the linked source before acting.

Integration logs are local troubleshooting records, not an enterprise audit system. List responses omit heavy payloads; full redacted request/response details load only when opened. Clearing logs does not alter sources, documents, versions, scans, comparisons, AI history, prompts, or provider settings. Deleting a connected website leaves its documents monitored independently. Deleting a monitored document is permanent and removes its versions, observations, comparisons, Impact analyses, saved questions and answers, scan entries, and unreferenced artifact files; an active scan must finish first.

## Connecting real sources

The first implementation supports public HTML pages, text-based PDFs, and plain text. Discovery fetches one listing page and inspects at most 50 distinct direct links within the configured host/path boundary. Direct PDF/TXT links are prioritised before applying that limit, and common navigation is excluded. Direct document URLs bypass discovery.

Results show extracted titles, actual content types and previews, or an individual error. Filtering covers titles, URLs, and the stored preview text of returned candidates; it is not full-site search. The interface shows inspected/verified/failed counts and any limits reached. Up to three candidates are processed at once, with a 120-second total inspection budget. Unfinished candidates remain visible and can be previewed separately. **Preview & add** confirms a selected document before creating its first live snapshot. A new link is not evidence of a legal amendment.

See [source compatibility notes](docs/SOURCES.md) for real examples. Native extraction does not render arbitrary JavaScript. FINMA's circulars page returns static text, but its dynamic list is not fully available. Fedlex ELI law URLs are handled specially: Helvetic Lens queries the official Fedlex Linked Data endpoint, resolves the latest applicable publication in the selected language, prefers HTML, and falls back to the official display/print PDF. An ELI URL containing an explicit version date or format remains pinned to it. The stable ELI URL stays on the watchlist while each snapshot records the resolved expression, manifestation, version date, format, and file URL. No change to the Add law → Preview document → Add to watchlist flow is required.

Native Fedlex resolution recognises Classified Compilation (`cc`), Official Compilation (`oc`), and Federal Gazette (`fga`) ELI URLs. URLs may end in `de`, `fr`, `it`, `rm`, or `en`; a bare language-neutral work URL deterministically selects German, while an explicit language is preserved. The selected language must actually exist. Other JavaScript routes and search pages still require a supported direct document URL. If Fedlex metadata or its publication file is unavailable, the preview/scan fails explicitly and the last good snapshot remains unchanged. A successful extraction does not establish complete legal coverage.

Source support is layered by platform, not hard-coded one law at a time. Ordinary public HTML and PDF URLs use the generic extractor. A platform adapter is only needed when a publisher exposes a JavaScript shell or a special document registry; the Fedlex adapter covers the supported `cc`, `oc`, and `fga` ELI URL patterns as a group. Adding another law within those patterns requires no code change. A genuinely different publishing platform may need one bounded adapter for that platform rather than a patch for every document URL.

Use reasonable fetch timeouts and download limits. If a page requires unsupported JavaScript rendering, authentication, or OCR, show a clear limitation and allow a direct PDF URL or a manual import where appropriate. An imported snapshot alone does not provide live monitoring: a reachable current document URL is still needed. Never report an empty or failed extraction as a successful check.

Current defaults: 8 MB per document, 25 seconds per source request, 1,000 PDF pages, 1.2 million extracted characters, 6,000 passages, and 25 documents per scan. Whitespace is normalised; changed words, numbers, and dates remain visible. Complex layouts and page headers can create extraction noise, so inspect previews. Optional Firecrawl requires your own server-side key and usable quota; its live path is not validated in this environment.

The current Compose stack has PostgreSQL-backed durable jobs, Redis/Celery workers, organization-scoped authentication and roles, and a private managed inference endpoint. It still binds to loopback and lacks Caddy/TLS, a backup rehearsal, and a measured 100-user capacity result. Do not expose it publicly yet; see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Public beta uses three implemented bounded official connectors rather than patches for individual URLs:

| Coverage          | Planned machine path                                                                                  | Important boundary                                                                                                                                               |
| ----------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Swiss federal law | Implemented Fedlex RSS discovery plus ELI/SPARQL/JOLux reconciliation and official cross-law impacts | RSS is only a recent window; reconciliation is mandatory, and SR/RS number is an identifier rather than immutable identity.                                      |
| Parliament        | Implemented official affairs catalogue, recent-tail and known-active reconciliation, language records, status, documents, committees, sessions, and relation candidates | Older affairs can change, so active-item polling is combined with complete `(id, updated)` reconciliation and required attribution. |
| Court decisions   | Implemented Swiss Federal Supreme Court latest/date reconciliation plus Swiss Federal Criminal Court latest-list overlap | Supreme Court evidence remains official HTML with separate decision/insertion dates. Criminal Court evidence remains the court-linked PDF. Each connector exposes its narrower coverage; absence never means that no decision exists. |

Fedlex official lifecycle/impact metadata and exact citations are evaluated before any model proposal. Parliamentary initiatives and judgments are labelled by their actual status: a proposal is not enacted law, and a judgment may cite or interpret an act without rewriting its statutory text.

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

## Stack: current baseline and planned public beta

| Layer                        | Choice                                         | Status and role                                                                                                                                                                                                  |
| ---------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Web app                      | **Next.js**                                    | Implemented with registry, login, organization, evidence, comparison, model, prompt, and diagnostic views. Five-language localization and the impact inbox remain public-beta work.                                                                                           |
| Styling and components       | **Tailwind CSS + shadcn/ui**                   | Implemented; keeps the expanded interface consistent and accessible.                                                                                                                                             |
| Backend                      | **FastAPI**                                    | Implemented; remains one modular codebase used by the API, scheduler, and worker processes.                                                                                                                      |
| System of record             | **PostgreSQL**                                 | Durable jobs, organization-aware shared works, identifiers, expressions, versions, official dates, events, relations, connector cursors/checkpoints/receipts, users, memberships, sessions, and minimal security events are implemented.       |
| Queue and scheduler          | **Redis + Celery/Beat**                        | Implemented for durable scan and AI jobs with six queues, persisted steps, leases, retries, cancellation, recovery, and an Activity view. Concrete scheduled connector work expands in HL-039–HL-042.                     |
| Public entry point           | **Caddy**                                      | Planned; TLS and routing on ports 80/443 while data, workers, and inference stay private.                                                                                                                        |
| Local inference              | **llama.cpp + quantized Apertus**              | Managed downloads, a stable fair gateway, four measured-safe routing profiles, provenance, and local-first policy are implemented. Apertus 8B becomes default only after the dual-GTX-1080 benchmark. |
| Optional inference           | **Infomaniak/OpenAI-compatible adapters**      | Implemented; retained as explicit organization opt-ins, disabled on a clean public installation and never used as silent fallback.                                                                               |
| Content and comparison       | **BeautifulSoup + PyMuPDF + Python `difflib`** | Implemented; immutable extraction/evidence and complete deterministic comparisons remain the foundation.                                                                                                         |
| Optional candidate retrieval | **pgvector**                                   | Deferred until a labelled cross-document recall benchmark proves a material gap. It never replaces complete comparison evidence.                                                                                 |

## Keep one coherent deployment

Public beta stays in one repository and on one physical server. API, workers, scheduler, model manager, and inference runners are separate processes from the same deployment because their workloads and restart behavior differ; they are not independently operated product services.

The two evidence pipelines share the same corpus and rules:

```text
Direct URL / earlier artifact
  -> fetch -> immutable version -> deterministic comparison -> local Apertus -> cited result

Fedlex / Parliament / Federal Supreme Court / Federal Criminal Court
  -> incremental connector -> regulatory event -> exact identifier/full-text candidates
  -> local Apertus potential-impact review -> organization impact inbox -> cited evidence
```

- Preserve source URLs, official identifiers, raw artifacts, hashes, dates with provenance, stable passages/pages, and complete deterministic diffs. A failed source or model never overwrites the last valid evidence.
- Fetch and parse an official public version once, then attach organization watch state and company-specific analysis separately. Private uploads remain inside their organization.
- Persist every long command before queueing it. Redis may redeliver; database constraints and idempotency keys prevent duplicate legal records or conclusions.
- Keep local inference as the clean-install policy. If no model is ready, registry, evidence, timelines, and diffs still work and AI jobs wait visibly.
- Treat official lifecycle/link metadata as facts and model-generated relations as labelled proposals with validated citations.
- Tune connector concurrency, CPU extraction, model context, and GPU slots from measured results on the target host.

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
- [ ] **M6:** durable jobs, managed local models/GPU profiles, shared-corpus migration, login, organizations, enforced roles, and the five-locale catalogue/error/date foundation (`HL-029`–`HL-035`, start `HL-057`).
- [ ] **M7:** normalized registry plus incremental Fedlex, Parliament, Federal Supreme Court, scheduling, and official notices (`HL-036`–`HL-043`).
- [ ] **M8:** explainable relation candidates, local impact analysis, and organization impact inbox (`HL-044`–`HL-046`).
- [ ] **M9:** complete five-language UI/AI/history, administration, public single-server operations, recovery rehearsal, and measured 100-user gate (`HL-047`–`HL-049`, `HL-057`).
- [ ] Add broader news, pgvector, digests, graph review, identity refinements, more courts, or multi-host deployment only after their entry conditions (`HL-050`–`HL-056`).

## Definition of done

- A user can connect a supported website, discover documents, and track a law without editing code. Direct HTML/PDF law URLs also work independently of discovery.
- Sources, tracked laws, version history, and scan results survive an application restart.
- A user can import a previous version, choose it as a baseline, fetch the current source, and inspect exact text changes with an Apertus explanation and a cited follow-up answer.
- Running an explicit historical comparison again works even when the current live snapshot is unchanged; it does not create duplicate snapshots or claim a newly detected live amendment.
- An ordinary scan of unchanged content creates no duplicate document version. A first scan without a baseline is labeled **Baseline created**.
- Failed fetching, unsupported input, empty extraction, and unavailable model responses have clear, distinct outcomes. None silently overwrite the last good snapshot or masquerade as success.
- A citation opens evidence from the actual version used in the answer, including an imported version when relevant.

A dashboard with preset change cards or a scan button that only plays an animation does not meet this definition.

Public-beta acceptance additionally requires local-only clean-install behavior, model download/benchmark/recovery on the target GPUs, organization isolation and viewer authorization, restart-safe jobs, live contract checks for all three official connectors, correct time-grouped registry events, evidence-backed cross-links, complete `de-CH`/`fr-CH`/`it-CH`/`rm-CH`/`en-CH` browser and local-AI checks, and the checked-in 100-user scenario from `HL-049`.

## Product boundaries

- The current MVP remains a local single-workspace product until `HL-029`–`HL-049` and `HL-057` are implemented; its loopback Compose file is not a public deployment.
- Public beta adds two organization roles and a deployment administrator, not enterprise SSO, SCIM, arbitrary custom roles, or compliance certification.
- It adds bounded official connectors and scheduled workers, not an exhaustive crawler or a claim of universal Swiss legal coverage.
- It stores an evidence-backed relation graph as a data model, but a visual graph and pgvector wait for measured value.
- Kubernetes, multi-host workers, database/broker high availability, OCR, login-gated ingestion, model training/fine-tuning, and automatic legal decisions remain outside the public-beta release.

The complete task definitions, dependencies, acceptance gates, and explicitly deferred work live in [BACKLOG.md](BACKLOG.md).
