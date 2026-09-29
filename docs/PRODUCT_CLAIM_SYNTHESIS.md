# Consented claim-grounded research — 1.42

Status: DONE within bounded implementation and verified publication scope. Scope recorded before code on 29 September 2026.
Contributes to MV2-002/020/023/024; full architecture and human acceptance OPEN.

## Scope and dependencies

Reuse ResearchThread, DossierClaim, ClaimEvidence, ClaimReview, source/version
snapshots, current private completed-run access, existing model client and exact
citation validation. No schema, new sources/providers, automatic inference,
public publication or new domain engine. Existing captured evidence is ready;
fixtures are fictional and do not establish live professional accuracy.
Unified specification read fully, especially sections 24–25, 59, 61 and 65.

Add an explicit claims_v1 preview/request contract. Old previews and requests
retain precisely their existing source categories and optional fingerprint.
Expanded requests require the current preview fingerprint; current clients show
exact inputs and generate only on deliberate confirmation. Reviewer reasons,
identities and histories never enter provider inputs.

Consider at most 12 lexically ranked eligible claims. Prioritize current human
acceptance within that bounded set, selecting at most two complete groups with
at most eight total exact quotations. Include all own and paired comparison
citations, including contradictions and dismissed comparisons with their actual
state; omit the whole group when completeness/validity/size cannot be guaranteed.
Retain at least ten slots for ordinary saved evidence within the existing total
of 18 excerpts. Expose selection bounds and omissions. Acceptance is a workflow
state, not truth, source authority or confidence. Preserve machine state.

Persist immutable claim-context pins outside provider input. Recheck before and
after inference and before replay/read/export/working-answer acceptance. Changed
claim, review, comparison or source state marks the original answer obsolete;
a fresh preview/generation is required before acceptance. Missing/excluded or
inaccessible dependencies hide the whole generated content on reads, replay and
exports. Original audit remains retained. Working-answer acceptance never changes
claims. Existing page freshness remains compatible.

## Acceptance

- Both products show exact claim statements, human/machine state, citation
  relationships and comparison context before the explicit Generate action.
- Legacy requests do not receive new claim data; invalid/missing/version-switched
  consent and inference-time mutations fail closed. Retry identity is preserved.
- Exact quote validation, complete contradiction groups, bounds, private scope,
  exclusion and completed-run gates are proved with fictional fixtures.
- Changed review or evidence invalidates retained working answers and prevents
  reconfirmation; unavailable dependencies are absent from all serialized copies
  and exported briefs. No automatic write/model replay or claim acceptance.
- Affected Core tests, exact API lint, backlog invariant; both client test/lint/
  type/build gates; immediate main pushes; exact existing Sites artifacts and
  normal Core activation verified without browser/private records/paid probes.

Existing search, vectors, source reviews, nine Monitoring sections and all
completed stages remain intact. Canonical entities, domain claim types,
applicability and full Market Access remain open. Frozen evaluations untouched.

## Implementation and verification

The new product_claim_synthesis module selects current eligible completed private
claim groups and reuses product_claim_review context/projection. Stable workflow
priority applies only inside the 12-candidate lexical/recency window. Complete
own/comparison citation groups share eight quote slots; other saved evidence keeps
at least ten slots. Incomplete, invalid or oversized groups are omitted whole.
Exact provider input includes claim statements, separate machine/human state,
comparison kind/status and source-linked literal quotations. No review reasons,
reviewer identities or histories are sent. Internal dependency pins never enter
the preview or serialized note. The existing model client and quote validator
remain authoritative; preview reads do not call any model.

An explicit claims_v1 request requires the matching current preview fingerprint.
Legacy previews, input categories and unpinned generation remain unchanged.
Retries bind author, question revision, scope and original preview. Original
context pins survive working-answer acceptance; a changed review/claim/comparison/
source requires new generation, never silently reconfirms the old answer.

Every note serialization and retry checks current dependencies. Missing, excluded,
uncompleted or inaccessible dependencies hide all generated content. Linked gap
follow-ups and their action audit copies inherit that restriction. JSON exports
and printable briefs use the same protection. Existing page review behavior is
preserved. Clients show original generation context and all selected conflicting
quotes, refresh visible claim-aware questions every 15 seconds and on focus, and
hide selected content on failed reads without rerunning models or writes.

Both clients passed 220 tests, lint, type checks and exact production builds.
New UI checks prove explicit scope-bound retry identity, distinct machine/human
states, preserved dismissed contradictions, escaped quotations, focus freshness,
hidden content after failed reads and no stale gap-copy action. One native React
fixture initially lacked Element, corrected without changing product behavior.
Source parity, whitespace and the count-only protected-value scan passed.
Initial Core suite: 51 passes, three fixture assertions expected HTTP 200 while
the existing idempotent action route correctly returns 201. All hidden payloads
were already sanitized. Assertions corrected. The final affected suite passed all 26 cases, including all 14 new cases collected then; the additional current-brief escaping/citation case also passed. Together with the 41 existing checks from the initial suite, 56 distinct Core checks passed (15 new). The final backlog invariant and exact API lint passed. Initial publication verified below.
No browser/private production/inference evaluation. Full target and human
acceptance remain OPEN.

## Verified publication

Core `4204cdfb6e6655255bb91d498d0e74c57a538455` activated normally at
2026-09-29T02:57:51Z as `git-4204cdfb6e66`. All 39 relevant runtime hashes,
unchanged migration 0bd495bef125 and review constraints, five running containers
and nine Monitoring routes were verified. Both canonical product origins passed
45 HTTP/access checks and 47 exact asset hashes.

- Legal `283dd346e89946d30020df7ccb2750905c645b5c`, existing Sites 42,
  activated 2026-09-29T02:56:05.136617Z.
- Pharma `1c29a8b7b2e9d2b5e1bfcefaa4f718d0dbeb754f`, existing Sites 42,
  activated 2026-09-29T02:56:31.691053Z.

See the [frozen receipt](product-releases/2026-09-29-1.42-claim-synthesis.json).
All three main checkouts were freshly fetched, clean and aligned. The final
English evidence-only Core commit follows normal activation, recorded in the
parent checkpoint; unchanged clients are not republished. Native backups still
pause API/tunnel; zero downtime is not claimed. No browser, private production
dossier, paid model probe or frozen evaluation was used. Full architecture,
professional quality, whole-ledger ranking and human acceptance remain OPEN.
