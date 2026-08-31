# Apertus RegWatch

**Know what changed. Know what it means. Know what to do.**

Apertus RegWatch is a regulatory change monitor that turns updates to public regulatory pages and PDFs into visible diffs, plain-language impact summaries, and practical next steps with links back to the evidence.

Built for a hackathon: one clear workflow, a small set of sources, and a demo people can understand in minutes.

> **Project status:** This repository currently contains the MVP plan. The application and the features described below are not implemented yet.

## The value proposition

Teams should not have to reread every regulatory document to find out whether an update matters to them. RegWatch connects three questions in one screen:

- **What changed?** Compare the previous and current versions, with added and removed text highlighted.
- **What does it mean?** Ask Apertus to explain the change and its possible impact on a simple company profile.
- **What should we do?** Get a short, prioritized action list grounded in the source text.

Start with a Switzerland-focused demo, 2-3 curated public sources, and one company profile. Expand only after the core workflow works.

## MVP scope

| Feature | What the user can see and do |
| --- | --- |
| **Dashboard** | See monitored sources, last scan times, new changes, and an impact indicator. Distinguish changed, unchanged, and failed scans. |
| **Scan now** | Trigger an on-demand scan with visible progress and a result summary. A background scheduler is not required. |
| **Version detection** | Extract and normalize document text, compare a content hash, and save a new version only when the text changes. The first scan establishes a baseline. |
| **Visual diff** | Open a change and compare the previous and current text, with additions and removals highlighted and the original source linked. |
| **Apertus impact analysis** | Generate a concise summary, why it matters, affected business areas, an indicative high/medium/low impact, and 1-3 suggested actions. Keep supporting passages visible. |
| **Ask Apertus with citations** | Ask questions about the selected document or change. Answers cite the source URL and an identifiable passage, plus a PDF page where available. Say when the supplied text does not support an answer. |
| **Optional: impact matrix** | Show changes against business areas such as HR, IT, Legal, and Operations, with an indicative priority and a short reason. Add only if the core demo is complete. |

Impact labels and suggested actions are AI-generated aids for review, not authoritative legal conclusions. Users can check the linked source before acting.

## A demo in five steps

1. Open the dashboard and see the small source list and its last known state.
2. Click **Scan now** and watch a document move to **Changed**.
3. Open the document to see the exact before/after diff.
4. Read Apertus's explanation of what changed, why it matters, and what to do next.
5. Ask **"Which teams should review this, and why?"** and follow the answer's citations back to the relevant passages.

Keep one pair of clearly labeled **demo snapshots** available so the presentation is reproducible even when live sources have not changed. Demo content must remain visibly distinct from live regulatory updates.

## Proposed stack

| Layer | Choice | Role in the MVP |
| --- | --- | --- |
| Web app | **Next.js** | Dashboard, document detail, diff view, and question interface. |
| Styling and components | **Tailwind CSS + shadcn/ui** | Build a polished, consistent interface quickly. |
| Backend | **FastAPI** | Fetch sources, detect changes, and serve analysis and question endpoints. |
| Database | **PostgreSQL** | Store sources, document versions, detected changes, and saved analyses. |
| Language model | **Apertus v1.5 8B** | Proposed target for impact analysis and cited answers, through one configurable inference endpoint. |
| Content extraction | **BeautifulSoup + PyMuPDF** | Extract text from HTML and text-based PDFs. |
| Diff engine | **Python `difflib`** | Compute text differences for the visual comparison. |
| Optional retrieval | **pgvector** | Add passage retrieval only if the corpus outgrows direct context selection. Not needed for the first demo. |

Confirm access to the proposed Apertus model endpoint before implementation. Keep its endpoint and model identifier configurable; hosting a model server is a separate setup choice, not another product feature.

## Keep the implementation small

Use one Next.js app, one FastAPI service, one PostgreSQL database, and one Apertus endpoint.

The core pipeline is:

```text
Curated source URL
  -> fetch HTML or PDF
  -> extract and normalize text
  -> compare with the last saved version
  -> store a new version when changed
  -> compute the visual diff
  -> ask Apertus for impact and actions
  -> show results with source evidence
```

- Store source URLs, fetch times, extracted text, content hashes, and simple change/analysis records. A failed fetch must not replace the last good version.
- Pass changed passages and nearby context to Apertus. For questions, use relevant passages from the selected document; start without embeddings or a separate vector database.
- Attach stable passage references during extraction so displayed citations map to real evidence. Show dates only when they are present in the source.
- Save analysis results for each version pair so opening the same change does not regenerate the summary every time.
- Handle ordinary fetch or model errors visibly in the interface. Avoid adding background queues or orchestration frameworks for the demo.

## Build order

- [ ] Build the dashboard and document detail view with labeled demo data.
- [ ] Add HTML/PDF extraction, baseline storage, and on-demand scanning.
- [ ] Detect new versions and render a useful visual diff.
- [ ] Connect Apertus and display an impact summary with suggested actions and evidence.
- [ ] Add Ask Apertus with working citations.
- [ ] Rehearse one complete demo, including unchanged-source and failed-scan states.
- [ ] If time remains, add the impact matrix and assess whether pgvector is actually needed.

## Definition of done

The demo can take one source through baseline, changed version, visual diff, impact analysis, and a cited follow-up answer. Users can see where each conclusion came from. Unchanged content does not create duplicate versions, and unavailable sources or model responses do not appear as successful results.

## Not in this MVP

- Enterprise SSO, multi-tenancy, granular roles, audit-log platforms, or compliance certification infrastructure.
- Broad crawling, complex schedules, distributed workers, or a large ingestion platform.
- Knowledge graphs, autonomous agent frameworks, or training/fine-tuning a model.
- OCR for scanned PDFs, exhaustive jurisdiction coverage, or automatic legal decisions.

Prioritize the visible end-to-end workflow. Add infrastructure only when a demonstrated need justifies it.
