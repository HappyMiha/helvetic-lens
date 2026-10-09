# Saved research reading performance

## Scope before implementation — 9 October 2026

Scoped MV2-002/021/051 usability and retrieval repair; broader tasks stay open.
The owner reports saved research loading for minutes and failing. A read-only
production replay took 23.24 seconds and generated 6.48 MB without any AI call.
Profiling found repeated current-knowledge construction and per-claim review work.

Dependencies: existing dossier authorization, current source/citation guards,
read-view cache isolation, saved mission and both product readers. Source readiness:
use only already retained authorized evidence; no new source access or provider calls.

Acceptance: a dedicated compact read carries the same saved answer, citations,
uncertainties, document completion and controls, while omitting raw plans, source
snapshots and execution receipts. Full findings remain available on demand. Current
rights, exclusion, retained ancestry and review changes must remain effective.
No read may enqueue or repeat research. Remove unnecessary cross-run review work
and duplicate reconstruction; compare exact live record timing and response size.
Validate Core authorization/reading tests and both clients' required gates, push
main and verify production activation. No completion is claimed before those checks.

## Implemented and locally verified

- `GET .../investigations/{id}/reading` reuses the ordinary dossier/session/source
  authority checks and serves a compact checked reading. Raw plan documents,
  captures, activity, model receipts, repeated checkpoint answers and document
  reconciliation trees remain available through the existing full reader.
- Both clients use this endpoint for the dossier checkpoint, retain cited answers,
  gaps and complete/incomplete document status, and offer the full findings view.
  Current professional context/history is explicitly deferred to that view.
- Mission projections are reused only within one synchronous read response.
  Current knowledge batches evidence and avoids comparison/provenance reconstruction
  for findings without a human review; reviewed findings keep exact fingerprint checks.
- Exact API Ruff gate and 25 affected Core tests passed, including 420-page reading,
  answer/citation parity, owner/product/dossier authentication, no provider execution,
  fresh reviews and evidence withdrawal across retained answer ancestry.
- Each client passed 555 existing tests plus the added mounted compact-read case;
  affected exploration suite: 179 passed each. Lint, typecheck and production builds
  passed. No new visual-browser acceptance is claimed for this data-loading change.
- Read-only candidate replay of the reported record: 258,979 JSON bytes instead of
  6,480,410 (about 25x smaller); 240 SQL statements instead of the original profiled
  1,467. Candidate reading/full projections took 5.58/6.01 seconds while regression
  tests ran concurrently, versus the original 23.24 seconds. The saved answer was
  identical. These are server projection measurements, not mobile network timings.
- Publication/activation and live post-release verification are tracked separately.
