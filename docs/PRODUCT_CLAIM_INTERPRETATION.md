# Reviewed claim kinds — 1.43

Status: DONE within the bounded classification and verified release scope.
Scope recorded before code for MV2-002/020/023/024 and
Unified sections 10–13, 31, 38–39, 48–50. Full architecture and human acceptance
remain OPEN.

## Outcome and audited contracts

Editors classify what a retained machine-proposed claim represents while saving
its existing human review: a source statement, a user assertion, AI interpretation,
or explicitly unclassified. Legal and Pharma register their own types through the
shared internal DomainPack. A source statement describes a source's assertion;
it is not independently established fact, binding authority or applicability.

DossierClaim stores machine evidence state and history. ClaimReview already owns
editor identity (erasure-aware), decision, reason, revision, request identity and
the exact evidence basis. Reuse its append-only basis JSON for this optional
versioned classification. No new Claim, Finding, table, service or model call.
Never relabel legacy untyped claims from URL, model label, source support or an
accepted decision. Classification does not edit the original statement or quotes.

## Dependencies and source readiness

Use current completed audience-eligible runs, complete retained citation and
comparison groups, existing editor/guest/publication guards, explicit public
consent, ClaimReview history and DomainPack. These sources already exist locally;
no collection, provider keys, paid inference or private production reads are needed.
Source authority, jurisdiction and effective dates remain unassessed; this stage
does not implement their classification or claim regulatory/legal applicability.

## Acceptance

- One explicit type choice in the folded review form, with an unclassified option;
  domain-incompatible types and obsolete registry versions rejected.
- Store server-resolved kind/type labels and pack revision with the existing
  review and evidence basis. Preserve current and historical classifications,
  including stale and hidden-source behavior and reviewer erasure.
- Legacy requests remain compatible until a classification is explicitly saved;
  subsequent writes must explicitly preserve/change it, never silently clear it.
  Historical request fingerprints/replays remain compatible.
- Review revision fences type changes. Current search displays the classification
  separately from machine and human states; changes invalidate saved search and
  claim-grounded answer pins through the existing review projection.
- Keep saved-only and claims_v1 provider input categories unchanged. Classification
  is reader/review metadata in this stage, not new model input or ranking logic.
  A later explicit synthesis contract can include typed domain interpretation.
- Export uses the same protected ledger. Hidden supporting sources hide review
  metadata; a stale review never presents its classification as current.
- Both clients use shared contracts/readers, preserve readable dossier layout and
  the 1.36 reconciliation fix. Test real review/render/retry behavior, domain/access
  fences, history, legacy compatibility and search/synthesis invalidation.
- Affected Core tests, exact lint and backlog invariant; changed client full tests,
  lint/types/build; main pushes, existing Sites publication and exact production
  verification. Code and activation evidence remain separate until confirmed.

Canonical entities, source authority/applicability, model-generated domain types,
typed synthesis, general-domain support and full Market Access remain OPEN.


## Implementation and compatibility

`product_claim_interpretation.py` defines the bounded request schema, registered
choices and server-resolved recorded metadata. DomainPack 1.3.0 advertises those
choices. The existing review POST stores classification inside ClaimReview.basis;
reviewer FK erasure, publication consent, source visibility, evidence fingerprint,
request identity and the 100-review limit remain authoritative. No migration.

Legacy records omit classification rather than guessing it. A missing optional
field is excluded from the retry digest, preserving historical request identities.
Once a classification is saved, a later write must explicitly preserve, replace
or set it to UNKNOWN/UNCLASSIFIED. A late identical retry returns current state
without restoring an earlier type. Pack revisions and human-readable labels are
stored with the review, so a future registry update does not rewrite history.

Current review projections include classification only when its original source
basis remains visible. Stale evidence retains the older classification with a
review-needed state; hidden related evidence hides classification and review
explanations. Search uses the same projection, without embedding classification or
altering relevance scores. Claim-grounded answer pins already depend on this
projection, so changes force new research instead of reconfirming old output.

Saved-only and claims_v1 provider inputs are unchanged. The reader shows current
classification in review/search, while existing notes retain their original
human/machine input snapshot. No new private category enters a model silently.

Both clients use one matching reader implementation and existing native-select
primitive inside the folded review; no new top-level panel or navigation route.
The exact original claims, quotes, contradictions and source dates remain visible.

## Validation and publication

Both clients: 222 tests, lint, type checks and production build passed.
Domain context/template regression: 33 passed. Exact API lint and active-backlog
invariant passed. Known protected-value scan and shared-reader parity passed.
The review/search/synthesis suite passed 81 of 82 initial cases; the remaining
fixture was repaired and its targeted rerun passed. Together with the 33 domain
checks, all 115 distinct affected Core cases pass (12 new classification cases).
Initial implementation activation is verified below.
A new synthesis fixture initially supplied an empty search_queries list, contrary
to the established response schema; it was corrected to use the cited-answer
fixture. The corrected cited-answer check passed, including accepted-answer invalidation
and rejection of obsolete reconfirmation. No additional live inference was used.


Both GitHub main branches and their existing public Sites are published as version
43: Legal `841a9dc557df3db1a23ee8520d5a03ce1ca05593`, Pharma
`5beffed19f4c3dcbf0bdbb58b23c51bd8d6b47ec`. Core implementation
`ada06c3c2790de7996818e95c422bec1847a46f9` activated at
2026-09-29T04:59:52Z. The [frozen release receipt](product-releases/2026-09-29-1.43-claim-interpretation.json)
confirms 40 exact native module hashes, DomainPack 1.3.0 with claim types,
unchanged migration 0bd495bef125, five running containers and all nine Monitoring
routes. Each canonical product origin passed 45 HTTP/access checks and 47 exact
asset hashes. Source checkouts were clean and aligned with freshly fetched main.

The follow-up English evidence commit uses normal native activation; its final
SHA and verification are retained in the parent cycle checkpoint. Clients remain
unchanged and need no repeat publication. Native backup still briefly stops API
and tunnel; this release does not provide zero-downtime deployment. Browser,
authenticated production and professional human acceptance were not performed.
Full architecture, typed synthesis, source authority/applicability and the
complete Market Access journey remain OPEN.
