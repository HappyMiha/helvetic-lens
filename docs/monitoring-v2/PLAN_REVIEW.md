# Monitoring v2 — plan review

Date: 2026-09-10. Plan version: 1.4. This review covers **documentation and plan integrity**, not v2 implementation. Version 1.3 translated the plan into English; version 1.4 records the product-channel split without changing the published task definitions or delivery order.

## Completeness checks

- 71 unique MV2 IDs: 62 required, 9 DEFERRED.
- All 126 exact source AC retained: 116 active (20 CORE, 60 C1/C2/C3/C5/C6/C7, 36 B2/B7/B8), 10 AC-C4 deferred.
- 79 supplemental requirement groups S-01…S-79, each with an accountable task.
- 35 non-DONE legacy HL items have MV2 successors; original text and statuses are preserved.
- Task reference existence, acyclic dependencies, Markdown paths/anchors, closed code fences, unchanged source specification and legacy content checked.

## Independent review and corrections

Specification coverage and compatibility with the current architecture were reviewed separately. The following ambiguities were resolved before completing the plan:

1. MV2-003 can complete a dossier with a blocked outcome; one source's credentials do not stop all other sources.
2. Deferred task IDs are normalized to three digits.
3. Semantic thresholds are calibrated on training/validation data; held-out data is reserved for the independent gate.
4. Legacy read/enqueue budgets are preserved separately from the new time-series workload.
5. Implementation behind a feature flag is separate from model promotion to avoid hidden acceptance cycles.
6. An expiry notice or official link does not replace permitted retained evidence for historical comparison.
7. Metadata-only tender integration does not close required document/Q&A version-diff acceptance.
8. Auction ending-soon hours are configurable; 24h is an example. Stop/continue for one auction does not disable profile discovery.
9. Today exposes explicit Review / Evidence / Not relevant actions; IP deadlines include days_remaining and verification state.

## Scope change following the user's decision

C4 "Customs rates" is a possible future implementation with no current development. MV2-026/027 moved to LATER/P2/DEFERRED; MV2-061 remains deferred. Active tasks have no dependencies on deferred tasks. The UI has 6 Personal + 3 Business templates, 8 subject types and 4 Source Packs. C4 discovery/licensing, pilot and acceptance are excluded; 10 AC-C4 and S-41/42/43 remain DEFERRED, and mixed S requirements have explicit scope notes. The shared numeric engine remains active for C5/C6/C7/B8. Restoring C4 requires a new explicit user decision, not merely an available API.

## First delivery: Pollen Watch

Following the user's next decision, explicit MV2-069/070/071 tasks were added, MV2-030/031 were raised to P0, and their dependencies changed to independent C5 contracts. Validation checks that the transitive predecessors of MV2-071 are only MV2-001/069/070/030/031, without full-v2 source/UI/business/pilot gates. Shared parent acceptance remains required for the remaining scope. Traceability contribution semantics were clarified: preparatory MV2-069/070 do not prematurely require the live end-to-end AC accepted in MV2-031/071, eliminating an implicit acceptance cycle. The active retention/export gate was separately checked for absence of a BAZG/C4 rights requirement. Complete C5 requires official observation **and forecast**; privacy/a11y/language/ops acceptance and a ready first-wave protocol for ≥5 real B2C participants are separately defined. Testing has not yet taken place; the plan does not substitute for future results.

## English edition integrity (version 1.3)

All 71 task IDs, dependencies, phases, priorities, responsible roles, sizes and acceptance-criterion counts were checked against version 1.2. All 126 source AC and 79 supplemental requirement text/location/owner cells remain unchanged. The English specification edition translates 61 prose lines while preserving all 4,534 physical line positions and every original AC. The original source hash and archived backlog content remain unchanged. Active planning and entry documents contain no remaining Cyrillic prose; the immutable source and historical multilingual regression-test input are retained as evidence. Document links/anchors, dependency cycles, C4 exclusions and the independent Pollen Watch delivery path passed validation.

## Workstream organization (version 1.4)

The project map organizes Support & Infrastructure, Legal Hackathon 2026 and Monitoring v2 into **three activities and two code/deployment channels**. Support remains parked by user instruction. Main-product changes, including hackathon connectors, use `main` and its existing automatic deployment on HappySnowman at helveticlens.ch. Monitoring v2 uses `codex/HappyDucky02/monitoring-v2` and an independent deployment on HappyDucky02 at monitoring.helveticlens.ch. The frozen MVP tag remains immutable while `main` continues to evolve.

The active Monitoring v2 backlog belongs to the dedicated branch; its main-branch copy is clearly marked as a published snapshot. The 71-task index and detailed task blocks are unchanged from version 1.3. Additional deployment work must receive an explicit task on the active v2 branch before implementation. Separate deployment setup is in progress, but these documents do not establish public availability, data isolation or branch-triggered updates; those require operational evidence in the deployment task.

## Result boundaries

The documentation changes reviewed here do not implement connectors, alter application code or migrations, or modify the MVP release tag. Deployment implementation and operational evidence are tracked separately on the v2 branch; this review is not evidence of a live site. The 71 published feature-task definitions gain no implementation evidence from routing changes; sources retain their own access and functional gates.

KPI values, pilot samples and new performance targets are proposed criteria of this plan. They are neither the specification author's requirements nor measured results of the current product.
