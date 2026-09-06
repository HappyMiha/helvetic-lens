# Server-paged saved evidence

Implemented on 6 September 2026 for HL-076/096/099. Native and legacy evidence viewers no longer fetch the full saved document just to show one page. This changes the reading projection, not extraction, comparison, AI evidence or stored originals.

## Contract

- `GET /api/versions/{id}/page` and `GET /api/regulatory-versions/{id}/page` accept `offset` (zero-based), `limit` (1–50, default 50) and optional exact `passage` ID. A citation resolves directly to its containing page; duplicate IDs resolve to the first saved occurrence, consistent with the former viewer. A missing citation is explicit, never silently redirected to a different paragraph.
- Metadata includes actual full passage/character counts, but only the selected passages are transferred. SQL expands the saved JSON once per page query; target lookup selects only its ordinal. No full Version or RegulatoryDocumentVersion object is hydrated. Both metadata and content projections reuse the same organization access query. Native event admission/relation/watch and private legacy bindings remain enforced. All values are bound; no caller-supplied SQL identifier is used.
- When no passages were saved, `mode=text` returns at most 16,000 Unicode characters and exact offsets. It does not invent passage IDs/citations. The UI labels ranges as characters. Empty text remains a metadata-only record. Extracted text is never modified or summarized by this API.
- Pagination returns offset/end/total/size, previous/next offsets and target-found state. Out-of-range/negative/oversized offsets or invalid limits return an explicit 422; unavailable or revoked evidence returns 404. The original artifact route and legacy complete-document APIs remain unchanged for existing callers. Missing stored files do not hide extracted text.

## Reading behavior

Citation links and PDF page anchors retain the exact saved version and passage. Each page has a distinct organization-scoped cache key. A requested next/previous page is loaded before replacing the visible text, with busy controls; failure leaves the old page readable and permits retry. This does not reload the document or switch the user's route. Session changes, unmounts and different source/citation navigation discard stale asynchronous results. Personal evidence-display milestones retain their existing foreground/viewport boundaries and are not repeated merely by paging.

## Bounds and remaining work

The API/browser transfer and Python object count are bounded by one page. This is **not** a constant-time database guarantee: counting/locating an ordinal and JSON expansion may parse the whole saved array in the database, and a single saved passage may itself be large. Plain-text transfer has a fixed character bound. Normalized indexed passage rows, strict per-passage byte policy, corpus-wide API paging and target-host concurrent-reader measurements remain possible follow-up work; do not claim the 100-user capacity gate from these functional tests. Full legacy endpoints intentionally remain full responses for compatibility.

## Verification

`test_evidence_pages.py` covers 10,001-passage native and legacy documents, exact late targets, a bounded final page, missing targets, no full ORM version loads, Unicode text reconstruction, empty records, malformed/out-of-range parameters and private source denial. Disposable PostgreSQL suites `evidence-pages`, `evidence-pages-native` and `evidence-text-pages` exercise database-specific JSON and substring behavior. The production-browser suite `check:native-evidence:browser` covers five locales at 390/1440px, legacy compatibility, page failures/retries, exact citations, text-page reconstruction and no full-document requests. All source/model/mail inputs are synthetic or intercepted; no deployment or production data changes are authorized by this work.
