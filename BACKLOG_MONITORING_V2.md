# Helvetic Lens Monitoring v2 — active implementation backlog

**Plan version:** 1.6 · **Date:** 10 September 2026 · **Code baseline:** `7109a2891f9c99e53572008cc7c1a86001792a57`

**Status:** implementation and acceptance tracking; individual task evidence distinguishes implemented, tested and deployed behavior.

**Scope:** 9 required scenarios, 64 required tasks, 9 deferred tasks. 116 active acceptance criteria (AC); 10 AC-C4 criteria retained as deferred.

**Principle:** authoritative source → material change → personal relevance → evidence → user decision.

## Development and deployment

The main-branch copy of this file is the sole active Monitoring backlog. The user's
12 September 2026 instruction replaces multi-computer, host-alias, task-branch and
separate Monitoring integration rules: **one agent, complete features, commit and
push main**. Both sites keep separate deployments, private data and source approvals.
See [the development cycle](docs/DEVELOPMENT.md) and [release evidence](docs/monitoring-v2/DEPLOYMENT_STATUS.md).

## How to use this backlog

Define a complete user outcome and its criteria, implement across as many continuations
as needed, then run required tests, fix failures, update English evidence, commit and
immediately push main. Continue the next feature while existing deployment checks run;
never duplicate or interrupt them. Preserve unfinished work in the development checkout.
Do not publish unfinished technical substeps or mark DONE merely because code was pushed.

This is the single source of scope, priorities, dependencies and acceptance for Monitoring.
Support is parked; hackathon work has its own entry page in [PROJECT_MAP.md](PROJECT_MAP.md).
The [previous backlog](BACKLOG_V1_ARCHIVE.md) is history; its outstanding obligations remain
in the [legacy disposition](docs/monitoring-v2/LEGACY_DISPOSITION.md).

Input: [Practical Use Case Specification v1.0 — English reading edition](docs/monitoring-v2/requirements/HELVETIC_LENS_PRACTICAL_USE_CASE_SPECIFICATION_v1.0_EN.md). The [original source](docs/monitoring-v2/requirements/HELVETIC_LENS_PRACTICAL_USE_CASE_SPECIFICATION_v1.0.md) is preserved byte for byte, SHA-256 `a6f4e7da87a9ae30171164512d16ce4be411f2913c22d90ed7bf7e1bc94ece4c`. The English edition preserves line positions and all original AC wording; it translates the remaining source prose without changing requirements.

**User scope decision on 2026-09-10 (version 1.1):** customs rates are a possible future implementation and must not be taken into development. C4, the Swiss Customs source pack, the CURRENCY template, MV2-026/027/061 and their criteria are retained only as future possibilities. They are excluded from v2.0 implementation, UX, discovery/licensing, pilot and acceptance, and are not release blockers. Returning them to scope requires a new explicit user decision and an update to this backlog; no implementation date is set. This decision supersedes the original specification's scope.

The source document's statements about existing capabilities have been checked against the code and are not treated as implementation evidence. The plan and architectural decisions below result from that analysis; example amounts, dates, cities, thresholds and scores in the specification have not become implicit global defaults.

Before implementation, read the task criteria, dependencies, source gate and inherited legacy obligations. Record necessary refinements as explicit MV2 subtasks in this backlog, then implement on main. Preserve the full acceptance coverage of parent tasks.

Statuses: **PLANNED → READY → IN PROGRESS → VERIFYING → DONE**. **BLOCKED** always identifies a specific external dependency, owner and next action. **DEFERRED** is outside v2.0. READY means that dependencies are satisfied and the necessary contracts/data are available. The first C5 delivery uses the explicitly extracted MV2-069/070 contracts without waiting for the broader parent tasks to be DONE. Code in Git, a mock, passing JSON schema validation or a written document does not mean DONE.

**P0** means integrity, shared foundations or a gate before the relevant external pilot. **P1** is a required v2.0 capability. **P2** is explicitly deferred scope. These are development priorities, distinct from the specification's P1/P2/P3 notification priorities.

Roles identify responsibility, not an already staffed team. S/M/L indicates relative uncertainty and effort, not a calendar estimate. L-sized tasks require refinement before implementation.

## Product decision

The user specifies **what matters to them**. Setup follows Create Monitor → Personal/Business → understandable fields → preview of expected data/matches → explicit Start. A single ongoing loop follows: Today → What changed → Why received → Evidence → Decision → ongoing monitoring. Ordinary users do not need to enter a source API key or design a crawler.

| ID | User outcome | Main required tasks |
|---|---|---|
| C1 | Warnings for Home/Office and other Swiss locations | MV2-028, MV2-029 |
| C2 | Changes affecting a regular journey/line/stop on the relevant days and at the relevant times | MV2-037, MV2-038, MV2-039 |
| C3 | A2/Gotthard/A13: direction, closures, congestion and planned changes | MV2-037, MV2-040, MV2-041 |
| C4 | **Possible future implementation; excluded from v2.0 development** | DEFERRED: MV2-026, MV2-027, MV2-061 |
| C5 | Selected pollen near a supported station, with observations and forecasts | MV2-030, MV2-031 |
| C6 | Water/station: level, discharge, temperature and official danger state | MV2-032, MV2-033 |
| C7 | PM2.5/PM10/O3/NO2: meaningful changes, improvements and limitations | MV2-034, MV2-035 |
| B2 | Tender discovery and changes to already monitored tender dossiers | MV2-042…045 |
| B7 | Exact/lexical/phonetic IP candidates and register/deadline review | MV2-046…048 |
| B8 | Official Ticino auctions: asset, budget, deadlines and conditions | MV2-049, MV2-050 |

Shared UI: **Today / Monitoring / Investigate / Workspace / Admin**. Existing Topics, laws, Discover, Impact Inbox/Matrix, Digests and Marvin receive clear places in this structure. All active scenarios share navigation. Semantic AI supports explained business ranking, while active C1/C2/C3/C5/C6/C7 and numeric/time-based B8 rules work without an LLM.

The value beyond an ordinary subscription is one verifiable history of material updates, with a reason specific to the user and renewed review when an already reviewed fact changes.

## First delivery — complete Pollen Watch for real users

**Next product outcome:** a complete Pollen Watch, accepted under MV2-071 and ready for the first round of testing with people. This is the first scenario to implement. Until it is ready, the tasks below and their necessary shared foundations take priority; source discovery for other active cases may run in parallel. Their connectors and user-facing capabilities must not precede C5 without a new priority decision.

**Sequence:** MV2-001 → MV2-069 → MV2-070 → MV2-030 → MV2-031 → MV2-071 → ready to begin user testing; the next active v2 scenarios may then start. F3 denotes a domain group, not a requirement to wait for all of F1/F2. MV2-001 is DONE; MV2-069 and MV2-070 are IN PROGRESS, with C01a using the recorded configuration contract while source gates remain open. Subsequent tasks remain PLANNED. No complete Pollen Watch or real-user acceptance is claimed.

| Step | Concrete outcome | Acceptance owner |
|---|---|---|
| C5 contract | Supported locations/stations/allergens, rules and UX; separately verified official observation **and forecast** channels, rights and live samples | [MV2-069](#mv2-069) |
| Platform for C5 | Personal monitor, generic states/rules/evidence/history, Today/review/reopen, working in-app/email delivery, privacy, recovery and necessary legacy compatibility | [MV2-070](#mv2-070) |
| Official integration | Real observed/forecast states, versioned categories/units, freshness, corrections and coverage | [MV2-030](#mv2-030) |
| Complete user journey | Setup → current state → material change → why/evidence → review → new revision/reopen → notification; all 10 AC-C5 criteria | [MV2-031](#mv2-031) |
| Ready for user testing | Independent acceptance, privacy/operations/device/language evidence, a protected environment and a protocol for the first round with ≥5 B2C participants | [MV2-071](#mv2-071) |

**Completeness boundary:** an observation-only connector, a demo with a mocked forecast, a card without working rules/delivery/history, or unverified coverage does not complete Pollen Watch. If the official forecast gate has not passed, full delivery remains BLOCKED with a specific next action. Waiting for a natural category crossing must not hide the current state: current official data is visible immediately; labelled historical replay demonstrates transitions separately from live freshness.

**Dependency boundary:** MV2-069/070 are explicit C5-scoped subtasks of shared parent tasks, with their own AC and evidence. They do not depend on those broader parents being DONE. MV2-030/031 depend on these extracted contracts; MV2-071 does not wait for business AI, all sources, the UI for every template or the general v2 pilot. Parent tasks reuse the result and close only when their entire scope is complete; the C5 contribution does not automatically make them DONE.

| Explicit C5 subtask | Contribution to parent tasks | Remaining parent scope |
|---|---|---|
| MV2-069 | MV2-002/003/015/025: C5 journey, source/forecast rights and coverage contract | Other active use cases and completeness of the shared catalogue/UX |
| MV2-070 C01–C02 | MV2-004…011/015/017/020/053/055: C5 personal configuration, persistence, rules, isolation, stations, evidence and history | Other typed schemas, rules/geography and full rights/data acceptance |
| MV2-070 C03–C04 | MV2-012…014/017…022: full C5 UI/review/delivery loop with legacy feed compatibility | Other v2 cards/forms and domain-specific/team workflows |
| MV2-070 C05–C08 + MV2-071 | MV2-016/024/025/052…056/060/068: C5 access, languages/accessibility, operations/capacity/privacy/retention, bridge and restore | Full-v2/inherited matrices, other locale×domain flows, full target-host workload and business evaluation |

The first test with ≥5 people checks usability and helps find defects. It does not replace the four-week MV2-058 pilot with ≥10 B2C participants and ≥5 organizations, or prove general v2 KPIs. User results exist only after actual sessions. Fixes arising from those sessions receive explicit MV2 IDs/subtasks in this same backlog before implementation.

## Architecture and source gates

The [architecture decision](docs/monitoring-v2/ARCHITECTURE.md) defines an additive generic kernel within the existing FastAPI/PostgreSQL/Celery/Next.js stack. The [code audit](docs/monitoring-v2/BASELINE_AUDIT.md) shows that legal-only CHECK/FK constraints, connectors, Today grouping and ActionDecision cannot support these cases merely by adding templates. Keep the stack, jobs/outbox, authentication, artifact storage, local models and regulatory domain; add typed entities, states, developments, rules and a compatibility bridge.

Key invariants: immutable evidence; idempotent ingestion/delivery; source state ≠ review ≠ decision ≠ delivery; source failure ≠ no change/all-clear; source severity ≠ user relevance ≠ notification priority; UNKNOWN ≠ 0; forecast ≠ observation. Match reasons belong to a workspace/subject revision, while official data may be shared.

The [source feasibility review](docs/monitoring-v2/SOURCE_FEASIBILITY.md) contains dated official references and verification limits. **A documented API does not establish an implemented connector or approved access.** MV2-003 can close once all nine active cases have an accurate dossier and an approved/blocked outcome; it does not require obtaining every credential at the same time. Each adapter also has its own **G(case)**: permitted access → schema/identity/coverage contract → permitted live sample → lifecycle/quality → rights enforcement. C4 is excluded from MV2-003 and current source gates; no C4 rights/access investigation is scheduled now.

| Gate | Current planning finding | Owner / next action |
|---|---|---|
| G(C1), G(B8) | Official pages exist; supported APIs/automated reuse have not been established | Integration, MV2-028/049: supported channel and permitted monitoring contract |
| G(C3) | FEDRO access term and raw-data export restrictions | Integration/Operations, MV2-040: permitted derived fields, renewal and retention |
| G(B2) | SIMAP API, publication terms and separate attachment rights | Integration, MV2-042: client contract, publication timing/corrections and access-gated documents |
| G(B7) | IPI API through an account/terms; permission for monitoring emails needs clarification | Product/Integration, MV2-046: document the channel scope in writing |
| G(C2), G(C6) | Documentation exists, but rate limits/live-window definitions are ambiguous | Integration, MV2-038/032: conservative bounded probe and contract clarification |
| G(C5), G(C7) | C5 observation OGD is documented; official forecasts need separate confirmation in MV2-069. Air coverage depends on station/dataset | Integration, MV2-069/030/034: observation and forecast contracts, exact stations/metrics/units/rights |

For the nine active scenarios, an unmet required source gate leaves the required task BLOCKED and full v2.0 unaccepted. An external website link or mock does not satisfy an automatic monitoring AC. UNKNOWN is honest behavior for an individual record; systematic absence of a mandatory capability, such as forecast, delay, documents/Q&A or a deadline, leaves the corresponding AC open. Signing terms, purchasing access, registering on behalf of a company or submitting external applications are separate explicit actions for the owner/authorized implementer during execution.

## Implementation sequence and checkpoints

**Execution instruction — user decision, 2026-09-11:** Continue development
iteratively while previous changes undergo tests and automatic deployment.
Pending verification alone does not block the next ready task or independently
implementable slice using recorded versioned contracts. Run checks in the
background, collect results without duplicate runs, prioritize failures and
record implementation, push, test and release evidence separately. Keep pending
acceptance IN PROGRESS/VERIFYING; DONE still requires all applicable gates.
Source rights, missing required contracts and unsafe dependencies remain real
blockers. See [the iteration workflow](docs/MULTI_PC_DEVELOPMENT.md#monitoring-iteration-continues-during-verification).

Start with MV2-001 and the first Pollen Watch work: MV2-069/070/030/031/071. UX MV2-002 and source dossiers MV2-003 for other active scenarios may proceed in parallel; their full DONE status does not block C5. Once the minimum persistence/rule/delivery contracts exist, build the **complete C5 delivery** without waiting for all domains or a perfect generic framework. Catalogues/interfaces for other sources may be investigated in parallel; activation requires their gates. Task IDs are not execution order: for example, MV2-060/068 provide early compatibility work, not post-release work.

| Checkpoint | Outcome and exit evidence |
|---|---|
| G0: F0 | Architectural contracts, reproduced legacy baseline, investigated UX journeys and source dossiers; blockers have owners |
| G1: FIRST, Pollen Watch | MV2-069/070/030/031/071: complete C5 with real official observations + forecasts; 10 C5 AC and CORE within C5 scope, ready for user testing; independent of completion of other domains |
| G2: F3 | C1/C5/C6/C7 accepted against their own AC and source gates; shared numeric/location contracts verified |
| G3: F4 | C2/C3 with time/route/expiry, direction and restoration; explained cross-source association |
| G4: F5 | B2/B7/B8 with discovery **and** change monitoring, calibrated semantic candidates, documents, deadlines and decisions |
| G5: F6 | 116 active AC (10 AC-C4 deferred), inherited regressions, five-language/accessibility acceptance, target-host capacity/recovery, privacy and pilot; independent go/no-go |
| Release | MV2-059: v2.0 artifacts and upgrade/rollback runbook; production deployment requires separate authorization |

F2 does not require completing the entire UI before the first delivery: only the needed portions of dependent tasks are required, while DONE requires all their criteria. Whenever an extracted portion becomes an independent work item, add it to this backlog as a subtask with its own dependencies.

MV2-023/043/047 complete implementation behind feature flags after training/validation checks; the independent held-out gate MV2-051 later permits production promotion. Their DONE conditions do not block each other in a cycle.

Design F6 test protocols/fixtures from the start; the listed dependencies govern final execution and gate closure.

The first delivery's critical external path is verified C5 observation **and forecast** channels, rights and coverage in MV2-069. For the remainder of v2, it is C1, B7 and B8 rights/access and verified source coverage. The engineering path is entity/state/evidence → rules/development → scoped relevance/outbox → one UI loop → nine adapter+journey deliveries → quality/recovery/pilot. No calendar commitments are made before source gates and staffing have been assessed.

## Definition of Ready and Definition of Done

**Ready:** the implementer understands the task; predecessors are complete, or an approved versioned interface exists for an explicitly recorded subtask; source access needed for implementation is permitted; independent positive/negative fixtures and target acceptance are defined; a review owner is assigned.

**Done:** all task AC, the task's explicitly defined contribution to mapped source AC in active scope, and inherited outstanding legacy acceptance within the task's scope are satisfied. API/database/UI and the source path have been verified within that scope. Record the commit, test command/result, fixture hash, source/schema/rule version, rollout flag, limitations and reviewer. No critical defects remain; update the task status and traceability evidence. Field, human and hardware criteria require the corresponding evidence, not an agent's self-assessment.

**Traceability does not create hidden dependencies:** when an AC has multiple task owners, each closes only its named deliverables/contribution. The MV2-069 dossier does not require a finished UI; MV2-070 checks platform contracts/components before the live connector. Full C5 source-to-user acceptance belongs to MV2-031/071; full cross-domain acceptance belongs to MV2-057. An AC reference in a preparatory task does not require completing later tasks and does not close the entire AC.

Each active case's adapter + workflow must cover initial state, new/material updates, unrelated/nonmaterial negatives, duplicate replay, applicable cancellation/restoration, a stale source, history/evidence, personal/team permissions, review/reopen and channel policy. Not every numeric series has an official all-clear; do not invent one.

Earlier reasons remain reproducible after source/rule/profile changes and after review. A source that permits only a limited evidence representation must not receive an implicit raw-export path.

## Measurement, assumptions and deferred scope

The numerical gates below are **proposed plan targets**, not specification facts or current results. Fix them before measurement; changes require a justified plan revision rather than fitting targets to results.

- First value: setup to the first understandable current/saved source-backed state ≤5 minutes; measure waiting for a new natural event separately. Median alert-to-understanding ≤60 seconds.
- Pilot: ≥90% delivered relevance precision, ≥90% material-change precision, ≥90% understandable explanations, duplicates <1%. Every denominator and sample size is visible; aggregate results must not hide a failing case.
- Candidate evaluation: ≥85% precision / ≥90% recall for business ranking on an independent held-out set, with ≥200 labelled pairs and ≥50 for each of B2/B7/B8. This is not a probability of IP infringement.
- Capacity: the existing 100-account/10-organization gate plus a proposed 1000 subjects/1M observations; retain legacy read p95≤500ms and enqueue≤1s. Proposed budgets for new time-series/history endpoints are p95≤2s and post-ingest deterministic processing≤30s. Measure upstream and delivery lag separately. Actual supported cadence depends on the source.
- Four-week pilot: ≥10 B2C participants and ≥5 independent organizations. When events are sparse, use historical replay as separate evidence, not as a substitute for live samples.
- English-first implementation, with new v2 five-language acceptance inheriting the EN/DE/FR/IT/RM contract; preserve the exact language of official documents. Machine translation does not replace independent language review.

MV2-036 deliberately includes the source-described correlation opportunity in v2 as bounded, explainable association. This is a plan decision, not a minimum specification AC. C4 customs rates are fully deferred, including the connector, currency selection, thresholds, history, digest and purchase calculator; they do not start automatically after v2.0. An extended tender lifecycle and national auction expansion are possible post-2.0 scope. Additional vertical use cases, a navigation engine, medical treatment, infringement verdicts, autonomous bids/filings, a new identity system and an unsupported stack replacement are outside this plan.

Five historical conditional directions remain explicit DEFERRED tasks MV2-063…067, not an implicit parallel development stream.

## Task index

| ID | Task | Phase | Priority | Size | Status | Dependencies |
|---|---|---|---|---|---|---|
| [MV2-001](#mv2-001) | Establish extension contracts and MVP compatibility | F0 | P0 | M | DONE | None |
| [MV2-002](#mv2-002) | Validate first-value journeys and shared navigation | F0 | P0 | M | PLANNED | None |
| [MV2-003](#mv2-003) | Verify source rights, coverage and contracts for the nine active scenarios | F0 | P0 | L | PLANNED | [MV2-001](#mv2-001) |
| [MV2-004](#mv2-004) | Personal workspace and team monitoring permissions | F1 | P0 | M | PLANNED | [MV2-001](#mv2-001) |
| [MV2-005](#mv2-005) | MonitoringSubject and versioned Monitoring Templates | F1 | P0 | L | PLANNED | [MV2-001](#mv2-001), [MV2-004](#mv2-004) |
| [MV2-006](#mv2-006) | ObservedEntity: stable source identity | F1 | P0 | M | PLANNED | [MV2-001](#mv2-001), [MV2-003](#mv2-003) |
| [MV2-007](#mv2-007) | ObservedState and immutable evidence | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006) |
| [MV2-008](#mv2-008) | Deterministic ChangeRule, ChangeSet and numeric thresholds | F1 | P0 | L | PLANNED | [MV2-005](#mv2-005), [MV2-007](#mv2-007) |
| [MV2-009](#mv2-009) | Development, deduplication and lifecycle | F1 | P0 | L | PLANNED | [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-008](#mv2-008) |
| [MV2-010](#mv2-010) | Structural relevance with evidence for every match | F1 | P0 | L | PLANNED | [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-009](#mv2-009) |
| [MV2-011](#mv2-011) | Reliable state ingestion, queues and freshness | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-009](#mv2-009) |
| [MV2-012](#mv2-012) | Notification policy and transactional outbox | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-011](#mv2-011) |
| [MV2-013](#mv2-013) | Review, Decision and owner assignment | F1 | P0 | M | PLANNED | [MV2-004](#mv2-004), [MV2-009](#mv2-009) |
| [MV2-014](#mv2-014) | Shared-feed API and read projections | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-013](#mv2-013) |
| [MV2-015](#mv2-015) | Geography, station and coverage catalogue | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006) |
| [MV2-016](#mv2-016) | Time windows, deadlines and reminders | F1 | P0 | L | PLANNED | [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-012](#mv2-012) |
| [MV2-017](#mv2-017) | Create Monitor: nine understandable templates | F2 | P1 | L | PLANNED | [MV2-002](#mv2-002), [MV2-005](#mv2-005), [MV2-010](#mv2-010), [MV2-015](#mv2-015) |
| [MV2-018](#mv2-018) | Monitoring: manage saved subjects | F2 | P1 | M | PLANNED | [MV2-005](#mv2-005), [MV2-011](#mv2-011), [MV2-017](#mv2-017) |
| [MV2-019](#mv2-019) | Today: one card across all domains | F2 | P1 | L | PLANNED | [MV2-014](#mv2-014), [MV2-017](#mv2-017) |
| [MV2-020](#mv2-020) | Investigate: states, diffs, evidence and history | F2 | P1 | L | PLANNED | [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014) |
| [MV2-021](#mv2-021) | Workspace: Impact Inbox, decisions and Impact Matrix | F2 | P1 | M | PLANNED | [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-019](#mv2-019), [MV2-020](#mv2-020) |
| [MV2-022](#mv2-022) | Notifications and Digests from the same developments | F2 | P1 | L | PLANNED | [MV2-012](#mv2-012), [MV2-014](#mv2-014), [MV2-019](#mv2-019) |
| [MV2-023](#mv2-023) | Ask and Marvin in the context of v2 evidence | F2 | P1 | M | PLANNED | [MV2-010](#mv2-010), [MV2-020](#mv2-020) |
| [MV2-024](#mv2-024) | Clear guidance, accessibility and five languages | F2 | P0 | L | PLANNED | [MV2-002](#mv2-002), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022) |
| [MV2-025](#mv2-025) | Admin: accurate source capabilities and access management | F2 | P0 | M | PLANNED | [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-018](#mv2-018) |
| [MV2-026](#mv2-026) | Possible future implementation: C4 official customs-rate connector | LATER | P2 | M | DEFERRED — possible future implementation; do not start development | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011) |
| [MV2-027](#mv2-027) | Possible future implementation: C4 currency, thresholds, history and digest | LATER | P2 | M | DEFERRED — possible future implementation; do not start development | [MV2-008](#mv2-008), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-022](#mv2-022), [MV2-026](#mv2-026) |
| [MV2-028](#mv2-028) | C1: official warnings and hazard geography | F3 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071) |
| [MV2-029](#mv2-029) | C1: Home/Office locations and the complete warning workflow | F3 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-028](#mv2-028) |
| [MV2-030](#mv2-030) | C5: official pollen observations and forecasts | F3 | P0 | M | IN PROGRESS | [MV2-069](#mv2-069), [MV2-070](#mv2-070) |
| [MV2-031](#mv2-031) | Pollen Watch — the first complete end-to-end scenario (C5) | F3 | P0 | L | IN PROGRESS | [MV2-070](#mv2-070), [MV2-030](#mv2-030) |
| [MV2-032](#mv2-032) | C6: hydrological stations, metrics and official danger levels | F3 | P1 | M | VERIFYING | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071) |
| [MV2-033](#mv2-033) | C6: River / Lake thresholds, escalation and history | F3 | P1 | M | VERIFYING | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-032](#mv2-032) |
| [MV2-034](#mv2-034) | C7: official air-quality series and interpretation | F3 | P1 | M | VERIFYING | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071) |
| [MV2-035](#mv2-035) | C7: Air Quality — metrics, changes and improvements | F3 | P1 | M | VERIFYING | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-034](#mv2-034) |
| [MV2-036](#mv2-036) | Related developments from multiple sources | F4 | P1 | M | PLANNED | [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-029](#mv2-029), [MV2-033](#mv2-033), [MV2-041](#mv2-041), [MV2-071](#mv2-071) |
| [MV2-037](#mv2-037) | Journey/Trip/Route/Stop and Road Corridor reference data | F4 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-015](#mv2-015), [MV2-016](#mv2-016), [MV2-071](#mv2-071) |
| [MV2-038](#mv2-038) | C2: Service Alerts and Trip Updates | F4 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071) |
| [MV2-039](#mv2-039) | C2: Regular commutes and low-noise transport alerts | F4 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-038](#mv2-038) |
| [MV2-040](#mv2-040) | C3: ASTRA traffic and planned closures | F4 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071) |
| [MV2-041](#mv2-041) | C3: My Route Watch for A2 / Gotthard / A13 | F4 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-040](#mv2-040) |
| [MV2-042](#mv2-042) | B2: SIMAP discovery and publication monitoring | F5 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071) |
| [MV2-043](#mv2-043) | B2/B7/B8: Structured profiles and semantic candidate ranking | F5 | P1 | L | PLANNED | [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-010](#mv2-010), [MV2-071](#mv2-071) |
| [MV2-044](#mv2-044) | Versioned document sets and conditions | F5 | P1 | L | PLANNED | [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-071](#mv2-071) |
| [MV2-045](#mv2-045) | B2: Tender discovery → review → material update | F5 | P1 | L | PLANNED | [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-042](#mv2-042), [MV2-043](#mv2-043), [MV2-044](#mv2-044) |
| [MV2-046](#mv2-046) | B7: Official trademark publications and register updates | F5 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071) |
| [MV2-047](#mv2-047) | B7: Exact, lexical and phonetic candidates | F5 | P1 | L | PLANNED | [MV2-043](#mv2-043), [MV2-046](#mv2-046) |
| [MV2-048](#mv2-048) | B7: IP review, review deadlines and register changes | F5 | P1 | L | PLANNED | [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-046](#mv2-046), [MV2-047](#mv2-047) |
| [MV2-049](#mv2-049) | B8: Official Ticino auctions | F5 | P1 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071) |
| [MV2-050](#mv2-050) | B8: Auction profiles, price limits and ending-soon alerts | F5 | P1 | L | PLANNED | [MV2-008](#mv2-008), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-043](#mv2-043), [MV2-044](#mv2-044), [MV2-049](#mv2-049) |
| [MV2-051](#mv2-051) | Independent matching and local AI evaluation | F6 | P0 | L | PLANNED | [MV2-023](#mv2-023), [MV2-043](#mv2-043), [MV2-047](#mv2-047) |
| [MV2-052](#mv2-052) | Operational metrics, degraded mode and source recovery | F6 | P0 | M | PLANNED | [MV2-011](#mv2-011), [MV2-012](#mv2-012), [MV2-025](#mv2-025) |
| [MV2-053](#mv2-053) | Personal-location privacy and access control | F6 | P0 | M | PLANNED | [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-023](#mv2-023) |
| [MV2-054](#mv2-054) | Single-server capacity and queues with different priorities | F6 | P0 | L | PLANNED | [MV2-011](#mv2-011), [MV2-014](#mv2-014), [MV2-043](#mv2-043), [MV2-052](#mv2-052) |
| [MV2-055](#mv2-055) | History storage, retention and permitted exports | F6 | P0 | M | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-020](#mv2-020), [MV2-044](#mv2-044) |
| [MV2-056](#mv2-056) | Migration, compatibility and rollback rehearsal | F6 | P0 | L | PLANNED | [MV2-001](#mv2-001), [MV2-053](#mv2-053), [MV2-055](#mv2-055), [MV2-060](#mv2-060) |
| [MV2-057](#mv2-057) | Executable checks for 116 active AC and adversarial regression | F6 | P0 | L | PLANNED | [MV2-029](#mv2-029), [MV2-031](#mv2-031), [MV2-033](#mv2-033), [MV2-035](#mv2-035), [MV2-036](#mv2-036), [MV2-039](#mv2-039), [MV2-041](#mv2-041), [MV2-045](#mv2-045), [MV2-048](#mv2-048), [MV2-050](#mv2-050), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-053](#mv2-053), [MV2-056](#mv2-056), [MV2-068](#mv2-068), [MV2-071](#mv2-071) |
| [MV2-058](#mv2-058) | Measured B2C/B2B pilot | F6 | P0 | L | PLANNED | [MV2-002](#mv2-002), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-054](#mv2-054), [MV2-057](#mv2-057), [MV2-071](#mv2-071) |
| [MV2-059](#mv2-059) | Helvetic Lens Monitoring v2.0 acceptance and release | F6 | P0 | M | PLANNED | [MV2-025](#mv2-025), [MV2-052](#mv2-052), [MV2-054](#mv2-054), [MV2-055](#mv2-055), [MV2-056](#mv2-056), [MV2-057](#mv2-057), [MV2-058](#mv2-058) |
| [MV2-060](#mv2-060) | Legacy bridge for Topics, watches and legal events | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014) |
| [MV2-061](#mv2-061) | Possible future feature: Customs purchase calculator | LATER | P2 | S | DEFERRED — possible future feature; do not take into development | [MV2-027](#mv2-027) |
| [MV2-062](#mv2-062) | After v2.0: Additional auction cantons and extended tender workflow | LATER | P2 | L | DEFERRED | [MV2-045](#mv2-045), [MV2-050](#mv2-050) |
| [MV2-063](#mv2-063) | Conditional: pgvector after a demonstrated recall gap | LATER | P2 | M | DEFERRED | [MV2-051](#mv2-051), [MV2-054](#mv2-054) |
| [MV2-064](#mv2-064) | Conditional: Relationship graph after a usefulness test | LATER | P2 | M | DEFERRED | [MV2-021](#mv2-021), [MV2-036](#mv2-036), [MV2-058](#mv2-058) |
| [MV2-065](#mv2-065) | Conditional: Multiple servers / HA based on measured need | LATER | P2 | M | DEFERRED | [MV2-054](#mv2-054), [MV2-056](#mv2-056) |
| [MV2-066](#mv2-066) | Conditional: The next two cantonal regulatory packs | LATER | P2 | M | DEFERRED | [MV2-068](#mv2-068) |
| [MV2-067](#mv2-067) | Beyond the ten source use cases: Opt-in public-discourse pilot | LATER | P2 | M | DEFERRED | [MV2-058](#mv2-058) |
| [MV2-068](#mv2-068) | Complete legacy coverage verification and repair old artifacts | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-060](#mv2-060) |
| [MV2-069](#mv2-069) | Pollen Watch FIRST: Confirm sources and the first-delivery contract | FIRST | P0 | M | IN PROGRESS — first implementation priority | [MV2-001](#mv2-001) |
| [MV2-070](#mv2-070) | Pollen Watch FIRST: Implement the shared platform within C5 scope | FIRST | P0 | L | IN PROGRESS — first implementation priority | [MV2-069](#mv2-069) |
| [MV2-071](#mv2-071) | Pollen Watch FIRST: Accept the complete scenario and prepare for testing with real users | FIRST | P0 | M | IN PROGRESS — first user-testing gate | [MV2-031](#mv2-031) |
| [MV2-072](#mv2-072) | Isolated Monitoring deployment on HappyDucky02 | OPS | P0 | M | IN PROGRESS | None; user deployment decision |
| [MV2-073](#mv2-073) | Show Monitoring backlog completion and deployment progress | OPS | P0 | M | VERIFYING | None; user progress-visibility request |

## OPS — Separate Monitoring environment

<a id="mv2-072"></a>

### MV2-072 — Isolated Monitoring deployment on HappyDucky02

**Pollen release repair, 2026-09-12:** The bdb5947 gate exhausted memory while installing dependencies on the shared Docker host, before lint/tests ran. Bound dependency build/download/install concurrency in the versioned QA image, retain frozen dependencies and all gates, and validate a cold installation under a tighter memory limit. Apply this deployment fix to both channels receiving the authorized MV2-031 feature. Other services, host memory limits, source policies and the pinned controller stay unchanged.

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Platform + Operations · **Size:** M

**Dependencies:** None; independent of product source gates. **Requirements:** explicit user deployment decision, 2026-09-10.

**User outcome:** Monitoring evolves separately while the main product receives hackathon improvements.

**Work:** Adapt the existing release transaction for a dedicated Windows/Docker instance and branch, install its persistent automatic deployment task, and publish monitoring.helveticlens.ch with isolated data and a reproducible operating procedure.

**Acceptance criteria:**

1. Only `codex/HappyDucky02/monitoring-v2` supplies the Monitoring application; main continues through the existing HappySnowman channel. Source, immutable releases, controller configuration, Compose project, volumes, queues, database credentials, backup paths and domain route are separate.
2. Native Windows polling persists the exact branch, Docker context and paths; concurrent runs are excluded. The existing Linux defaults and rollback pipeline pass regression tests. Controller changes remain explicitly pinned.
3. A clean first installation succeeds without borrowing existing containers, models or user data. Failed candidates preserve the prior release; first-install failure reports the absence of a previous release and retains evidence.
4. Production configuration validation, application quality gates, scoped resource budgets, backup and recovery checks pass. Authentication remains protected with valid SMTP; no anonymous mode or mock data is used to claim readiness.
5. HTTPS serves the Monitoring instance with independently verified release identity. A subsequent branch commit is picked up automatically and main remains unaffected. Record the exact revisions, scheduler status and live evidence.
6. An English runbook documents update, rollback, pause/resume, reboot/login requirements, resource limits and remaining operational constraints. The environment alone does not complete Pollen Watch or claim high availability.

**Verification:** platform/unit and existing release regressions; rendered Compose isolation; first-install and rollback rehearsal against only the new instance; public HTTPS and automatic second-revision checks.

**Explicit subtask — dated digest fixtures (IN PROGRESS, 2026-09-11):** Investigate the 49 digest/brief failures in automatic candidate 9034523, separately from its already repaired backlog mismatch. The shared topic fixture is dated 2026-09-04 08:00 UTC and falls outside the real seven-day digest window after 2026-09-11 08:00 UTC. Reproduce the failure, anchor synthetic current-event fixtures relative to the test clock before evidence is generated, and verify real period boundaries plus affected topic/brief/delivery tests. Preserve application filtering and all quality gates. This supports acceptance criterion 4; no production digest behavior or main-branch update is authorized by this repair.

**Dated-fixture evidence, 2026-09-11 (implemented/tested; release pending):** The paging failure reproduced before changing the shared synthetic detection timestamp to five minutes before fixture creation. All 81 focused regressions passed, including the 49 previously failing digest/brief cases, shared topic matching and real digest-period boundaries. Mandatory backlog consistency, Ruff and diff checks passed. [Evidence and limits](docs/monitoring-v2/evidence/MV2-072-digest-clock.md). Current automatic tests continue independently; parent status and live acceptance remain open.

**Explicit subtask — deployment branch identity (INTEGRATED; live acceptance pending):** Make the deployment page's explanatory text and Git label reflect the branch reported by this instance's status. Missing or unreadable status must report an unknown branch rather than inventing `main`. Verify main, the dedicated Monitoring branch and unavailable status with focused API and localized UI checks. This supports acceptance criteria 1 and 5; it does not add a product scenario or claim live deployment acceptance.

**Subtask evidence, 2026-09-10:** Six isolated deployment-status API regressions and targeted Ruff checks passed. `npm run check:i18n`, web TypeScript checking and the production frontend build passed. The existing `npm run check:deployments:browser` passed 10 localized desktop/mobile history journeys, five unavailable-branch views and 20 full-document accessibility checkpoints with synthetic API responses. The check covers `main`, the dedicated Monitoring branch, honest unknown status and mobile wrapping. Original MV2-001–071 task definitions remain unchanged. Live deployment and automatic update acceptance remain part of MV2-072's separate verification.

**Explicit subtask — repeatable controller ACL protection (VERIFIED; paused upgrade succeeded):** Verify and preserve an existing controller file or directory ACL only when its owner is the current deployment SID, inheritance is disabled, and its two explicit Allow FullControl entries are exactly that SID and SYSTEM with the expected inheritance/propagation flags. Reapplying an already correct ACL on Windows can fail with SeSecurityPrivilege. Do not request extra privileges, broaden permissions or accept ACL drift. Verify real first and repeated protection for directories and files, then retry the paused pinned upgrade. This supports acceptance criterion 2.

**Explicit subtask — Task Scheduler owner identity (VERIFIED; paused upgrade succeeded):** After a successful first bootstrap and recovery rehearsal, Windows returned the registered task principal as the local short account name. The installer compared only the SID and qualified name, so it correctly refused to overwrite an unrecognized task. Resolve the existing principal to a Windows SID and compare it to the current deployment user's SID; fail closed for an unknown or different identity and preserve the exact task description and action checks. Verify SID, qualified-name and short-name readback, foreign/unresolvable owners, and a real paused controller upgrade before enabling the task. This supports acceptance criterion 2; it does not relax task ownership or deployment gates.

**Execution evidence, 2026-09-10:** First bootstrap of `69a63823d6f6e04e9167077d9f89396ba2be9ab1` succeeded through every release gate: 2023 API tests passed, 12 skipped; image build, initial backup and public HTTPS checks passed. The public endpoint independently reported instance `monitoring-v2` and that full release; login returned 200 and the unauthenticated deployment API returned 401. An actual database/document backup and restore rehearsal passed, its temporary probes were removed, and the same release restarted with verified HTTPS identity. All 30 unrelated running containers retained their start times; the authenticated main deployment UI still showed `4aa4981e11e946a4fc8bb49865ab7455de374295`. SMTP STARTTLS/authentication is verified; email delivery and a real user account flow remain unverified. Native installer regressions now cover SID, qualified-name and short-name owners plus foreign/unresolved rejection; the actual paused task passed read-only SID ownership validation. The actual paused upgrade succeeded with pinned controller `dc93efcb5e16db3ac74c45fa1adfa290d8045338`, including exact ACL preservation. The dedicated task was enabled at 2026-09-10T21:48:00Z and automatically picked up that application revision at 21:48:10Z; checkout, configuration and lint passed and the full API suite is running. The prior accepted release remains current during these gates. **Next action:** verify automatic release acceptance, exact progress snapshots and the real user account/email flow. [Deployment status and remaining acceptance](docs/monitoring-v2/DEPLOYMENT_STATUS.md).

<a id="mv2-073"></a>

### MV2-073 — Show Monitoring backlog completion and deployment progress

**Status:** VERIFYING · **Priority:** P0 · **Owner:** Platform + Frontend · **Size:** M

**Dependencies:** None; user-authorized visibility work. **Requirements:** explicit user request for simple development progress, 2026-09-10.

**User outcome:** The deployment page shows what the Monitoring backlog records as completed in Git, what completion is present in the running release, what remains, and an approximate completion percentage, with Pollen Watch easy to find.

**Work:** Derive immutable progress snapshots from the existing Markdown backlog at the latest successfully fetched Monitoring commit and the actually deployed commit. Display a compact summary, remaining tasks and the six-task Pollen Watch path on the existing deployment page. Keep the backlog as the only manually maintained source. Implementation can proceed alongside MV2-072; live verification requires the Monitoring site to be running.

**Contract:** [Monitoring progress snapshots and counting rules](docs/MONITORING_PROGRESS.md).

**Acceptance criteria:**

1. The deployment collector reads only `BACKLOG_MONITORING_V2.md` from exact Git commit blobs. The latest snapshot uses the successfully fetched configured Monitoring branch SHA; the deployed snapshot uses the actual deployment record SHA. The application reads sanitized persisted metadata and does not fetch Git or contact GitHub. No second manually maintained task list or counter is introduced.
2. Each snapshot validates unique detailed task IDs and allowed Status values against its task index. Missing, unreadable, malformed or inconsistent data produces an explicit unavailable state with a safe reason. Missing progress never appears as zero completion, and a latest-snapshot failure does not invalidate an independently valid deployed snapshot. A last-verified deployment record is not proof of current runtime state: failed rollback or interruption after startup produces deployed unavailable, retaining the journal SHA; a successful rollback or failure before runtime changes may preserve the prior snapshot.
3. Only tasks with Status DONE count as completed. PLANNED, READY, IN PROGRESS, VERIFYING and BLOCKED remain unfinished. Every DEFERRED task is excluded from the denominator, remaining-work count and Pollen completion claims. All required backlog items, including OPS tasks MV2-072 and MV2-073, count equally; the UI clearly calls this approximate unweighted backlog completion, not an estimate of effort, time, implementation volume or product readiness.
4. The page distinguishes Completed in Git, Already on this site and Remaining. The first and remaining values use the latest snapshot; the deployed value uses the deployed snapshot. Each count/percentage uses its own snapshot's required-task denominator, visibly showing X/Y when backlog versions differ. Already on this site means recorded DONE in the deployed backlog, not independently verified business outcomes. During an active deployment, label the deployed measure Last verified release. A failed or pending deployment must not copy latest progress into the deployed result.
5. Pollen Watch highlights MV2-001 → MV2-069 → MV2-070 → MV2-030 → MV2-031 → MV2-071, with task titles and separate latest/deployed statuses. The latest and deployed Pollen counts are each DONE out of the six listed tasks. Missing snapshot data is unavailable; a task absent from a valid older snapshot is labelled not present in that revision. No partial count or operations completion is described as Pollen readiness, forecast coverage or completed real-user testing.
6. The user can inspect unfinished required tasks and completed tasks awaiting deployment, with their IDs, titles and statuses. Awaiting deployment is computed by task ID as latest DONE without deployed DONE, never by subtracting aggregate counts; it is unavailable when either required snapshot is unavailable. Reopened tasks and different backlog sizes render consistently. Task contents are displayed as text through existing page authorization, accessibility and localization conventions.
7. Backend/collector and UI checks cover separate Git/deployed SHAs, all status values, the nine deferred exclusions, no-DONE valid snapshots, an unavailable snapshot, malformed/duplicate/index-inconsistent tasks, an older deployed backlog with a different denominator, reopened tasks and Pollen status differences. No tests assert invented progress or bypass the deployment quality gates.
8. After the feature is deployed, verify the summary against the exact latest and deployed backlog blobs and record the application/controller revisions and evidence. A later automatic update refreshes the deployed snapshot only after the deployment is accepted. Keep MV2-073 IN PROGRESS or VERIFYING until its own criteria pass; do not pre-mark it DONE to inflate its first visible progress result.

**Verification:** focused parser/collector and page tests; exact-blob count comparison; deployed-page inspection and subsequent automatic-update evidence. A passing build or an IN PROGRESS task is not completion.

**Execution evidence, 2026-09-10:** Reviewed backend task `f3d53570b28b5024ac259534780a9c7589ee4d97` passed 112 focused parser, collector, release and API tests plus Ruff. Reviewed UI task `1e2780805d55a7b767525221b93151e7227c6796` passed seven semantic counting tests, i18n, TypeScript, the production frontend build and the existing deployment browser check with 40 full-document accessibility checkpoints across five locales and desktop/mobile views. Independent review findings on Markdown indentation/fences and per-task status labels were resolved. Both task branches are integrated here. Browser fixtures are synthetic evidence, not a live deployment or actual completion percentages. The installed controller remains pinned to the prior MV2-072 revision until bootstrap and the paused recovery rehearsal complete. Exact live snapshots, deployed-page inspection and subsequent automatic-update acceptance remain pending; keep this task VERIFYING.

## F0 — Decisions, sources and validation of user needs

<a id="mv2-001"></a>

### MV2-001 — Establish extension contracts and MVP compatibility

**Status:** DONE · **Priority:** P0 · **Owner:** Architect + Backend · **Size:** M

**Dependencies:** None. **Requirements:** §§1–7,19,27,30.

**User outcome:** Development starts from a verified foundation.

**Work:** Approve the ADR for the generic kernel; inventory APIs, schemas, routes, jobs and 35 open legacy items; define feature flags by template and workspace.

**Acceptance criteria:**

1. The baseline is 7109a28; the MVP tag remains unchanged; all 35 open HL items have a disposition.
2. New entities do not bypass legal CHECK constraints; additive migrations, the bridge and fallback to legacy readers are documented.
3. Source facts, system calculations, AI and decisions are separated; contracts are aligned with ARCHITECTURE.md.

**Verification:** Review schemas and the compatibility matrix; run characterization tests on an isolated database copy.

**Execution evidence, 2026-09-11:** Implemented [ADR and contract v1](docs/monitoring-v2/EXTENSION_CONTRACT.md), exact workspace/template/version rollout grants with default legacy fallback, and a reproducible Git inventory. Baseline/MVP commit `7109a2891f9c99e53572008cc7c1a86001792a57` and annotated tag object `c33f3094e51019bfe1083bec71a53858eef1917c` are unchanged. Against integration base `cb47c01c0ef4c3632e0e65388d4092801ca42c2d`, the inventory reports 174 API routes, 30 web pages, 75 models, no removed routes or changed legacy models, and all 35 open legacy items mapped. Three new boundary/copy-characterization tests and 18 existing corpus/Basel tests passed; targeted Ruff and diff checks passed. The copy test preserves all rows and evidence hashes through repeated migration and rejects pollen records under the legacy legal CHECK. [Evidence and limitations](docs/monitoring-v2/evidence/MV2-001.md). Reviewer: Codex implementation review, not independent human acceptance. **Release accepted:** implementation SHA `8d5e94b786885609cf4413f17a640ac6a8097792` completed every automatic release step at 2026-09-11T07:04:38Z; independent public readiness confirmed the same SHA. MV2-001 is DONE within its foundation scope. This does not activate Pollen Watch or close source/human/production-migration gates.

<a id="mv2-002"></a>

### MV2-002 — Validate first-value journeys and shared navigation

**Status:** PLANNED · **Priority:** P0 · **Owner:** Product + UX · **Size:** M

**Dependencies:** None. **Requirements:** §§20–21,25–26,34.

**User outcome:** People can create a monitor without understanding Sources/Topics.

**Work:** Prototype Create Monitor → preview → Today → evidence → decision; cover personal and team modes and the journeys of all nine active templates.

**Acceptance criteria:**

1. At least 5 B2C participants and 5 B2B representatives complete tasks relevant to them; retain the error log.
2. The prototype explicitly shows unavailable coverage, the wait for an initial state and the lack of fresh data.
3. Navigation includes Today / Monitoring / Investigate / Workspace / Admin; preserve access to existing laws, Topics, Discover and Impact Matrix.

**Verification:** Observe users without prompting; use the results to refine copy and configuration without expanding the nine active cases.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-003"></a>

### MV2-003 — Verify source rights, coverage and contracts for the nine active scenarios

**Status:** PLANNED · **Priority:** P0 · **Owner:** Integration + Product · **Size:** L

**Dependencies:** [MV2-001](#mv2-001). **Requirements:** §§23,38; all authoritative source sections.

**User outcome:** Only promise data that can be obtained and displayed.

**Work:** Create a separate dossier for C1/C2/C3/C5/C6/C7/B2/B7/B8; C4 is excluded from current work. Cover endpoint, auth, terms, licence, fields, territories, languages, cadence, history, correction/delete and evidence retention/export; maintain a capability catalogue.

**Acceptance criteria:**

1. Each of the nine active cases has a dated dossier with the URL/version of its terms, an exact capability inventory, an owner and an approved or blocked outcome. If access is blocked, a documented blocker is sufficient; a successful response sample is required only for the case’s own G(case), not for MV2-003 to be DONE.
2. C3 controls access expiry and the prohibition on raw redistribution; SIMAP respects publication time.
3. An unavailable mandatory case remains BLOCKED; mocks or replacement with a third-party source do not make it DONE.
4. C4 is DEFERRED by the user’s decision; its dossier, API probes, access requests and licensing are not undertaken in v2.0 and do not block MV2-003.

**Verification:** Review the nine active source dossiers; perform a successful bounded API probe and conformance fixtures in each adapter’s G(case) after obtaining permitted access.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.


## FIRST — Pollen Watch: implement first together with MV2-030/031

<a id="mv2-069"></a>

### MV2-069 — Pollen Watch FIRST: Confirm sources and the first-delivery contract

**Status:** IN PROGRESS — first implementation priority · **Priority:** P0 · **Owner:** Product + Integration + UX · **Size:** M

**Whole-feature engineering evidence, 2026-09-12:** The integrated Pollen candidate now includes approved-source collection/decoder contracts, private Start/current state, Today/evidence, four-state review/reopening, lifecycle/export and independently consented delivery. Final standard-path Pollen/Monitoring tests: 346 passed; PostgreSQL concurrency/migration checks, 47 browser axe checkpoints, real Docker web/native builds and restore rehearsals passed. The broader Windows run retained two environment-sensitive legacy failures; isolated unchanged rerun passed 9/9. See [complete evidence and CORE-20 trace](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md). Source/category/seasonal, independent human and actual-release acceptance remain open; no production source activation or real email was performed.

**Dependencies:** [MV2-001](#mv2-001). **Requirements:** User decision 2026-09-10: Pollen Watch first; §12, §§23–25; AC-C5-01…10; S-45…48.

**User outcome:** A complete Pollen Watch for real users is defined, and official data is verified as sufficient to deliver it.

**Work:** Explicit C5 contribution to MV2-002/003/015/025: clarify the first user journey, supported stations/locations/allergens, observation and forecast contracts, rights, units/categories, cadence/freshness and the initial-state waiting experience. Work on the C5 dossier independently of the other eight active cases.

**Acceptance criteria:**

1. The product contract covers all AC-C5-01…10, multiple allergens, user thresholds/rapid increases, observations and forecasts, why/evidence/history/review/reopen and opt-in email. Supported coverage and the station-based nature of measurements are visible before Start; the data is not an exact measurement at the user’s home.
2. G(C5-observation): dated source/terms/schema, station/allergen/unit/category inventory, attribution/retention/display/alert rights and a permitted live sample with timestamp/provenance. Documented cadence is checked against actual publication; a successful HTTP response is not evidence of a fresh measurement.
3. G(C5-forecast): separately establish the official endpoint/channel, usage rights, allergens/stations or area mapping, issue_time/valid_time and category semantics; obtain a permitted live forecast sample. The observations API alone does not establish this. A missing forecast contract leaves MV2-069/030/071 BLOCKED for complete delivery.
4. A short C5 prototype/usability review checks setup, thresholds, reading observations/forecasts, reasons/evidence, pause and unavailable coverage; results are recorded. Other UX journeys in MV2-002 do not block this finding.
5. Versioned interfaces/fixtures and the supported-coverage list allow MV2-070 to start; there is no promise of all-Switzerland coverage or medical assessment. C4 research is excluded.

**Verification:** Separate dated observation/forecast dossiers with permitted live samples and source hashes; review the contract and C5 prototype. Missing access is recorded as a specific blocker, owner and next action without substituting a mock.

**Execution evidence, 2026-09-11:** Codex on HappyDucky02 implemented bounded source capture and offline proof decoding on `codex/HappyDucky02/mv2-069-pollen-sources`. Real PBS hourly observations and a separate official AMBRsnc/DEN forecast are retained with hashes, source identities and UTC times. The exact catalogue contains 15 stations; only PBS observations were sampled. [Evidence](docs/monitoring-v2/evidence/MV2-069.md), [source dossier](docs/monitoring-v2/POLLEN_SOURCES.md) and [draft contract](docs/monitoring-v2/POLLEN_CONTRACT.md) distinguish implementation from acceptance. The initial native decoder/definitions mismatch is resolved by the matched 2.47.0/v2.47.0.2 offline rerun and pinned dependency recipe; all 15 forecast points, observations and provenance match the prior proof. 23 focused source tests passed. Category semantics, seasonal birch/grass forecast evidence, infrastructure/lifecycle terms and prototype review remain open; their dependent live activation stays blocked. Independent contract work continues while previous automatic tests/deployment run.

**MV2-069 configuration slice, 2026-09-11:** The immutable v1 Python configuration contract and exported JSON schema now cover multiple allergens, explicit observation/forecast aggregation periods, Decimal threshold/reset and rapid-increase rules, timezone and opt-in delivery schedules. 25 focused boundary tests and Ruff passed. The documented interface is available for independent MV2-070 C01 implementation; it does not authorize Start, approve hourly categories or complete the source/prototype gates. See [contract and semantic constraints](docs/monitoring-v2/POLLEN_CONTRACT.md). MV2-001's real automatic release has separately been accepted.

<a id="mv2-070"></a>

### MV2-070 — Pollen Watch FIRST: Implement the shared platform within C5 scope

**Status:** IN PROGRESS — first implementation priority · **Priority:** P0 · **Owner:** Backend + Frontend + Integration + QA · **Size:** L

**Whole-feature engineering evidence, 2026-09-12:** The integrated Pollen candidate now includes approved-source collection/decoder contracts, private Start/current state, Today/evidence, four-state review/reopening, lifecycle/export and independently consented delivery. Final standard-path Pollen/Monitoring tests: 346 passed; PostgreSQL concurrency/migration checks, 47 browser axe checkpoints, real Docker web/native builds and restore rehearsals passed. The broader Windows run retained two environment-sensitive legacy failures; isolated unchanged rerun passed 9/9. See [complete evidence and CORE-20 trace](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md). Source/category/seasonal, independent human and actual-release acceptance remain open; no production source activation or real email was performed.

**Dependencies:** [MV2-069](#mv2-069). **Requirements:** User decision: first complete Pollen Watch; AC-CORE-01…20, AC-C5-01…10; C5 subset of the named parent tasks and inherited obligations.

**User outcome:** The platform is ready for real C5 integration, from a personal monitor to history and notifications, with user isolation and recovery from errors.

**Feature verification, 2026-09-11: Choose a station and understand pollen channels.** Implemented the complete named-station → optional local distance ranking → allergen-channel overview → preview/save → reopen flow, with all 15 records tied to retained official metadata, five-language guidance, unknown-code preservation and no coordinate storage/transmission or automatic selection. Production build/frontend gates, 16 new directory/geographic/channel cases, 36 API/configuration/backlog regressions and 41 full-document browser axe checkpoints passed, including real browser geolocation with synthetic positions, keyboard choice, cancelled/late callbacks and all earlier draft workflows. Documentation explicitly separates dated channel capabilities from unverified live coverage. Actual candidate activation and independent human/source/live acceptance remain open; MV2-070 stays IN PROGRESS. [Evidence](docs/monitoring-v2/evidence/MV2-070.md#feature-named-stations-and-pollen-channel-guidance--11-september-2026).

**Whole-block feature refinement, 2026-09-11 (before implementation):** The user explicitly requested the entire remaining Pollen block as one feature. MV2-069/070/030/031/071 engineering proceeds in one worktree across continuations under the [complete feature plan](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md). Implement accepted-source Start, current state, changes/evidence/review, lifecycle and delivery together. Publish no further separate draft controls or technical slices. Existing source, independent human and actual release acceptance gates remain mandatory; current task statuses are not changed by scope selection.

**Feature definition, 2026-09-11 (before implementation): Choose a station and understand pollen channels.** Deliver the C01/C05 and AC-C5-01/02 setup outcome: select an official station by name, optionally rank stations by distance from a device location used only in browser memory, select allergens, inspect separate documented hourly-observation/forecast capabilities, then preview/save and reopen the chosen settings. Use the 15-station metadata from the retained, hashed MV2-069 catalogue as a dated directory, never its sample concentrations as live data. Source attribution/date, station measurement limits and the distinction between documented capability and unverified current availability must be visible. Request geolocation only after an explicit user action; do not send/store coordinates, silently select a station or infer home-level exposure. Handle unsupported/denied/timed-out location, cancellation/late callbacks, existing unknown station IDs without data loss, all five languages, keyboard/mobile and exact configuration preservation. A station or allergen change invalidates preview; numeric/delivery settings and imported configurations remain intact. Verify catalogue provenance, geographic calculations, privacy/no-network/no-auto-save boundaries, role/scope recovery and the complete existing draft workflow after the feature is implemented. Source-backed Start, actual current coverage and human source/usability acceptance stay gated. Publish only this complete feature with its evidence, not individual controls or metadata substeps.

**Feature verification, 2026-09-11: Private draft backup and restore.** The complete saved-settings download → local file review → server preview → new private draft workflow is implemented with current-access rechecks, exact numeric text, bounded/strict file compatibility, unchanged original history, same-key uncertain-save retry and five-language UI/help. Production build/frontend gates, 24 new portable-file cases, 36 API/configuration/backlog checks, targeted Ruff and 36 full-document browser axe checkpoints passed, including real file downloads/uploads, cancelled late operations and prior CRUD/delivery/recovery. No source/activation/consent or identity/history transfer is introduced. Prior `72bc489` is now an accepted actual automatic release; this feature's activation and independent human/source/live acceptance remain unverified. MV2-070 stays IN PROGRESS. [Evidence](docs/monitoring-v2/evidence/MV2-070.md#feature-private-draft-backup-and-restore--11-september-2026).

**Feature definition, 2026-09-11 (before implementation): Private draft backup and restore.** Deliver one complete user outcome across C01/C05/C06/C07: an owner can download the current saved settings, keep a portable backup and restore it into a new private draft after reviewing it. The explicit versioned JSON file contains configuration only, never subject/owner/workspace IDs, request keys, credentials, observations, evidence or history. Export must reread current authorized state and cancel on scope/navigation changes; a failed/revoked read must not export cached settings. Import reads only an explicitly selected, bounded local file, rejects unsupported/unknown formats without discarding fields, preserves exact decimal text and delivery preferences, and opens a dirty review form. Nothing is sent or written until explicit Preview and separate Save; Save uses the existing scoped idempotent creation flow, never overwrites an existing draft, starts monitoring or grants email consent. Include five-language guidance on the personal file, saved-only snapshot, new-copy behavior and missing history/activation; keyboard/mobile/error/access/lost-response journeys and contract boundaries must pass as one feature regression set. No automatic browser persistence, unsaved crash recovery, raw source export or full backup/restore acceptance is claimed. Implement and verify the whole workflow before its single feature publication; retain unfinished work in the feature worktree across continuations.

**Work:** Explicit C5 contribution to shared MV2-004…022/024/025/052…056/060/068; boundaries are listed in the first-delivery table. Use the generic MV2-001 contracts, additive persistence/API changes and existing authentication/outbox/UI. Do not create a separate pollen-only service. Work is limited to the named C5 criteria; full parent tasks remain incomplete until the rest of their own scope is delivered.

**C01 implementation refinement, 2026-09-11 (before implementation):** C01a adds generic subject/revision tables by an additive migration and an internal personal-draft repository using the MV2-069 v1 configuration contract. Acceptance: create/read/list/edit/delete drafts; immutable configuration history; scoped idempotency keys with conflicting-payload rejection; compare-and-swap edits; tenant and owner isolation, active membership recheck and revoked/viewer write denial; rollback/restart retention and unchanged legacy rows. No source activation, collector, Start, public endpoint or email is introduced by C01a. C01b follows with authenticated API/preview/explicit Start and lifecycle gates; C01c adds UI and job/evidence/cache permission checks. The original C01 acceptance remains mandatory. C01a may proceed while MV2-069's source/prototype gates are open because it only stores validated drafts.

**C01a-R1 publication follow-up:** The previous c2ab0d6 automatic release failed its existing backlog consistency test because MV2-069's detail status had changed without its index row; later MV2-001/070 updates had the same omission. Synchronize those three index rows with the evidence-backed detail statuses and verify the existing parser. Preserve the parser's strict mismatch rejection and all deployment gates. This repairs publication metadata, not product acceptance.

**C01b1 API refinement, 2026-09-11:** Expose authenticated private draft CRUD, paged list/history and configuration-only preview under the exact workspace/template/version shadow grant, disabled by default. Verify CSRF, same-workspace other-owner and cross-workspace denial, revoked access, revision conflicts, cache prevention and bounded input/rate behavior. Start must explicitly reject unaccepted source/live workflow gates without changing state or enqueuing jobs. C01b2 will implement accepted-source Start/lifecycle; a permanently blocked Start is not completion of C01b or Pollen Watch.

**C02a threshold component refinement, 2026-09-11 (before implementation):** Implement a pure versioned numeric threshold evaluator with immutable series/sample/state/evidence contracts. Bind state to one private subject/configuration revision and exact source/station/allergen/method/period; forecasts additionally bind model/grid/member/layer/cell/issue. First usable state and recovery establish a baseline without a change alert. Apply inclusive trigger/reset with hysteresis; unknown/stale/unapproved inputs retain the last good value and cannot resolve a condition. Exact replay is idempotent; conflicting same-revision bytes fail; older samples request history handling without rolling current state backwards; latest corrections rebaseline without manufacturing a crossing. Return deterministic transition identities and full previous/current evidence for a later atomic ledger/outbox. Reject rapid/category rules in this threshold-only component. Verify Decimal boundaries, clock/freshness, revisions, forecast separation and serialized restart. C02b supplies rapid/category and historical recomputation; C02c supplies transactional persistence/replay/delivery. No collector, endpoint, rollout activation, source approval or mail is included, and C02 remains incomplete.

**Acceptance criteria:**

1. C01 — Personal subject/access (004/005/010/015/017/053): location/station, one or multiple allergens, threshold/rapid increase, notification choices; draft/preview/explicit Start/edit/pause/archive/delete; idempotent Start, revisioned configuration and permissions on API/jobs/evidence/cache; negative cross-tenant, role-revocation and private-location tests. Other template schemas and UI are not required.
2. C02 — State/rules (006/007/008/009/011/020/055): versioned observation/forecast and prior state, source/station/time/quality/rights, Decimal/unit/period, category crossing, threshold boundary/hysteresis/reset/rapid increase and missing/stale/revised/out-of-order data; sufficient immutable evidence for history; duplicate replay/restart neither loses state nor creates an alert.
3. C03 — Daily workflow (013/014/017/018/019/020/021): C5 Create Monitor → initial current state → Today → why/previous-current/evidence/history → Review/Not relevant/continue; reopening after a material update preserves the previous decision; pause/mute is distinct from source resolution. Shared Today remains compatible with the legal feed, without requiring other new domains.
4. C04 — Delivery (012/022): shared fetch and scoped relevance/outbox, in-app and opt-in email/digest, deduplication across subjects, quiet hours/priority/unsubscribe; sending rechecks permissions. Source failure is not presented as low pollen or no change; recovery does not flood users with historical alerts.
5. C05 — Accessibility/languages (024): C5 forms/cards/evidence/settings/error/stale/forecast are checked with a keyboard, a narrow/mobile viewport and a screen reader; critical C5 copy and EN/DE/FR/IT/RM translations are ready for independent sign-off in MV2-071. Language work for other templates does not block C5.
6. C06 — Operations/privacy (025/052/053/054/055): source last-good state/observation lag, worker/outbox/delivery errors, bounded retries/rate limits and operator alerts; minimal location data/logs, working deletion/export and enforcement of source rights/retention. Workload and budgets for the declared C5 pilot are measured separately; full v2 and inherited budgets are not weakened.
7. C07 — Compatibility/recovery (016/056/060/068): isolated migration/backup/restore/restart rehearsal, representative legacy authentication/law/topic/Today/evidence/URL checks and feature-flag fallback without losing new records or old evidence. Legacy fixes required for this path are included; remaining inherited acceptance is not declared DONE.
8. C08 — Contract/component acceptance: all 20 AC-CORE have a verified C5 contract/component contribution and evidence within this task; this is not final live end-to-end acceptance before the connector exists. Source/rule/state/schema revisions are linked to evidence. Extensibility is checked with a schema/contract fixture without implementing a second new scenario; an offline LLM does not block the core workflow. MV2-031/071 perform full integrated C5/CORE acceptance within C5 scope after MV2-030.

**Verification:** API/DB/UI integration, independent source-contract fixtures, a role matrix, boundary/replay/failure/restart checks and C5 build/restore evidence. MV2-031 completes live product end-to-end acceptance; MV2-071 provides the final gate for user testing.

**Execution evidence, 2026-09-11:** C01a internal draft persistence implemented on `codex/HappyDucky02/mv2-070-personal-subjects`: additive generic subject/revision tables, owner-scoped create/read/list/edit/history/delete, conditional revision updates and idempotent concurrent creation. 10 repository tests passed on each of SQLite and isolated PostgreSQL 17; three existing foundation/legacy characterization tests and Ruff also passed. [Evidence and remaining boundaries](docs/monitoring-v2/evidence/MV2-070.md). Exact automatic deployment, C01b API/Start, C01c UI and C02–C08 remain open; this does not activate pollen sources or notifications.

**C01b1 execution evidence, 2026-09-11:** Added the [authenticated draft API](docs/monitoring-v2/PERSONAL_DRAFT_API.md), default-off exact shadow rollout, private create/read/edit/delete, configuration-only preview, list/history pagination and explicitly blocked Start. Eight HTTP cases, eleven SQLite repository cases, four existing authentication cases and the required backlog consistency check passed; the new pagination case also passed on disposable PostgreSQL 17. Targeted Ruff passed. The serving configuration remains off; no accepted source, live Start, UI or delivery is claimed. See the [continuation evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C02a execution evidence, 2026-09-11:** Implemented the [pure numeric threshold component](docs/monitoring-v2/POLLEN_THRESHOLD_COMPONENT.md) with immutable source/private binding, Decimal boundaries/hysteresis, freshness/rights withholding, silent first/recovery/revision baselines, prior/current evidence, deterministic transition IDs and serialized restart. 39 new component tests and 25 configuration regressions passed; targeted Ruff passed. No route, collector, ledger, outbox or rollout uses it yet. C02b/C02c and source/product acceptance remain open; no source approval or live notification is claimed. [Evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C02b1 exact-window rapid comparison refinement, 2026-09-11 (before implementation):** Add a pure rapid-increase-only comparison using the C02a immutable sample/source contract and private configuration binding. Require exactly the configured 1–24 hours, matching observation method or forecast issue/member/grid/layer/cell, source policy and parser. Compare Decimal current minus baseline inclusively against the selected minimum increase without rounding. Missing/ineligible baseline, stale current data, revoked rights and incompatible windows cannot become zero or a match. An approved historical baseline may naturally be older than its live freshness deadline; explicit stale/missing quality remains ineligible. Retain both complete input records, a structured unavailable reason and deterministic comparison identity; input corrections change that identity. This calculates a comparison only, not a new alert/episode. C02b2 must coordinate overlapping rapid windows, recovery/revisions and combined threshold+rapid rules; categories and historical recomputation remain open. Verify exact window/precision boundaries, forecast/privacy separation and serialization replay without any source activation or delivery.

**C02b1 execution evidence, 2026-09-11:** Implemented [exact-window rapid comparison](docs/monitoring-v2/POLLEN_RAPID_COMPONENT.md) with private/source/forecast identity, lossless Decimal subtraction, inclusive minimum, explicit unavailable reasons, historical baseline policy and deterministic comparison IDs. 45 new comparisons and 64 threshold/configuration regressions passed; targeted Ruff passed. Both inputs and evaluation time are retained as evidence. No comparison is treated as an alert episode; overlapping windows, combined rules, recovery/revision coordination, categories and persistence remain open. [Evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C02b2 numeric rule coordinator refinement, 2026-09-11 (before implementation):** Coordinate threshold-only, rapid-only and combined threshold+rapid configurations per exact private/source binding. Retain independent rule conditions and complete component evidence. Contiguous overlapping rapid windows form one condition: emit a rapid transition only when a usable non-match becomes a match, and reset when an eligible window falls below the minimum. Initial, missing/recovery, latest-source/baseline correction and policy baselines are silent. Same-source replay and JSON restart cannot produce another transition; conflicting revision content fails and older current/baseline receipts require history handling. When both rules transition on one input, return one deterministic material-update identity containing all reasons, without declaring the entire monitor resolved when only one rule resets. Reuse C02a source-order validation. No category rule, full historical recomputation, database/outbox, rollout or live notification is included. Verify combined transitions, overlap/reset, incomplete rapid coverage with valid threshold results, corrections, private identity and replay.

**C02b2 execution evidence, 2026-09-11:** Implemented the [numeric coordinator](docs/monitoring-v2/POLLEN_NUMERIC_COORDINATOR.md), preserving independent conditions, silent correction/recovery baselines and one deterministic material update for simultaneous transitions. Final verification passed 129 cases: 19 coordinator cases, 109 component/configuration regressions and the actual-backlog consistency check. Targeted Ruff passed. The prior `030ab29` release was actually activated at `2026-09-11T12:21:06Z` after 2180 API tests passed (12 skipped), with its SHA independently confirmed through public readiness. C02b2 still requires automatic release verification; categories, full historical recomputation, atomic ledger/outbox and UI remain open. MV2-070 remains IN PROGRESS. [Evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C02c1 checkpoint/evidence refinement, 2026-09-11 (before implementation):** Add generic, tenant-scoped evaluation stream and append-only entry tables with an internal C5 numeric repository. Bind each stream to the actual private subject/configuration revision and exact source identity; persist evaluator output and checkpoint atomically under compare-and-swap sequence control. Request-key retries return the original entry; changed payloads conflict. Retain non-material and history-required evidence without inventing delivery. Recheck active owner membership, role and current draft revision on writes; lock against concurrent configuration edits/deletion. Reads and paged history retain owner/workspace scope, including old configuration revisions. Caller rollback must remove both evidence and state changes, deletion must cascade, and restart/concurrent-writer tests must cover SQLite and isolated PostgreSQL. This slice supports internal draft rehearsal only, has no API/job/collector caller and emits no outbox message. Source admission, authoritative historical sample ledger/recomputation, active lifecycle and dispatch remain C02c2 and later acceptance; stored synthetic rehearsal evidence is never live coverage.

**C02c1 execution evidence, 2026-09-11:** Implemented the [private evaluation ledger](docs/monitoring-v2/EVALUATION_LEDGER.md) on isolated `codex/HappyDucky02/mv2-070-numeric-ledger`, based on `5a07cd4`. An additive migration and internal repository persist checkpoint plus exact request/decision atomically, with configuration/owner/membership validation, sequence CAS, idempotent replay, scoped history and cascading deletion. Final verification passed 59 SQLite/component/API/contract/backlog checks and all 17 ledger cases on isolated PostgreSQL 17; 11 existing draft repository cases also passed on PostgreSQL in the preceding run. Ruff passed. No caller, source activation or outbox is added. Actual candidate release, authoritative historical source ledger, retention/export, active lifecycle and delivery remain unverified/open. MV2-070 stays IN PROGRESS. [Evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C01c1 private draft reader refinement, 2026-09-11 (before implementation):** Add the `/pollen-watch` interface for authenticated, owner-scoped draft list/detail and immutable configuration history using C01b1. Bound list/history pages; preserve selection under pagination and cancel/ignore superseded requests. Reset all private component state when user/workspace changes; use no persistent browser storage or shared resource cache for private drafts. Show selected station/allergens, period-specific threshold/rapid rules and saved delivery preferences without treating them as live coverage or sending consent. Default-off rollout, revoked/unauthenticated access, empty results and transient failures must be distinct; never show empty measurements as zero pollen. Provide five-language copy with native review still pending, keyboard/narrow-viewport/browser checks and a disabled Start explanation. Creation/edit/delete forms and configuration preview follow as C01c2, live lifecycle and source-backed Start remain gated; this reader does not close C01/C05 or source acceptance.

**C01c1 execution evidence, 2026-09-11:** Implemented the [private draft reader](docs/monitoring-v2/POLLEN_DRAFT_READER.md) at `/pollen-watch`, with list/detail/history pagination, principal-scoped component lifetime, cancellation of superseded requests, explicit access/error states, exact saved numeric settings and unavailable Start. Five-language copy and contextual help are included. Production build/type checks and existing frontend gates passed; six full-document browser axe checkpoints, five locales, desktop/mobile, keyboard/focus, history, late-response and access-state journeys passed. Nine API/backlog regressions passed. Native-language/screen-reader review, operational rollout, creation/edit/delete/preview forms (C01c2), live Start and final user acceptance remain open. MV2-070 stays IN PROGRESS. [Evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C01c2a creation refinement, 2026-09-11 (before implementation):** Add an authenticated manager-only new-draft form to the gated reader. Collect station code, multiple allergens, timezone and optional threshold/rapid rules for explicit observation/forecast periods; preserve decimal input strings and keep email off. Require a configuration-only server preview of the exact settings before a separate Save action; edits invalidate preview. Use one retained request key and frozen payload after a potentially committed save, so an explicit retry cannot duplicate the draft. Prevent concurrent submissions, clear state on principal change/revoked access, warn before losing unsaved or uncertain work, and show successful saved-draft navigation without issuing Start. Five-language labels, keyboard/mobile/browser and backend contract checks are required. Existing-draft edit/delete and delivery-preference editing remain C01c2b; accepted source coverage, live preview/Start, native-language and human acceptance remain open.

**C01c2a execution evidence, 2026-09-11:** Added the [new private draft creator](docs/monitoring-v2/POLLEN_DRAFT_READER.md#c01c2a-new-private-drafts) with multiple allergens, period-specific numeric rules, server configuration-only preview and separate idempotent Save. Preview invalidation, frozen same-key uncertain-save retry, role/access boundaries and explicit discard protect unfinished work. Production build/type/frontend gates passed; 34 API/contract/backlog tests and 11 browser axe checkpoints passed with five-language creation, mobile/keyboard, exact values, CSRF, duplicate clicks, lost response, saved navigation and revocation. Email remains off and Start is not called. Existing-draft edit/delete, delivery preferences, browser Back/Forward/crash recovery and actual rollout/live acceptance remain open. MV2-070 remains IN PROGRESS. [Evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C01c2b1 deletion refinement, 2026-09-11 (before implementation):** Add manager-only deletion of the selected owned draft through the existing revision-checked DELETE API. Confirm the exact station/revision and irreversible removal of configuration/evaluation history. Block duplicate submissions and competing reader actions while pending. A revision conflict preserves the attempted view but requires a fresh read before another confirmation; never retry with an unseen revision. Success clears private detail/history and restarts pagination. An uncertain response permits an explicit same-revision retry; a later missing record is reported as unavailable, not falsely confirmed deletion. Revoked/default-off access clears private state. Verify five-language confirmation, cancel/success, stale revision, double clicks, ambiguous response/missing, role/access and no Start. Existing-draft editing, delivery preferences and navigation/crash recovery remain C01c2b2 and later work; this is not active-monitor lifecycle or live-source acceptance.

**C01c2b1 execution evidence, 2026-09-11:** Implemented [confirmed private draft deletion](docs/monitoring-v2/POLLEN_DRAFT_READER.md#c01c2b1-confirmed-deletion) with exact station/revision review, server CAS, duplicate/busy guards, fresh-read conflict recovery, private-state clearing and distinct uncertain/missing outcomes. Production build/type/frontend gates passed; 16 browser axe checkpoints with five-language deletion journeys and 10 API/DB/backlog checks passed, including the existing private-history cascade. Prior `40e7283` is an accepted actual release after 2261 API passes/12 skips; this new candidate is not yet verified active. Existing-draft editing, delivery preferences, navigation/crash recovery and source/live acceptance remain open. MV2-070 stays IN PROGRESS. [Evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C01c2b2 revision editing refinement, 2026-09-11 (before implementation):** Reuse the numeric draft form for authenticated owner-manager edits of a freshly read draft. Clone the entire supported v1 configuration, preserving metadata and saved delivery preferences; unsupported versions/fields/categories must remain read-only instead of being dropped. Require a new server configuration preview before PATCH with the originally reviewed expected revision. Conflicts require explicit discard/reload/review, never silent rebasing. After an uncertain PATCH, read current state and the exact next immutable history revision: a matching configuration hash proves requested settings exist in history; an unchanged original checkpoint allows a separate retry; differing history remains a conflict. Do not create another revision merely to recover a response. Verify five-language form/read-only states, numeric/metadata/preference preservation, CAS conflict, lost-response recovery, revocation and existing create/delete regressions. Delivery editing, broader unsupported configurations, navigation/crash recovery and source/live acceptance remain open.

**C01c2b2 implementation evidence, 2026-09-11:** Revision-checked numeric editing is implemented with preserved v1 metadata/delivery preferences, fresh configuration preview, explicit conflict reload/review and read-only recovery of uncertain writes through exact next immutable history. Unknown/future/category settings remain read-only. Production build/frontend gates, 15 compatibility tests, 20 API/repository/backlog tests and the five-language browser suite with 21 full-document axe checkpoints passed. Existing create/read/delete journeys remain covered. See [MV2-070 evidence](docs/monitoring-v2/evidence/MV2-070.md). Candidate activation, delivery-preference editing, broader configurations, navigation/crash recovery, human-language/accessibility and source/live acceptance remain open; MV2-070 stays IN PROGRESS.

**C01c2b3 delivery-preference refinement, 2026-09-11 (before implementation):** Add delivery fields to new and existing supported private drafts: email off/immediate/daily digest, an explicitly entered digest time only in digest mode, optional distinct quiet-hour start/end including overnight intervals, and the existing IANA timezone. New drafts remain email-off by default; changing away from digest clears its time, and disabling quiet hours explicitly clears that interval. Changes invalidate preview and use the same validated create/revision-CAS paths, frozen uncertain-write recovery and private scope. Explain that saving preferences does not establish live email consent, start monitoring or schedule/send messages; runtime timezone/DST and permission/consent rechecks remain C04. Verify all five locales, required/invalid clocks and equal quiet hours, mode switching, exact preview/save payloads, preservation of numeric settings, history/recovery and existing CRUD regressions. Native-language, live email, source and user acceptance remain open.

**C01c2b3 implementation evidence, 2026-09-11:** Added [delivery-preference fields](docs/monitoring-v2/POLLEN_DRAFT_READER.md#c01c2b3-delivery-preferences) to new/existing supported drafts with off defaults, explicit digest/quiet clocks, overnight/equal-time handling, mode/interval clearing and preview invalidation. Existing revision recovery and numeric settings are preserved. Build/type/frontend gates, 35 API/contract/backlog checks, targeted Ruff and 26 full-document browser axe checkpoints passed with five-language CRUD/delivery journeys. A real API regression verifies immutable schedules and no job/outbox creation. Previous `fc62f43` is an accepted actual release; this candidate is not yet verified active. Runtime email consent/scheduling/DST, broader configurations, navigation/crash recovery and human/source/live acceptance remain open. MV2-070 stays IN PROGRESS; [evidence](docs/monitoring-v2/evidence/MV2-070.md).

**C01c2b4a saved-draft recovery refinement, 2026-09-11 (before implementation):** Add an identifier-only URL fragment for the selected saved draft. Reloading or opening that link reads current configuration/history through existing owner/workspace authorization; neither configuration nor request keys enter URLs or browser storage. Preserve Next history state when replacing the fragment. Expose five-language link/recovery guidance and explicitly distinguish saved-state recovery from lost unsaved fields or uncertain new-draft request keys. Returning from browser page cache must clear retained private state and reread current authorization/data; failed/revoked/missing reads must clear selection and fragment. New-draft creation, successful deletion and explicit list reset clear the saved-draft fragment. Fix link-departure guards so same-document anchors and modified/new-tab/download clicks do not discard the current form, and accepted workspace/sign-out navigation does not prompt twice. Test reload/current revision, back/forward restored documents, denied/default-off/missing links, no write-on-recovery and unchanged existing CRUD/delivery flows. This slice does not claim full cancellation of same-document browser history traversal or recovery of unsaved fields after a crash; those remain C01c2b4b with an explicit privacy/recovery design.

**C01c2b4a implementation evidence, 2026-09-11:** Added [identifier-only saved-draft links and recovery](docs/monitoring-v2/POLLEN_DRAFT_READER.md#c01c2b4a-saved-state-recovery), authorized current-revision reads after reload, cached-document private-state clearing/session reload and corrected non-departing-link/committed-navigation guards. No private settings/request keys are persisted in the browser and recovery issues no writes. Build/type/frontend gates, two locator tests, 10 API/backlog checks and the five-language browser suite with 31 full-document axe checkpoints passed, including Back/Forward document traversal, current revisions, revoked/default-off/missing links and existing CRUD/delivery. Same-document traversal cancellation while editing and unsaved/crash recovery remain C01c2b4b; candidate activation, independent human/accessibility/language and source/live acceptance remain open. MV2-070 stays IN PROGRESS; [evidence](docs/monitoring-v2/evidence/MV2-070.md).

<a id="mv2-071"></a>

### MV2-071 — Pollen Watch FIRST: Accept the complete scenario and prepare for testing with real users

**Status:** IN PROGRESS — first user-testing gate · **Priority:** P0 · **Owner:** Product + QA + Operations + Independent reviewer · **Size:** M

**Release-recovery refinement, 2026-09-12:** The first complete candidate passed real API tests/builds but failed its decoder health probe and then rollback to an older schema; the site is unavailable. One operational repair will verify normal decoder startup and the exact health probe, transactional older-backup restoration across new foreign keys, and failure preservation. Preserve published migrations and the exact pre-failure backup; do not bypass gates or claim activation. Scope and manual recovery boundary: [POLLEN_RELEASE_RECOVERY.md](docs/monitoring-v2/POLLEN_RELEASE_RECOVERY.md).

**Complete-feature checkpoint, 2026-09-12:** The entire remaining Pollen block is implemented together in one unpublished feature worktree. The [pilot runbook](docs/monitoring-v2/POLLEN_PILOT_RUNBOOK.md) and [whole-feature record](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md) define the reviewable scenario and evidence boundaries. Independent source/category/seasonal, language, accessibility, real-user and actual release acceptance remains **HOLD**. No invitations, real email or production source/rollout activation were performed. This status records implementation and review preparation, not accepted upstream dependencies or readiness for participants.

**Dependencies:** [MV2-031](#mv2-031). **Requirements:** User decision 2026-09-10 on first delivery and real users; AC-C5-01…10; AC-CORE within C5 scope; §§31–34.

**User outcome:** A complete Pollen Watch delivery is verified, with a concrete protocol for starting tests with real users.

**Work:** Separate early C5 release/user-testing gate. Verify real observations/forecasts, the end-to-end product, privacy/accessibility/languages, operational support and user-test scenarios. It does not depend on MV2-051/057/058/059 being DONE or on other domains being implemented. This establishes first-delivery readiness, not acceptance of all v2.0 or completion of a pilot.

**Acceptance criteria:**

1. All 10 AC-C5 and all 20 AC-CORE are accepted within C5 scope: test/protocol, commit/build, source/fixture version, verification time and independent reviewer. Live observations and live official forecasts are visible as separate states with source/station/time; mocks or stale samples do not satisfy source readiness.
2. A test user, without prompting, completes location + multiple allergens + threshold → preview/Start → current state → material change → why/evidence/history → review → material update/reopen → opt-in delivery → pause/delete. A natural material event or explicitly labelled historical replay tests transitions; live freshness is verified separately.
3. Verify below/exact/above threshold, HIGH flapping, improvement, forecast revision, missing data/allergen/uncovered location, station changes, provider outage/staleness, source recovery, duplicates/restart and an offline LLM. There are no critical defects, invented measurements, medical diagnoses, lost reviews or cross-tenant leaks.
4. C5 flows have independent EN/DE/FR/IT/RM sign-off and keyboard/mobile/screen-reader evidence. The pilot environment is separate from production with protected access; the versioned build, backups/restore, telemetry, email opt-in/unsubscribe, support owner and stop/rollback runbook are verified. Response/processing/delivery lag is measured for the declared number of pilot users; inherited budgets are preserved for affected endpoints.
5. A first-wave protocol is ready for ≥5 real B2C users who need pollen monitoring within confirmed coverage: tasks, voluntary consent/data minimization, feedback method, owner and pause/fix criteria. Initial tasks cover setup, interpretation of observations/forecasts, threshold/why/evidence and review/pause; collect completion, errors, time to first value, explanation understanding and relevance/noise with visible denominators. The ≥5 sample is a target for this early usability test, not statistical confirmation of KPIs.
6. Record READY FOR USER TESTING or HOLD with blockers/limitations and next actions. A ready protocol does not mean people have already been invited or the pilot is complete. Deployment, external invitations and messages happen only after the corresponding authorization; the full four-week v2 pilot in MV2-058 remains separate.

**Verification:** An independent C5 go/no-go checklist, live-source end-to-end recording, acceptance evidence manifest, isolated restore/privacy/device/language reports and a ready moderated user-test protocol. Record measured user results after actual testing.

**Execution evidence:** Complete-feature implementation and isolated verification are recorded in [POLLEN_COMPLETE_FEATURE.md](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md), including CORE-20 traceability, retained native evidence, private lifecycle/delivery and the pilot HOLD boundary. Publication, actual release identity and independent source/human acceptance remain open; this task is not DONE.


## F1 — Shared contracts and compatibility

<a id="mv2-004"></a>

### MV2-004 — Personal workspace and team monitoring permissions

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + UX · **Size:** M

**Dependencies:** [MV2-001](#mv2-001). **Requirements:** §§5,27.1,27.7.

**User outcome:** B2C users do not need to invent a company; team data remains within the team.

**Work:** Reuse Organization/personal workspace and auth; define subject owner_scope, creator, access, membership, deletion and ownership transfer.

**Acceptance criteria:**

1. A personal workspace is isolated by default; another organization cannot see the Home address.
2. Admin manages shared monitors; a viewer has only permitted read/personal acknowledgement actions; a shared decision requires permission.
3. Workspace switching, access revocation and old links do not disclose a state or an AI conclusion.

**Verification:** API role matrix, negative cross-tenant tests and browser switching/revocation checks.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-005"></a>

### MV2-005 — MonitoringSubject and versioned Monitoring Templates

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Frontend · **Size:** L

**Dependencies:** [MV2-001](#mv2-001), [MV2-004](#mv2-004). **Requirements:** §§5,19.1,25,27.1.

**User outcome:** One configuration describes what the user wants to monitor.

**Work:** 8 active subject types and 9 template_id values; CURRENCY and the C4 template are deferred. Include schema_version, configuration, filters/thresholds/rules, source bindings, draft/active/paused/archived, revision and preview.

**Acceptance criteria:**

1. Validate LOCATION, JOURNEY, ROAD, ALLERGEN, MEASUREMENT_STATION, TENDER_PROFILE, TRADEMARK and AUCTION_PROFILE; C6/C7 use different templates over MEASUREMENT_STATION. CURRENCY/C4 require no schema, API or UI implementation in the current scope.
2. Activation requires an available source capability; preview does not trigger hidden activation.
3. Editing retains the revision and actor; repeating create with the same idempotency key does not duplicate a monitor.

**Verification:** Schema/API tests for valid and incompatible parameters across all nine active templates.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-006"></a>

### MV2-006 — ObservedEntity: stable source identity

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Integration · **Size:** M

**Dependencies:** [MV2-001](#mv2-001), [MV2-003](#mv2-003). **Requirements:** §§4,27.2,29.

**User outcome:** Fetching a record again does not create a new real-world entity.

**Work:** Identity = source_namespace + entity_type + external_id; aliases for confirmed republications and language versions; provenance and domain extensions.

**Acceptance criteria:**

1. An entity has a stable ID across polling, languages and restarts; namespaces do not merge unrelated identifiers.
2. When no reliable ID exists, use a versioned fallback strategy with collision tests and an uncertainty marker.
3. Changing a name, owner or URL does not delete history; merge/split operations are audited and can be corrected.

**Verification:** Replay duplicated/renamed records and collision/split fixtures.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-007"></a>

### MV2-007 — ObservedState and immutable evidence

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006). **Requirements:** §§19.2,27.3,30.

**User outcome:** Every state can be verified and compared with its predecessor.

**Work:** Typed payload, units, measurement/forecast, quality, fetched/published/effective/observed/valid times; schema_version, checksum, evidence locators and source retention policy.

**Acceptance criteria:**

1. A repeated snapshot with identical content does not create a material change; retain transport fetch logs separately.
2. A late/corrected response preserves history but does not roll back current without a revision-ordering rule.
3. Distinguish UNKNOWN, missing, zero, stale, forecast and provisional; evidence access/export complies with source rights.

**Verification:** Round-trip snapshots; out-of-order, correction, missing-data and rights-filter tests.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-008"></a>

### MV2-008 — Deterministic ChangeRule, ChangeSet and numeric thresholds

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend · **Size:** L

**Dependencies:** [MV2-005](#mv2-005), [MV2-007](#mv2-007). **Requirements:** §§4,19.3,22,33.

**User outcome:** A notification results from a meaningful change, rather than a timestamp refresh.

**Work:** NEW_ENTITY, STATE_TRANSITION, NUMERIC_THRESHOLD, PERCENTAGE_DELTA, FIELD_CHANGED, DEADLINE_CHANGED, DOCUMENT_ADDED, STATUS_CHANGED; SEMANTIC_MATCH is integrated as a candidate assessment in MV2-043. The shared numeric engine remains necessary for C5/C6/C7 and B8 price rules; customs-specific events, calendars and daily/weekly FX workflows are not implemented in v2.0.

**Acceptance criteria:**

1. Calculations use Decimal, unit/basis/aggregation-period; a zero baseline does not produce an invented percentage.
2. Define > versus ≥, previous-effective/daily/weekly baseline, crossing direction, hysteresis, cooldown and reset.
3. Each evaluation stores the rule revision, input state IDs, reason and result; preview and worker use the same evaluator.
4. The first state is a baseline; an active official hazard may produce an initial alert, but a numeric delta without a baseline may not.

**Verification:** Boundary/property/replay tests: equality, zero, null, flapping, gaps, units and weekly baseline.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-009"></a>

### MV2-009 — Development, deduplication and lifecycle

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend · **Size:** L

**Dependencies:** [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-008](#mv2-008). **Requirements:** §§6,27.4,29.

**User outcome:** The user sees one evolving history.

**Work:** Development + immutable revisions; separate source lifecycle from review/delivery; domain-specific correlation keys; audit manual splits.

**Acceptance criteria:**

1. The same incident/announcement and its language copies produce one development; a new trip service date or warning ID is not merged.
2. A material revision reopens review; an unchanged refresh neither reopens review nor sends a notification.
3. CANCELLED/RESOLVED/EXPIRED have different reasons; disappearance from a feed or a timeout does not mean an official all-clear.
4. Updates and reopening after a restart are handled idempotently.

**Verification:** State-machine and concurrent-ingestion tests; replay manual correction/merge/split operations.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-010"></a>

### MV2-010 — Structural relevance with evidence for every match

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend · **Size:** L

**Dependencies:** [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-009](#mv2-009). **Requirements:** §§7,19.4,22,27.6.

**User outcome:** “Why am I seeing this?” has a precise answer.

**Work:** RelevanceAssessment over subject revision × development revision; rule IDs, matched fields, source anchors and method; one development can have multiple reasons.

**Acceptance criteria:**

1. Block delivery without a reason and evidence; AI text does not replace a structural match.
2. A profile change reevaluates current relevance but does not rewrite the historical reason.
3. Exclusions take precedence over semantic score; UNKNOWN is not treated as a confirmed match.
4. One development matching multiple monitors does not generate multiple notifications for the same recipient.

**Verification:** Golden match/nonmatch cases, preview/worker parity and cross-profile replay.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-011"></a>

### MV2-011 — Reliable state ingestion, queues and freshness

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Operations · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-009](#mv2-009). **Requirements:** §§3,23,28,33.

**User outcome:** A monitor reports its state accurately even during failures.

**Work:** Extend PostgreSQL jobs + Celery; separate scheduled connector ingestion from bounded match fan-out; source leases, cursors, backoff, Retry-After and priority queues.

**Acceptance criteria:**

1. One shared source fetch serves many subjects; quota exhaustion or 429 does not trigger endless retries.
2. Restart/replay does not lose the watermark or duplicate revisions; history reprocessing does not send notifications by default.
3. Fresh/late/stale/failed/no-data are distinct from no-change; the next expected update comes from the capability.
4. Urgent deterministic jobs do not wait behind the LLM; one tenant cannot monopolize the queue.

**Verification:** Kill/restart, duplicate-worker, 429/partial-feed and overload tests; queue-lag telemetry.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-012"></a>

### MV2-012 — Notification policy and transactional outbox

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend · **Size:** L

**Dependencies:** [MV2-004](#mv2-004), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-011](#mv2-011). **Requirements:** §§28–29,33.

**User outcome:** Delivery channels respect settings without generating spam.

**Work:** Extend the existing outbox; recipient + development revision + channel policy revision; immediate/important/digest, mute, quiet hours, user timezone and opt-in.

**Acceptance criteria:**

1. Verify the material revision and recipient permissions before enqueue and send; revoked/paused/muted monitors receive no delivery.
2. Material escalation may bypass cooldown only under an explicit template rule; it does not override the user’s channel opt-out.
3. Retries, send timeouts and restarts do not duplicate in-app events; an external email acknowledgement is not presented as guaranteed delivery.
4. Urgent means processing priority after receiving source data, without promising to replace an emergency system.

**Verification:** Outbox race/retry/revocation tests, quiet hours/DST, send ambiguity and deduplication.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-013"></a>

### MV2-013 — Review, Decision and owner assignment

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Frontend · **Size:** M

**Dependencies:** [MV2-004](#mv2-004), [MV2-009](#mv2-009). **Requirements:** §§6,21,27.7,31.

**User outcome:** The user’s decision is saved with the evidence version.

**Work:** Personal read state, workspace Review, append-only Decision; REVIEWED/ACTION_REQUIRED/NO_ACTION/NOT_RELEVANT/MONITOR/RESOLVED and domain decisions.

**Acceptance criteria:**

1. A decision includes development revision, actor, owner, comment and timestamp; a concurrent write does not overwrite another.
2. A new material update marks the previous decision as based on an older revision; its text remains in history.
3. BID/NO_BID/INSPECT/ESCALATE_TO_IP_COUNSEL are internal decisions; no external submission or sending occurs.
4. Deactivating an owner does not lose unresolved reviews; reassignment to another member is permitted.

**Verification:** Optimistic concurrency, roles, reopening, reassignment and personal/shared-state tests.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-014"></a>

### MV2-014 — Shared-feed API and read projections

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend · **Size:** L

**Dependencies:** [MV2-004](#mv2-004), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-013](#mv2-013). **Requirements:** §§20–21,26,33.

**User outcome:** Today and history stay fast with mixed data.

**Work:** New versioned API contracts; projections, cursor pagination, unseen revision count, template/status/subject/severity filters and lazy-loaded evidence.

**Acceptance criteria:**

1. Today does not perform a cross-join over all states, AI calls or generation; maximum page size, period and enrichment are bounded.
2. Unread count is based on visible revisions and does not depend on the current page.
3. Stable cursors do not lose records when new revisions arrive; archived/resolved history remains accessible.
4. Endpoint authorization checks the workspace for every development, evidence item and decision.

**Verification:** SQL query-count/plan checks, pagination during updates and serialization contracts.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-015"></a>

### MV2-015 — Geography, station and coverage catalogue

**Status:** PLANNED · **Priority:** P0 · **Owner:** Integration + Backend + UX · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006). **Requirements:** §§8,12–14,19.1.

**User outcome:** The selected location corresponds to actual coverage.

**Work:** Official municipality/station IDs, coordinates, CRS, polygon/radius, station metrics and validity; reuse pack metadata.

**Acceptance criteria:**

1. Test boundary intersections, overlapping canton/municipality areas, radius and CRS using fixtures.
2. The nearest station is not presented as a measurement at home; show distance, representativeness, available metrics and limitations.
3. An uncovered location does not activate a fictitious monitor; an unavailable parameter is not replaced with another.
4. A relocated/closed station receives an explicit remap with history, rather than a silent replacement.

**Verification:** Geo boundary/CRS tests, station gap/change fixtures and keyboard selector UX.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-016"></a>

### MV2-016 — Time windows, deadlines and reminders

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend · **Size:** L

**Dependencies:** [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-012](#mv2-012). **Requirements:** §§9–10,15–17,27,28.

**User outcome:** Deadline changes and planned journeys are handled correctly.

**Work:** UTC storage + Europe/Zurich display, overnight windows, service date >24h and weekdays; explicit versus calculated deadlines, evidence rule version and rescheduled jobs.

**Acceptance criteria:**

1. DST gaps/folds and 23:00–05:00 work under a defined policy; retain the source timezone.
2. Unknown/ambiguous deadlines are not invented; a calculated legal deadline always has verification_required.
3. Rescheduling/cancelling an auction or tender cancels previous ending-soon jobs; reminders are idempotent per deadline revision.
4. Document the difference between official resolution and system expiry; past events remain in history.

**Verification:** Fake-clock tests for DST, midnight, delays, rescheduling, expiry and source corrections.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-060"></a>

### MV2-060 — Legacy bridge for Topics, watches and legal events

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Frontend · **Size:** L

**Dependencies:** [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014). **Requirements:** §§1,26–27; legacy HL-073,076–080,089,098–100.

**User outcome:** Existing Helvetic Lens capabilities remain available in the new model.

**Work:** Bridge references from old Topic/RegulatoryEvent/Watch IDs → generic Subject/Entity/Development; compatibility read adapters without a blanket foreign-key rewrite.

**Acceptance criteria:**

1. Legal records remain in the existing tables; generic contracts do not require AI analysis/comparison for numerical decisions.
2. Backfill does not turn old reviewed events into new unread items; the two fan-out systems do not send duplicates.
3. Topics/watch settings, locales, citations and user decisions are preserved; old links resolve to the corresponding evidence.
4. Unsupported legacy-only records remain visible through the old reader with an explanation, rather than being silently dropped; repairs are audited.

**Verification:** A gold legacy corpus shaped like production, bridge replay, read parity and notification suppression.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-068"></a>

### MV2-068 — Complete legacy coverage verification and repair old artifacts

**Status:** PLANNED · **Priority:** P0 · **Owner:** Integration + Backend + QA · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-060](#mv2-060). **Requirements:** legacy HL-080,098,100; §§1,26,30.

**User outcome:** New domains do not conceal unfinished quality work in existing legal monitoring.

**Work:** Carry forward the remaining HL-080/098 work: exact source coverage of federal/cantonal streams, Basel pilot evidence, bounded versioned re-extraction/repair with preview; immutable originals remain unchanged.

**Acceptance criteria:**

1. Claimed existing coverage has verified types, languages, geography, time, history and known gaps; Ticino auctions do not satisfy the Basel regulatory gate.
2. A repair has a new normalization revision and an explanation; the old hash/evidence is not overwritten.
3. Repeated repair/resume does not create false amendments or duplicate notifications; affected comparisons and cached briefs are superseded in a controlled way.
4. After repair, old URLs, citations, review/read state and legal-relationship evidence pass regression checks.

**Verification:** A representative legacy corpus before/after with hashes, permitted live legal/cantonal samples, re-extract/cancel/retry checks and user-journey evidence.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.


## F2 — One user journey

<a id="mv2-017"></a>

### MV2-017 — Create Monitor: nine understandable templates

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + UX · **Size:** L

**Dependencies:** [MV2-002](#mv2-002), [MV2-005](#mv2-005), [MV2-010](#mv2-010), [MV2-015](#mv2-015). **Requirements:** §§5,25,33.

**User outcome:** The user configures the goal, and the system selects the source.

**Work:** Personal/Business template picker; guided form, capability availability, why-match/no-match preview, defaults and explicit start.

**Acceptance criteria:**

1. Provide six Personal templates C1/C2/C3/C5/C6/C7 and three Business templates B2/B7/B8; unsupported/blocked active scenarios explain the reason and cannot be activated. C4 is absent from the current picker; no customs-rate placeholder or form is required.
2. The form collects the domain configuration from the requirements without asking users for a URL, API key or technical source ID.
3. Preview labels a sample/baseline and does not create real alerts; double-clicking Start does not create duplicates.
4. Errors retain the draft and suggest corrections; the first state shows the expected wait, source and next step.

**Verification:** Browser journeys for creation, editing and unavailability across the nine active templates.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-018"></a>

### MV2-018 — Monitoring: manage saved subjects

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend · **Size:** M

**Dependencies:** [MV2-005](#mv2-005), [MV2-011](#mv2-011), [MV2-017](#mv2-017). **Requirements:** §§9.12,25–26.

**User outcome:** Users can see exactly what is monitored and whether ingestion is working.

**Work:** List personal/shared subjects; status, source, last observation/success/next expected update, thresholds, pause/resume/archive and contextual Monitor this.

**Acceptance criteria:**

1. Edits and pause/resume persist after reload; archiving does not delete history.
2. No change, first data pending, stale, source unavailable and disabled have distinct wording and actions.
3. Pause commute today resumes automatically according to the timezone and shows the time; archive has no automatic resume.
4. Existing Topics and watched documents remain accessible through the bridge; new navigation does not duplicate management.

**Verification:** Browser persistence, real-time status updates, stale recovery and legacy-link tests.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-019"></a>

### MV2-019 — Today: one card across all domains

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + UX · **Size:** L

**Dependencies:** [MV2-014](#mv2-014), [MV2-017](#mv2-017). **Requirements:** §§20,26.1,33.

**User outcome:** Mixed events are equally easy to understand.

**Work:** Shared card shell: type, authority severity, state/delta, why, timestamps, evidence and review; domain-specific fields within the shell.

**Acceptance criteria:**

1. The card includes the fact, previous→current, source/time, structural why and an explicit CTA; the initial baseline does not invent a previous state. Review / Evidence / Not relevant are explicit on the card.
2. Observed, forecast, stale and system calculation have visible labels; source severity is separate from user priority.
3. One development aggregates multiple subjects; material updates/reopened states are marked without creating a second independent card.
4. Legacy legal and all 9 active v2 templates work with filters, accessible empty/loading/error states and global unread counts.

**Verification:** Populated mixed-feed browser replay; keyboard, narrow viewport and live revision updates.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-020"></a>

### MV2-020 — Investigate: states, diffs, evidence and history

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014). **Requirements:** §§21,30.

**User outcome:** Users can verify what has changed since their decision.

**Work:** Typed numeric/state diffs, document-set diff plug-in, pinned evidence, current/historical revisions, provenance and an AI section.

**Acceptance criteria:**

1. A historical card opens the corresponding old evidence; a today/current response does not replace it.
2. Fact / AI / calculation / decision are explicitly separated; a numeric value includes unit, period and quality.
3. Raw download/export is available only where source policy permits it; otherwise provide permitted normalized evidence + official link + an explanation of limitations.
4. Load large documents and timelines in parts; a broken/live source does not invalidate retained permitted evidence.

**Verification:** Evidence-version navigation, permissioned export and long-text/large-history browser checks.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-021"></a>

### MV2-021 — Workspace: Impact Inbox, decisions and Impact Matrix

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** M

**Dependencies:** [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-019](#mv2-019), [MV2-020](#mv2-020). **Requirements:** §§15–17,26.4,27.7.

**User outcome:** Unfinished work has an owner and context.

**Work:** Unresolved/reopened/assigned filters, notes, decisions and safe batch review; preserve the existing Matrix in its regulatory context without invented cross-domain impact scores.

**Acceptance criteria:**

1. A high-severity hazard, relevant IP candidate or tender update can have an Inbox review; source state is not mixed with the decision.
2. Batch review is tied to visible revisions; a new revision arriving during the action is not considered reviewed.
3. BID/NO_BID/INSPECT/escalate have domain-specific labels and send nothing externally.
4. Owner assignment and decision history are visible only within the permitted scope; Matrix and old inbox links work.

**Verification:** Concurrent revision/decision browser journeys, owner filters and legacy Matrix regression.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-022"></a>

### MV2-022 — Notifications and Digests from the same developments

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-012](#mv2-012), [MV2-014](#mv2-014), [MV2-019](#mv2-019). **Requirements:** §§28,33; AC-B2-12; C4 digest deferred.

**User outcome:** Users manage noise in one place.

**Work:** In-app center and opt-in email digest; monitor/type/event/channel mute, priority, frequency, quiet hours and review/evidence deep links.

**Acceptance criteria:**

1. Immediate notifications and digests do not duplicate the same revision without an explicitly selected recap policy.
2. A digest contains only material changes from the permitted period and identifies source gaps; preview uses the sending rules.
3. Settings are saved per user/workspace; unsubscribe and permissions are applied before sending.
4. Improvement/cancellation messages link to the preceding development; unread state is synchronized between Today and the center.

**Verification:** Send-preview parity, race/unsubscribe tests, multi-monitor deduplication and bounded-period queries.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-023"></a>

### MV2-023 — Ask and Marvin in the context of v2 evidence

**Status:** PLANNED · **Priority:** P1 · **Owner:** AI + Frontend · **Size:** M

**Dependencies:** [MV2-010](#mv2-010), [MV2-020](#mv2-020). **Requirements:** §§21–22,26.3,31; legacy HL-083–087,089.

**User outcome:** Asking about an event does not trigger unnecessary generation or change a monitor.

**Work:** Reuse cached briefs; entity-aware read context and cited answers; follow-up intent and explicit draft/preview for monitor changes.

**Acceptance criteria:**

1. The core of active C1/C2/C3/C5/C6/C7 works with the LLM offline; an unavailable model presents evidence/extractive mode.
2. A saved conclusion is tied to state/profile/model/prompt/locale revisions; a stale answer is not presented as current.
3. Ask does not promise medical treatment, infringement findings or a guaranteed legal deadline; official instructions are quoted accurately.
4. Natural-language configuration creates a draft for review; no autonomous activation, bid or external message occurs.

**Verification:** Context revocation, stale briefs, prompt-injection fixtures and cited-answer checks under a feature flag. DONE means integration with manual/extractive fallback; production model enablement separately passes MV2-051.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-024"></a>

### MV2-024 — Clear guidance, accessibility and five languages

**Status:** PLANNED · **Priority:** P0 · **Owner:** UX + Frontend + Language reviewers · **Size:** L

**Dependencies:** [MV2-002](#mv2-002), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022). **Requirements:** §§20–21,25–26; legacy HL-057,073,095–097.

**User outcome:** New capabilities are accessible by keyboard, on a phone and in a supported language.

**Work:** English-first implementation with existing i18n contracts; EN/DE/FR/IT/RM release strings and human review; F1/Page guide/Show me for new actions.

**Acceptance criteria:**

1. New sections explain data provenance, every action, waiting/configuration and the effects of mute/review.
2. Keyboard/focus/contrast/screen-reader checks pass for populated/error/stale flows; color is not the only signal.
3. Independent fluent reviewers verify new v2 flows in all five languages; an unreviewed language is not declared ready.
4. Primary actions are simple; provider/queue/debug fields stay in Admin, and units/dates/number formats are localized.

**Verification:** Browser/axe + screen-reader/device review + language sign-off; automated checks do not replace human acceptance.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-025"></a>

### MV2-025 — Admin: accurate source capabilities and access management

**Status:** PLANNED · **Priority:** P0 · **Owner:** Integration + Frontend · **Size:** M

**Dependencies:** [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-018](#mv2-018). **Requirements:** §§23,26.5,38.

**User outcome:** Administrators understand why a template is available or blocked.

**Work:** Catalogue 4 active source packs: Swiss Safety & Environment, Swiss Mobility, Swiss Business Opportunities and Swiss IP; Swiss Customs is deferred. For active packs, include conformance version, access expiry, supported fields/location/history, quotas, freshness and reprocess controls.

**Acceptance criteria:**

1. Export restrictions, access expiry, correction requirements and licence version are enforced through policy, rather than only documented.
2. Missing access shows an actionable state; viewers cannot see secrets or credentials.
3. Reprocess provides preview, bounded scope, progress/cancel/resume; historical replay does not create an alert burst.
4. A terms/capability change disables the dependent function and notifies the administrator; no silent third-party fallback occurs.

**Verification:** API permission tests, licence-expiry clock, source failure/recovery and reprocess browser checks.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.


## F3 — Numeric states, environment and hazards

<a id="mv2-028"></a>

### MV2-028 — C1: official warnings and hazard geography

**Status:** PLANNED · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071). **Requirements:** §8.4–8.9; AC-C1-02,04,05,07,09.

**User outcome:** An official warning has a stable history and affected area.

**Work:** Alertswiss/federal/cantonal capability-specific adapter; authority ID, severity scale, certainty, instructions, publication/effective/valid times and cancellation. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Verify access and permitted geography; hazard categories reflect actual source coverage, including outages if the source supplies them.
2. Retain instructions and authority severity without AI rewriting; multiple languages do not duplicate a warning.
3. Retain polygon/municipality expansion/reduction as an update; cancellation/all-clear is distinct from a feed gap.
4. Missing types or cantonal data are marked unavailable, rather than “no hazard”.

**Verification:** Source fixtures for creation/update/instructions/geography/cancellation; controlled live fetch with permission.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-029"></a>

### MV2-029 — C1: Home/Office locations and the complete warning workflow

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-028](#mv2-028). **Requirements:** §8; AC-C1-01…10.

**User outcome:** Only people affected by the area receive the warning.

**Work:** Multiple saved locations, hazards/minimum importance, Review/View official/Not relevant/Mute type; active and historical warning state.

**Acceptance criteria:**

1. Satisfy AC-C1-01…10; Home inside the affected geometry receives a warning, while Home outside it does not.
2. New instructions, severity, geography, time or cancellation create a material revision; formatting/timestamp refreshes do not.
3. Verify that material escalation reopens a reviewed item; an all-clear closes the active source event while retaining review history.
4. Critical source instructions are visible without AI; show the official source and freshness alongside them; no-data is not shown as an all-clear.

**Verification:** E2E multi-location, boundary, changed instructions, reviewed→reopened→all-clear, mute and offline-model checks.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-030"></a>

### MV2-030 — C5: official pollen observations and forecasts

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Integration · **Size:** M

**Complete-feature checkpoint, 2026-09-12:** Bounded official hourly/daily collection, shared source leases, immutable revisions/retention and the isolated pinned ICON-CH2 decoder/collector are implemented in the same feature as MV2-070/031. Canonical LF definitions reproduce the retained 15-station ragweed proof exactly; synthetic transports test failure and correction handling. These are engineering checks, not permitted current birch/grass forecast or official category/operating acceptance. See the [source dossier](docs/monitoring-v2/POLLEN_SOURCES.md) and [whole-feature record](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md).

**Dependencies:** [MV2-069](#mv2-069), [MV2-070](#mv2-070). **Requirements:** §12.3–12.8; AC-C5-03,06,08.

**User outcome:** A verified allergen × station time series is available.

**Work:** MeteoSwiss/SwissPollen dataset contract, parameter list, categories, units and station capability; separate observation and forecast series. The first C5 implementation uses the completed contracts from MV2-069/070; DONE status for the general parent tasks MV2-003/007/011/015 is not a prerequisite.

**Acceptance criteria:**

1. Demonstrate support for birch/grasses at the selected station; an unavailable allergen is not treated as zero.
2. Do not mix observation_time, issue_time and forecast_valid_time; a revised forecast does not overwrite a measurement.
3. Retain official categories/scales with their version; distinguish provisional/corrected readings.
4. Polling follows verified source cadence; a 20-minute refresh does not imply a separate alert.
5. G(C5-observation) and G(C5-forecast) each have separate permitted live samples, stations/allergens/time fields and sufficient retained evidence. A synthetic forecast or a forecast without a confirmed official channel does not satisfy the complete scenario.

**Verification:** Official dataset sample, missing station/allergen, revision and forecast-versus-observation conformance.

**Execution evidence:** Complete-feature implementation and isolated verification are recorded in [POLLEN_COMPLETE_FEATURE.md](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md), including CORE-20 traceability, retained native evidence, private lifecycle/delivery and the pilot HOLD boundary. Publication, actual release identity and independent source/human acceptance remain open; this task is not DONE.

<a id="mv2-031"></a>

### MV2-031 — Pollen Watch — the first complete end-to-end scenario (C5)

**Receiving subtask, 2026-09-12 — Monitoring navigation and general availability:** Add a distinct desktop/mobile Monitoring group with Pollen Watch in all five locales. Permit current and future authenticated workspaces, preserving explicit revocation, source approval, user ownership and delivery consent. Integrate all Monitoring commits into current main by explicit user request; preserve main changes and the frozen tag. Verify affected API, navigation, migration and deployment compatibility. Publication is not activation evidence; retain unverified acceptance as IN PROGRESS.

**Receiving-subtask evidence:** [General availability and main integration](docs/monitoring-v2/POLLEN_GENERAL_AVAILABILITY.md) records the implementation, passing API/build/browser/Compose checks and staged wildcard grant. Exact public activation and independent pilot acceptance remain open.

**Release repair, 2026-09-12:** The automatic rollout of 79b0147 stopped at API lint because the newly added pytest import has an extra blank line. Correct the import grouping and run the exact full deployment lint gate plus affected HTTP tests before republishing the same feature to both authorized channels. No source, consent, runtime or acceptance-gate behavior changes.

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Frontend + Backend + UX · **Size:** L

**Complete-feature checkpoint, 2026-09-12:** The implementation joins explicit Start, current observation/forecast, material changes in Today, exact why/evidence, review history/reopening, pause/edit/resume/archive/delete/export and separately consented email. Five-language synthetic browser scenarios and isolated SQLite/PostgreSQL checks are recorded in the [whole-feature record](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md). Full regression and publication are in progress; no DONE or user-testing acceptance is claimed.

**Dependencies:** [MV2-070](#mv2-070), [MV2-030](#mv2-030). **Requirements:** §12; AC-C5-01…10.

**User outcome:** Location + pollen type + threshold produce an understandable monitor.

**Work:** Create one coherent delivery slice using a real permitted source: setup, initial state, category crossing, review, improvement and history. This is the first functional product delivery; it does not depend on completion of the all-template UI, business AI, mobility or the whole of F6. Implement and verify its shared prerequisites in the explicit C5 subtask MV2-070. Admission of real users is a separate gate in MV2-071.

**Acceptance criteria:**

1. Satisfy AC-C5-01…10; support one or multiple pollen types, threshold/high-or-above and a rapid-increase window.
2. HIGH fluctuations do not generate spam; improvement updates the same development after the configured reset.
3. Observed and Forecast tomorrow have different labels/times; explain station coverage and local limitations.
4. Provide no diagnosis/dosage; first value is available with the LLM disabled.

**Verification:** Golden + permitted live E2E, reviewed updates, flapping, station gaps and email opt-in; recorded demo.

**Execution evidence:** Complete-feature implementation and isolated verification are recorded in [POLLEN_COMPLETE_FEATURE.md](docs/monitoring-v2/POLLEN_COMPLETE_FEATURE.md), including CORE-20 traceability, retained native evidence, private lifecycle/delivery and the pilot HOLD boundary. Publication, actual release identity and independent source/human acceptance remain open; this task is not DONE.

<a id="mv2-032"></a>

### MV2-032 — C6: hydrological stations, metrics and official danger levels

**Status:** VERIFYING · **Priority:** P1 · **Owner:** Integration · **Size:** M

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071). **Requirements:** §13.3–13.5; AC-C6-01,02,05,08.

**User outcome:** Water level, discharge, temperature and danger are not mixed.

**Work:** FOEN station/waterbody mapping; parameter units/reference datum/aggregation/quality; explicit source danger versus a locally calculated threshold. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Verify coverage for each metric; an absent station parameter = UNKNOWN.
2. Water levels with different datums are not compared as a single series; discharge/temperature have their own units.
3. An official danger level comes from an official product and area, rather than being invented from the water level.
4. Confirm the live/history window and recovery watermark, accounting for contradictory documentation.

**Verification:** Metric/datum/quality fixtures and source-contract probe; hydrology sample review.

**Authorized C6 feature scope, 12 September 2026:** The user selected the next complete direction after Pollen and main-only delivery. This scoped implementation uses existing authenticated workspace boundaries, durable jobs and deterministic monitoring patterns without waiting for the broader shared parents or human Pollen pilot to finish. It does not complete those parent tasks. Deliver River / Lake station search, official FOEN live measurements and independently sourced LINDAS station danger, validated absolute/change-window rules, explicit preview/start, pause/resume/edit/archive/delete, private web developments and review, separate measurement/change histories, stale/unknown handling and bounded recovery. Source contracts and verification are recorded in docs/monitoring-v2/RIVER_LAKE_WATCH.md. External email delivery is outside this C6 slice; changes are delivered in the authenticated web reader, with no implicit email consent. Pollen remains compatible and all current source/privacy gates apply.
**Execution evidence:** Complete C6 implementation and acceptance mapping: [River / Lake Watch](docs/monitoring-v2/RIVER_LAKE_WATCH.md). Real FOEN probe: 243 stations, current Basel W/Q and independently sourced official danger; unavailable WT remains UNKNOWN. Focused source/lifecycle/privacy/worker/retention tests, 135 affected auth/release/backlog regressions, 271 Pollen/shared-runtime/job/isolation regressions, production frontend build and seven browser accessibility checkpoints across five locales passed. The feature publishes on main; exact release activation remains pending, so this task is VERIFYING rather than DONE. Broader shared parent and human pilot acceptance are not implied.

<a id="mv2-033"></a>

### MV2-033 — C6: River / Lake thresholds, escalation and history

**Status:** VERIFYING · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** M

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-032](#mv2-032). **Requirements:** §13; AC-C6-01…10.

**User outcome:** The user monitors the waterbody or station they need.

**Work:** Station/waterbody picker, water-level/discharge/temperature/danger selection; absolute/rate-of-change window; escalation/downgrade.

**Acceptance criteria:**

1. Satisfy AC-C6-01…10; an absolute threshold >2.5m and +30cm over a specified time use the appropriate units/window.
2. Official danger escalation has higher priority and is not suppressed by a lower custom threshold.
3. A downgrade changes the existing development; unchanged readings do not create duplicates.
4. Measurement history is separate from change history; the source timestamp/quality is visible.

**Verification:** E2E threshold/window/danger override/reversal/duplicate/missing-reading checks.

**Authorized C6 feature scope, 12 September 2026:** The user selected the next complete direction after Pollen and main-only delivery. This scoped implementation uses existing authenticated workspace boundaries, durable jobs and deterministic monitoring patterns without waiting for the broader shared parents or human Pollen pilot to finish. It does not complete those parent tasks. Deliver River / Lake station search, official FOEN live measurements and independently sourced LINDAS station danger, validated absolute/change-window rules, explicit preview/start, pause/resume/edit/archive/delete, private web developments and review, separate measurement/change histories, stale/unknown handling and bounded recovery. Source contracts and verification are recorded in docs/monitoring-v2/RIVER_LAKE_WATCH.md. External email delivery is outside this C6 slice; changes are delivered in the authenticated web reader, with no implicit email consent. Pollen remains compatible and all current source/privacy gates apply.
**Execution evidence:** Complete C6 implementation and acceptance mapping: [River / Lake Watch](docs/monitoring-v2/RIVER_LAKE_WATCH.md). Real FOEN probe: 243 stations, current Basel W/Q and independently sourced official danger; unavailable WT remains UNKNOWN. Focused source/lifecycle/privacy/worker/retention tests, 135 affected auth/release/backlog regressions, 271 Pollen/shared-runtime/job/isolation regressions, production frontend build and seven browser accessibility checkpoints across five locales passed. The feature publishes on main; exact release activation remains pending, so this task is VERIFYING rather than DONE. Broader shared parent and human pilot acceptance are not implied.

<a id="mv2-034"></a>

### MV2-034 — C7: official air-quality series and interpretation

**Status:** VERIFYING · **Priority:** P1 · **Owner:** Integration · **Size:** M

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071). **Requirements:** §14.3–14.6; AC-C7-01,03,06,07.

**User outcome:** The user sees a known metric with the correct period.

**Work:** FOEN/NABEL and permitted cantonal adapters; PM2.5/PM10/O3/NO2, station/model distinction and hourly/daily/24h fields. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Confirm station and parameter support, including for the selected Lugano location; missing coverage is visible.
2. O3 hourly and daily-max values and NO2/PM 24h values are not compared directly; source measurement time is distinct from fetch time.
3. Categories have an official scale/source; without one, display the numeric state and user rule without invented medical risk classes.
4. Label provisional/invalid/corrected data and local representativeness.

**Verification:** Unit/aggregation/category source conformance; provisional/missing/corrected data cases.

**Execution evidence — complete Basel feature, 12 September 2026:** [Air Quality Watch](docs/monitoring-v2/AIR_QUALITY_WATCH.md) records the licensed source, six additive tables, private lifecycle/revisions, explicit hourly or complete 24-hour rules, hysteresis/cooldown, pollutant mute, immutable corrections, Today/review/reopen, history and five-language reader. The actual collector retrieved 384 samples and all four current Basel pollutants into an isolated scratch database. Focused behavior, worker, migration and privacy tests, affected regressions, full frontend build and eight browser accessibility checkpoints passed. The first enabled footprint is Basel-Binningen; Lugano and other areas explicitly remain unsupported pending their source contracts. Numeric user thresholds do not claim an official category scale. Exact release activation and applicable field/human acceptance remain unverified, so the task stays VERIFYING. Broader shared parents and national source coverage are not completed by this scoped feature.

<a id="mv2-035"></a>

### MV2-035 — C7: Air Quality — metrics, changes and improvements

**Status:** VERIFYING · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** M

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-034](#mv2-034). **Requirements:** §14; AC-C7-01…10.

**User outcome:** Pollution is monitored without notifications for every fluctuation.

**Work:** Location/station, pollutant multiselect, category/material increase, mute pollutant, adjust threshold and compare/history.

**Acceptance criteria:**

1. Satisfy AC-C7-01…10; a relevant change appears in Today and explains the station/area match.
2. Category thresholds and cooldown do not mix different aggregation periods.
3. An improved/resolved state updates the same development; source unavailability does not mean normal.
4. The UI does not infer the health of an individual user; limitations/evidence are accessible.

**Verification:** E2E pollutants/periods, improvement, noise suppression, unsupported-station and history checks.

**Execution evidence — complete Basel feature, 12 September 2026:** [Air Quality Watch](docs/monitoring-v2/AIR_QUALITY_WATCH.md) records the licensed source, six additive tables, private lifecycle/revisions, explicit hourly or complete 24-hour rules, hysteresis/cooldown, pollutant mute, immutable corrections, Today/review/reopen, history and five-language reader. The actual collector retrieved 384 samples and all four current Basel pollutants into an isolated scratch database. Focused behavior, worker, migration and privacy tests, affected regressions, full frontend build and eight browser accessibility checkpoints passed. The first enabled footprint is Basel-Binningen; Lugano and other areas explicitly remain unsupported pending their source contracts. Numeric user thresholds do not claim an official category scale. Exact release activation and applicable field/human acceptance remain unverified, so the task stays VERIFYING. Broader shared parents and national source coverage are not completed by this scoped feature.

## F4 — Mobility and related events

<a id="mv2-036"></a>

### MV2-036 — Related developments from multiple sources

**Status:** PLANNED · **Priority:** P1 · **Owner:** Backend + UX · **Size:** M

**Dependencies:** [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-029](#mv2-029), [MV2-033](#mv2-033), [MV2-041](#mv2-041), [MV2-071](#mv2-071). **Requirements:** §§13.7,29.

**User outcome:** A flood and a road closure can be reviewed together.

**Work:** Associate records across sources using verified identifiers, geography and time; provide a grouped overview, evidence for each event, explainable links and reversible splits.

**Acceptance criteria:**

1. River danger, Alertswiss and a road closure can be linked to one location story without losing their separate authority IDs.
2. Proximity in time alone does not prove a common cause; an unconfirmed relationship is labelled as possible.
3. Conflicting sources are displayed separately; cancellation of one event does not close the others.
4. Merging or splitting does not duplicate delivery or automatically transfer review decisions from another event.

**Verification:** A three-source fixture, an unrelated nearby-location negative case, and correction/split replay.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-037"></a>

### MV2-037 — Journey/Trip/Route/Stop and Road Corridor reference data

**Status:** PLANNED · **Priority:** P0 · **Owner:** Integration + Backend · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-015](#mv2-015), [MV2-016](#mv2-016), [MV2-071](#mv2-071). **Requirements:** §§9.4–9.8,10.3–10.5.

**User outcome:** A transport subject is matched using a stable entity.

**Work:** GTFS/static identifiers, timetable service dates, stop/line/trip/route/journey/direction; saved road segments and corridor geometry. Turn-by-turn routing is outside scope.

**Acceptance criteria:**

1. Origin and destination can select a verified journey or explicit legs; a city keyword match is not presented as a route intersection.
2. Trip ID is tied to the service date, cross-feed stop ID mappings are versioned, and timetable times >24h are supported.
3. Road direction, segment and corridor IDs are matched separately from railway routes.
4. Reference-data refreshes preserve monitors; unresolved mappings are communicated to the user.

**Verification:** Static↔realtime ID fixtures, a replaced timetable, an overnight trip and the opposite road direction.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-038"></a>

### MV2-038 — C2: Service Alerts and Trip Updates

**Status:** PLANNED · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071). **Requirements:** §9; AC-C2-02,06,07,08.

**User outcome:** A regular journey receives the official disruption state.

**Work:** Official GTFS-RT alerts/trip updates; cancellation, partial cancellation, stop/platform changes, replacement and restoration; documented full/differential feed semantics. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Every claimed event type is mapped to fields actually available in the feed; missing platform or delay data is not invented.
2. GTFS service date, entity ID, validity, delay minutes and language editions are preserved.
3. A repeated response, entity disappearance and an expired alert have distinct semantics; deletion does not guarantee restoration.
4. The authentication and rate-limit contract is clarified with the source; the documented conflict between 2/5 req/min is not resolved by guessing.

**Verification:** Protocol replay: full/differential/delete/stale, cancellation, a changed stop, and replacement/restoration.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-039"></a>

### MV2-039 — C2: Regular commutes and low-noise transport alerts

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-038](#mv2-038). **Requirements:** §9; AC-C2-01…10.

**User outcome:** Alerts relate to the route and the journey time.

**Work:** Journey/line/stop/trip selector, weekdays and time window, threshold in minutes, pause today, mute event; NORMAL→…→RESTORED state transitions.

**Acceptance criteria:**

1. AC-C2-01…10 are met; a cancellation outside the route is not delivered; time overlap is required for immediate delivery.
2. Outside the time window, ignore the event or include it in an opt-in digest according to a visible policy; delays of 1/2/3/4 minutes do not generate repeated alerts with a threshold of 10.
3. Restoration or partial resumption updates the same service-day development; historical disruptions remain available.
4. A cancellation near departure has priority in the deterministic queue; stale source data is visible before planning the journey.

**Verification:** End-to-end commute checks for weekdays, time/DST, thresholds, partial restoration, pause today and historical replay.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-040"></a>

### MV2-040 — C3: ASTRA traffic and planned closures

**Status:** PLANNED · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071). **Requirements:** §10; AC-C3-02,04,05,07,08.

**User outcome:** Known roads have states and planned changes supported by source evidence.

**Work:** Permitted ASTRA/FEDRO feeds; DATEX or another confirmed format; segment/direction, lane/full closure, incident, congestion/delay and planned time windows. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Access, the six-month access period and renewal are tracked; raw machine-readable redistribution is prohibited according to the source policy.
2. Closures and measured congestion/delay are separate capabilities: one safety feed is insufficient to claim coverage of all road states.
3. Planned/live events, rescheduling and reopening are normalized; source instructions and evidence are preserved in a permitted form.
4. Coverage and direction for A2/Gotthard/A13 are confirmed; estimated_delay is UNKNOWN when the feed does not provide it.

**Verification:** Contract probe and replay of full/lane closures, roadworks, missing delay, planned rescheduling and reopening.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-041"></a>

### MV2-041 — C3: My Route Watch for A2 / Gotthard / A13

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-040](#mv2-040). **Requirements:** §10; AC-C3-01…10.

**User outcome:** The user knows about a material change on a saved corridor.

**Work:** Multiple corridor selection, direction, event types, minimum delay, planned overnight closures, comparison, source, review and history.

**Acceptance criteria:**

1. AC-C3-01…10 are met; a northbound filter excludes southbound and unrelated segment events.
2. OPEN→CLOSED, lane restrictions, roadworks/accidents and rescheduled closures are displayed correctly.
3. Repeated traffic records for one event are combined; reopening preserves history.
4. The 15-minute threshold is applied only to a valid delay; a missing delay does not suppress an explicit full closure.

**Verification:** End-to-end checks for the opposite direction, a planned date shift, no delay value, closure/reopening and duplicate language editions.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.


## F5 — Business scenarios

<a id="mv2-042"></a>

### MV2-042 — B2: SIMAP discovery and publication monitoring

**Status:** PLANNED · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071). **Requirements:** §15; AC-B2-02,05,06,11.

**User outcome:** Public procurement notices arrive as new and changed entities.

**Work:** Official SIMAP API/client registration, pages/cursors, publication IDs and tender dossier linking; authority/CPV/region/language/deadline/documents/Q&A. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Publications are not distributed before the source permits publication at 08:00; originals, commentary and the required notice remain distinct.
2. Access to public publications does not automatically grant access to restricted tender attachments; coverage of each field is explicit.
3. Corrections, cancellations, awards/status and multilingual publications are versioned without duplicate opportunities.
4. Backfill bounds and watermarks preserve late publications; prohibited documents are not retrieved through workarounds.

**Verification:** Contract/API fixtures for pagination, the publication gate clock, corrections and public versus restricted attachments.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-043"></a>

### MV2-043 — B2/B7/B8: Structured profiles and semantic candidate ranking

**Status:** PLANNED · **Priority:** P1 · **Owner:** Backend + AI · **Size:** L

**Dependencies:** [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-010](#mv2-010), [MV2-071](#mv2-071). **Requirements:** §§15.4,15.9,16.6,17.3,19.3,22.

**User outcome:** Business matching goes beyond a word in the title and is understandable to the user.

**Work:** Typed capability/brand/asset profiles, deterministic inclusion and exclusion rules; lexical candidates followed by bounded optional semantic assessment; match facets and unknown gaps.

**Acceptance criteria:**

1. A tender profile stores CPV/capabilities, regions/languages/exclusions, size and qualification constraints; the example score of 70 does not become an unvalidated default.
2. An asset profile has category/location/keywords/brands/price; UNKNOWN price does not produce a “within budget” result.
3. SEMANTIC_MATCH has a versioned score/model/evidence; the LLM cannot bypass hard exclusions.
4. A qualification absent from the profile is an unknown gap, not proven noncompliance. DONE means implementation, schema and bounded evaluation on training/validation data under a disabled semantic flag; independent promotion in MV2-051 is not a reverse dependency.

**Verification:** An independent structured/semantic match set, hard exclusions, unknown fields, profile revisions and preview parity.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-044"></a>

### MV2-044 — Versioned document sets and conditions

**Status:** PLANNED · **Priority:** P1 · **Owner:** Backend + Frontend · **Size:** L

**Dependencies:** [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-071](#mv2-071). **Requirements:** §§15.5,15.8,17.4,17.7,17.10.

**User outcome:** Changes to a file, requirement or Q&A remain visible after an earlier review.

**Work:** DocumentSetManifest: stable item ID, type, URL, hash, retrieval/version time and access status; add/replace/remove; link existing exact/legal diffs where applicable.

**Acceptance criteria:**

1. New Q&A, a changed file at the same URL, document removal/withdrawal and changed conditions produce distinct deltas.
2. List reordering or a changed signed URL does not create a false material update.
3. Historical document sets and changed requirements link to exact permitted snapshots/locators; a denied attachment is unavailable, not removed.
4. Failed OCR/parsing does not invent content; the UI offers official evidence and identifies incomplete information.

**Verification:** Gold fixtures for document addition/replacement/removal/reordering/403, deadline versus body diffs and historical views.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-045"></a>

### MV2-045 — B2: Tender discovery → review → material update

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-042](#mv2-042), [MV2-043](#mv2-043), [MV2-044](#mv2-044). **Requirements:** §15; AC-B2-01…12.

**User outcome:** A company chooses Bid/No-bid/Monitor and sees changes to the conditions.

**Work:** Tender profile wizard, discovery candidates, follow tender, explanations of matched capabilities and gaps, explicit deadline, Q&A/document changes and owner.

**Acceptance criteria:**

1. AC-B2-01…12 are met; both discovery and following/updates are available.
2. A deadline change from 20→27, required references from 3→5 and Q&A v3 reopen the earlier review with the same tender ID.
3. Irrelevant opportunities are suppressed; explanations of matches and gaps link to evidence and do not promise eligibility.
4. BID/NO_BID/MONITOR records an internal decision; it never submits a bid; the digest includes new opportunities and material updates.
5. Without permitted capture/versioning/diffing of the required documents and Q&A, AC-B2-08 and the relevant part of AC-B2-06 remain BLOCKED; metadata alone or an unavailable badge does not satisfy this case.

**Verification:** End-to-end profile→publication→review→3-field revision→reopen→digest, negative cases and an unavailable attachment.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-046"></a>

### MV2-046 — B7: Official trademark publications and register updates

**Status:** PLANNED · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071). **Requirements:** §16; AC-B7-02,06,08,10.

**User outcome:** Publications and registration versions are supported by source evidence.

**Work:** Official IPI/Swissreg API after terms and account approval; mark/owner/representative/classes/goods-services/application/publication/registration/status. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Automated access, retention and permitted in-app/email uses are approved; the search UI is not used as evidence of an API licence.
2. Application, publication and registration dates are not interchangeable; Swiss jurisdiction and rights coverage are explicit.
3. Owner/representative/goods-services/renewal/cancellation/status updates preserve the previous state.
4. Missing mark fields are not inferred; publication evidence has a stable official ID.

**Verification:** Official API contract fixtures, multilingual goods/services, status/owner corrections and a rights-policy test.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-047"></a>

### MV2-047 — B7: Exact, lexical and phonetic candidates

**Status:** PLANNED · **Priority:** P1 · **Owner:** Backend + AI/domain reviewer · **Size:** L

**Dependencies:** [MV2-043](#mv2-043), [MV2-046](#mv2-046). **Requirements:** §16.4–16.7; AC-B7-01,03,04,05,07.

**User outcome:** Similar names can be found with an explanation of the matching basis.

**Work:** Multiple-brand portfolio, optional word variants/owners, Unicode normalization, exact/near lexical/phonetic matching, and class and goods/services overlap.

**Acceptance criteria:**

1. ALMORA/ALMORA exact, ALMORE/ALMORIA lexical and phonetic cases are reproducible; normalization and version are recorded.
2. Goods/services overlap affects priority; the same class code alone does not prove similarity or conflict.
3. False positives are measured by language; thresholds are calibrated on training/validation data and then frozen. MV2-051 performs the held-out evaluation; held-out data is not used for tuning.
4. The result is a candidate for IP review; it is never confirmed infringement, even with a perfect score.

**Verification:** Independent exact/near/phonetic/goods-services cases, accents/transliterations and unrelated-class negative cases.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-048"></a>

### MV2-048 — B7: IP review, review deadlines and register changes

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-046](#mv2-046), [MV2-047](#mv2-047). **Requirements:** §16; AC-B7-01…12.

**User outcome:** A brand owner receives a candidate and a controlled review workflow.

**Work:** Portfolio wizard, candidate evidence, deadline context/rule, review/relevant/not relevant/monitor/escalate decision and register updates.

**Acceptance criteria:**

1. AC-B7-01…12 are met; a high-priority candidate is available in the Impact Inbox.
2. A calculated review deadline has a source date, an approved applicable rule/version, a calculation trace and a verification warning; an unknown rule makes the deadline unavailable. days_remaining is displayed using the same timezone and rule revision.
3. A material change to owner/status/goods-services reopens the review while preserving the previous decision.
4. In v2, Send to counsel marks the item or prepares a permitted evidence export; external sending requires a separate user action.

**Verification:** End-to-end multiple-brand→candidate→review→register update, missing date/rule, deadline changes and export rights.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-049"></a>

### MV2-049 — B8: Official Ticino auctions

**Status:** PLANNED · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071). **Requirements:** §17.3–17.7,17.11; AC-B8-02,05,06,11.

**User outcome:** An official opportunity has verified fields and a source.

**Work:** Official Ticino auction source contract; real estate/vehicles/equipment capability; auction/lot IDs, dates, documents, conditions, price type and status. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Automated access and reuse are confirmed; HTML availability is not presented as an API licence.
2. Current bid, estimate and starting/minimum price are stored as distinct types; missing bid_count/price/end is UNKNOWN.
3. Auctions and lots are not merged; cancellation/postponement/conditions/document updates are versioned.
4. Category coverage in Ticino is verified; unsupported categories/areas are clearly shown, without an unofficial fallback.

**Verification:** A bounded official sample, multiple-lot/unknown-field/cancellation fixtures and parser drift tests.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-050"></a>

### MV2-050 — B8: Auction profiles, price limits and ending-soon alerts

**Status:** PLANNED · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-008](#mv2-008), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-043](#mv2-043), [MV2-044](#mv2-044), [MV2-049](#mv2-049). **Requirements:** §17; AC-B8-01…12.

**User outcome:** A buyer sees relevant assets and important auction changes.

**Work:** Category/location/keywords/brand/budget, new matches, price crossings, end-time shifts, documents/conditions and cancellation; Bid/No-bid/Inspect/Monitor.

**Acceptance criteria:**

1. AC-B8-01…12 are met; supported category/location/keyword filters work; a new canton adapter does not change the domain workflow. Extensibility is demonstrated with a second canton adapter conformance fixture; no live rollout to other cantons is claimed.
2. CHF8500→12700 with a limit of 12000 produces a crossing; individual bid increments do not generate repeated alerts without opt-in.
3. Ending-soon alerts use a configurable number of hours before the end; 24h is an example. An end-time change recalculates the reminder; cancelled auctions or an unknown end time do not trigger it.
4. UNKNOWN price does not pass the budget filter as zero; the Bid action does not place a bid; history is available.
5. A user can stop or continue following a specific auction without stopping discovery for the entire profile; historical decisions remain.

**Verification:** End-to-end new auction→inspect→price/conditions/end change→reminder→cancel, unknown fields and an adapter-swap fixture.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.


## F6 — Quality evidence, pilot and release

<a id="mv2-051"></a>

### MV2-051 — Independent matching and local AI evaluation

**Status:** PLANNED · **Priority:** P0 · **Owner:** AI + Independent domain reviewers · **Size:** L

**Dependencies:** [MV2-023](#mv2-023), [MV2-043](#mv2-043), [MV2-047](#mv2-047). **Requirements:** §§7,22,31,34; legacy HL-064,089,091–094,100.

**User outcome:** Semantic matching does not earn trust merely by returning valid JSON.

**Work:** Independent gold set, held-out partition, evaluation by case/language/negative example; approvals for local model/task/locale profiles; semantic benchmark before feature promotion.

**Acceptance criteria:**

1. At least 200 independently labelled match/nonmatch pairs, with ≥50 for each of B2/B7/B8; the held-out split, disagreements and adjudication are recorded.
2. Precision and recall are measured per case for calibrated business candidate ranking; proposed gates are ≥85% precision and ≥90% recall, with no claim of legal conflict accuracy.
3. 100% of checked citations refer to a permitted snapshot/field; there are zero invented facts/deadlines in the release-critical fixture set.
4. Without an approved profile, semantic mode is unavailable or extractive; deterministic results are not blocked; a measured score is not presented as a probability without calibration.

**Verification:** A reproducible offline benchmark with report/hash/config; independent review by people who did not author the same expected answers.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-052"></a>

### MV2-052 — Operational metrics, degraded mode and source recovery

**Status:** PLANNED · **Priority:** P0 · **Owner:** Operations + Backend · **Size:** M

**Dependencies:** [MV2-011](#mv2-011), [MV2-012](#mv2-012), [MV2-025](#mv2-025). **Requirements:** §§23,28,33.11–12,34; legacy HL-094,099.

**User outcome:** The administrator can see missing data and the reason for a delay.

**Work:** Per-source ingestion/matching/delivery lag, last good state, error taxonomy and coverage gaps; alerts for actionable source failures; access-renewal reminders.

**Acceptance criteria:**

1. Charts distinguish source publication lag, ingestion lag, processing lag and channel delivery lag; zero does not replace unknown.
2. When data is stale or a licence expires, the UI and jobs follow the policy; recovery backfills gaps without flooding users with historical alerts.
3. AI utilization/budget/reuse and fairness are measured; diagnostics have a short timeout and do not delay the response.
4. Logs contain no secrets, Home coordinates or complete user prompts; correlated job IDs are sufficient for support.

**Verification:** Failure injection for source/queue/provider/email/DB telemetry and regression checks for bounded diagnostic locking.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-053"></a>

### MV2-053 — Personal-location privacy and access control

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Security reviewer · **Size:** M

**Dependencies:** [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-023](#mv2-023). **Requirements:** §§5,27,31; inherited personal/organization access contract.

**User outcome:** Private Home locations, commutes and business interests are not exposed to another workspace.

**Work:** Consent and data minimization, owner-only personal scope, retention/deletion/export of user configuration, cache isolation and role checks; secrets stay in the current provider store.

**Acceptance criteria:**

1. Session, CSRF and current-role checks cover new endpoints, jobs, exports and evidence; negative IDOR tests pass.
2. Personal coordinate precision is limited to what matching needs; the public corpus does not contain private subject definitions.
3. Deleting an account or monitor applies the private-state/decision policy without destroying shared official history used by other workspaces.
4. Cloud AI is disabled by default; explicit opt-in shows which data is transmitted, with no hidden location/profile disclosure.

**Verification:** API privacy-boundary tests, deletion/export workflow, revocation during a job and browser workspace switching.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-054"></a>

### MV2-054 — Single-server capacity and queues with different priorities

**Status:** PLANNED · **Priority:** P0 · **Owner:** Operations + Backend + AI · **Size:** L

**Dependencies:** [MV2-011](#mv2-011), [MV2-014](#mv2-014), [MV2-043](#mv2-043), [MV2-052](#mv2-052). **Requirements:** §§22,28,34; legacy HL-032,048,049,084,099.

**User outcome:** Realtime monitoring is not displaced by document ingestion or LLM work.

**Work:** Measured workload on the target i7/32GB/2×GTX1080 hardware; independent deterministic/source/matching/AI queues; data growth and database indexes; no infrastructure rewrite without evidence.

**Acceptance criteria:**

1. Reproduce the inherited gate: 100 accounts, 300 reads, 10–20 concurrent users, 20 AI jobs, parallel synchronization, restart and recovery. Preserve the original matrix of 10 organizations, a 100k legal corpus/20 readers and 50-run assistant stability.
2. Add the proposed v2 workload: 1000 active subjects, 9 active templates and 1M observation rows; publish the budget model and actual measurements.
3. Preserve inherited thresholds: legacy reads p95≤500ms and enqueue≤1s on the corresponding baseline workload. Measure the proposed new history/time-series endpoint threshold p95≤2s and post-ingestion deterministic readiness≤30s separately; existing budgets are not weakened.
4. GPU OOM, degraded mode or offline operation does not break active C1/C2/C3/C5/C6/C7; an 8B default is allowed only after the target-hardware gate; pgvector/HA requires evidence of need.

**Verification:** Load/restart benchmark on the target host, otherwise mark BLOCKED; a synthetic workstation report does not satisfy the gate.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-055"></a>

### MV2-055 — History storage, retention and permitted exports

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Operations · **Size:** M

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-020](#mv2-020), [MV2-044](#mv2-044). **Requirements:** §§27,29–30,38.

**User outcome:** History remains verifiable while data volume is controlled.

**Work:** Retention by source/data class, raw/normalized states, compaction/downsampling policy, evidence pinning for delivered revisions and export manifests.

**Acceptance criteria:**

1. Evidence for delivered developments and decisions is not lost through telemetry compaction; the old/new states required for diffs remain available in a permitted form.
2. A retention/rights conflict requires a durable permitted raw or normalized snapshot with provenance sufficient for historical comparison. An expiry notice or link does not replace evidence; if a sufficient form cannot be stored, G(case) and the affected AC remain BLOCKED.
3. ASTRA raw-data export/API redistribution is blocked, SIMAP originals and commentary are separated, and IP permissions are enforced.
4. History exports reproduce provenance/state/rule/decision revisions; personal data is available only within the authorized scope.

**Verification:** Retention time travel, restoration of archived evidence, prohibited raw-export checks and negative cross-tenant export tests.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-056"></a>

### MV2-056 — Migration, compatibility and rollback rehearsal

**Status:** PLANNED · **Priority:** P0 · **Owner:** Backend + Operations + QA · **Size:** L

**Dependencies:** [MV2-001](#mv2-001), [MV2-053](#mv2-053), [MV2-055](#mv2-055), [MV2-060](#mv2-060). **Requirements:** §§1,26–27,30; legacy HL-048,049,098.

**User outcome:** The transition to v2 preserves existing users and MVP evidence.

**Work:** Additive Alembic migrations, resumable bridge backfill, dry runs/checkpoints, dual reads/shadow comparison and feature-flag rollout; backup→restore in an isolated environment.

**Acceptance criteria:**

1. Organization/member/session/watch/topic IDs, review/unread/preferences, source packs, artifact hashes and analyses/citations are preserved before and after migration.
2. Repeated migration, interruption and partial backfill do not duplicate records or notifications.
3. Legacy API/URLs/Ask/Today/Basel journey/Page guide work; a shadow-parity report records deliberate differences.
4. Rollback flags, compatible code/schema and verified database restore are rehearsed; the MVP tag without a corresponding backup is not considered a database rollback.

**Verification:** Rehearsal on a sanitized snapshot shaped like production, row/hash counts, restart/resume, rollback and a regression report.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-057"></a>

### MV2-057 — Executable checks for 116 active AC and adversarial regression

**Status:** PLANNED · **Priority:** P0 · **Owner:** QA + Domain reviewers · **Size:** L

**Dependencies:** [MV2-029](#mv2-029), [MV2-031](#mv2-031), [MV2-033](#mv2-033), [MV2-035](#mv2-035), [MV2-036](#mv2-036), [MV2-039](#mv2-039), [MV2-041](#mv2-041), [MV2-045](#mv2-045), [MV2-048](#mv2-048), [MV2-050](#mv2-050), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-053](#mv2-053), [MV2-056](#mv2-056), [MV2-068](#mv2-068), [MV2-071](#mv2-071). **Requirements:** Active AC-CORE/C1/C2/C3/C5/C6/C7/B2/B7/B8; AC-C4 deferred; §§29–34.

**User outcome:** v2 completeness is demonstrated by concrete scenarios rather than commit counts.

**Work:** AC-linked integration/browser tests, versioned official fixtures with licence/provenance; positive/negative, material/nonmaterial, history and role cases for each template.

**Acceptance criteria:**

1. Each of the 116 active source AC (20 CORE, 60 C1/C2/C3/C5/C6/C7, 36 B2/B7/B8) has an executable check or reviewer protocol and an evidence reference; active supplemental coverage is also verified. The 10 AC-C4 are preserved as DEFERRED and are not a release gate; C4 tests are outside current work.
2. Replaying the same batch twice, restart, out-of-order data, duplicate translations, 429, source disappearance and an offline model do not violate invariants.
3. Zero critical defects: cross-tenant leaks, false official all-clear, invented numerical/legal facts, duplicate internal delivery or lost reviews.
4. Tests do not merely repeat the implementation; gold fixtures are independent, and the live freshness contract is verified separately.
5. Persistent absence of a required source capability (forecast, delay, documents/Q&A or deadline) leaves the affected AC open. UNKNOWN is correct behavior for an individual record, not a substitute for a required capability of the entire template.

**Verification:** The full suite, recordings of all nine active domain demos, contract reports and independent evidence spot-checks.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-058"></a>

### MV2-058 — Measured B2C/B2B pilot

**Status:** PLANNED · **Priority:** P0 · **Owner:** Product + QA + Operations · **Size:** L

**Dependencies:** [MV2-002](#mv2-002), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-054](#mv2-054), [MV2-057](#mv2-057), [MV2-071](#mv2-071). **Requirements:** §34; legacy HL-088,090,101.

**User outcome:** Evidence confirms that people understand changes and return to monitoring.

**Work:** Proposed four-week pilot: ≥10 B2C participants and ≥5 organizations; representative coverage of all nine active cases; C4 is excluded from the pilot; supplement sparse events with labelled historical replay. This is the overall v2 pilot after the first Pollen Watch user testing; it is not a prerequisite for MV2-071.

**Acceptance criteria:**

1. For each active template, record the eligible sample, precision/materiality/duplicates, explanation helpfulness, decisions and time to understand.
2. Proposed targets: delivered relevance≥90%, material-change precision≥90%, understandable why≥90%, duplicate rate<1%, first value≤5min of setup and median understanding time≤60s.
3. Measure actionability without a minimum that forces invented actions; taking no action can be a useful decision.
4. An insufficient sample or blocked source is explicit incomplete evidence; replay is not presented as a live pilot, and targets are not presented as achieved results.

**Verification:** An anonymized pilot report with denominators, confidence/limitations, defects and an expand/fix/hold decision.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-059"></a>

### MV2-059 — Helvetic Lens Monitoring v2.0 acceptance and release

**Status:** PLANNED · **Priority:** P0 · **Owner:** Release owner + Product + Operations · **Size:** M

**Dependencies:** [MV2-025](#mv2-025), [MV2-052](#mv2-052), [MV2-054](#mv2-054), [MV2-055](#mv2-055), [MV2-056](#mv2-056), [MV2-057](#mv2-057), [MV2-058](#mv2-058). **Requirements:** §§33,39–40; v2.0 scope after the user decision to defer C4.

**User outcome:** v2 can be restored, verified and supported.

**Work:** Release checklist, immutable source/tag, manifest/checksums/build versions, migrations/backup/restore, source credential/licence-renewal runbook and release notes.

**Acceptance criteria:**

1. All 62 required backlog tasks are DONE (MV2-059 closes with the final release evidence), all 116 active AC are accepted, and all 9 active templates have permitted sources and end-to-end evidence. The 9 DEFERRED tasks, including MV2-026/027/061, and the 10 AC-C4 are excluded from acceptance.
2. None of the nine required cases is omitted to obtain the 2.0 label; partial milestones are labelled preview/limited pilot.
3. Fresh installation and upgrade, rollback restore, supported languages and source/export policies are verified; no critical defects remain.
4. The MVP tag is unchanged; production rollout is a separate, explicitly approved operation with health and rollback checks.

**Verification:** Independent go/no-go checklist, release-artifact restore/build verification, and post-deployment checks only after deployment authorization.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.


## Deferred scope — excluded from v2.0

<a id="mv2-026"></a>

### MV2-026 — Possible future implementation: C4 official customs-rate connector

**Status:** DEFERRED — possible future implementation; do not start development · **Priority:** P2 · **Owner:** Integration · **Size:** M

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011). **Requirements:** §11; AC-C4-02,03,07,09; user decision 2026-09-10: outside v2.0 development.

**User outcome:** Possible future outcome: retain the official customs rate itself.

**Work:** Future possibility only. Do not undertake C4 discovery, integration, UI, licensing or tests in current development. Reactivation requires a new explicit user decision on scope; obtaining access or completing v2.0 does not activate the task by itself. After that decision: obtain/document BAZG/SIX reuse rights and verify XML, currency unit/basis, effective day and correction/weekend semantics.

**Acceptance criteria for possible future implementation:**

1. Written confirmation or a valid licence permits the intended use; production ingestion/distribution is not activated before this.
2. The rate retains currency, nominal units, CHF basis, effective date and source; JPY/100 is not interpreted as JPY/1.
3. A weekend/missing publication does not create a zero rate; date corrections are versioned.
4. No market FX fallback is labelled as customs.

**Verification after returning to scope:** Licensed sample replay and 1/100-unit fixtures; source-contract report.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-027"></a>

### MV2-027 — Possible future implementation: C4 currency, thresholds, history and digest

**Status:** DEFERRED — possible future implementation; do not start development · **Priority:** P2 · **Owner:** Frontend + Backend · **Size:** M

**Dependencies:** [MV2-008](#mv2-008), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-022](#mv2-022), [MV2-026](#mv2-026). **Requirements:** §11; AC-C4-01…10; user decision 2026-09-10: outside v2.0 development.

**User outcome:** Possible future outcome: the user receives meaningful changes to the selected rate.

**Work:** Future possibility only. Do not undertake C4 discovery, integration, UI, licensing or tests in current development. Reactivation requires a new explicit user decision on scope; obtaining access or completing v2.0 does not activate the task by itself. After that decision: currency selector; daily/weekly/absolute crossing/every-change rules; previous/current/delta/chart/digest. The purchase calculator is separate in MV2-061.

**Acceptance criteria for possible future implementation:**

1. Satisfy AC-C4-01…10; 0.9412→0.9547 produces +1.43434…%, displayed as +1.43% with the exact underlying value retained.
2. Strictly greater than 1% does not trigger at exactly 1%; explain the weekly baseline and a missing baseline.
3. Evaluate the threshold using unrounded Decimal; every-change requires explicit opt-in; history and evidence are accessible.
4. The template is fully useful without a purchase value.

**Verification after returning to scope:** End-to-end licensed source→state→rule→Today→digest; below/exact/above threshold and weekend/correction fixtures.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-061"></a>

### MV2-061 — Possible future feature: Customs purchase calculator

**Status:** DEFERRED — possible future feature; do not take into development · **Priority:** P2 · **Owner:** Product + Backend · **Size:** S

**Dependencies:** [MV2-027](#mv2-027). **Requirements:** §11.8 — explicitly future; user decision 2026-09-10: outside v2.0 development.

**User outcome:** Possible future outcome: estimate the change in CHF valuation for a specified purchase.

**Work:** A future possibility only. Do not perform C4 discovery, integration, UI, licensing or tests in current development. Reintroduction requires a new explicit user decision on scope; obtaining access or completing v2.0 does not activate the task on its own. After that decision: optional purchase amount/currency, official rate basis and deterministic delta; this is not a general customs-duty/tax calculation.

**Acceptance criteria for possible future implementation:**

1. Source rights permit the calculation; the optional amount is not required for the primary exchange-rate watch.
2. The previous/current CHF basis and delta explain the rate, nominal units and rounding; they make no tax-liability claim.

**Verification after returning to scope:** Decimal/unit calculation and optional-form checks.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-062"></a>

### MV2-062 — After v2.0: Additional auction cantons and extended tender workflow

**Status:** DEFERRED · **Priority:** P2 · **Owner:** Product + Integration · **Size:** L

**Dependencies:** [MV2-045](#mv2-045), [MV2-050](#mv2-050). **Requirements:** §§15.10,17.11 — explicitly future.

**User outcome:** Coverage expands without requiring a second architecture.

**Work:** Additional cantonal source packs after a separate source gate; QUALIFY/SUBMITTED/CLOSED/AWARDED/NOT_AWARDED when justified by confirmed need.

**Acceptance criteria for possible future implementation:**

1. Each source has its own rights/coverage dossier; this is not an automatic promise of national coverage.
2. New decision states do not change historical records or submit bids; priority is updated only through the canonical backlog.

**Verification after returning to scope:** Adapter conformance and backward-compatible decision tests.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-063"></a>

### MV2-063 — Conditional: pgvector after a demonstrated recall gap

**Status:** DEFERRED · **Priority:** P2 · **Owner:** Product + Architect · **Size:** M

**Dependencies:** [MV2-051](#mv2-051), [MV2-054](#mv2-054). **Requirements:** legacy HL-024.

**User outcome:** A deferred commitment is preserved without expanding the current release scope.

**Work:** Preserve HL-024: first measure direct-context retrieval; add pgvector to the existing PostgreSQL only if improvement is demonstrated.

**Acceptance criteria for possible future implementation:**

1. A vector database is not a v2 prerequisite; the benchmark compares citations, recall, latency and cost.
2. Exact-version context and a direct fallback are preserved.

**Verification after returning to scope:** A separate evidence report when the activation condition is met; implementation starts only after the decision and priority are recorded in this backlog.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-064"></a>

### MV2-064 — Conditional: Relationship graph after a usefulness test

**Status:** DEFERRED · **Priority:** P2 · **Owner:** Product + Architect · **Size:** M

**Dependencies:** [MV2-021](#mv2-021), [MV2-036](#mv2-036), [MV2-058](#mv2-058). **Requirements:** legacy HL-053.

**User outcome:** A deferred commitment is preserved without expanding the current release scope.

**Work:** Preserve HL-053: a list-versus-graph user experiment; existing relationship review remains available.

**Acceptance criteria for possible future implementation:**

1. A no-benefit result ends the experiment without requiring a graph to be built.
2. The graph does not replace the evidence list or change the status of unconfirmed relationships.

**Verification after returning to scope:** A separate evidence report when the activation condition is met; implementation starts only after the decision and priority are recorded in this backlog.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-065"></a>

### MV2-065 — Conditional: Multiple servers / HA based on measured need

**Status:** DEFERRED · **Priority:** P2 · **Owner:** Product + Architect · **Size:** M

**Dependencies:** [MV2-054](#mv2-054), [MV2-056](#mv2-056). **Requirements:** legacy HL-056.

**User outcome:** A deferred commitment is preserved without expanding the current release scope.

**Work:** Preserve HL-056: begin scaling/HA design only in response to a documented bottleneck or recovery requirement.

**Acceptance criteria for possible future implementation:**

1. Measured necessity and a resource plan exist; Kubernetes/microservices are not added merely to support templates.
2. Job identity, storage, tenancy, backup/restore and Git host contracts are preserved.

**Verification after returning to scope:** A separate evidence report when the activation condition is met; implementation starts only after the decision and priority are recorded in this backlog.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-066"></a>

### MV2-066 — Conditional: The next two cantonal regulatory packs

**Status:** DEFERRED · **Priority:** P2 · **Owner:** Product + Architect · **Size:** M

**Dependencies:** [MV2-068](#mv2-068). **Requirements:** legacy HL-081.

**User outcome:** A deferred commitment is preserved without expanding the current release scope.

**Work:** Preserve HL-081: two separately named and verified regulatory packs after Basel; these are distinct from C1 coverage and B8 Ticino.

**Acceptance criteria for possible future implementation:**

1. Each pack has independent evidence for rights, parser behavior, drift, localization, history and acceptance.
2. Completion of new-domain connectors alone does not activate this task automatically.

**Verification after returning to scope:** A separate evidence report when the activation condition is met; implementation starts only after the decision and priority are recorded in this backlog.

**Execution evidence:** Deferred; not a current work item or release gate.

<a id="mv2-067"></a>

### MV2-067 — Beyond the ten source use cases: Opt-in public-discourse pilot

**Status:** DEFERRED · **Priority:** P2 · **Owner:** Product + Architect · **Size:** M

**Dependencies:** [MV2-058](#mv2-058). **Requirements:** legacy HL-082.

**User outcome:** A deferred commitment is preserved without expanding the current release scope.

**Work:** Preserve HL-082 outside v2.0: at most two commentary sources after a separate scope-change decision.

**Acceptance criteria for possible future implementation:**

1. Separate gates for source rights, expiry, diversity, noise, usefulness, corrections and removal.
2. Unofficial commentary is never mixed with authoritative facts; alerts require explicit organization opt-in.

**Verification after returning to scope:** A separate evidence report when the activation condition is met; implementation starts only after the decision and priority are recorded in this backlog.

**Execution evidence:** Deferred; not a current work item or release gate.

## Traceability and plan changes

[126 preserved AC: 116 active + 10 deferred; 79 supplemental requirements](docs/monitoring-v2/REQUIREMENTS_TRACEABILITY.md) · [Legacy disposition](docs/monitoring-v2/LEGACY_DISPOSITION.md) · [Architecture](docs/monitoring-v2/ARCHITECTURE.md) · [Official sources](docs/monitoring-v2/SOURCE_FEASIBILITY.md).

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-09-10 | Complete plan for ten scenarios, source gates, generic extension, MVP compatibility, 126 AC/79 supplemental requirements and 35 legacy dispositions; new features were not implemented |
| 1.1 | 2026-09-10 | By user decision, C4 customs rates became a possible future implementation, excluded from current development. MV2-026/027 moved to DEFERRED; MV2-061 remained deferred. 9 active scenarios, 59 required/9 deferred tasks, 116 active/10 deferred AC. Removed C4 from source gates, UI, pilot and release dependencies; preserved the original requirements |
| 1.2 | 2026-09-10 | Pollen Watch became the first complete delivery for real-user testing. Added MV2-069/070/071, explicit C5 subtasks and an independent early gate; MV2-030/031 became P0 with dependencies on C5 contracts. 62 required/9 deferred tasks; the remaining nine-case scope and 116 active AC were preserved |
| 1.3 | 2026-09-10 | Translated the backlog and supporting planning documents into English and added a line-preserving English reading edition of the source specification. Scope, IDs, dependencies, priorities and acceptance obligations are unchanged. The user explicitly authorized integration and push to main |
| 1.4 | 2026-09-10 | Organized three activities into two product channels. Main-product/hackathon changes use main → HappySnowman → helveticlens.ch; Monitoring v2 uses codex/HappyDucky02/monitoring-v2 → HappyDucky02 → monitoring.helveticlens.ch. Main retains a planning snapshot while this branch owns the active backlog. Support is parked; the original 71 task definitions remain unchanged |
| 1.5 | 2026-09-10 | Added MV2-072 for the user-selected dedicated Monitoring branch, Windows host and hostname. 63 required/9 deferred tasks; original product task details and Pollen Watch order preserved |
| 1.6 | 2026-09-10 | Added MV2-073 for user-requested backlog progress on the deployment page: exact latest/deployed Git snapshots, required-only completion and the Pollen Watch path. 73 tasks: 64 required and 9 deferred. Product scenarios and original task definitions remain unchanged. Updated MV2-072 evidence to SMTP verified and bootstrap IN PROGRESS; no live acceptance claimed |


**Integration history:** MV2-031 shared Monitoring code with main on 12 September. The later single-agent instruction makes main the sole active development and backlog branch; instance isolation remains mandatory.
