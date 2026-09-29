# Human review in saved-evidence search — 1.41

Status: DONE within bounded search and verified publication scope. Scope recorded before code on 29 September 2026.
Contributes to MV2-002/020/023/024; full architecture and human acceptance OPEN.

## Audit and dependencies

The full Unified Target Architecture specification was read; §§24–25 and 59
require claim-aware retrieval and a separate grounded-synthesis outcome.
Existing product_evidence_search and product_corpus_search search current private
completed research, SQL-filtering source access before counts and pagination.
Their local vectors contain title/statement/quotation only, not human judgments.
Universal Ask's saved-evidence action opens this same search. In contrast,
product_research.research_bundle selects up to 18 team/page/event snapshots and
has a separate preview/consent and post-inference fingerprint contract. It does
not yet read ClaimReview. Expanding that provider input requires a separate
complete consent, synthesis and retained-answer freshness stage.

Reuse DossierClaim, ClaimEvidence, ClaimReview and the existing review context,
source/version/comparison pins, permissions and search UI. No schema, new source,
provider, claim copy, new engine or live inference evaluation. Only retained
eligible citations are ready; fixture content is not current professional fact.

## Bounded outcome

All three saved-evidence modes show the current human review alongside the
original machine status and exact citation relationship. Human acceptance never
becomes a truth/relevance score and does not suppress rejected, unreviewed or
contradictory evidence. Ranking and local model input remain unchanged.

Decorate only the returned window (at most 12 claims) after search under current
access and evidence checks. Reuse the shared current review projection, including
source/version/related-comparison staleness. Include no reviewer reason, identity
or history in search/model input. Expose whether the bounded review context is
complete and whether it contains conflicting evidence. The existing finding
reader remains the route to all citations and detailed review history.

A separate bounded review fingerprint fences the displayed claim state. Existing
15-second/focus checks validate it without inference; a changed decision, source
version, comparison or permission hides obsolete results and requests a fresh
search. An explicit review save in the same dossier invalidates displayed search
immediately. Requests use current access, and neither old results nor retries
can reinstate old acceptance. Stable source-text vectors remain reusable because
they do not encode human decisions; review projections are never cached in them.
Legacy clients retain compatible search and check-only contracts.

## Acceptance

- Legal and Pharma literal/direct/corpus results distinguish accepted, dismissed,
  needs-more-evidence, unreviewed and stale, separately from machine status.
- Supporting and contradicting citations and original claims remain retrievable;
  current review agrees with the existing review reader. Incomplete context is
  explicit; no rank promotion, truth guarantee or full contradiction count.
- Changed decisions/comparisons/source revisions invalidate the review fence;
  excluded/foreign/public/uncompleted claims cannot be projected by private search.
  Private reviewer notes never enter search responses or model inputs.
- Cache reuse after a review-only change is safe; cached vectors cannot retain
  a human decision. Current permission checks also run after inference.
- Actual UI checks prove labels, escaped content, same-dossier invalidation,
  failed freshness reads hiding results, and no automatic inference/write replay.
- Affected Core checks, exact API lint, backlog invariant; both changed clients'
  tests/lint/types/build; immediate main push and exact existing Sites deployment;
  normal Core activation and public asset/access verification.

No browser, private production dossiers, paid probes, frozen evaluation reruns
or external inference. Full accepted-claim prioritization/grounded synthesis,
canonical entities, domain claim types and Market Access remain separate work.

## Implementation

`product_claim_review.decision_state` is shared by the established reader and the
new private projection. The latter loads only the latest review and its current
source/claim/comparison context; review text and reviewer identity are omitted.
`product_search_review` decorates at most the returned 12 claims after rechecking
access and the original evidence fingerprint. It hashes current review context
(including invalid/partial contexts) separately from the stable source-text input.
The existing search endpoint accepts optional bounded UUID review IDs/fingerprint
only on check-only requests; unchanged legacy requests remain supported.

`product_evidence_search.ledger` now carries the actual ClaimEvidence relation.
Corpus rank, lexical/direct rank, semantic input, embeddings and provider routing
are unchanged. A review-only change reuses source vectors and returns fresh human
metadata. A change during local comparison is resolved by the final current read;
it cannot attach an earlier accepted state to the result. No review-based rank
promotion is claimed. Failed review checks hide displayed results without
replaying inference or writes. Explicit same-dossier claim/comparison saves also
cancel and fence outstanding search responses while retaining the typed question.

The full specification checksum remains
f5cb4d2218f377b317295b26c75c0c3eef2130c0624de668ded1c5308ecf048a.
The completed 1.34/1.35 top-level backlog overviews were archived verbatim to
BACKLOG_MONITORING_V2_RELEASE_HISTORY.md, retaining task details and the 512 KiB
active-backlog guard. Original frozen evaluation/validation files are untouched.

## Validation

Both clients passed 216 tests, lint, type checking and exact production builds.
Seven added cases cover five displayed review states with original contested
citations, focus-check fingerprints hiding obsolete results, and same-dossier
invalidation fencing late responses without replaying search. Existing duplicate
search reconciliation remains passing. Shared source parity, diff checks and the
protected-value scan passed. No browser was used in this background cycle.

The initial Core run passed 95 cases and exposed three new fixture mistakes:
an anonymous helper sent a None CSRF header; a simulated concurrent reviewer
recursively called TestClient from its event-loop thread; the overflow fixture
used an evidence ID as its investigation scope. Fixtures were corrected without
weakening production access or validation. All 84 existing review/direct/corpus/
backlog cases passed. The final new-case run also covers native page correction
and unavailable review reads. Database timeouts retain the actionable read error,
and reported elapsed time includes the final current-review projection.
The final 16 new cases passed after those repairs, including all three modes,
current review, source/version changes, bounds, privacy, cache reuse, races and
timeout handling. Together with the 84 passing existing cases, 100 distinct Core
checks passed. Exact API lint passed. Initial production activation is verified below.

## Verified publication

Core `aef408b76eb78b5f019d3d310ddbd43c67b18335` activated normally at
2026-09-29T01:01:49Z as `git-aef408b76eb7`. All 36 relevant runtime hashes,
unchanged migration 0bd495bef125 and retained review constraints, five running
containers and nine Monitoring routes are verified. Each canonical product
origin passed 43 HTTP/access checks and 47 exact asset hashes.

- Legal `3154275617a2e2e8107a9343d3834dac98fb403e`, existing Sites 41,
  activated 2026-09-29T00:59:22.746694Z.
- Pharma `55d90de2dfc5de1bede741bfb37557f61e16e1a3`, existing Sites 41,
  activated 2026-09-29T01:00:21.295711Z.

See the [frozen receipt](product-releases/2026-09-29-1.41-reviewed-search.json).
All three main checkouts were freshly fetched, clean and aligned. The final
English evidence-only Core commit follows normal deployment; final activation
is recorded in the parent checkpoint. Unchanged clients are not republished.
Backup still pauses API/tunnel; zero downtime is not claimed. No browser,
private production dossier or inference probe was used. Full architecture,
professional quality, accepted-claim synthesis and human acceptance remain OPEN.
