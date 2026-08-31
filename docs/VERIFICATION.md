# Verification record

The source-to-diff workflow and the Settings page are verified. Model acceptance against an actual Apertus endpoint remains separate and incomplete.

## Completed checks

- 74 Python regression cases pass using isolated SQLite databases and actual API/service/migration code.
- State checks cover initial baselines, unchanged scans, 30 → 60 changes, A → B → A reuse, duplicate imports, repeated historical comparisons, and saved comparisons without source requests.
- Failure checks cover unavailable/empty sources, partial batches, overlapping scans, paused laws, invalid/cross-law input, and interrupted-run recovery.
- Evidence checks cover complete article/passage alignment, every saved passage exactly once, all changed passages despite a smaller warning threshold, legacy persisted-diff upgrades, artifacts, PDF pages, missing records, old/new citations, exact quotes, and whitespace-only bogus quotes.
- Test-only model doubles cover timeout with an intact diff, analysis-only retry, cache reuse, profile invalidation, unsupported unrelated questions, rejection of insufficient-context answers for complete change questions, rejected fabricated citations, invalid JSON repair, and failure after exactly one unsuccessful repair. They do not establish that Apertus works.
- Settings checks cover immediate application, restart persistence, key preservation/removal/environment inheritance, invalid-input handling without secret echoing, and configuration changes while an analysis is in progress.
- HTTP transport doubles exercise the actual model adapter's endpoint, credential and User-Agent headers, generation options, JSON mode, timeout, and connection failures. They verify separate authentication, access, missing-route/model, and quota errors without exposing provider bodies. They are test-only protocol checks, not a live Apertus deployment.
- TypeScript checking, formatting, Python linting, and a Next.js production build pass, including the Settings route.
- Linux API/web container builds pass. An isolated Compose stack starts with healthy PostgreSQL and API services; an existing database upgrades through both migrations. In that stack, a stable Fedlex ELI URL created one baseline, a subsequent scan completed as unchanged, the official resolved file stayed attached to the version, and the observation count increased without duplicating the version.
- A second app instance retains sources, paused state, versions, observations, comparisons, and completed scans in the same test database.
- The native API extracted a FINMA introduction, FDPIC FAQ, 108-page FDPIC PDF, and Fedlex ELI publications. The FINMA source was previewed and saved through the browser UI. These are source-compatibility checks, not claims of full legal coverage. See [SOURCES.md](SOURCES.md).
- Fedlex regression checks cover stable/current and explicitly dated ELI parsing, official HTML resolution and provenance, unavailable languages/formats, and rejection of out-of-scope file metadata before any download.
- Live resolver checks selected the current applicable English FADP expression (7 July 2025; 39,543 characters and 331 passages), retained the explicit 1 September 2023 expression separately (38,851 characters and 328 passages), and used a 238-page PDF fallback for a French Federal Gazette ELI resource.

## Browser and PostgreSQL checks

- Used the unchanged **Add a law** dialog to preview the stable Fedlex FADP ELI URL. The browser displayed “Federal Act on Data Protection”, `text/html`, 39,543 characters, 331 passages, and enabled **Add to watchlist**; the preview was not saved to the user's watchlist.
- Connected and previewed a website, discovered the synthetic policy, added it to the watchlist, pasted its earlier text, and selected the historical baseline through the actual interface.
- Fetched the current public GitHub fixture and inspected the actual diff: **2 added, 1 removed, 2 modified**, including deletion **30** and insertion **60**. Change filtering, jump navigation, and the saved old passage link were exercised.
- Repeated the historical scan while the current source stayed unchanged. Two immutable snapshots remained; each real fetch added an observation. An ordinary check separately reported **Unchanged**.
- Verified that a duplicate import with a newly stated date preserves original snapshot metadata and records the new date/provenance in the observation table.
- Discovery inspects bounded candidate pages, retains previews and errors, observes section/redirect limits, and does not create watched laws automatically. Tests cover 55 candidates with a 50-page limit, unavailable/empty candidates, time-budget exhaustion, and avoiding deeper traversal.
- Saved Apertus parameters through the Settings form in a disposable PostgreSQL workspace, using an explicitly synthetic, nonfunctional credential for key-handling verification. Editing another parameter preserved the key; saved key text did not reappear in the form.
- Tested an unsaved, unavailable local model address. The UI showed an error, and reloading restored the saved address and parameters. No model answer was fabricated.
- Selected the Public AI preset in the browser. Only the draft URL/model changed; key handling and generation values stayed intact, and saved configuration was unchanged.
- Added and exercised a Hugging Face router preset for the same Apertus 8B model. Browser checks confirmed the URL/model, unchanged key handling and generation parameters, and no automatic save. Desktop/mobile widths had no overflow; TypeScript and formatting checks passed. No existing provider credential was sent to Hugging Face, so this is configuration verification, not successful inference.
- Checked the diff and Settings layouts at desktop and 390-pixel viewport widths; no horizontal overflow was found.
- Ran [the real HTTP smoke check](../scripts/smoke_http.py) multiple times through the web/API/PostgreSQL stack. The final run retained **2 versions and 13 observations**, with matching comparison IDs across repeated historical scans.
- Stopped and restarted the isolated web, API, and database services without deleting volumes. The recorded sources, paused state, snapshots, artifact content, completed scan, and browser-saved model settings all matched afterward.

The Windows agent's default pytest temporary directory had a permission conflict when switching execution contexts. The documented test command was rerun with a fresh task-local temporary directory and cache; no global permissions or user data were changed.

## Remaining gates

- Obtain successful authentication to a real Apertus deployment through **Settings**. A Public AI connection was attempted: an API root without /v1 returned 404; testing the documented /v1 base URL and provider model ID returned 401. No successful model response was obtained, and draft tests left saved user settings unchanged. The provider preset and distinct error messages make the required correction visible.
- After a successful connection, run an impact analysis, changed-wording and old-version questions, and an unsupported question, then open citations. No actual Apertus deployment has been validated in this session.
- Validate optional Firecrawl with a key and available credit.
- JavaScript-only portals, OCR, authentication-gated pages, and exhaustive multi-page discovery remain outside this narrow implementation.

The full MVP is not accepted while real-model gates remain. Deterministic tests do not conceal that limitation.
