# Shared source-change journey verification — 1.47

Status: DONE within the verified bounded fixture journey. Scope recorded before implementation, 29 September 2026;
MV2-002/020/023 and architecture C11/C13/C26/C44.

## Outcome and dependencies

Prove the existing shared Legal and Pharma path across real API/job boundaries,
and correct stale architecture claims from evidence. Reuse versioned templates,
domain context, native page acquisition, monitoring-research scheduler/worker,
DossierClaim/ClaimReview, evidence changes, source-analysis Ask, Coverage and
existing access controls. Do not create parallel Finding or Claim records.

Source readiness: explicitly fictional local HTML and scripted model responses;
no live drug/legal assertions, paid research, private production dossiers, new
source registration or source-rights claims. The Pharma context names the planned
Semaglutide—Switzerland example, but the test page only describes a fictional
administrative record. Existing selected catalogue packs are not asserted to have
been scanned. Clients and runtime behavior should remain unchanged unless the
journey reveals an actual defect requiring a separately scoped repair.

## Acceptance

1. Create one Legal control and one Pharma Market Access dossier through the same
   APIs, retaining the selected template and explicit domain context after reload.
2. Acquire baseline/A/B via the real scanner with a local FakeFetcher; drive due
   research through the existing worker. Retain exact original version evidence,
   acquisition provenance and the paired change; no hand-seeded claims/evidence.
3. Unchanged captures must retain the same version and produce no duplicate
   research, claim or inference call.
4. Review the acquired findings through authorized revision/evidence-pinned APIs:
   accept one with explicit claim kind/source roles, dismiss another, retain the
   same claim IDs/machine assessments, review history and audit events. Exact
   retries must not duplicate decisions; stale requests must fail.
5. Explicit typed source-analysis Ask must receive current human state and both
   retained versions, produce checked literal quotations and separate AI analysis,
   and preserve citation version provenance. Review reasons remain private.
6. A subsequent failed source attempt must be visible in Coverage while prior
   success/evidence remain readable; unchanged recovery must not reanalyse.
7. Private evidence and generated notes must remain unavailable to anonymous and
   foreign-workspace readers. Public listings remain empty.
8. Record precise remaining gaps: required review policy, explicit supersession,
   independent conflicting-source acquisition, coverage-to-Ask integration and live
   Market Access source contracts/human acceptance. Fixture success closes none of
   those broader requirements.

## Checks and release evidence

Two integration cases passed in 64.23 seconds, one per product, plus the backlog
invariant (three distinct Core cases). Exact `ruff check services/api
deploy/release_manager.py` passed. The first run correctly rejected a duplicated
source assessment in the new test request: a paired comparison contains the
claim's own citation as well. Deduplicating the test's assessments by captured
source ID fixed the fixture; no production guard or runtime code changed.

The proof creates one dossier per fixture, reloads the saved template/context,
retains three acquired page versions and two worker-generated claims, and verifies
one paired UPDATES comparison. Unchanged scans and failure recovery add no
research. Two decisions and two review events survive exact retries; stale
revisions fail. Typed Ask receives the accepted current claim and rejected earlier
claim, both source-version pins and explicit editor assessments. Literal quotation
and AI interpretation remain separate, and reviewer rationale is not model input.
Anonymous and foreign-workspace access fails through actual API routes.

Untouched 1.46 runtime and clients retain their completed regression evidence;
the 232-client-case suites/builds are not claimed as new runs in this cycle.
No client files or runtime service modules changed. Existing Sites 46 remain
in place. Core publication/activation and protected-value checks are recorded
separately below. Frozen 1.35/1.37 receipts and unopened validation are preserved.

## Limits identified by the composed proof

C13 is PARTIAL, not TODO: the existing transaction already stores ClaimReview and
its audit event atomically on the extracted claim. Review classification is
versioned editor context, not canonical subject/predicate/object or truth.
Required domain review rules, claim validity and explicit supersession remain open.

The composed case compares two versions of one source. Independent conflicting
source acquisition is still a separate proving requirement; existing isolated
contradiction tests must not be relabeled as a new live vertical demonstration.
Coverage shows failed scans and limitations, but this Ask contract does not yet
receive a dossier coverage manifest. The recorded template/domain context does
not automatically become retrieval or inference context. Requested sources in
profile.config.source_requests are also not projected by product_coverage yet.
These are next scoped integration directions, not completed acceptance.

The named Semaglutide—Switzerland context is user-provided fixture metadata. No
BAG, Swissmedic, EMA or reimbursement facts, source rights or real human decisions
were validated by these tests. P6, the full target and professional acceptance
remain OPEN.


## Publication and verification

Core `afdeae8a8f3eb2b461b5558dfc975573d176e98f` activated as
`git-afdeae8a8f3e` at 2026-09-29T11:53:52+00:00. The
[frozen receipt](product-releases/2026-09-29-1.47-shared-journey.json) records
fresh exact hashes for 41 runtime modules, unchanged DomainPack 1.4.0 and
0bd495bef125 schema, five containers and all nine native routes. Fresh fetches
confirmed all three main checkouts clean/aligned. Both product homes returned 200;
Sites reported both existing projects active/public with latest version 46.

Legal remains `d42bfac5fc46485037068f446e55f4b2d24917da`; Pharma remains
`239578eafddba919eee511ac5f276e80eae3f6b8`. The frozen prior 1.46 receipt's 45
access/HTTP checks and 47 exact assets per client were checksum-verified and
reused, not rerun or republished. The new cycle's local evidence is two composed
integration cases plus the backlog invariant; exact lint and protected-value/
shared-source scans passed. The 1.23 completed backlog overview was archived
verbatim without changing the 512 KiB guard.

The normal deployment passed its smoke/functional policy. Its separate integration
step was explicitly skipped under existing policy; the two affected integration
cases ran locally before publication. Native backup still briefly pauses API/tunnel;
no zero-downtime claim is made. No browser, private production dossier, paid model
probe or real professional review occurred. Final documentation activation is
observed in the parent checkpoint; unchanged clients are retained.
