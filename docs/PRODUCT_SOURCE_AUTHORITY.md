# Reviewed source roles — 1.44

Status: DONE within the bounded source-role and verified release scope.
Scope recorded before code for MV2-002/020/023/024;
Unified sections 9, 29, 31, 35, 38–39 and 48–50. Full architecture, professional
authority/applicability and human acceptance remain OPEN.

## Outcome and source audit

An editor can assess each cited source's role while reviewing an existing finding.
The assessment belongs to that finding review and exact captured source, not every
document at a URL or every source supporting a claim. A mixed-source claim never
receives blanket authority. Unassessed sources remain explicitly unassessed.

InvestigationSource retains a capture hash/snapshot; ClaimEvidence supplies exact
quote/locator. ClaimReview already pins own and paired comparison sources, optional
native Version identity/revision/hash, reviewer, public consent and review history.
Native Source metadata identifies an acquisition origin; RegulatoryWork.authority
is source metadata, not a reviewed determination of binding force or applicability.
URL-level source reviews select/exclude material; source relationships compare
captures without establishing authorship or independence. None of these fields
can safely auto-classify authority, effective dates or clinical/regulatory truth.

## Dependencies and source readiness

Reuse current completed audience-eligible evidence, ClaimReview.basis, the internal
DomainPack registry, review API, protected export/search and existing folded UI.
Available local retained citations suffice; no new table, migration, collection,
provider access, inference, private production dossier or paid probe is required.

## Bounded contract and acceptance

- Optional versioned source_assessments on the existing review request, at most
  12 distinct sources per review. Each item has a source ID, registered domain
  category, exact evidence ID and editor reason. Server resolves labels and pins
  quote, locator, capture fingerprint/hash/time and native version when available.
- Only valid citations within the complete current review context may be chosen.
  Reject duplicate/foreign source IDs, mismatched citations, obsolete pack versions,
  invalid categories, forged metadata and changed evidence. Public consent and
  current editor/source rights apply to all new assessment text.
- Omitted optional data preserves legacy retry fingerprints. Once explicitly
  recorded, subsequent decisions must explicitly retain/update/clear assessments;
  omission never silently erases them. Empty items explicitly clears current
  assessments while immutable earlier review history stays inspectable.
- DomainPack registers Legal authority roles and Pharma publication roles.
  Every label is an editor assessment, never guaranteed truth, regulatory status,
  clinical value, legal validity, applicable jurisdiction or effective dates.
- Review/history show the exact assessment basis. Search shows only the role
  matching its result source; no reviewer reasons/identities/history enter the
  projection. Hidden original sources hide the entire review metadata; changed
  evidence marks assessments stale. Existing search and claim-synthesis pins
  invalidate on review changes, including role changes and explicit clearing.
- Saved and claims_v1 inference inputs, ranking and embeddings remain unchanged.
  Typed synthesis/authority ranking need a separate explicit validated contract.
- Fold source controls into existing review forms using installed primitives;
  preserve readable dossier chapters and the 1.36 single-search repair.
- Verify mixed-source, history, stale/hidden, public/private/domain/access fences,
  exact version pins, retry compatibility, search/answer invalidation and real UI
  behavior. Run affected Core tests/exact lint/backlog invariant, both client
  tests/lint/types/build, main pushes, existing Sites and native activation checks.

Full source registry composition, Legal applicability, canonical entities, generic
Findings, GENERAL, typed extraction/Ask and full Market Access remain OPEN.

## Implementation and compatibility

`product_source_authority.py` registers bounded Legal/Pharma roles through
DomainPack 1.4.0. The existing review POST accepts schema 1 assessments and saves
server-resolved source/citation metadata in ClaimReview.basis. All existing editor,
publication, complete-evidence, revision/replay, erasure and history limits apply.
No migration or machine-claim mutation. Public source-selection reviews retain
their independent include/exclude meaning.

Legacy omission leaves the request digest unchanged. Explicit assessment state,
including an empty clear, must be supplied on subsequent reviews. Replays return
current state; they cannot reinstate an earlier assessment. Historic pack labels
and exact quotes remain stored, while changed registry choices require reload.

Full review and export carry the assessment's recorded quote, locator, source
hash/capture fingerprint and optional native version. Search projection carries
only source ID, category and server label; it excludes editor reasons, quote copies,
reviewer identities and history. The result reader selects by exact source ID.
Whole-review hidden-source checks and stale evidence state remain authoritative.
Review revision changes already invalidate search and immutable claim-research
pins. Model input categories and relevance ranking remain unchanged.

Both clients place the optional editor inside the existing folded review. Each
source requires a citation and explanation. New edits reset public consent;
unchanged retries retain identity, while changed roles or clearing create a new
request identity. Missing historical citations require correction or removal.
History distinguishes old assessments and preserves the recorded version basis.

## Validation and release

225 tests, lint, type checks and production builds passed in each
client, including three new real-render/form cases. The initial public-checkbox
test needed the animation-frame scheduler supplied by browsers; the local test
harness now supplies and restores it, and the case passes. All 129 affected Core cases passed, including 14 new source-assessment cases
and the extended exact native-version test. Exact API lint, the active-backlog
invariant and protected-value/shared-client parity scan passed. Initial publication and exact production activation are verified below.

Both existing public Sites are published as version 44: Legal
`534c6b8bebd055c61769c5f8741d7a35a59e7c25`, Pharma
`fa203e0f77b5de2c5f05546f54f85e70bbf978bc`. Core implementation
`b4d9de5967e94987b8b2e49f279686cd1c4390bf` activated at
2026-09-29T07:04:09Z. The [frozen release receipt](product-releases/2026-09-29-1.44-source-authority.json)
confirms 41 exact runtime module hashes, DomainPack 1.4.0 source roles,
unchanged migration 0bd495bef125, five running containers and nine Monitoring
routes. Each canonical product origin passed 45 HTTP/access checks and 47 exact
asset comparisons. All three main branches were clean and aligned after fetch.

The final English evidence commit follows normal native activation; its exact
SHA and verification are recorded in the parent cycle checkpoint. Clients are
unchanged and do not need another publication. Native backup still briefly
stops API/tunnel. Browser, private production dossier and professional human
acceptance were not performed; no inference calls or provider changes occurred.

Next audit: a separately consented typed synthesis contract, including distinct
own/related claim kinds and source-specific editorial roles. Existing saved and
claims_v1 inputs must stay unchanged. Full architecture, source authority ranking,
applicability, GENERAL and complete Market Access acceptance remain OPEN.
