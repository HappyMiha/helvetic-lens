# Apertus RegWatch

**Know what changed. Know what it means. Know what to do.**

Apertus RegWatch lets users connect regulatory websites, add specific laws or documents to a watchlist, import earlier versions, and run real checks against current source content. It turns detected differences into visual comparisons, plain-language impact summaries, and practical next steps with links back to the evidence.

The MVP must be a functional product with a narrow scope. Sources are configured through the interface, data persists between sessions, and the demonstration uses the same fetching, comparison, and analysis pipeline as everyday use.

> **Project status:** This repository currently contains the MVP plan. The application and the features described below are not implemented yet.

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

Connecting a website and monitoring a law are separate actions: a **source** is a website or listing page; a **tracked law** is a specific document with a current URL; a **version** is a saved snapshot of that document.

## MVP scope

| Feature | What the user can see and do |
| --- | --- |
| **Website connections** | Add and edit a public source URL or listing page, test extraction, and preview discovered document links. Source configuration persists in the database. |
| **Law discovery and watchlist** | Search discovered documents by title or keyword, add selected laws, or add a specific law directly by URL. Name, pause, and resume tracked documents through the interface. |
| **Import previous version** | Upload a PDF, HTML, or TXT file, paste text, or fetch a historical copy by URL. Review the extracted text, attach it to a law, and optionally record its stated version date. |
| **Dashboard** | See connected sources, tracked laws, last scan times, changes, and impact indicators. Distinguish newly discovered documents, changed documents, unchanged documents, and failures. |
| **Scan now** | Check one law or the watchlist, with per-document progress and a final summary. A first fetch without a prior version establishes a baseline. A background scheduler is not required. |
| **Version detection and history** | Extract and normalize text, compare a content hash, and preserve version history. Choose an earlier snapshot for comparison without replacing the latest successfully observed version. |
| **Visual diff** | Choose old and new versions and see added, removed, and modified passages. Show side-by-side text, inline word highlights, a list of changes, and links to the saved evidence and original source. |
| **Apertus impact analysis** | Generate a concise summary, why it matters, affected business areas, an indicative high/medium/low impact, and 1-3 suggested actions. Keep supporting passages visible. |
| **Ask Apertus with citations** | Ask questions about the selected document or comparison. Cite the version and an identifiable passage, with the source URL or imported file provenance and a PDF page where available. Say when the supplied text does not support an answer. |
| **Optional: impact matrix** | Show changes against business areas such as HR, IT, Legal, and Operations, with an indicative priority and a short reason. Add only if the core demo is complete. |

Impact labels and suggested actions are AI-generated aids for review, not authoritative legal conclusions. Users can check the linked source before acting.

## Connecting real sources

The first implementation supports public HTML pages and text-based PDFs. For website discovery, start from a user-selected listing page and inspect a bounded set of links within the configured site or section, for example one link level and at most 50 candidate pages per run. Allow direct document URLs to bypass discovery.

Show the discovered title, URL, content type, and an extraction preview before a document is added. Users choose which results to monitor; discovering a new link does not itself mean a law was amended. Search covers the inspected documents, and the interface must show the inspection limit rather than imply exhaustive coverage of the website.

Use reasonable fetch timeouts and download limits. If a page requires unsupported JavaScript rendering, authentication, or OCR, show a clear limitation and allow a direct PDF URL or a manual import where appropriate. An imported snapshot alone does not provide live monitoring: a reachable current document URL is still needed. Never report an empty or failed extraction as a successful check.

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
| Optional retrieval | **pgvector** | Add passage retrieval only if the corpus outgrows direct context selection. Not needed for the first demo. |

Confirm access to the proposed Apertus model endpoint before implementation. Keep its endpoint and model identifier configurable; hosting a model server is a separate setup choice, not another product feature.

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
- Pass changed passages and nearby context to Apertus. For questions, use relevant passages from the selected versions and state any context limits; start without embeddings or a separate vector database.
- Attach stable passage references during extraction so displayed citations map to saved evidence. Distinguish source-stated dates from dates supplied by users.
- Save analysis results for each version pair so opening the same change does not regenerate the summary every time.
- Process small scan batches in the FastAPI service and expose actual per-stage status to the interface. Record interruptions as incomplete runs. A separate worker fleet, distributed queue, or orchestration framework is not needed for this scope.

## Build order

- [ ] Implement persistent source and law management, including direct document URLs.
- [ ] Add real HTML/PDF fetching, extraction previews, and bounded document discovery.
- [ ] Add previous-version import, immutable snapshots, and explicit baseline selection.
- [ ] Implement live scanning with real progress, version detection, and repeatable historical comparisons.
- [ ] Render the version history and visual diff with passage navigation and word highlights.
- [ ] Connect Apertus and display an impact summary with suggested actions and evidence.
- [ ] Add Ask Apertus with working citations.
- [ ] Verify the complete workflow with real supported sources and an imported previous version, then rehearse the demo through that same workflow.
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
