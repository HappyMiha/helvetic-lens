# Source-pinned human claim review — 1.40

Status: IMPLEMENTED / VERIFYING publication. Scope recorded before product code on 29 September 2026.
Contributes to MV2-002/020/024; full target and human acceptance remain OPEN.

## Audit, dependencies and source readiness

Unified Target Architecture §§10–13,23,30,61,65 requires a distinct human decision.
Existing DossierClaim is the durable machine-extracted proposed assertion (the
finding); ClaimEvidence already retains supporting/contradicting/context quotes.
ClaimChange reviews relationships; EntityIdentityReview reviews mention pairs;
ResearchThread.accepted_entry_id accepts a working answer, not its every claim.
Reuse these records, source snapshots, native editor/guest roles, current public
consent, SQL audience/source filters, and the readable research chapter. No new
Finding model, duplicate claim, domain engine, source, provider or inference call.
The full unified specification was read (unchanged SHA-256
f5cb4d2218f377b317295b26c75c0c3eef2130c0624de668ded1c5308ecf048a).
Only retained eligible completed research is ready; missing citations remain
unreviewable. Source versions and extraction provenance are captured as recorded,
never inferred. Historical unknown model versions remain explicitly unknown.

## Bounded outcome

One append-only contained ClaimReview per decision, with nullable reviewer FK,
claim composite FK, request identity, revision and evidence fingerprint. A current
editor explicitly accepts, dismisses or requests more evidence, with a reason.
An accepted finding updates the human ledger projection of the SAME DossierClaim;
it neither copies the assertion nor rewrites its machine evidence status/history.
No existing claim becomes accepted automatically. Findings begin pending review;
accepted/dismissed/needs-more-evidence map to ACCEPTED/REJECTED/UNRESOLVED human
claim states. Changed evidence maps to review-needed, retaining earlier decisions.

Bind to claim revision/text/status, all captured citation hashes/excerpts, recorded
extraction routes, and all eligible comparisons touching the claim (including
related claim evidence and relationship review revisions). Added/changed/removed
comparisons stale the review. Original statements and conflicting sources remain.
Persist versioned source/claim/provenance pins; hide a historical note when any
pinned source loses audience eligibility. Never expose a note derived from a
withdrawn contribution through an otherwise visible claim. Public explanations
require explicit current-publication consent. No automatic Ask promotion yet.

A folded Review findings reader in both clients paginates 10 eligible claims,
shows exact evidence and related comparisons, human decision separately from
source assessment, and retained review history. Each detail is bounded to 100
citations and 20 comparisons; overflow is explicit and disallows saving a partial
review. At most 100 append-only decisions per claim. Private export includes
eligible ledger state/history under the existing interactive export bound.

## Acceptance

- Same durable claim transitions pending → accepted/dismissed/needs-more-evidence;
  contradictory evidence, statement and machine statuses/history remain intact.
- Current editor, guest revoke, CSRF, source exclusions, same dossier/audience,
  public withdrawal/revision and explicit explanation consent fence every write.
- Revision conflict, fingerprint mismatch, idempotent retry and late retry do not
  create duplicate reviews or silently reinstate old acceptance. New evidence or
  comparison changes require explicit review; old pins/history are retained.
- SQL source/audience gating before claim counts/pages; unavailable dependent
  evidence hides historical notes. No private review appears on a public route.
- Reviewer erasure retains de-identified history; additive migration preserves
  originals, scoped claim deletion cascades, downgrade refuses retained reviews.
- Actual client reader has no fetch while folded, explicit choice/no preselected
  acceptance, current-scope fencing, retry without automatic write replay, failed
  reads hide cached evidence, accessible controls and preserved unique React keys.
- Controlled fictional fixtures prove the full shared Legal/Pharma API flow;
  affected tests and exact API lint, backlog invariant; both clients tests/lint/
  types/build. Immediate main pushes, normal Core activation, exact existing Sites
  publication and public asset/access verification. No browser/private production
  dossier/paid probe/inference evaluation. Professional and human acceptance OPEN.

Canonical entities, dependency chains, effective-date verification, domain claim
types, accepted-claim Ask ranking and full Market Access remain separate work.

## Implementation and validation

`product_claim_review.py` projects the human ledger from the existing durable
assertion. `product_claim_review_api.py` reuses current native editor/guest/public
participation and source gates, organization locks, explicit public consent,
optimistic revision and retry identity. Migration `0bd495bef125` only adds
`product_claim_reviews`; no existing evidence status is migrated or accepted.
Source pins include retained page revisions/hashes and recorded extraction route
metadata. Comparison changes in either direction, including dismissed links,
participate in the binding; only completed eligible research may be reviewed.
Historical notes disappear from reads when any pinned source loses eligibility.

Both clients use the same folded Review findings reader, nested readable finding
cards, supporting/contradicting quotes and separate human/machine labels. Nothing
is fetched while folded. Failures preserve explicit retry identity without
replaying a write; failed reads remove cached evidence. Public explanations have
an unchecked consent control; no decision is selected by default. Source changes
reset the review form through its evidence fingerprint. Existing saved-search
component keys and the original research and comparison readers are preserved.

Both clients passed 209 tests, lint, types and exact production builds. New cases
exercise actual React rendering/reconciliation, explicit choice, failed retry,
access revocation, escaped contradictions, stale decisions, bounds and isolated
public proxy routes. An accessibility lint finding was corrected by using the
native output element. All 52 distinct affected Core checks passed: 26 claim-review cases, 25 retained
entity-review compatibility cases and the active backlog invariant. Exact API
lint passed. The final accessible output-tag adjustment passed all 66 affected
client render checks again per product. Controlled fixtures never establish live
domain accuracy; production activation remains pending until recorded below.

The Core cases include actual controlled coordinator extraction→comparison→human
review for both product aliases, all three decisions on the same claim, retained
contradictions, explicit public consent and anonymous reads, CAS/retry, new/changed/
withdrawn evidence, unfinished related research, source exclusions before pages,
current guest roles, real account erasure, interactive export, bounds, additive
schema/FKs/cascade and guarded rollback. A native saved-page correction stales the
review without rewriting the retained quotation. Initial fixture failures used
an invalid uppercase workspace role and then attempted account erasure without
an eligible workspace administrator; the fixture now exercises viewer access and
restores its own administrator role for the existing account-erasure flow. No
production permission or erasure gate was loosened. No external inference ran.
