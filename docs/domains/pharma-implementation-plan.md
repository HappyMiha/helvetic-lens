# PharmaPack implementation plan

Status: planned incremental migration; 28 September 2026. Pharma already runs on
the common Core. This plan extends it rather than creating another Pharma engine.
See [current state](../architecture/current-state.md),
[gap analysis](../architecture/core-gap-analysis.md) and the owner's
[specification](../UNIFIED_TARGET_ARCHITECTURE_SPEC.md).

## Current foundation and limits

The existing product configuration has medicine/active-substance labels, example
questions including Market access, and suggested Swissmedic/EMA/FDA page watches.
Those are UI examples and individual watched pages, not a completed Market Access
template or a verified comprehensive regulatory feed. Core has shared dossier
creation, files, discussion, investigation, claims, page/web/topic monitoring,
source comparisons, local evidence retrieval and explicit publication.

[product_research.public_search](../../services/api/helvetic_lens/product_research.py)
implements Europe PMC literature discovery. This is not a dedicated PubMed,
ClinicalTrials.gov, Swissmedic authorization or BAG reimbursement connector.
General web discovery may find relevant documents, but does not establish source
coverage, current product status or complete market-access research.

## First template and typed context

Implementation update, 28 September: [release 1.31](../PRODUCT_STRUCTURED_CONTEXT.md)
persists optional, versioned Pharma subject fields on the shared dossier with
readable details, explicit editing and change history. Values are user-provided;
they do not resolve entities, alter monitoring or imply source coverage. Exact
product/substance IDs, aliases and applicability remain open.
[Release 1.32](../PRODUCT_DOSSIER_TEMPLATES.md) adds explicit versioned Market Access,
Regulatory Monitor and Safety template selection with retained guidance and
history. It does not establish source readiness or the proving journey below.

The first validated template is **Market Access Dossier**. The proving example is
**Semaglutide — Switzerland**; Wegovy is a possible product context from the
specification, not a factual reimbursement/authorization assertion in this plan.

Proposed optional typed fields: product names and IDs, active substances and IDs,
indications, company names, therapeutic areas, countries/markets, regulatory IDs,
market-access IDs, trial IDs, comparators and tags. Retain alias provenance and
human corrections. A substance is not interchangeable with a brand, presentation,
dose, indication or country. Resolve exact identifiers deterministically where
possible; uncertain matches require review. One field is enough to start a draft.

Store pack/template/context schema revisions. Keep the existing work context and
LegalMonitoringProfile link readable during migration. Both clients use the same
creation and update handlers; domain context does not alter permission scope.

## Source readiness before activation

| Candidate | What can be reused now | Required source gate |
|---|---|---|
| BAG/FOPH and Spezialitätenliste | Existing source/page ingestion infrastructure | Verify official machine/document interface, permitted reuse, stable IDs, market/indication limits, date semantics, change scope and source failure handling |
| Swissmedic | Suggested public page watch and generic capture | Verify the exact source needed for the template; an index-page change is not automatically an authorization or label change |
| EMA | Suggested public page watch | Verify source contract, identifiers and territorial scope; do not equate EU status with Swiss status |
| Europe PMC / clinical evidence | Existing typed public discovery adapter | Keep publication identity, retrieval scope and evidence limits; deduplicate across indexed origins |
| ClinicalTrials.gov / other clinical APIs | Shared fetch/normalization/job foundations | Add only after actual interface, rights and version/update semantics are verified |
| Guidelines / company publications | URL contribution and permitted source reader | Classify authority/interest, retain originals and source-specific permissions |
| Private customer evidence | Existing contained upload/contribution path | Original/hash/uploader/provenance and current access; no automatic hosted disclosure or public projection |

Source validation is implementation work, not a reason to claim these adapters
already exist. Record requested/unsupported/auth-required sources in Coverage.
Build adapters only for the sources needed by the first real slice; other
configured sources must remain honestly incomplete. Do not construct a replacement
public database or promise global source coverage.

## Delivery sequence

| Slice | Complete user outcome | Dependencies and acceptance |
|---|---|---|
| P1: pack-aware setup | Pharma receives appropriate context, suggestions and capability labels through common setup | Internal registry, legacy compatibility and both-client tests; Legal prompt must not be silently reused |
| P2: shared source/scan contracts | User sees exactly which configured sources were attempted and their last success | Existing registry/watch/connector state adapted into durable manifest; failed/disabled/unsupported entries retained |
| P3: common Finding and Review | A source update becomes a reviewable Finding with exact old/new evidence | Stable dedup key; reviewed source revision; accept/dismiss/needs-more-evidence with atomic claim action |
| P4: domain semantics | Product/substance/market/indication and claim type are explicit | Pack schema, exact identifier/alias resolution and mandatory review policies |
| P5: cited dossier Ask | Answer uses reviewed claims and current supporting/contrary evidence | Same shared Ask and local retrieval; coverage/context limitations visible; no invented factual assertions |
| P6: first real Market Access journey | Semaglutide–Switzerland can be created, monitored and reviewed end to end | Source contracts, authorized live readiness, exact release proof and functioning human review |

The cross-platform phases in [target architecture](../architecture/target-architecture.md)
remain the dependency order. These Pharma slices reuse their delivered services;
they do not fork them or require a separate release of untouched clients.

## Review and claim policy

Register regulatory status, market-access status, safety signal, clinical result,
label change, reimbursement change, supply event, competitor event, evidence
interpretation and AI analysis separately. A retrieved document states a source
fact; its significance for reimbursement or safety may be an interpretation.

Require a recorded human decision for high-impact/safety findings, generative
regulatory or reimbursement interpretation, contradictory evidence, uncertain
product/indication match and incomplete coverage as defined by the versioned
policy. The system may collect, compare and propose automatically; it must not
fabricate the reviewer's identity or treat a classifier score as approval.

## Smallest shared end-to-end proof

Run one Legal control dossier and one Pharma Market Access dossier through the
same API, job, evidence and review contracts:

1. Create with domain/template/context; reload the persisted draft.
2. Configure at least the source necessary for the example and an explicit
   unavailable source. Record the difference between fixture and live readiness.
3. Capture version A, original artifact, provenance and exact passages.
4. Repeat unchanged capture: no duplicate version, Finding or unnecessary AI call.
5. Capture version B: deterministic change, linked Finding and visible manifest.
6. Accept through an authorized, revision-pinned review; atomically create/update
   a typed Claim. Dismiss a second Finding and retain its audit record.
7. Preserve a conflicting source; mark the disagreement rather than erase it.
8. Ask what changed: cite exact evidence/version and review state with incomplete
   coverage explicitly disclosed. Verify private evidence stays private.
9. Make the next source attempt fail: retain prior success and historical evidence;
   do not present the scan as complete or the prior status as freshly checked.

Fixtures establish mechanics without making factual drug or legal claims.
Production release identity, source permissions/readiness and real human review
decisions are separate evidence. The example is not complete if only the UI
renders a preset dossier name.

## Verification and completion

Reuse existing product, version/history, source-health, investigation, claim-change,
access/publication, evidence-retrieval and decision-adapter tests. Add behaviour
tests for exact substance/product alias matching; market/indication mismatch;
regulatory/reimbursement version change; clinical duplicate identity; delayed and
unavailable source; required review; replay-safe acceptance; stale review and
permission revocation; deterministic processing making no model calls.

For changed API code run the exact lint gate and affected suites. For each changed
client run its tests, lint, typecheck and build, then publish the exact validated
artifact to its existing project. Observe the normal native deployment and verify
actual release identity. Do not rerun paid research solely to manufacture a demo.

Full §74 remains open until all nine criteria have corresponding evidence. An
unavailable required source stays explicitly open. Validate the human review
workflow without pretending a test reviewer certified real drug evidence;
continue independent implementation without inventing coverage or sign-off.
