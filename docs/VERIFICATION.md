# Verification record

Verification is in progress. Implemented behavior and acceptance against external services are distinguished below.

## Completed checks

- 36 Python regression cases pass using isolated SQLite databases and actual API/service/migration code.
- State checks cover initial baselines, unchanged scans, 30 → 60 changes, A → B → A reuse, duplicate imports, repeated historical comparisons, and saved comparisons without source requests.
- Failure checks cover unavailable/empty sources, partial batches, overlapping scans, paused laws, invalid/cross-law input, and interrupted-run recovery.
- Evidence checks cover artifacts, PDF pages, missing records, old/new citations, exact quotes, and whitespace-only bogus quotes.
- Test-only model doubles cover timeout with an intact diff, analysis-only retry, cache reuse, profile invalidation, unsupported questions, and rejected fabricated citations. They do not establish that Apertus works.
- TypeScript checking and a Next.js production build pass.
- Linux API/web container builds pass. An isolated Compose stack starts with healthy PostgreSQL and API services.
- A second app instance retains sources, paused state, versions, observations, comparisons, and completed scans in the same test database.
- The native API extracted a FINMA introduction, FDPIC FAQ, and 108-page FDPIC PDF. The FINMA source was previewed and saved through the browser UI. See [SOURCES.md](SOURCES.md).

## Remaining gates

- Finish browser checks for imports, scan repetition, change navigation, saved evidence, and responsive layouts.
- Verify restart persistence through the PostgreSQL/container workflow.
- Supply a real Apertus endpoint, authentication if required, and served model ID. Run an impact analysis, an old-version question, and an unsupported question, then open citations. No real inference request has succeeded because no endpoint is configured.
- Validate optional Firecrawl with a key and available credit.
- RW-008 currently lists bounded links and fetches a candidate on preview. Automatic inspection of all candidate pages and per-candidate errors are not implemented.

The full MVP is not accepted while real-model gates remain. Deterministic tests do not conceal that limitation.
