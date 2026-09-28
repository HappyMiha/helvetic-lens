# Captured-source relationships across research runs — 1.38

Status: implementation/tests complete; VERIFYING normal production publication.
Scope recorded before implementation, 28 September 2026.
Parents MV2-002/020 remain open. Investigation Engine sections 33–39 and Unified
Target Architecture sections 8–9, 23, 29 and 65 guide this bounded outcome.

## User outcome

In Changes over time, readers can distinguish two captures with matching content,
versions retained at the same source address, and sources whose relationship is
unknown. A later capture date must not imply publication, legal effect or a real
world status change. Show this beside both original quotations in the existing
reader, including anonymous public dossiers and private exports.

## Existing architecture and reuse

The common ClaimChange already pins both exact ClaimEvidence records and their
InvestigationSource rows across two eligible runs. Source hashes, addresses and
capture times are retained; active/dismissed review is revisioned and source
visibility is checked before pagination/counts. Existing client cards render the
server basis text. Reuse these contracts, scope filters, exports and human review.
Add a deterministic versioned source-comparison projection, not another registry,
model, provider, graph database or research call. No schema migration is needed.

## Bounded contract

- Compare only the two exact, currently visible evidence sources already in a
  saved comparison; never search another dossier, audience or hidden source.
- Valid matching SHA-256 hashes within the same capture kind establish matching
  captured content only. Bounded capture hashes do not prove complete documents,
  independent publishers, original authorship or source truth.
- Exact HTTP(S) addresses, ignoring only fragments, establish the same recorded
  address. Keep query/path/scheme distinctions; do not merge by host or title.
- Distinct hashes/addresses, missing hashes and different capture kinds never
  establish independence. Equal quoted text can be reported as a shared excerpt,
  never as proof of copied documents or independent corroboration.
- Emit policy-versioned structured metadata and concrete plain-language basis
  in the existing comparison card. Source capture times are observation times;
  publication/effective/validity dates remain unestablished by this projection.
- Preserve original comparison kind, claims, citations, revisions and all reviews.
  The projection is an explicit provenance annotation, not a retroactive factual
  decision, claim merge or source-quality score. Source-dependency chains and
  reviewed cross-run entity identity remain separate future scope.

## Acceptance and source readiness

Current retained sources only; no external access, paid/local inference or raw
private production data. API integration tests cover both products/private and
public readers, identical captures, later changed captures at one URL, different
URLs with unknown independence, conservative URL rules, missing hashes, matching
quotes with different contents, review/replay, exports and withdrawn-source
privacy. Required API lint, affected evolution/research tests and backlog invariant
must pass. Verify the existing client consumes the basis; do not republish or
retest unchanged clients. Publish complete Core code/evidence to main, observe
normal native deployment and verify exact runtime plus anonymous client access.
Human/professional acceptance and the full target architecture remain OPEN.

## Implemented contract and verification

`product_source_relationships.compare` projects only the two evidence payloads
already selected by the existing audience-safe comparison query. Version
`captured-source-comparison/v1` reports matching captured content, the same
recorded address or an unestablished relationship. Missing/incomparable hash
metadata stays unknown. Matching quotes remain a separate observation. All
results explicitly leave publisher independence and publication/effective dates
unestablished by this method; observation timestamps retain their actual meaning.

The existing evolution payload adds `source_relationship` and places its short
explanation in `basis`, already rendered by both existing client cards. No extra
query, model call, schema migration or reinterpretation of saved comparison kind,
claim status or editor history is introduced. Private exports and review replay
include the same annotation. Source exclusion is applied before payloads/counts.
These read-time provenance annotations do not identify a common original report
behind differently worded articles or resolve canonical entities across runs.

58 distinct affected checks passed: 23 new provenance/unit/API checks, 34 existing
evolution/worker/review/privacy/migration cases and the required backlog invariant.
The initial run passed 56 and found two new Legal fixture setup errors: the fixture
stored `legal` instead of the retained `loyer` storage identity. Corrected fixture
setup then passed both cases through the current `/legal/` API alias. No production
storage or alias behavior was changed. Exact API Ruff passed after the correction.

Read-only inspection confirms both unchanged `components/claim-evolution.tsx`
render `value.basis`, and both typed API contracts accept that existing string.
Their source files are identical and remain at the verified 1.36/Sites 38 commits.
No client tests/builds/publication were repeated. No browser, private production
record, external source request or paid/local inference was used for verification.
Normal Core activation and fresh anonymous product access remain the release gate.
