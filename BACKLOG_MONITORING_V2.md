# Helvetic Lens Monitoring v2 — active implementation backlog

**Plan version:** 1.6 · **Date:** 10 September 2026 · **Code baseline:** `7109a2891f9c99e53572008cc7c1a86001792a57`

**Status:** implementation and acceptance tracking; individual task evidence distinguishes implemented, tested and deployed behavior.

**Scope:** 9 required scenarios, 64 required tasks, 9 deferred tasks. 116 active acceptance criteria (AC); 10 AC-C4 criteria retained as deferred.

**Principle:** authoritative source → material change → personal relevance → evidence → user decision.

## Development and deployment

The main-branch copy of this file is the sole active Monitoring backlog. The user's
12 September 2026 instruction replaces multi-computer, host-alias, task-branch and
separate Monitoring integration rules: **one agent, complete features, commit and
push main**. Only `helveticlens.ch` on HappySnowman is active. The user retired
the separate Monitoring site; do not recreate its deployment. Preserve retained
private data and source approvals.
See [the development cycle](docs/DEVELOPMENT.md) and [release evidence](docs/monitoring-v2/DEPLOYMENT_STATUS.md).

## How to use this backlog

**Publication instruction, 13 September 2026:** The owner requested an immediate
main publication of all implemented directions and enabled, visible sections,
followed by continued development. The integrated release includes public Tender
Watch and the implemented Commute, Road, Hazard and Trademark workflows, with
source readiness remaining explicit. All affected tasks retain their recorded
IN PROGRESS/VERIFYING status; B8 remains PLANNED and C4 remains DEFERRED.
See [release scope and checks](docs/monitoring-v2/evidence/2026-09-13-integrated-publication.md).
Earlier dated statements about uncommitted code or disabled production defaults
describe the checkpoints at which they were written, not this release's defaults.

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
| G(C1) | Native Swiss MeteoAlarm wind/thunderstorm source implemented with reviewed public terms and geography; live warning/pilot and other hazard coverage remain open | Integration, MV2-028/029: verify activation and remaining source coverage |
| G(B8) | Official pages exist; supported APIs/automated reuse have not been established | Integration, MV2-049: supported channel and permitted monitoring contract |
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
blockers. The later whole-feature and main-only instruction supersedes technical
slice publication: see [the current development cycle](docs/DEVELOPMENT.md).

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

22 September production verification: `1890d66` completed all twelve deployment
stages and public readiness. Full QA passed 5,075 tests / 18 skips in 1h18m23s,
33.14% less elapsed time than the prior successful suite on this host. All 55
pilot watches and 15 enabled legal streams passed live checks; five comparisons,
three Ask examples, 30 relation reports and tenant/viewer boundaries were verified.
Native daily freshness, SIMAP cycle gaps and external source gates stay explicit.
See [production evidence](docs/BASELTECH_PILOT_VERIFICATION.md). MV2-052 remains
IN PROGRESS for its broader gates; these demo accounts do not complete MV2-058,
which remains PLANNED. C4 remains DEFERRED.

22 September saved-citation navigation recovery: the live AsylG answer quotes
Article 66 correctly, but its old passage ID also exists in the newer version
under Article 63. Scoped MV2-052 work must resolve comparison and AI-history
citations by both immutable version and passage, retaining exact evidence links
when no unambiguous in-comparison target exists. Dependencies are the existing
comparison payload and citation URLs; no source access or AI rerun is required.
Acceptance: colliding IDs on both sides, unrelated/missing versions and passages,
history behavior, build checks and the real saved AsylG/IDG browser replay.
MV2-052 remains IN PROGRESS; broader operational and human gates stay open.

22 September AI-configuration release recovery: the full gate exposed interest-
brief configuration tests whose synthetic client uses a reviewed capability
registry while the fixture's environment resolver still sees the default registry.
The reproduced failure occurs before the intended runtime/edit hook. Align only
that fixture's deployment-owned registry paths, preserving saved public settings,
real configuration fencing and capability revocation. Acceptance: complete
interest/configuration/reader/job regressions, relation freshness checks and exact
API Ruff. MV2-052 remains IN PROGRESS until the normal full gate and activation.
All 390 related checks passed, with five existing environment-dependent skips,
in 686 seconds. Exact API Ruff passed. All eleven reproduced configuration cases
are included; no production policy or test selection was weakened.

22 September SIMAP pilot recovery: scoped MV2-052 work repairs the public IWB
abandonment record rejected by lot projection. The official SIMAP 1.5.1 schema
uses `abandonedLot` for a specific cancelled lot. Preserve that exact identity,
source locator and original hash; reject conflicting scope or reference IDs.
Do not borrow procurement/geography from the project or reopen a cancelled lot.
Dependencies are the existing public collector, retention and tenant contracts.
Acceptance requires the real source replay, malformed-scope negatives and a
durable collector regression with unchanged sibling lots and replay behavior.
The four IT gaps reproduce the same contract: three specific lots and one
explicit whole-project abandonment (`abandonedLot: null`). For the latter,
update only existing scoped dossier identities; do not create inferred lots.
Other pilot collection gaps must be diagnosed before claiming complete coverage;
authenticated documents and Q&A remain separate source-access gates. MV2-052
remains IN PROGRESS pending normal deployment and production verification.

All 269 SIMAP/tender and required backlog checks passed; the final focused
malformed-scope/collector/backlog selection passed 37 checks. Read-only replay of
all five exact public originals succeeded. Exact API Ruff passed. These results
do not imply activated production recovery or authenticated document access.

23 September test-policy scope (MV2-052 / MV2-057): the owner requests faster,
smaller routine release checks, separate platform smoke / functional / integration
suites, and an explicit emergency deployment without tests. Implement a reviewed
suite inventory, bounded parallel execution, standard and full release profiles,
and a one-invocation hotfix pinned to the fetched main SHA with a recorded reason.
Unknown tests stay in integration; retain the complete regression inventory.
Dependencies are the existing isolated QA runner, release lock, backup/rollback,
read-only administrator journal and immutable releases. No source activation is
needed. Acceptance: suite coverage/disjointness, real smoke/functional results,
bounded parallel integration evidence, failed-check blocking, exact-SHA rejection,
honest skipped-test history, and retained build/backup/readiness/rollback behavior.
Both parent tasks remain IN PROGRESS; this supersedes the older full-suite-on-
every-release policy only for this user-requested change.
Local verification: 726 standard checks passed in 35.59 seconds, 177 affected
controller/migration/data/backlog checks passed, and 70 browser checkpoints
covered five languages and both widths. All 5,119 existing cases are retained;
the 4,420-case integration tier is separate. [Policy and measured evidence](docs/TESTING.md)
distinguish local results from production activation and unmeasured full-suite time.

21 September release-test performance follow-up: investigate the measured
1h57m complete API gate without reducing its test selection. Profile repeated
HTTP-fixture setup and reuse a session-local, empty SQLite schema created by the
real migration chain, copying it into each test's private temporary directory.
Keep ordinary application initialization and dedicated migration tests unchanged.
Acceptance includes fresh-copy isolation, foreign-key enforcement, migration
round trips, representative HTTP/identity regressions and comparable timings.
This is scoped MV2-052 release recovery; full-gate activation remains separate.
The user explicitly authorized stopping the obsolete 8993ce1 check. Only its
verified isolated QA container was stopped; the normal e66f272 run continues.
Its retained output also exposed an offline-digest fixture that expects an
assessed medium-severity result without the required relation capability grant.
Use the existing explicitly approved synthetic fixture only for that recovery
case, retain unapproved-evidence cases, and run the complete related digest tests.
The unchanged 54-case HTTP/identity selection passed in 95.97 seconds before
schema reuse and 50.98 seconds after. Fifteen isolation, lifecycle, migration,
retained-history and backlog checks passed. Full-suite speed remains unverified.
All 204 related digest/runtime/evidence checks then passed, with one existing
skip; the assessed offline-recovery fixture is corrected. Exact API Ruff passed.

21 September BaselTech / Ukraine pilot recovery: scoped MV2-052 work verifies
the existing legal connectors and live scenario readiness before populating two
isolated demonstration workspaces. Basel-Stadt null publisher links must retain
explicit metadata-only evidence without blocking valid records; Fedlex must fetch
the exact official filestore artifact and avoid consultation query multiplication.
Regression checks cover provenance, malicious URLs, replay and preserved limits.
Existing public source contracts and tenant roles are dependencies. No source
permission or unavailable scenario is invented, and broader pilot acceptance stays
open. See the task detail and `docs/BASELTECH_PILOT_VERIFICATION.md`.
The explicit Basel/Bern request also includes bounded native resolution of a
single LexWork law URL to its current official PDF, plus exact historical URLs.
This is direct document monitoring, not the deferred national/cantonal pack work.
The same pilot verifies complete SEM FAQ extraction: an explicit main-content
container must include sibling answers instead of selecting the first embedded
article. Tests preserve navigation exclusion and detect edits in later answers.
Direct Fedlex watches must also retain the requested language and pinned date;
existing work-wide records remain readable without being reused for another
language or edition. The shared regulatory-work identity remains unchanged.
The same recovery reconciles the accepted `www.fedlex.admin.ch` host with shared
record assignment and reuses existing tenant-private editions without disclosure.
Small-context AI requests must measure the actual batch count before admission;
excess change units stay in the exact diff with explicitly limited AI coverage.
Current/history cantonal scans must consume the resolver's verified publisher
identity; ordinary FAQ URL continuity must not be confused with legal-work proof.
The requested pilot also needs explicit daily direct-document checks: opt-in per
watch, existing records off, bounded durable scans, pause/revocation checks, and
visible next-check state. This does not complete the broader MV2-060 bridge.
Before comparing HTML captured by an older parser, derive a separately retained
extraction from the saved original using the current parser. Preserve the old
evidence and provenance; an extractor upgrade alone must not become a legal
change, while concurrent source edits must still be detected. Missing or damaged
originals must stop the comparison. Cantonal acts also need a jurisdiction-neutral
document-type label in all five interface languages.
For newly acquired Ukrainian guidance, a German-language website directory must
not override predominantly Ukrainian document text. Retain explicit publisher
language metadata as authoritative, use conservative bounded script evidence,
and display the Ukrainian source-language label without adding a new UI locale.
Daily-watch API, migration, frontend and local browser checks passed; production
scheduled execution remains pending activation, with MV2-052 IN PROGRESS.
Native catalogue comparisons must also reject HTML pairs acquired with different
extractor revisions. Retain their immutable evidence and existing comparison
history; do not interpret parser completeness changes as legal amendments.
Verify that new selections fail without writes and stale selections cannot feed
AI or the comparison page. Same-parser comparisons remain available.
The live Basel viewer scenario exposed a POST transport mismatch for the purely
extractive native evidence reader. Permit that reader under existing source and
ownership checks, retaining CSRF and all write/model restrictions. Exercise both
administrator and viewer roles through real HTTP before release.
The live IDG question about § 39 must retrieve that provision instead of reusing
an unrelated general report. Correct legal-unit routing and exact provision
selection, invalidate the old Ask cache revision, and retain partial coverage
when reusing a limited report. Verify the actual saved before/after evidence;
the independent interpretation-quality gate remains unchanged.
The specific-provision implementation and retained-IDG preflight passed locally;
the deployed question replay remains pending. MV2-052 stays IN PROGRESS.
The real Apertus replay also exposed a four-citation materialization cap beneath
the existing ten-row selection contract. Retain the validated selected body
citations within that contract and verify exact quote links after replay.
The real one-call model preflight now retains all six citations, including both
§ 39 bodies; 94 related checks passed. Deployed replay remains pending.
The source-language audit also requires exact expression titles on event/evidence
views and brief inputs; the shared multilingual work title is only a fallback.
Italian articles alone must not create related-law candidates. Preserve bounded
queries, ownership and exact-reference paths, version the relation retrieval rule,
and use the existing recovery workflow for retained candidates.
The full release gate found one extra scalar label query per inbox page. Merge
the language/title read into the existing bounded event query, preserving the
13-read budget for both one and fifty events, with no document hydration and
unchanged exact-expression/work/tenant binding.
The repaired inbox path passed 46 context, paging, history, title and digest
checks, including the unchanged query budget. Normal release validation remains
in progress; this does not complete MV2-052.
The host's full API suite reached 99% when its existing 7,200-second budget
expired. Use the existing bounded operator setting for 10,800 seconds on future
scheduled runs, retaining all required tests and the current CPU/memory budgets.
An already-started run is not interrupted or reconfigured.
The subsequent full run exposed three measured-token tests that import an
unidentified synthetic document without the required explicit assignment. Keep
the production identity guard, make that fixture's operator confirmation explicit,
and prove measured coverage, evidence preservation and cache reuse still execute.
All 55 token-evidence, identity, guidance, workflow and backlog checks passed;
the three originally failing cases also passed separately. The complete release
gate remains required; no production identity exception was added.
The same live pilot reproduced relation-analysis schema failures and unsupported
generated conclusions on an unreviewed small model. Apply the existing capability
policy to the separate relation-impact task, use a compact cited-row selection
when explanation is unapproved, and label its impact as unassessed. Keep official
relation facts, private evidence, retained failure history and review decisions.
Measure the bounded dossier against the observed context and reject invalid row
references. Verify real Apertus output, capability/cache changes, source quotes,
unknown severity and ordinary production replay; no quality approval is invented.
The expanded relation/capability/inbox regression suite passed 220 checks with
one existing skip, and the isolated production web build passed. Both retained
live dossiers completed with actual Apertus in one call and exact saved quotes
or an explicit empty selection. Production activation/replay remain pending.
The retained pilot inventory also contains unrelated candidates supported only
by Riehen/Bettingen or the instrument words “interkantonale Vereinbarung”. Extend
only relation retrieval's non-subject terms for the requested Basel/Bern geography
and generic agreements, version the rule and preview retained-candidate recovery.
Preserve topic geography, meaningful subjects, exact norm references, confirmed
official relations, workspace decisions and all historical evidence. Acceptance
includes the actual retained pairs, unrelated and substantive multilingual cases,
and bounded preview/apply with no inference or delivery recreation.
Revision v4 passed 94 related checks with one existing skip; the exact retained
inventory kept eight BaselTech and twelve personal leads and rejected fourteen
and forty-eight unsupported pairs respectively. Production recovery is pending.
The direct Basel BPG preflight additionally requires bounded support for its
2.44 MB official metadata envelope, which embeds full XHTML. Retain publisher,
language, version and PDF checks and prove oversized metadata still fails closed.
The live pilot also exposed a watch-removal foreign-key failure after related
events were delivered. Complete the existing explicit document/history deletion
contract for the requesting workspace, preserving shared corpus and other tenants,
and refuse removal while its related analysis is still running or queued.
Replay of the enabled Fedlex RSS streams found an official relation targeting a
dated JOLux Work URI. Resolve that verified parent work while retaining the exact
dated reference as evidence; do not widen root discovery or accept foreign URLs.
Daily scans of the new pilot guidance exposed false identities from unlabelled
dates and contents numbering, and legal citations mistaken for document titles.
Require explicit SR/RS labels and preserve short guidance titles/cover headings;
refresh prior derived identity assessments without changing original evidence.
The live Ukrainian registry also exposes an incomplete display/filter path:
recognize Ukrainian as a source language and use a watch's current bound artifact
language before the work's historical language aggregate, without rewriting it.
The Ukrainian SEM page has Ukrainian introductory content plus a multilingual
link directory. A clearly Ukrainian title and dominant Cyrillic introduction
must not inherit German from its hosting path; mixed or ambiguous titles remain
subject to the conservative language check and explicit publisher precedence.
The expanded live source audit also requires complete Fedlex HTML annex evidence
and root-work-only catalogue discovery; historical dated members are versions.
Shared language-specific watches must still bind to one official corpus work,
without exposing private legacy watches to global catalogue ingestion.
Historical federal-gazette archive references remain metadata-only; recognize
the court's German `Entscheid vom` heading while retaining docket/date checks.

15 September recurring-closure feature: MV2-040 and MV2-041 remain IN PROGRESS
in this index and their details. The explicit-offset source/calendar, private
history/delivery and five-language interval reader are implemented; live
permission/topology and broader acceptance remain open. See
[recurring closure evidence](docs/monitoring-v2/ROAD_RECURRING_CLOSURES.md).

15 September XLSX feature: MV2-044 and MV2-045 remain IN PROGRESS in this index
and their details after the complete permitted-original spreadsheet reader,
comparison, private revision and download workflow. Live source and broader B2
acceptance remain open. See [XLSX evidence](docs/monitoring-v2/TENDER_XLSX.md).

15 September source-history feature: MV2-052 remains IN PROGRESS in this index
and its detail after the complete nine-category sampler/chart/table workflow.
Historical sampling starts with activation; true processing/delivery latency and
broader operational acceptance remain open. See [source history](docs/monitoring-v2/SOURCE_HISTORY.md).

14 September timed-pause feature: MV2-018 and MV2-039 remain IN PROGRESS after
the visible Commute notification-pause journey. The Centre and exact settings
reader show its Europe/Zurich expiry, separate from source checks and permanent
pause. See [scope and checks](docs/monitoring-v2/COMMUTE_TIMED_PAUSE.md).

14 September deadline feature: MV2-048 remains IN PROGRESS in this index and
its detail after the tested five-language calculation/review/export feature.
Independent rule/calendar review, real source and release/human acceptance remain
open; see [deadline evidence](docs/monitoring-v2/TRADEMARK_WATCH.md#reviewed-deadline-feature--14-september-2026).

| ID | Task | Phase | Priority | Size | Status | Dependencies |
|---|---|---|---|---|---|---|
| [MV2-001](#mv2-001) | Establish extension contracts and MVP compatibility | F0 | P0 | M | DONE | None |
| [MV2-002](#mv2-002) | Validate first-value journeys and shared navigation | F0 | P0 | M | IN PROGRESS | None |
| [MV2-003](#mv2-003) | Verify source rights, coverage and contracts for the nine active scenarios | F0 | P0 | L | PLANNED | [MV2-001](#mv2-001) |
| [MV2-004](#mv2-004) | Personal workspace and team monitoring permissions | F1 | P0 | M | IN PROGRESS | [MV2-001](#mv2-001) |
| [MV2-005](#mv2-005) | MonitoringSubject and versioned Monitoring Templates | F1 | P0 | L | PLANNED | [MV2-001](#mv2-001), [MV2-004](#mv2-004) |
| [MV2-006](#mv2-006) | ObservedEntity: stable source identity | F1 | P0 | M | PLANNED | [MV2-001](#mv2-001), [MV2-003](#mv2-003) |
| [MV2-007](#mv2-007) | ObservedState and immutable evidence | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006) |
| [MV2-008](#mv2-008) | Deterministic ChangeRule, ChangeSet and numeric thresholds | F1 | P0 | L | PLANNED | [MV2-005](#mv2-005), [MV2-007](#mv2-007) |
| [MV2-009](#mv2-009) | Development, deduplication and lifecycle | F1 | P0 | L | PLANNED | [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-008](#mv2-008) |
| [MV2-010](#mv2-010) | Structural relevance with evidence for every match | F1 | P0 | L | PLANNED | [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-009](#mv2-009) |
| [MV2-011](#mv2-011) | Reliable state ingestion, queues and freshness | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-009](#mv2-009) |
| [MV2-012](#mv2-012) | Notification policy and transactional outbox | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-011](#mv2-011) |
| [MV2-013](#mv2-013) | Review, Decision and owner assignment | F1 | P0 | M | IN PROGRESS — native business item workflow implemented | [MV2-004](#mv2-004), [MV2-009](#mv2-009) |
| [MV2-014](#mv2-014) | Shared-feed API and read projections | F1 | P0 | L | PLANNED | [MV2-004](#mv2-004), [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-013](#mv2-013) |
| [MV2-015](#mv2-015) | Geography, station and coverage catalogue | F1 | P0 | L | PLANNED | [MV2-003](#mv2-003), [MV2-006](#mv2-006) |
| [MV2-016](#mv2-016) | Time windows, deadlines and reminders | F1 | P0 | L | PLANNED | [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-012](#mv2-012) |
| [MV2-017](#mv2-017) | Create Monitor: nine understandable templates | F2 | P1 | L | IN PROGRESS | [MV2-002](#mv2-002), [MV2-005](#mv2-005), [MV2-010](#mv2-010), [MV2-015](#mv2-015) |
| [MV2-018](#mv2-018) | Monitoring: manage saved subjects | F2 | P1 | M | IN PROGRESS — nine-category settings implemented | [MV2-005](#mv2-005), [MV2-011](#mv2-011), [MV2-017](#mv2-017) |
| [MV2-019](#mv2-019) | Today: one card across all domains | F2 | P1 | L | IN PROGRESS — shared review counts implemented | [MV2-014](#mv2-014), [MV2-017](#mv2-017) |
| [MV2-020](#mv2-020) | Investigate: states, diffs, evidence and history | F2 | P1 | L | PLANNED | [MV2-007](#mv2-007), [MV2-009](#mv2-009), [MV2-014](#mv2-014) |
| [MV2-021](#mv2-021) | Workspace: Impact Inbox, decisions and Impact Matrix | F2 | P1 | M | IN PROGRESS — native batch review implemented | [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-019](#mv2-019), [MV2-020](#mv2-020) |
| [MV2-022](#mv2-022) | Notifications and Digests from the same developments | F2 | P1 | L | IN PROGRESS — native email centre implemented | [MV2-012](#mv2-012), [MV2-014](#mv2-014), [MV2-019](#mv2-019) |
| [MV2-023](#mv2-023) | Ask and Marvin in the context of v2 evidence | F2 | P1 | M | IN PROGRESS — native evidence and configuration drafts implemented | [MV2-010](#mv2-010), [MV2-020](#mv2-020) |
| [MV2-024](#mv2-024) | Clear guidance, accessibility and five languages | F2 | P0 | L | IN PROGRESS | [MV2-002](#mv2-002), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022) |
| [MV2-025](#mv2-025) | Admin: accurate source capabilities and access management | F2 | P0 | M | IN PROGRESS — encrypted connector settings implemented | [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-018](#mv2-018) |
| [MV2-026](#mv2-026) | Possible future implementation: C4 official customs-rate connector | LATER | P2 | M | DEFERRED — possible future implementation; do not start development | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011) |
| [MV2-027](#mv2-027) | Possible future implementation: C4 currency, thresholds, history and digest | LATER | P2 | M | DEFERRED — possible future implementation; do not start development | [MV2-008](#mv2-008), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-022](#mv2-022), [MV2-026](#mv2-026) |
| [MV2-028](#mv2-028) | C1: official warnings and hazard geography | F3 | P1 | L | IN PROGRESS | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071) |
| [MV2-029](#mv2-029) | C1: Home/Office locations and the complete warning workflow | F3 | P1 | L | IN PROGRESS | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-028](#mv2-028) |
| [MV2-030](#mv2-030) | C5: official pollen observations and forecasts | F3 | P0 | M | IN PROGRESS | [MV2-069](#mv2-069), [MV2-070](#mv2-070) |
| [MV2-031](#mv2-031) | Pollen Watch — the first complete end-to-end scenario (C5) | F3 | P0 | L | IN PROGRESS | [MV2-070](#mv2-070), [MV2-030](#mv2-030) |
| [MV2-032](#mv2-032) | C6: hydrological stations, metrics and official danger levels | F3 | P1 | M | VERIFYING | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071) |
| [MV2-033](#mv2-033) | C6: River / Lake thresholds, history and consented digest | F3 | P1 | M | VERIFYING | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-032](#mv2-032) |
| [MV2-034](#mv2-034) | C7: Basel and Lugano hourly/daily air-quality series and interpretation | F3 | P1 | M | VERIFYING | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071) |
| [MV2-035](#mv2-035) | C7: Air Quality — changes, improvements and consented digest | F3 | P1 | M | VERIFYING | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-034](#mv2-034) |
| [MV2-036](#mv2-036) | Related developments from multiple sources | F4 | P1 | M | IN PROGRESS | [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-029](#mv2-029), [MV2-033](#mv2-033), [MV2-041](#mv2-041), [MV2-071](#mv2-071) |
| [MV2-037](#mv2-037) | Journey/Trip/Route/Stop and Road Corridor reference data | F4 | P0 | L | IN PROGRESS | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-015](#mv2-015), [MV2-016](#mv2-016), [MV2-071](#mv2-071) |
| [MV2-038](#mv2-038) | C2: Service Alerts and Trip Updates | F4 | P1 | L | IN PROGRESS | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071) |
| [MV2-039](#mv2-039) | C2: Regular commutes and low-noise transport alerts | F4 | P1 | L | IN PROGRESS — renewal regression fixed | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-038](#mv2-038) |
| [MV2-040](#mv2-040) | C3: ASTRA traffic and planned closures | F4 | P1 | L | IN PROGRESS | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071) |
| [MV2-041](#mv2-041) | C3: My Route Watch for A2 / Gotthard / A13 | F4 | P1 | L | IN PROGRESS | [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-040](#mv2-040) |
| [MV2-042](#mv2-042) | B2: SIMAP discovery and publication monitoring | F5 | P1 | L | IN PROGRESS | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071) |
| [MV2-043](#mv2-043) | B2/B7/B8: Structured profiles and semantic candidate ranking | F5 | P1 | L | IN PROGRESS | [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-010](#mv2-010), [MV2-071](#mv2-071) |
| [MV2-044](#mv2-044) | Versioned document sets and conditions | F5 | P1 | L | IN PROGRESS | [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-071](#mv2-071) |
| [MV2-045](#mv2-045) | B2: Tender discovery, Today review and material updates | F5 | P1 | L | IN PROGRESS | [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-042](#mv2-042), [MV2-043](#mv2-043), [MV2-044](#mv2-044) |
| [MV2-046](#mv2-046) | B7: Official trademark publications and register updates | F5 | P1 | L | IN PROGRESS | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071) |
| [MV2-047](#mv2-047) | B7: Exact, lexical and phonetic candidates | F5 | P1 | L | IN PROGRESS | [MV2-043](#mv2-043), [MV2-046](#mv2-046) |
| [MV2-048](#mv2-048) | B7: IP review, review deadlines, register changes and consented digest | F5 | P1 | L | IN PROGRESS | [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-046](#mv2-046), [MV2-047](#mv2-047) |
| [MV2-049](#mv2-049) | B8: Official Ticino auctions — native collection implemented; access/coverage open | F5 | P1 | L | IN PROGRESS | [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071) |
| [MV2-050](#mv2-050) | B8: Auction profiles, price limits and ending-soon alerts | F5 | P1 | L | IN PROGRESS — adapter conformance checked | [MV2-008](#mv2-008), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-043](#mv2-043), [MV2-044](#mv2-044), [MV2-049](#mv2-049) |
| [MV2-051](#mv2-051) | Independent matching and local AI evaluation | F6 | P0 | L | IN PROGRESS | [MV2-023](#mv2-023), [MV2-043](#mv2-043), [MV2-047](#mv2-047) |
| [MV2-052](#mv2-052) | Operational metrics, degraded mode and source recovery | F6 | P0 | M | IN PROGRESS | [MV2-011](#mv2-011), [MV2-012](#mv2-012), [MV2-025](#mv2-025) |
| [MV2-053](#mv2-053) | Personal-location privacy and access control | F6 | P0 | M | IN PROGRESS — account erasure and ownership handover implemented | [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-023](#mv2-023) |
| [MV2-054](#mv2-054) | Single-server capacity and queues with different priorities | F6 | P0 | L | IN PROGRESS — queue fairness, native batching and scan health verified locally | [MV2-011](#mv2-011), [MV2-014](#mv2-014), [MV2-043](#mv2-043), [MV2-052](#mv2-052) |
| [MV2-055](#mv2-055) | History storage, retention and permitted exports | F6 | P0 | M | IN PROGRESS | [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-020](#mv2-020), [MV2-044](#mv2-044) |
| [MV2-056](#mv2-056) | Migration, compatibility and rollback rehearsal | F6 | P0 | L | PLANNED | [MV2-001](#mv2-001), [MV2-053](#mv2-053), [MV2-055](#mv2-055), [MV2-060](#mv2-060) |
| [MV2-057](#mv2-057) | Executable checks for 116 active AC and adversarial regression | F6 | P0 | L | IN PROGRESS — AC protocols linked | [MV2-029](#mv2-029), [MV2-031](#mv2-031), [MV2-033](#mv2-033), [MV2-035](#mv2-035), [MV2-036](#mv2-036), [MV2-039](#mv2-039), [MV2-041](#mv2-041), [MV2-045](#mv2-045), [MV2-048](#mv2-048), [MV2-050](#mv2-050), [MV2-024](#mv2-024), [MV2-051](#mv2-051), [MV2-053](#mv2-053), [MV2-056](#mv2-056), [MV2-068](#mv2-068), [MV2-071](#mv2-071) |
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

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Product + UX · **Size:** M

**Whole-feature scope, 14 September 2026:** Give new users a persisted personal
choice across all nine Monitoring directions on the first-run page, direct native
configuration and a return path, with source/Start/consent distinct from setup
intent. See [scope and acceptance](docs/monitoring-v2/MONITORING_FIRST_RUN.md).
Measured first value, independent users and language acceptance remain open.

**Dependencies:** None. **Requirements:** §§20–21,25–26,34.

**User outcome:** People can create a monitor without understanding Sources/Topics.

**Work:** Prototype Create Monitor → preview → Today → evidence → decision; cover personal and team modes and the journeys of all nine active templates.

**Acceptance criteria:**

1. At least 5 B2C participants and 5 B2B representatives complete tasks relevant to them; retain the error log.
2. The prototype explicitly shows unavailable coverage, the wait for an initial state and the lack of fresh data.
3. Navigation includes Today / Monitoring / Investigate / Workspace / Admin; preserve access to existing laws, Topics, Discover and Impact Matrix.

**Verification:** Observe users without prompting; use the results to refine copy and configuration without expanding the nine active cases.

**Execution evidence, 14 September 2026:** The personal first-run choice across
all nine directions is implemented, with saved continuation, five-language
registration guidance and explicit source/Start/consent boundaries. Corrected API
acceptance passed 31 tests; isolated PostgreSQL migration/concurrency passed;
root build, 35 new browser/axe checkpoints and 40 legal regressions passed.
See [evidence and limits](docs/monitoring-v2/MONITORING_FIRST_RUN.md). This does
not replace the required observed human journeys or close MV2-002.

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

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Backend + UX · **Size:** M

**Dependencies:** [MV2-001](#mv2-001). **Requirements:** §§5,27.1,27.7.

**User outcome:** B2C users do not need to invent a company; team data remains within the team.

**Work:** Reuse Organization/personal workspace and auth; define subject owner_scope, creator, access, membership, deletion and ownership transfer.

**Acceptance criteria:**

1. A personal workspace is isolated by default; another organization cannot see the Home address.
2. Admin manages shared monitors; a viewer has only permitted read/personal acknowledgement actions; a shared decision requires permission.
3. Workspace switching, access revocation and old links do not disclose a state or an AI conclusion.

**Verification:** API role matrix, negative cross-tenant tests and browser switching/revocation checks.

**Execution evidence:** Explicit workspace sharing for Tender, IP and Auctions is implemented with code verification; see [whole-feature scope and acceptance](docs/monitoring-v2/BUSINESS_MONITOR_SHARING.md). Existing private defaults, personal email and authenticated source audiences remain separate. Complete native/API/role/privacy, PostgreSQL concurrency/migration and five-language browser checks are recorded there. Exact production activation, physical account deletion and independent human acceptance remain open.

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

**Status:** IN PROGRESS — native business item workflow implemented · **Priority:** P0 · **Owner:** Backend + Frontend · **Size:** M

**Dependencies:** [MV2-004](#mv2-004), [MV2-009](#mv2-009). **Requirements:** §§6,21,27.7,31.

**User outcome:** The user’s decision is saved with the evidence version.

**Work:** Personal read state, workspace Review, append-only Decision; REVIEWED/ACTION_REQUIRED/NO_ACTION/NOT_RELEVANT/MONITOR/RESOLVED and domain decisions.

**Acceptance criteria:**

1. A decision includes development revision, actor, owner, comment and timestamp; a concurrent write does not overwrite another.
2. A new material update marks the previous decision as based on an older revision; its text remains in history.
3. BID/NO_BID/INSPECT/ESCALATE_TO_IP_COUNSEL are internal decisions; no external submission or sending occurs.
4. Deactivating an owner does not lose unresolved reviews; reassignment to another member is permitted.

**Verification:** Optimistic concurrency, roles, reopening, reassignment and personal/shared-state tests.

**Execution evidence:** [Business monitor responsibility](docs/monitoring-v2/BUSINESS_MONITOR_SHARING.md) retains collection assignment/scope history and shared native access. [Business item work](docs/monitoring-v2/BUSINESS_ITEM_WORK.md) adds individual Tender/IP/Auction responsibility, comment-only work and atomic native decisions with evidence-bound owner/comment snapshots. Native entry points retain the same audit; deactivated assignees do not lose unresolved work. Broader shared/personal review-state coverage, physical account deletion and exact activation/human acceptance remain open.

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

**First-run contribution, 14 September 2026:** All nine templates now appear on
the post-registration guide with an owner-private persisted starting choice,
direct native setup and a return link. See
[first-run acceptance](docs/monitoring-v2/MONITORING_FIRST_RUN.md). Selection is
not activation; source, shared ownership and broader parent criteria stay open.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend + UX · **Size:** L

**Dependencies:** [MV2-002](#mv2-002), [MV2-005](#mv2-005), [MV2-010](#mv2-010), [MV2-015](#mv2-015). **Requirements:** §§5,25,33.

**User outcome:** The user configures the goal, and the system selects the source.

**Work:** Personal/Business template picker; guided form, capability availability, why-match/no-match preview, defaults and explicit start.

**Acceptance criteria:**

1. Provide six Personal templates C1/C2/C3/C5/C6/C7 and three Business templates B2/B7/B8; unsupported/blocked active scenarios explain the reason and cannot be activated. C4 is absent from the current picker; no customs-rate placeholder or form is required.
2. The form collects the domain configuration from the requirements without asking users for a URL, API key or technical source ID.
3. Preview labels a sample/baseline and does not create real alerts; double-clicking Start does not create duplicates.
4. Errors retain the draft and suggest corrections; the first state shows the expected wait, source and next step.

**Verification:** Browser journeys for creation, editing and unavailability across the nine active templates.

**13 September navigation follow-up:** All nine implemented directions are now linked from the shared desktop/mobile Monitoring menu for every role, with a named current destination. Enabled production defaults and individual source-readiness checks are preserved. See [navigation scope and verification](docs/monitoring-v2/MONITORING_CENTRE.md#all-nine-sections-in-navigation--13-september-2026). This does not complete the broader nine-template live-source and user acceptance criteria.

**14 September configuration availability:** Enabled sections are available to configure in the Centre; Hazard/Commute/Road/IP/Auction no longer carry a hard-coded preview-only classification. Source readiness remains in the domain and is not inferred from section availability. See [scope and verification](docs/monitoring-v2/MONITORING_CENTRE.md#configuration-availability--14-september-2026). Broader live-source/user acceptance remains IN PROGRESS.

**Execution evidence:** [Monitoring Centre scoped feature](docs/monitoring-v2/MONITORING_CENTRE.md): nine scenario choices with explicit availability, owner-private C5/C6/C7 inventory, freshness and lifecycle filters, exact links to existing settings/history and a legacy bridge. Uses existing configuration, ownership and source contracts; adds no source permission or activation route. Full parent acceptance remains open for the other domain journeys, shared business subjects and timed commute pause. Code checks, release identity and human acceptance are tracked separately in the evidence document.

<a id="mv2-018"></a>

### MV2-018 — Monitoring: manage saved subjects

**Settings contribution, 14 September 2026:** The requested nine-category settings hub reuses native monitor, lifecycle, sharing and email editors. Platform administrators can save encrypted IPI credentials, independent transport keys and native collector options, select existing source permissions, and check saved access explicitly. New requests/workers adopt versioned settings without restart; changed configurations invalidate old check results. [Acceptance evidence](docs/monitoring-v2/MONITORING_SETTINGS.md) records API, worker, build and 93 browser/axe checkpoints. Parent acceptance and exact production activation remain open.

**Active whole-feature scope, 14 September 2026:** Make the existing Commute
calendar-day notification pause visible in both its exact settings reader and
the Monitoring Centre, with the actual Europe/Zurich midnight expiry. Keep source
checking and permanent pause/archive separate, including DST and year rollover.
Reuse owner-private lifecycle commands; no new source or delivery permission.
See [scope and acceptance](docs/monitoring-v2/COMMUTE_TIMED_PAUSE.md).

**Scoped implementation evidence:** The shared pause reader and five-language
notice cover the calendar-day portion of AC3. The existing persisted command,
notification rules and source checks remain authoritative. Parent acceptance
still includes shared business subjects, live sources and human verification.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend · **Size:** M

**Dependencies:** [MV2-005](#mv2-005), [MV2-011](#mv2-011), [MV2-017](#mv2-017). **Requirements:** §§9.12,25–26.

**User outcome:** Users can see exactly what is monitored and whether ingestion is working.

**Work:** List personal/shared subjects; status, source, last observation/success/next expected update, thresholds, pause/resume/archive and contextual Monitor this.

**Acceptance criteria:**

1. Edits and pause/resume persist after reload; archiving does not delete history.
2. No change, first data pending, stale, source unavailable and disabled have distinct wording and actions.
3. Pause commute today resumes automatically according to the timezone and shows the time; archive has no automatic resume.
4. Existing Topics and watched documents remain accessible through the bridge; new navigation does not duplicate management.

**Verification:** Browser persistence, real-time status updates, stale recovery and legacy-link tests.

**Execution evidence:** [Monitoring Centre scoped feature](docs/monitoring-v2/MONITORING_CENTRE.md): nine scenario choices with explicit availability, owner-private C5/C6/C7 inventory, freshness and lifecycle filters, exact links to existing settings/history and a legacy bridge. Uses existing configuration, ownership and source contracts; adds no source permission or activation route. Full parent acceptance remains open for the other domain journeys, shared business subjects and timed commute pause. Code checks, release identity and human acceptance are tracked separately in the evidence document.

<a id="mv2-019"></a>

### MV2-019 — Today: one card across all domains

**Shared review summary, 14 September 2026:** Implemented all nine active
directions plus the legal feed using native visibility rules beyond the first
page, private database snapshots, explicit unavailable totals, five-language
section links and review-triggered refresh. The affected API suite passed 57
checks, the root build passed and 22 built-browser/axe checkpoints passed.
See [scope, evidence and limits](docs/monitoring-v2/TODAY_COUNTS.md). Large-workspace
capacity, source/human acceptance and exact activation remain unverified; this
does not complete cross-domain grouping or shared business ownership.

**Earlier whole-feature scope, 14 September 2026:** Add the missing River / Lake
Today and Impact Inbox cards, owner-private latest developments, review filtering,
bounded pagination and existing exact evidence/review actions. See [scope](docs/monitoring-v2/RIVER_TODAY.md).
This is a scoped MV2-033/019/021 contribution; broader cross-domain aggregation,
shared business-subject acceptance remain open. The later shared-count contribution
above supersedes the River-only count limitation for readable Today queues.

**Status:** IN PROGRESS — shared review counts implemented · **Priority:** P1 · **Owner:** Frontend + UX · **Size:** L

**Dependencies:** [MV2-014](#mv2-014), [MV2-017](#mv2-017). **Requirements:** §§20,26.1,33.

**User outcome:** Mixed events are equally easy to understand.

**Work:** Shared card shell: type, authority severity, state/delta, why, timestamps, evidence and review; domain-specific fields within the shell.

**Acceptance criteria:**

1. The card includes the fact, previous→current, source/time, structural why and an explicit CTA; the initial baseline does not invent a previous state. Review / Evidence / Not relevant are explicit on the card.
2. Observed, forecast, stale and system calculation have visible labels; source severity is separate from user priority.
3. One development aggregates multiple subjects; material updates/reopened states are marked without creating a second independent card.
4. Legacy legal and all 9 active v2 templates work with filters, accessible empty/loading/error states and global unread counts.

**Verification:** Populated mixed-feed browser replay; keyboard, narrow viewport and live revision updates.

**Execution evidence, 14 September 2026:** Scoped River Today / Impact Inbox integration adds latest owner-private retained changes, all/unreviewed filtering and River-only count, bounded stable pagination, exact evidence links and existing CAS review actions. Five-language cards distinguish recorded observations, old settings, correction/recovery and personal thresholds from official danger. See [scope, verification and limits](docs/monitoring-v2/RIVER_TODAY.md). Cross-domain aggregation/global unread counts, shared business ownership and broader parent acceptance remain open.

**Tender integration, 14 September 2026:** Owner-private public-summary cards now span saved Tender profiles on Today and Impact Inbox, with pending/following filters, retained prior decisions on reopen, restriction/embargo-aware counts and exact evidence/version links. See [feature evidence](docs/monitoring-v2/TENDER_TODAY.md). This remains a scoped contribution; shared ownership and cross-domain aggregation are not complete.

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

**Whole-feature implementation, 14 September 2026:** Explicit bounded batch review
from the nine native notification queues, with previewed evidence, domain-specific
decisions, atomic conflict handling and no external actions. See
[acceptance contract](docs/monitoring-v2/MONITORING_BATCH_REVIEW.md).

**Status:** IN PROGRESS — native batch review implemented · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** M

**Dependencies:** [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-019](#mv2-019), [MV2-020](#mv2-020). **Requirements:** §§15–17,26.4,27.7.

**User outcome:** Unfinished work has an owner and context.

**Work:** Unresolved/reopened/assigned filters, notes, decisions and safe batch review; preserve the existing Matrix in its regulatory context without invented cross-domain impact scores.

**Acceptance criteria:**

1. A high-severity hazard, relevant IP candidate or tender update can have an Inbox review; source state is not mixed with the decision.
2. Batch review is tied to visible revisions; a new revision arriving during the action is not considered reviewed.
3. BID/NO_BID/INSPECT/escalate have domain-specific labels and send nothing externally.
4. Owner assignment and decision history are visible only within the permitted scope; Matrix and old inbox links work.

**Verification:** Concurrent revision/decision browser journeys, owner filters and legacy Matrix regression.

**Execution evidence, 14 September 2026:** Scoped River Today / Impact Inbox integration adds latest owner-private retained changes, all/unreviewed filtering and River-only count, bounded stable pagination, exact evidence links and existing CAS review actions. Five-language cards distinguish recorded observations, old settings, correction/recovery and personal thresholds from official danger. See [scope, verification and limits](docs/monitoring-v2/RIVER_TODAY.md). Cross-domain aggregation/global unread counts, shared business ownership and broader parent acceptance remain open.

**Tender integration, 14 September 2026:** Public-summary cards span saved permitted Tender profiles on Today and Impact Inbox, with pending/following filters, retained prior decisions on reopen, restriction/embargo-aware counts and exact evidence/version links. See [feature evidence](docs/monitoring-v2/TENDER_TODAY.md). Explicit business sharing is recorded separately in [scope evidence](docs/monitoring-v2/BUSINESS_MONITOR_SHARING.md).

**Individual business work, 14 September 2026:** Native Tender/IP/Auction lists now support assigned-to-me and unassigned filters; item details offer individual responsibility, comments and atomic native decisions with paginated evidence-bound history. Private/authenticated document audiences, viewers and current source rights remain enforced. See [complete feature scope and checks](docs/monitoring-v2/BUSINESS_ITEM_WORK.md). Broader Inbox assignment/batch aggregation, personal directions and exact release/human acceptance remain open; the regulatory Matrix remains in its existing context.

<a id="mv2-022"></a>

### MV2-022 — Notifications and Digests from the same developments

**Implemented whole-feature scope, 14 September 2026:** Manage native email preferences
for every private Monitoring direction from one centre, including Pollen's
explicit pause/save/resume and consent boundaries. Reuse native policy and delivery
contracts; see [acceptance scope](docs/monitoring-v2/MONITORING_EMAIL_CENTRE.md).

**Email-centre verification:** 61 native API regressions, root build, 97 new
browser/axe checkpoints, 36 native Tender checkpoints and 8 Monitoring Centre
regressions passed. Pollen's explicit pause/save/resume and the other eight native
consent/schedule/quiet-hour editors remain authoritative. Publication is distinct
from activation; broader priority/event controls and source/human acceptance
remain open. See the linked evidence and reproduction instructions.

**Current whole-feature scope, 14 September 2026:** Extend the header notification
centre from legal events to all nine Monitoring review queues, with native
eligibility, bounded private pagination, synchronized review state and exact
evidence links. Add the missing pinned Pollen entry reader/panel as a dependency.
See [scope and acceptance](docs/monitoring-v2/MONITORING_NOTIFICATION_CENTRE.md).
Shared email preferences and broader source/human acceptance remain separate.

**14 September implementation evidence:** The complete in-app centre now exposes
all nine private native review queues and the legal feed, with scoped pagination,
shared Today eligibility and exact retained Pollen evidence. Local acceptance:
48 affected API checks, root build, exact API lint, 65 new browser/axe checkpoints,
80 legal notification checkpoints and 22 Today checkpoints passed. See the linked
evidence document. Exact activation, shared email/noise preferences and live/human
acceptance remain open; this contribution does not close the broader task.

**Status:** IN PROGRESS — native email centre implemented · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-012](#mv2-012), [MV2-014](#mv2-014), [MV2-019](#mv2-019). **Requirements:** §§28,33; AC-B2-12; C4 digest deferred.

**User outcome:** Users manage noise in one place.

**Work:** In-app center and opt-in email digest; monitor/type/event/channel mute, priority, frequency, quiet hours and review/evidence deep links.

**Acceptance criteria:**

1. Immediate notifications and digests do not duplicate the same revision without an explicitly selected recap policy.
2. A digest contains only material changes from the permitted period and identifies source gaps; preview uses the sending rules.
3. Settings are saved per user/workspace; unsubscribe and permissions are applied before sending.
4. Improvement/cancellation messages link to the preceding development; unread state is synchronized between Today and the center.

**Verification:** Send-preview parity, race/unsubscribe tests, multi-monitor deduplication and bounded-period queries.

**Execution evidence:** In-app queue and pinned Pollen acceptance is recorded in
[Monitoring notification centre](docs/monitoring-v2/MONITORING_NOTIFICATION_CENTRE.md).
Broader email/noise controls and live/human/release gates remain open.

<a id="mv2-023"></a>

### MV2-023 — Ask and Marvin in the context of v2 evidence

**Completed scoped feature, 14 September 2026:** Natural-language proposals in all
nine native configuration editors, with explicit unsaved application and manual
fallback. Scope, source readiness, dependencies and acceptance are recorded in
[Configuration drafts](docs/monitoring-v2/MONITORING_CONFIGURATION_DRAFTS.md).
Local API, build and 94 browser/axe checkpoints passed. Production activation,
model approval and broader parent acceptance remain open.

**Current whole-feature scope, 14 September 2026:** Implement evidence questions
from exact native records across all nine active directions, with model-offline
extracts, citations, binding/revocation checks and five-language reader actions.
Source display rights remain authoritative; no inference or monitor writes are
authorized by a question. See [acceptance contract](docs/monitoring-v2/MONITORING_EVIDENCE_ASK.md).
The complete native integration includes all nine record readers, exact display
references, source-unit context, locale bindings and access/changed-evidence
redaction. Scoped checks and publication evidence are recorded in the linked
contract. Broader draft/generative/human acceptance remains open.

**Status:** IN PROGRESS — native evidence and configuration drafts implemented · **Priority:** P1 · **Owner:** AI + Frontend · **Size:** M

**Dependencies:** [MV2-010](#mv2-010), [MV2-020](#mv2-020). **Requirements:** §§21–22,26.3,31; legacy HL-083–087,089.

**User outcome:** Asking about an event does not trigger unnecessary generation or change a monitor.

**Work:** Reuse cached briefs; entity-aware read context and cited answers; follow-up intent and explicit draft/preview for monitor changes.

**Acceptance criteria:**

1. The core of active C1/C2/C3/C5/C6/C7 works with the LLM offline; an unavailable model presents evidence/extractive mode.
2. A saved conclusion is tied to state/profile/model/prompt/locale revisions; a stale answer is not presented as current.
3. Ask does not promise medical treatment, infringement findings or a guaranteed legal deadline; official instructions are quoted accurately.
4. Natural-language configuration creates a draft for review; no autonomous activation, bid or external message occurs.

**Verification:** Context revocation, stale briefs, prompt-injection fixtures and cited-answer checks under a feature flag. DONE means integration with manual/extractive fallback; production model enablement separately passes MV2-051.

**Active whole-feature scope, 14 September 2026:** Correct Marvin section context and provide model-independent navigation help across all nine Monitoring directions and their centre. Reuse private conversations and source readers; no record access or source permission is inferred. See [scope and acceptance](docs/monitoring-v2/MARVIN_MONITORING_GUIDANCE.md). Broader evidence-aware Ask/drafts, language review and parent acceptance remain open.

<a id="mv2-024"></a>

### MV2-024 — Clear guidance, accessibility and five languages

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** UX + Frontend + Language reviewers · **Size:** L

**Dependencies:** [MV2-002](#mv2-002), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022). **Requirements:** §§20–21,25–26; legacy HL-057,073,095–097.

**User outcome:** New capabilities are accessible by keyboard, on a phone and in a supported language.

**Work:** English-first implementation with existing i18n contracts; EN/DE/FR/IT/RM release strings and human review; F1/Page guide/Show me for new actions.

**Acceptance criteria:**

1. New sections explain data provenance, every action, waiting/configuration and the effects of mute/review.
2. Keyboard/focus/contrast/screen-reader checks pass for populated/error/stale flows; color is not the only signal.
3. Independent fluent reviewers verify new v2 flows in all five languages; an unreviewed language is not declared ready.
4. Primary actions are simple; provider/queue/debug fields stay in Admin, and units/dates/number formats are localized.

**Verification:** Browser/axe + screen-reader/device review + language sign-off; automated checks do not replace human acceptance.

**Active whole-feature scope, 14 September 2026:** Correct Marvin section context and provide model-independent navigation help across all nine Monitoring directions and their centre. Reuse private conversations and source readers; no record access or source permission is inferred. See [scope and acceptance](docs/monitoring-v2/MARVIN_MONITORING_GUIDANCE.md). Broader evidence-aware Ask/drafts, language review and parent acceptance remain open.

<a id="mv2-025"></a>

### MV2-025 — Admin: accurate source capabilities and access management

**Settings contribution, 14 September 2026:** The requested nine-category settings hub reuses native monitor, lifecycle, sharing and email editors. Platform administrators can save encrypted IPI credentials, independent transport keys and native collector options, select existing source permissions, and check saved access explicitly. New requests/workers adopt versioned settings without restart; changed configurations invalidate old check results. [Acceptance evidence](docs/monitoring-v2/MONITORING_SETTINGS.md) records API, worker, build and 93 browser/axe checkpoints. Parent acceptance and exact production activation remain open.

**Active whole-feature scope, 14 September 2026:** Deliver the platform-admin
source-operations overview for all nine directions/four active packs. Show actual
stored acquisition/access/retry evidence with unknowns and source gaps, without
private data, network collection or permission mutation. See [scope and acceptance](docs/monitoring-v2/SOURCE_OPERATIONS.md).
This contributes to MV2-052; reprocessing and broader policy/operational gates remain.

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Integration + Frontend · **Size:** M

**Dependencies:** [MV2-003](#mv2-003), [MV2-011](#mv2-011), [MV2-018](#mv2-018). **Requirements:** §§23,26.5,38.

**User outcome:** Administrators understand why a template is available or blocked.

**Work:** Catalogue 4 active source packs: Swiss Safety & Environment, Swiss Mobility, Swiss Business Opportunities and Swiss IP; Swiss Customs is deferred. For active packs, include conformance version, access expiry, supported fields/location/history, quotas, freshness and reprocess controls.

**Acceptance criteria:**

1. Export restrictions, access expiry, correction requirements and licence version are enforced through policy, rather than only documented.
2. Missing access shows an actionable state; viewers cannot see secrets or credentials.
3. Reprocess provides preview, bounded scope, progress/cancel/resume; historical replay does not create an alert burst.
4. A terms/capability change disables the dependent function and notifies the administrator; no silent third-party fallback occurs.

**Verification:** API permission tests, licence-expiry clock, source failure/recovery and reprocess browser checks.

**Execution evidence, 14 September 2026:** Scoped source-operations overview implemented at `/admin/monitoring-sources` for all nine directions and four packs. The platform-admin-only metadata reader distinguishes configuration, permission-record validity, receipt/provider/retry clocks, errors and unknowns, excluding private monitors and secrets. Five-language mobile/keyboard and access-redaction checks pass. See [verification and remaining gates](docs/monitoring-v2/SOURCE_OPERATIONS.md). Broader policy/reprocessing, lag charts and operational acceptance remain open; this contribution does not complete the parent task.


## F3 — Numeric states, environment and hazards

<a id="mv2-028"></a>

### MV2-028 — C1: official warnings and hazard geography

**Native source publication candidate, 14 September 2026:** The normal collector
now initializes the reviewed public MeteoAlarm wind/thunderstorm contract and
hash-pinned swisstopo geometry while preserving explicit and revoked operator
decisions. Complete snapshots feed existing private history, Today/Inbox and
consented email with original-source attribution. Source status is visible in
five locales. All Hazard/source-operation tests passed (360), final guards (34),
root build and 60 browser checks passed; a real empty Swiss poll and native Basel
readiness were verified locally. Full C1, nonempty live warning/pilot and exact
production activation remain IN PROGRESS. See [source and acceptance evidence](docs/monitoring-v2/HAZARD_WATCH.md#native-source-activation-and-complete-vertical-workflow-14-september-2026).

**Active whole-feature scope, 14 September 2026:** Native MeteoAlarm Switzerland
Atom/linked-CAP collection through the existing private warning workflow. The
public feed and its additional redistribution terms are now located; Swiss feed
discovery was empty, so a real Swiss warning/geometry fixture and live acceptance
remain unverified. Implement complete-snapshot presence/withdrawal, source and
issue-time attribution, unmodified warning reader, permitted weather coverage,
bounded fresh collection, private events/Today/Inbox/consented delivery and the
required backend/frontend checks together before publication. Existing journal,
boundary catalogue and private lifecycle are dependencies. Do not claim power
outage/civil protection coverage from MeteoSwiss. See the
[complete source feature contract](docs/monitoring-v2/HAZARD_WATCH.md#native-meteoalarm-feature-selected-14-september-2026).

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-015](#mv2-015), [MV2-071](#mv2-071). **Requirements:** §8.4–8.9; AC-C1-02,04,05,07,09.

**User outcome:** An official warning has a stable history and affected area.

**Work:** Alertswiss/federal/cantonal capability-specific adapter; authority ID, severity scale, certainty, instructions, publication/effective/valid times and cancellation. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Verify access and permitted geography; hazard categories reflect actual source coverage, including outages if the source supplies them.
2. Retain instructions and authority severity without AI rewriting; multiple languages do not duplicate a warning.
3. Retain polygon/municipality expansion/reduction as an update; cancellation/all-clear is distinct from a feed gap.
4. Missing types or cantonal data are marked unavailable, rather than “no hazard”.

**Verification:** Source fixtures for creation/update/instructions/geography/cancellation; controlled live fetch with permission.

**Active scope, 13 September 2026:** C1 is the next independent direction while C2/C3/B2 access gates remain open. Implement the complete private-location warning workflow under the [Hazard Watch contract](docs/monitoring-v2/HAZARD_WATCH.md). Official CAP Suisse 1.1 defines a usable protocol contract, but FOCP describes third-party integration as planned by 2027; a current feed and source-specific reuse agreement are unverified. Source discovery does not establish current warning coverage. The local bounded CAP decoder, tri-state point geography and immutable predecessor ledger are implemented with synthetic fixtures. The final affected suite passed 63 tests in 0.54s, including the backlog invariant; required API Ruff and whitespace checks passed. Translation/technical updates retain evidence without incrementing material review state; late ancestor cancellation cannot close a newer warning. The private location draft workflow is now implemented across two tenant-scoped tables, owner-checked HTTP routes and the five-language reader, with CAS/idempotency, bounded history, archive/delete confirmation and a gated Monitoring Centre inventory. The corrected private HTTP/repository/auth/migration/compose/backlog suite passed 36 tests; 26 hazard/centre/Road API regressions passed, and the root web build passed. Isolated synthetic Chrome verified save/edit/history/archive/delete, denial redaction and five-language mobile forms; two full-document axe audits had zero violations with shared Marvin contrast incomplete. Current source access, reviewed administrative/radius geometry, durable warning evidence, active event lifecycle, delivery, live release and human acceptance remain open; no real source or monitor has been activated.

**Geography follow-up, 13 September 2026:** The 0–50 km radius matcher and offline native swissBOUNDARIES3D catalogue now pass 107 combined catalogue/radius/CAP/history/private-repository tests. Seven public-coordinate checks passed against the official January 2026 GeoPackage, whose archive matches the STAC SHA-256: 2,110 Swiss political municipalities, 26 cantons, Basel/Bern/Moutier membership, foreign/enclave exclusion and obsolete-code rejection. Version/hash/attribution and explicit review expiry accompany local membership proofs; uncertain borders and missing geography stay unavailable. Exact required API Ruff passed. Runtime catalogue installation/renewal, municipal warning-area intersections and the complete source/event/delivery workflow remain open; no feature completion, live warning coverage or release is claimed. See the [native geography evidence](docs/monitoring-v2/HAZARD_WATCH.md#native-administrative-catalogue-and-radius-13-september-2026).

**Runtime geography follow-up:** The offline operator installer, atomically selected/hash-pinned catalogue and private HTTP preview now work together. Cache reuse never survives missing/corrupt/expired/revoked selection; explicit renewal requires the current selection hash. Fifty installation/catalogue/private-API/repository tests and the isolated root web build passed. Real Basel membership was verified through an installation in a new local QA directory; production was unchanged. Five-language browser previews show matched municipality or location/catalogue failures and clear stale proof on edit; desktop/mobile axe checks had zero violations (Marvin contrast incomplete). Municipality/CAP matching and the full active warning workflow remain open. See [runtime catalogue evidence](docs/monitoring-v2/HAZARD_WATCH.md#runtime-catalogue-and-private-preview-13-september-2026).

**CAP geography follow-up:** Point/radius and whole-municipality matching now preserve the CAP Suisse distinction between precise extent and administrative filters. Canton/municipality labels cannot enlarge an explicit polygon to all addresses. Native multipart geometry/holes, circles, source-bound code editions, uncertain boundaries and revoked runtime catalogues are covered by 110 affected tests. Seven additional synthetic-warning checks passed against actual checksum-verified Basel geometry, separately from the seven native membership checks. API and operator-script Ruff passed. No source category/coverage/rights contract, durable warning events or delivery is implied; see [matching evidence](docs/monitoring-v2/HAZARD_WATCH.md#cap-municipalitycanton-matching-13-september-2026).

**Durable source journal follow-up:** Five shared tables now retain permission-bound CAP evidence, exact current predecessors, generation/cursor CAS and idempotent receipts without private locations. Independent usage rights, immutable retention, revocation purge, non-rehydrating identity tombstones, bounded storage and stale/expired evidence handling are locally verified. The combined journal/CAP/private API suite passed 113 tests; the final tightened storage suite passed 38 journal tests, including migration roundtrip and metadata comparison. These are synthetic grants and warnings. Native feed rights/coverage, collection/maintenance and private event/delivery acceptance remain open; MV2-028 stays IN PROGRESS. See [journal evidence](docs/monitoring-v2/HAZARD_WATCH.md#durable-cap-source-journal-13-september-2026).

**Private projection follow-up:** The journal now requires a separate default-denied permission for retained private decisions, and retention/revocation also erases derived content across organizations. Private projection binds exact current source and configuration revisions plus boundary proof, without establishing live coverage. The 87-test event/source/private API/repository run passed; final mute/API/source changes passed 65 tests and a separate two-organization purge check. Native acquisition/rights/coverage and scheduled maintenance remain open. See [private event evidence](docs/monitoring-v2/HAZARD_WATCH.md#private-warning-events-review-and-type-mute-13-september-2026).

**Official reader follow-up:** The five-language reader preserves original instructions, source language, attribution, freshness and actual warning level. Unavailable evidence is redacted; administrative filters do not become house-level coverage. The root build and 22 synthetic event-browser checks passed; final screenshots were reviewed. Native rights/access/coverage and scheduled collection remain open; MV2-028 stays IN PROGRESS. See [reader evidence](docs/monitoring-v2/HAZARD_WATCH.md#official-warning-reader-and-private-actions-13-september-2026).

**Today source-evidence follow-up:** Private Today/Inbox summaries recheck current rights, head, retention, configuration and boundary proof through the exact event reader. Missing/revoked/stale evidence cannot enter a card; no coverage or all-clear is inferred from an empty page. A mid-page revision cannot mix new evidence with the earlier cursor. The 44-test integration suite and final 16-test Today suite passed. Acquisition and maintenance remain open; MV2-028 stays IN PROGRESS. See [Today evidence](docs/monitoring-v2/HAZARD_WATCH.md#private-today-and-impact-inbox-13-september-2026).

**Lifecycle/source readiness and notification follow-up:** A fresh completed-poll marker, reviewed per-hazard jurisdiction and the entire saved footprint now gate start/resume; individual warning receipts do not establish coverage. Processing rechecks current source/geography and leases; scheduled retention erases expired/revoked content even with acquisition off. Five checks on the official January 2026 Swiss boundaries passed with explicitly synthetic jurisdictions. Notification rights are independently rechecked before consented email. Lifecycle suites passed 95 and 43 tests; cleanup/migration passed two; extended email/API/event/migration passed 58. Native CAP channel/rights/current coverage and live acceptance remain open; MV2-028 stays IN PROGRESS and unpublished. See [lifecycle evidence](docs/monitoring-v2/HAZARD_WATCH.md#lifecycle-and-source-readiness-13-september-2026) and [email evidence](docs/monitoring-v2/HAZARD_WATCH.md#consented-warning-email-13-september-2026).

<a id="mv2-029"></a>

### MV2-029 — C1: Home/Office locations and the complete warning workflow

**Native source integration, 14 September 2026:** Private start, source-bound
events, original reader, material re-review, Today/Inbox and consented delivery
now consume the native complete Swiss MeteoAlarm snapshot. Withdrawn or stale
warnings cannot become current instructions or mail; retained history stays
explicitly historical. The full 360-test Hazard suite and 60 browser checks
passed. Default source coverage is wind/thunderstorm only; other hazard types,
production operation and human acceptance remain open. Status stays IN PROGRESS.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-028](#mv2-028). **Requirements:** §8; AC-C1-01…10.

**User outcome:** Only people affected by the area receive the warning.

**Work:** Multiple saved locations, hazards/minimum importance, Review/View official/Not relevant/Mute type; active and historical warning state.

**Acceptance criteria:**

1. Satisfy AC-C1-01…10; Home inside the affected geometry receives a warning, while Home outside it does not.
2. New instructions, severity, geography, time or cancellation create a material revision; formatting/timestamp refreshes do not.
3. Verify that material escalation reopens a reviewed item; an all-clear closes the active source event while retaining review history.
4. Critical source instructions are visible without AI; show the official source and freshness alongside them; no-data is not shown as an all-clear.

**Verification:** E2E multi-location, boundary, changed instructions, reviewed→reopened→all-clear, mute and offline-model checks.

**Active scope, 13 September 2026:** C1 is the next independent direction while C2/C3/B2 access gates remain open. Implement the complete private-location warning workflow under the [Hazard Watch contract](docs/monitoring-v2/HAZARD_WATCH.md). Official CAP Suisse 1.1 defines a usable protocol contract, but FOCP describes third-party integration as planned by 2027; a current feed and source-specific reuse agreement are unverified. Source discovery does not establish current warning coverage. The local bounded CAP decoder, tri-state point geography and immutable predecessor ledger are implemented with synthetic fixtures. The final affected suite passed 63 tests in 0.54s, including the backlog invariant; required API Ruff and whitespace checks passed. Translation/technical updates retain evidence without incrementing material review state; late ancestor cancellation cannot close a newer warning. The private location draft workflow is now implemented across two tenant-scoped tables, owner-checked HTTP routes and the five-language reader, with CAS/idempotency, bounded history, archive/delete confirmation and a gated Monitoring Centre inventory. The corrected private HTTP/repository/auth/migration/compose/backlog suite passed 36 tests; 26 hazard/centre/Road API regressions passed, and the root web build passed. Isolated synthetic Chrome verified save/edit/history/archive/delete, denial redaction and five-language mobile forms; two full-document axe audits had zero violations with shared Marvin contrast incomplete. Current source access, reviewed administrative/radius geometry, durable warning evidence, active event lifecycle, delivery, live release and human acceptance remain open; no real source or monitor has been activated.

**Geography follow-up, 13 September 2026:** The native Swiss boundary catalogue and radius matcher are locally verified (107 combined tests plus seven checks against the checksum-verified official January 2026 file). They distinguish Swiss membership from source coverage and from whole-radius coverage. The draft API remains gated until the runtime catalogue and source permissions are installed; municipality warning matching, active lifecycle/review/mute/Today/Inbox and consented delivery remain unfinished. MV2-029 remains IN PROGRESS; no production source or user monitor changed.

**Runtime preview follow-up:** The five-language private preview now reports actual installed-catalogue membership or specific geography failures, with attribution and edition. Editing clears stale proof; administrative confirmation does not enable source monitoring or prove whole-radius coverage. Fifty affected backend tests, root web build and isolated browser workflow/locale/accessibility checks passed. Runtime installation was exercised only in a fresh local QA directory with the official checksum-verified archive. Full C1 lifecycle, source access, municipal warning matching, review/delivery and live acceptance remain IN PROGRESS.

**CAP geography follow-up:** The worker geometry entry point now distinguishes exact polygon/circle hits from whole-municipality administrative-filter matches. A matching filter alone never confirms a specific house; holes, radius overlap, unknown code editions and catalogue revocation are preserved. The 110-test affected suite and seven additional synthetic-warning checks on real Basel boundaries passed. Full official event persistence/lifecycle, review/mute/Today/Inbox, delivery and live acceptance remain unfinished; MV2-029 is IN PROGRESS.

**Durable source journal follow-up:** The private workflow now has a tested shared CAP journal to build on: exact immutable revisions, material sequence, rights rechecks and unavailable states preserve official meaning. Synthetic persistence/private API tests passed (113 combined; 38 source tests after final bounds). No private warning projection, active monitor lifecycle, review/mute, Today/Inbox or email was added by this internal journal. Those remain the next work; MV2-029 is IN PROGRESS and unpublished.

**Private event workflow follow-up:** Owner-private affected-place developments, exact historical source readers, material review/dismissal and immutable action history, plus per-place type mute are implemented in the gated API. New instructions reopen review; translation additions retain it; explicit all-clear and Cancel remain distinct. Multiple hazards cannot be silenced by muting only one selected type. Source/configuration/geography changes redact unconfirmed current data. The corrected 87-test backend/API suite, final 65-test mute suite and cross-organization cleanup check passed. Frontend event workflows, Today/Inbox, activation/pause/resume/archive, scheduling and consented delivery remain unfinished. MV2-029 remains IN PROGRESS and unpublished; synthetic active fixtures do not authorize real activation.

**Event UI follow-up:** Exact current/historical readers, source-language selection, review/dismiss with exact-revision audit and per-place type mute are now available in five languages. New instructions reopen review; translation-only updates preserve it. Malformed historical links never fall back to current, and delayed requests cannot repopulate another location. Final root build, three link/URL helper tests, 22 event-browser checks and 19 draft regressions passed. Desktop/mobile axe reported zero violations with shared Marvin contrast incomplete; final screenshots were inspected. Today/Inbox, active lifecycle, polling/maintenance, consented delivery and native/live acceptance remain open. MV2-029 stays IN PROGRESS; these fixtures do not activate any real source or monitor. See [reader evidence](docs/monitoring-v2/HAZARD_WATCH.md#official-warning-reader-and-private-actions-13-september-2026).

**Today/Inbox follow-up:** Five-language private summaries now show unread 48-hour material changes in Today and active/planned warnings or alarms in Impact inbox. Exact revision links open original instructions; review/dismiss/mute suppress cards and new material instructions reopen them. Translation does not renew the Today window. Pagination, unavailable states, retry and membership redaction are verified. The corrected 44-test integration suite, 16-test final Today suite, root build and 38 browser checks passed; four axe audits had zero violations with shared Marvin contrast incomplete. Active lifecycle/readiness, collection/maintenance, consented delivery and native/live acceptance remain open. MV2-029 remains IN PROGRESS and unpublished. See [Today evidence](docs/monitoring-v2/HAZARD_WATCH.md#private-today-and-impact-inbox-13-september-2026).

**Lifecycle and consented delivery follow-up:** Owner/version-checked start, pause, resume and archive now retain action history and cancel old work; stopping remains possible after source loss. The five-language controls expose readiness, check times and audit. Email is separately opt-in to a verified owner address, with quiet hours/DST-aware daily scheduling, no translation/history resend, overlapping-place deduplication and source/geometry/consent/review/mute checks immediately before fake SMTP. Failed or abandoned sends are uncertain and never automatically replayed. The final lifecycle suite passed 43 tests; extended email/API/event/migration passed 58; root lifecycle/email builds, 50 lifecycle/event browser checks and 19 email browser checks passed. Eight combined document axe audits had zero violations (shared Marvin contrast incomplete); screenshots were inspected. The entire feature remains local and unpublished pending native access/rights/current coverage, runtime installation and live/human acceptance; MV2-029 stays IN PROGRESS. See [current workflow evidence](docs/monitoring-v2/HAZARD_WATCH.md#consented-warning-email-13-september-2026).

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

### MV2-033 — C6: River / Lake thresholds, history and consented digest

**Today / Inbox follow-up, 14 September 2026:** The missing River cards now reuse retained changes and exact review/evidence on Today and Impact Inbox. See [complete scoped journey and verification](docs/monitoring-v2/RIVER_TODAY.md). River-only unreviewed counts do not claim a global unread total. Existing release and human acceptance remain VERIFYING.

**Active whole-feature scope, 14 September 2026:** Complete the C6 digest reuse
in specification §13.8: explicit verified-owner delivery settings, preview,
durable quiet-hour/daily email and exact private change links. Current numeric
condition, source freshness, configuration, review and consent must hold before
SMTP; no historical backfill or ambiguous retry. See the [complete acceptance
scope](docs/monitoring-v2/RIVER_LAKE_WATCH.md#active-complete-feature-consented-river-digest--14-september-2026).
MV2-012/022 are scoped contributions; C6/human acceptance remains VERIFYING.

**Digest execution evidence, 14 September 2026:** Complete consent/settings/preview,
durable delivery and exact private reader implemented with final source/numeric and
access revalidation. Same-clock current-reading and rise-baseline corrections retain
original evidence and suppress obsolete alerts. Regression runs: 89 passed and final
40 passed (overlapping); eight browser axe checkpoints without violations, five
locales/mobile/viewer redaction, root build, formatting and exact API lint passed.
Migration preserves source observations and prior changes. Tests used fake SMTP.
See [digest acceptance](docs/monitoring-v2/RIVER_LAKE_WATCH.md#consented-digest-acceptance--14-september-2026).
Actual release and human/source acceptance remain open.

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

### MV2-034 — C7: Basel and Lugano hourly/daily air-quality series and interpretation

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

**Lugano feature evidence — 14 September 2026:** The complete station feature adds independently checked NABEL data-query rights, bounded hourly collection and revision history for O3/NO2/PM10/PM2.5, fixed CET source labels, station selection/attribution in five languages, and the existing private lifecycle, Today/history and consented digest. The actual collector retained 384 readings, including all four metrics at 07:00 UTC. Root build and the Lugano browser journey passed nine full-document axe checkpoints. See [scope, rights and evidence](docs/monitoring-v2/AIR_QUALITY_WATCH.md#lugano-station-feature-scope--14-september-2026). Exact activation and human acceptance remain VERIFYING; other national stations and official category/daily-max interpretations are not claimed.

**Official daily feature evidence — 14 September 2026:** Native Basel and Lugano daily acquisition, period-separated immutable history, O3 daily maximum of hourly means and other pollutant daily means, completed-source-date display, independent thresholds/recency/gaps and consented final-send checks are implemented. Actual collectors retrieved seven complete dated reports per station (28 readings each). The full Air suite passed 96 tests; root build and two nine-checkpoint browser journeys passed. See [daily scope and evidence](docs/monitoring-v2/AIR_QUALITY_WATCH.md#official-daily-air-feature-scope--14-september-2026). Exact activation and applicable human acceptance remain VERIFYING; no official risk category is invented.

<a id="mv2-035"></a>

### MV2-035 — C7: Air Quality — changes, improvements and consented digest

**Official daily feature evidence — 14 September 2026:** Native Basel and Lugano daily acquisition, period-separated immutable history, O3 daily maximum of hourly means and other pollutant daily means, completed-source-date display, independent thresholds/recency/gaps and consented final-send checks are implemented. Actual collectors retrieved seven complete dated reports per station (28 readings each). The full Air suite passed 96 tests; root build and two nine-checkpoint browser journeys passed. See [daily scope and evidence](docs/monitoring-v2/AIR_QUALITY_WATCH.md#official-daily-air-feature-scope--14-september-2026). Exact activation and applicable human acceptance remain VERIFYING; no official risk category is invented.

**Lugano feature evidence — 14 September 2026:** The complete station feature adds independently checked NABEL data-query rights, bounded hourly collection and revision history for O3/NO2/PM10/PM2.5, fixed CET source labels, station selection/attribution in five languages, and the existing private lifecycle, Today/history and consented digest. The actual collector retained 384 readings, including all four metrics at 07:00 UTC. Root build and the Lugano browser journey passed nine full-document axe checkpoints. See [scope, rights and evidence](docs/monitoring-v2/AIR_QUALITY_WATCH.md#lugano-station-feature-scope--14-september-2026). Exact activation and human acceptance remain VERIFYING; other national stations and official category/daily-max interpretations are not claimed.

**Active whole-feature scope, 14 September 2026:** Complete the §14.8 Air digest
with explicit owner consent, saved preview, durable delivery and exact private
change reader. Preserve pollutant/period/hysteresis semantics and recheck current
source versions, complete windows, review and access before SMTP. Existing licensed
Basel access is sufficient; no national coverage or medical claims are implied.
See [scope and acceptance](docs/monitoring-v2/AIR_QUALITY_WATCH.md#active-whole-feature-consented-air-digest--14-september-2026).
MV2-012/022 are scoped contributions; field/human acceptance remains VERIFYING.

**Digest execution evidence, 14 September 2026:** Complete owner consent/settings,
saved preview, durable email and exact private reader implemented. Final-send checks
bind current pollutant/period input revisions and the hysteresis projection; muted,
withdrawn, stale, superseded or unreviewable evidence cannot send. Migration preserves
existing observations and changes. Final Air delivery suite: 26 passed; 89 tests
passed in the expanded Air/River/Centre run before correcting one hourly fixture
(overlapping counts). Root build, formatting, exact API lint and nine browser axe
checkpoints passed across five locales/mobile/viewer access. See [digest acceptance](docs/monitoring-v2/AIR_QUALITY_WATCH.md#consented-digest-acceptance--14-september-2026).
No real mail, broader national source coverage or production activation is claimed.

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

**Active whole-feature scope, 14 September 2026:** Implement the three-source
location-story workflow, verified geography/time associations, exact private
source readers and reversible grouping/splits. Road's TMC identity currently
has no cross-source geographic mapping; a separately reviewed binding is
required. Retain all four acceptance criteria and live source gates. See
[scope and acceptance](docs/monitoring-v2/RELATED_DEVELOPMENTS.md).

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Backend + UX · **Size:** M

**Dependencies:** [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-029](#mv2-029), [MV2-033](#mv2-033), [MV2-041](#mv2-041), [MV2-071](#mv2-071). **Requirements:** §§13.7,29.

**User outcome:** A flood and a road closure can be reviewed together.

**Work:** Associate records across sources using verified identifiers, geography and time; provide a grouped overview, evidence for each event, explainable links and reversible splits.

**Acceptance criteria:**

1. River danger, Alertswiss and a road closure can be linked to one location story without losing their separate authority IDs.
2. Proximity in time alone does not prove a common cause; an unconfirmed relationship is labelled as possible.
3. Conflicting sources are displayed separately; cancellation of one event does not close the others.
4. Merging or splitting does not duplicate delivery or automatically transfer review decisions from another event.

**Verification:** A three-source fixture, an unrelated nearby-location negative case, and correction/split replay.

**Execution evidence, 14 September 2026:** Complete private `/related-developments`
workflow implemented with actual Hazard/River/Road readers, additive durable
stories/revisions, explicit operator-reviewed municipality bindings, grouping,
reversible membership splits, exact source links, history and current-reference
refresh. Shared desktop/mobile navigation exposes the five-language view without
a rollout flag. Contract/storage/repository/real HTTP/backlog suite: 34 passed;
affected boundary/domain regressions: 79 passed; root production build passed;
13 full-document browser axe checkpoints passed with synthetic source responses.
See [detailed evidence and operator workflow](docs/monitoring-v2/RELATED_DEVELOPMENTS.md).
No domain decision or delivery is transferred. All four AC remain in force;
exact main-site activation, permitted live three-source geography/source review
and human usefulness acceptance remain open, so this task is not DONE.

<a id="mv2-037"></a>

### MV2-037 — Journey/Trip/Route/Stop and Road Corridor reference data

**Current C2 iteration, 12 September 2026:** The transport subset of MV2-037 and MV2-038/039 is in source-contract discovery and local reference validation. [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md) records complete-feature acceptance and exact gaps: anonymous live feeds return 401; authenticated binary samples/static version matching and the 2/5 requests-per-minute contradiction remain open. No transport capability or road-reference completion is claimed; publish only after the entire feature is ready.

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Integration + Backend · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-015](#mv2-015), [MV2-016](#mv2-016), [MV2-071](#mv2-071). **Requirements:** §§9.4–9.8,10.3–10.5.

**User outcome:** A transport subject is matched using a stable entity.

**Active renewal scope, 13 September 2026:** Preserve saved reference UUIDs across service dates and pinned timetable versions by finding an exact, unique agency/route/direction/ordered-stop/departure match in the new static archive. Source trip IDs may change; city/name similarity is not a mapping. Acceptance requires calendar exceptions, overnight/DST dates, ambiguity/missing matches, immutable prior mappings and a private monitor resolving the renewed mapping without a configuration rewrite. The import remains bounded and off the request path; scheduled archive acquisition and actual feed matching are separate unfinished gates.

**Automatic renewal integration scope, 13 September 2026:** Connect the shared static cache to durable bounded renewal of imported public references and known ordered connections for upcoming local departure dates. Preserve a shared continuation cursor, reuse the archive across users, perform long archive scans outside database transactions, and atomically publish exact dated mappings with progress only after source/lease/reference revalidation. Acceptance includes restart/replay, old-trip-ID replacement without private configuration changes, overnight dates, denied/ambiguous connections, and revocation or lease loss during scanning. This does not create source access or expand imported coverage into a full-network journey planner.

**Shared static collector, 13 September 2026 (local):** Exact CKAN lookup and bounded public ZIP retrieval now run through a default-off shared Celery collector. Both fresh permitted live feeds must identify the same timetable version. A durable lease/cooldown prevents duplicate downloads; immutable dataset/resource/hash bindings, verified reuse, bounded cache retention and denial/backoff preserve source identity. Collector/retrieval/live-source/catalog/migration checks passed **92 tests in 11.78s**, with exact API Ruff passing. The automatic renewal integration below extends this verified boundary. HTTP/ZIP data is synthetic; permitted live catalog/download access, real-feed matching and complete C2 acceptance remain unfinished. No credentials, grants or production activation were created. See [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md).

**Automatic renewal evidence, 13 September 2026 (local):** The collector now retains its shared lease while renewing imported public references and known connections from the cached archive. A durable cursor processes bounded batches over eight upcoming local departure dates, accounting for GTFS service-day offsets. Long scans hold no database connection; final source/lease/reference revalidation and mapping/cursor publication are atomic. New source trip IDs preserve private selections; changed/absent/ambiguous transfer rules retain their actual outcomes. The affected renewal/parser/catalog/collector/migration suite passed **125 tests in 24.98s**; final automatic-worker tests passed **10 tests in 7.47s**, including rollback/retry without another download and connection pagination. API Ruff passed. No source access, browser acceptance, release or full MV2-037/C2 completion is claimed.

**Deployment configuration evidence, 13 September 2026 (local):** Production Compose now explicitly passes Tender/Commute source controls, keys, permission IDs, redirect origins and quotas to API-based containers. Defaults remain disabled with empty credentials; Air/River controls retain their existing true defaults. Both environment examples document the controls. Twelve read-only Compose/application deployment checks passed with synthetic configuration, proving matching backend settings, effective source disablement despite populated keys and no transport credentials in web/other service environments. This renders configuration only; no deployment or production environment was changed.

**Road-reference evidence, 13 September 2026 (local):** `road_topology.py` validates normalized versioned TMC links and exact corridor flows, independently of railway references. Matching uses source-relative direction, reviewed adjacency and inward integer-metre offsets; missing topology/geometry, circular ambiguity and version mismatch stay unknown. The affected Road Watch suite passed 211 checks with temporal/materiality and source-pipeline compatibility (`.tmp/road-decisions.log`). `road_catalog.py` now persists reviewed topology grants, stable corridor UUIDs and exact-version maps, with distinct matching/display/notification rights, generation conflicts and retention. Latest denied revisions never fall back to older grants. The affected catalogue/source/collector/matching suite passed 148 tests in 17.84s (`.tmp/road-catalog.log`), including migration parity and rollback. Topology remains synthetic; licensed native-table import, actual A2/Gotthard/A13 coverage and full MV2-037 acceptance remain open.

**Renewal evidence, 13 September 2026 (local):** Exact bounded archive matching and an operator dry-run/apply command are implemented. Unique matches preserve reference UUIDs and private settings while recording the new trip IDs, source sequences and archive hashes. Missing/ambiguous/frequency/outside-feed outcomes stay explicit. The combined renewal/static/catalog/backlog suite passed 58 tests in 6.74s; the command's help and required API Ruff passed. Scheduled archive acquisition/renewal, real-source matching and road references remain open. See [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md); no MV2-037 closure or source activation is claimed.

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

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071). **Requirements:** §9; AC-C2-02,06,07,08.

**User outcome:** A regular journey receives the official disruption state.

**Durable processing update, 13 September 2026:** Bounded latest-feed storage binds internal source permission, source time, static version and original hash. The private worker persists checkpoints, material event history and review candidates atomically through the existing durable dispatcher. A separate shared binary collector now enforces source grants, lease ownership, request cooldown/backoff, bounded compression and reviewed redirects without sending private routes or forwarding keys to storage origins. Replay, missing/stale/future data, source revocation and historical evidence remain distinct. Actual service-dispatch and HTTP-collector tests use synthetic grants and binary fixtures; authenticated samples, redirect-origin review and real-source acceptance remain open. See [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md).

**Active local scope, 13 September 2026:** The binary GTFS adapter validates bounded full snapshots, preserves source IDs/languages/periods and distinguishes replay, disappearance, stale measurements and static-version changes. Exact stop-sequence projection covers explicit cancellation, skipped endpoints and boarding departure forecasts; changed-stop mappings and unsupported capabilities stay explicit. Local acquisition and durable processing are integrated; authenticated source samples and complete scenario acceptance remain open. No live release is claimed.

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

**Visible timed-pause evidence, 14 September 2026:** The existing pause-today
journey now shows its precise Zurich midnight expiry in Commute settings and
the shared Centre. DST, persistence, expiry, privacy and full browser workflows
passed (127 combined API tests; 33 full-document axe checkpoints across both
readers; root build and exact Ruff). See [evidence](docs/monitoring-v2/COMMUTE_TIMED_PAUSE.md).
This completes the scoped visible-pause feature, not live transport acceptance.

**Release regression, 14 September 2026:** Reproduced the failed production
connection-renewal replay across a ZIP timestamp change. Fixed the synthetic
archive's nondeterministic metadata; unchanged inputs now replay identically,
while changed source evidence still conflicts. All 141 fixture-consumer tests
and exact API Ruff passed. See [Transport Watch evidence](docs/monitoring-v2/TRANSPORT_WATCH.md).
No source permission, production validation or deployment gate was weakened;
live access and whole-direction acceptance remain open.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-038](#mv2-038). **Requirements:** §9; AC-C2-01…10.

**User outcome:** Alerts relate to the route and the journey time.

**Dated connection renewal, 13 September 2026 (local):** Renewal rechecks known ordered interchange pairs for new dates/versions, preserving old proof and private choices. It is now invoked by the shared cached-archive collector through a durable bounded cursor; unavailable mappings remain explicit. The automatic worker resolves archives outside database transactions and atomically records verified mappings, fresh connection outcomes and progress after revalidation. The affected combined suite passed 125 tests; final worker checks passed 10 tests, including a saved two-leg journey becoming startable only when the renewed interchange is usable. Actual feed coverage, complete browser evidence, release and acceptance remain open. See [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md); C2 remains IN PROGRESS and unpublished.

**Interchange implementation, 13 September 2026 (local):** Exact pinned GTFS interchange evidence now replaces the blanket multi-leg start prohibition for verified connections. The importer retains endpoint, source rule, minimum time and immutable leg/archive proof; ambiguous, prohibited or unverified connections remain blocked. Preview explains rules in five languages, while processing and email recheck current proof. A synthetic two-leg journey starts, records source-backed history and stops producing new notifications after proof removal. The combined suite passed 120 tests, final focused suite 33 tests, and the root web build passed. The 25-checkpoint browser harness remains unverified. Automatic archive/interchange renewal, real source matching and pilot acceptance remain open; see [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md). No production activation or whole C2 completion is claimed.

**Active notification scope, 13 September 2026:** Complete owner-opted-in immediate/daily transport email with verified-address consent, immutable settings revisions, quiet hours, exact event links, deduplication and a durable pre-send eligibility check. Enabling email must not backfill earlier signals or mark Today read. Outside-window candidates require daily-digest opt-in. Revoked source permission, changed identity/settings, pause/mute/review and ambiguous SMTP outcomes must prevent unsafe retries. Source activation, live email and human acceptance remain separate evidence gates.

**Notification implementation evidence, 13 September 2026 (local):** The additive consent/delivery schema, owner-only settings/preview API, atomic intents, quiet-hours/daily scheduling and durable pre-send rechecks are implemented. The combined backend regression passed 89 tests and the final delivery suite passed 34 tests with a fake mailer, including the actual service dispatcher. Verified-address consent is separate from journey settings and Today review, and enabling mail creates no history backfill. Uncertain SMTP attempts are retained without automatic resend. Saved journeys now expose five-language email preferences with explicit consent, quiet hours, verified-address and role gates, saved-settings preview and conflict/denial redaction. The root web build passed; the extended browser harness is not yet verified. Live delivery, source acceptance and the full browser scenario remain unfinished; see [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md). C2 stays IN PROGRESS and unpublished.

**Today integration, 13 September 2026 (local):** Private Today cards now project existing unread transport signals with current source rights, active configuration, pause/mute/review filters, bounded sparse pagination and stale/missing availability. Cards explain why an update appears and link to an exact immutable event version independently of history pagination. The reader preserves that version beside the latest known state and rechecks ownership and permission. The HTTP/privacy suite passed 23 tests; the combined transport/inventory/backlog suite passed 252 tests and the full root web build passed. Browser acceptance remains pending because the isolated test browser exited during startup and its harness stalled; no browser pass is claimed for this update. This adds no email delivery or source activation. C2 remains IN PROGRESS pending the complete scenario, real feeds and pilot acceptance.

**Durable lifecycle update, 13 September 2026:** Start/resume check current source permission, fresh stored feeds and an eligible dated single-leg journey, then enqueue durable processing. Private event history, exact review/mute, scheduler, cancellation and generic job-owner guards are integrated locally with a separately gated shared collector. The five-language `/commute-watch` interface now supports catalog selection, preview, private drafts, full lifecycle and event/settings history, with owner-private Monitoring Centre discovery. Connected multi-leg start is explicitly gated on interchange evidence. Review candidates are not email delivery; outbound digest integration, live source setup and real acceptance remain open. No production activation is claimed.

**Active local scope, 13 September 2026:** Private configuration and per-leg/journey evaluation cover weekdays/Zurich windows, thresholds/hysteresis, pause today, mute, outside-window policy and cancellation priority. A zero boarding delay cannot restore an unconfirmed skipped alighting stop. Additive catalog/private-state migrations and the authenticated CSRF-protected API cover owner isolation, dated static identity, CAS/replay/rollback and migration parity. Browser preview now resolves the exact permitted or uniquely dated timetable without requiring a technical archive identifier. Local UI tests cover source/role gates, lifecycle, review, pagination, conflicts and clearing denied or superseded responses. Notification integration, real-source matching and human acceptance remain open. See [Transport Watch](docs/monitoring-v2/TRANSPORT_WATCH.md); this task stays IN PROGRESS.

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

**Completed local feature scope, 15 September 2026 — recurring closures:** Decode the
source's DATEX II 2.2 Period / TimePeriodByHour and DayWeekMonth selectors,
including repeated night windows and exception periods, with explicit source
clock offsets. Resolve current and next eligible intervals under overall bounds;
preserve start-day semantics across midnight, month/week filters and exception
precedence. Never infer a timezone from an instant or silently convert missing
calendar/clock semantics into a closure, reopening or safe route. Unsupported
extensions and unqualified clocks remain explicit unavailable capabilities.
Use bounded expansion and preserve pre-feature stored evidence/hash identities.
The existing licensed topology, source freshness/rights, private profile, review,
Today and consented delivery workflows are dependencies, not new permissions.
Show recurring-source context and the evaluated interval in all five languages.
Acceptance: actual XML fixtures, midnight/offset/calendar/exception boundaries,
rescheduling and repeated polling, current interval transitions through private
history and notification eligibility, stale/revoked source denial, old-evidence
compatibility, browser presentation, lint/build and backlog integrity. No live
ASTRA feed or licensed corridor coverage is claimed by synthetic examples.
**Verification:** 139 core, 110 integrated and 73 final affected checks passed;
final compatibility/mapping checks passed (4), as did 12 five-language browser
axe checkpoints, root build and exact lint. See [evidence](docs/monitoring-v2/ROAD_RECURRING_CLOSURES.md).


**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Active complete-feature scope, 13 September 2026:** C3 is the next direction while C2 awaits external acceptance. [Road Watch](docs/monitoring-v2/ROAD_WATCH.md) defines the source/rights, versioned TMC corridor mapping, immutable lifecycle, private workflow and end-to-end gates for MV2-037/040/041. The local SOAP/DATEX decoder, full/delta reconciliation, permission-bound repository, default-off shared collector and retention schedule handle repeated version zero, replacement record sets, cancellation and private-note exclusion. Official historical examples replay as created/material_changed/revoked with 6/3/3 records. Unsupported extensions and unreviewed response contracts remain explicit. Licensed topology, private workflow and live acceptance remain unfinished. No live query, key, actual source permission or corridor coverage is claimed.

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-037](#mv2-037), [MV2-071](#mv2-071). **Requirements:** §10; AC-C3-02,04,05,07,08.

**User outcome:** Known roads have states and planned changes supported by source evidence.

**Work:** Permitted ASTRA/FEDRO feeds; DATEX or another confirmed format; segment/direction, lane/full closure, incident, congestion/delay and planned time windows. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Access, the six-month access period and renewal are tracked; raw machine-readable redistribution is prohibited according to the source policy.
2. Closures and measured congestion/delay are separate capabilities: one safety feed is insufficient to claim coverage of all road states.
3. Planned/live events, rescheduling and reopening are normalized; source instructions and evidence are preserved in a permitted form.
4. Coverage and direction for A2/Gotthard/A13 are confirmed; estimated_delay is UNKNOWN when the feed does not provide it.

**Verification:** Contract probe and replay of full/lane closures, roadworks, missing delay, planned rescheduling and reopening.

**Local implementation evidence, 13 September 2026:** Source storage and Commute migration compatibility passed 138 checks (`.tmp/road-storage-verified.log`). Collector/storage/decoder/reconciliation/Compose passed 155 checks (`.tmp/road-collector-final.log`); the subsequent provider-clock overlap regression and affected collector suite passed 33 (`.tmp/road-collector-clock.log`). Source migrations `f2ce409d70f4` and `a3df51ae81a5` are locally verified, totaling seven road tables. Coverage includes bounded private-free SOAP requests, ownership/cooldown, full/delta recovery, rollback, permission expiry during storage, cleanup with acquisition disabled and main backend configuration. Actual live response behavior, licensed corridor mapping, private reader, full feature commit/push and activation remain unfinished. Full end-to-end and human acceptance remain open.

<a id="mv2-041"></a>

### MV2-041 — C3: My Route Watch for A2 / Gotthard / A13

**Recurring closures, 15 September 2026:** Explicit-offset daily and calendar
recurrences now flow through private history, current/next interval display and
consented delivery. Existing review stays attached to its original version;
ending a window is not physical reopening. Decoder, private workflow and browser
checks passed; see [source limits and acceptance evidence](docs/monitoring-v2/ROAD_RECURRING_CLOSURES.md).
Missing source timezone semantics remain unknown. Live source/corridor permission
and broader C3 acceptance remain open.


**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Active scope, 13 September 2026:** Deliver C3 with the source work in MV2-040: verified corridor/direction selection, private profiles, material history/review, explicit missing-data state and consent-aware notifications. Exact TMC matching, durable reviewed corridor publication, private profiles/API, event processing/history/review and source-gated start/pause/resume/archive are implemented locally. The five-language reader and gated Monitoring Centre route inventory are implemented locally; TypeScript, reader/help checks and all 56 affected API/profile/worker/centre cases pass after correcting one test expectation; later browser/build evidence follows below. An A2/A13 name in text is not proof of northbound/southbound intersection. Source fixtures and licensed topology must prove the requested corridors before activation. See [Road Watch](docs/monitoring-v2/ROAD_WATCH.md). Today and exact-version comparisons are now implemented locally with permission rechecks, sparse pagination and independent mute/review state. The Today/jobs/API suite passed 48 tests and the final Today/exact-link HTTP suite passed 21 tests. Root and final web builds passed. Synthetic Chrome checks cover exact links with empty lists, previous/current comparison, sparse Today continuation, mute, stale data, permission redaction and five-language mobile layout. Four axe checkpoints reported zero violations; the shared Marvin contrast node remains incomplete. See Road Watch for evidence and limitations. Consented email is now implemented locally: explicit verified-owner policies, quiet hours/daily schedules, bounded intents, current rights and state rechecked before SMTP, and suppression of ambiguous retries. Delivery/source/worker/migration checks passed 78 tests; 69 API/Today/release-history checks and the corrected HTTP-to-fake-SMTP case passed. The final delivery suite passed 35 tests, including current mapping changes before SMTP and independent owners; five owner-isolation/backlog checks passed, and the root web build passed. Chrome verified consent, preview, access redaction and pause/edit/preview/save/start/resume/archive/delete; the email form had zero axe violations (shared Marvin contrast incomplete). Migration e71395e2c5e9 adds two tenant-scoped tables. Major-closure Impact Inbox is now implemented locally with private ownership, exact shared read/mute state, bounded sparse pagination, long-running current closures and honest unavailable-source metadata. The Inbox/Today/delivery suite passed 73 tests; the HTTP-to-fake-mail/shared-review case passed, and the final root build passed. Chrome verified sparse continuation, mute/unmute, stale-source redaction, mobile read and shared Today state; the desktop axe audit had zero violations (shared Marvin contrast incomplete). Native licensed-table import, complete acceptance and live verification remain unfinished; no actual source or user monitor was activated.

**Dependencies:** [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-010](#mv2-010), [MV2-012](#mv2-012), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-040](#mv2-040). **Requirements:** §10; AC-C3-01…10.

**User outcome:** The user knows about a material change on a saved corridor.

**Work:** Multiple corridor selection, direction, event types, minimum delay, planned overnight closures, comparison, source, review and history.

**Acceptance criteria:**

1. AC-C3-01…10 are met; a northbound filter excludes southbound and unrelated segment events.
2. OPEN→CLOSED, lane restrictions, roadworks/accidents and rescheduled closures are displayed correctly.
3. Repeated traffic records for one event are combined; reopening preserves history.
4. The 15-minute threshold is applied only to a valid delay; a missing delay does not suppress an explicit full closure.

**Verification:** End-to-end checks for the opposite direction, a planned date shift, no delay value, closure/reopening and duplicate language editions.

**Local execution evidence, 13 September 2026:** Pure matching/time/source checks passed 211 tests (`.tmp/road-decisions.log`); private profile/API/catalogue/storage checks passed 73 (`.tmp/road-private-bounds.log`). The integrated worker/profile/API/catalogue/source/collector suite now passed **125 tests in 99.03s** (`.tmp/road-worker-final.log`), including stable material history across source record replacement/language editions, planned rescheduling, opposite-flow exclusion, source disappearance versus withdrawal/clearance, exact review/mute, source/topology redaction/retention, lifecycle cancellation, owner/job isolation and fourteen-table migration parity. Final job-lease/cancellation and probable-clearance regressions passed **23 worker tests in 37.85s** (`.tmp/road-worker-lease.log`), including real durable dispatch and authenticated HTTP review. Required API Ruff passed. Reader/Today/centre, consented delivery, native licensed-table import and real-user acceptance remain required before full feature commit/push and closure.


## F5 — Business scenarios

<a id="mv2-042"></a>

### MV2-042 — B2: SIMAP discovery and publication monitoring

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071). **Requirements:** §15; AC-B2-02,05,06,11.

**User outcome:** Public procurement notices arrive as new and changed entities.

**Work:** Official SIMAP API/client registration, pages/cursors, publication IDs and tender dossier linking; authority/CPV/region/language/deadline/documents/Q&A. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Active scope (12 September):** The user authorized all nine active directions. Public API parsing, publication-time gating, cursor recovery and durable collection are implemented locally under [Tender Watch](docs/monitoring-v2/TENDER_WATCH.md). A bounded real collector rehearsal reached private evidence storage; this does not prove a complete scan or activation. Source registration, restricted document/Q&A acceptance and the complete user workflow remain open.

**Acceptance criteria:**

1. Publications are not distributed before the source permits publication at 08:00; originals, commentary and the required notice remain distinct.
2. Access to public publications does not automatically grant access to restricted tender attachments; coverage of each field is explicit.
3. Corrections, cancellations, awards/status and multilingual publications are versioned without duplicate opportunities.
4. Backfill bounds and watermarks preserve late publications; prohibited documents are not retrieved through workarounds.

**Verification:** Contract/API fixtures for pagination, the publication gate clock, corrections and public versus restricted attachments.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-043"></a>

### MV2-043 — B2/B7/B8: Structured profiles and semantic candidate ranking

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Backend + AI · **Size:** L

**Dependencies:** [MV2-005](#mv2-005), [MV2-008](#mv2-008), [MV2-010](#mv2-010), [MV2-071](#mv2-071). **Requirements:** §§15.4,15.9,16.6,17.3,19.3,22.

**User outcome:** Business matching goes beyond a word in the title and is understandable to the user.

**Work:** Typed capability/brand/asset profiles, deterministic inclusion and exclusion rules; lexical candidates followed by bounded optional semantic assessment; match facets and unknown gaps.

**Active scope (12 September):** B2 typed profiles, deterministic per-lot matching and immutable private profile revisions are implemented locally under [Tender Watch](docs/monitoring-v2/TENDER_WATCH.md). Official CPV tree edges bind descendant matches to source evidence; missing taxonomy and qualifications remain explicit unknowns. Disabled B2 semantic assessment and an offline development/validation evaluator now bind exact quotes, profile/facts/model/prompt/schema identities, preserve deterministic exclusions, detect split leakage and report abstentions separately. The 98 contract/evaluation/matching checks use synthetic outputs and do not measure actual model quality. A bounded identified-model run, B7/B8 contributions and the complete B2 user journey remain open; no semantic promotion is implied.

**Acceptance criteria:**

1. A tender profile stores CPV/capabilities, regions/languages/exclusions, size and qualification constraints; the example score of 70 does not become an unvalidated default.
2. An asset profile has category/location/keywords/brands/price; UNKNOWN price does not produce a “within budget” result.
3. SEMANTIC_MATCH has a versioned score/model/evidence; the LLM cannot bypass hard exclusions.
4. A qualification absent from the profile is an unknown gap, not proven noncompliance. DONE means implementation, schema and bounded evaluation on training/validation data under a disabled semantic flag; independent promotion in MV2-051 is not a reverse dependency.

**Verification:** An independent structured/semantic match set, hard exclusions, unknown fields, profile revisions and preview parity.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-044"></a>

### MV2-044 — Versioned document sets and conditions

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Backend + Frontend · **Size:** L

**Completed local feature scope, 15 September 2026 — XLSX tender conditions:**
Read already-permitted XLSX originals through the existing private attachment
store, preserving workbook/worksheet/cell locators and exact literal cell values.
Support referenced worksheets, inline/shared rich strings and finite numeric,
boolean and ISO-date literals without executing Office, macros, links or formulas.
Formula text is distinct and cached results are not asserted as current values;
formulas, unsupported formatting/embedded content and hidden structures make the
projection explicitly partial. Reject malformed/ambiguous/encrypted/macro or
oversized packages and preserve original bytes/hash on parse failure. Spreadsheet
comparisons must retain cell identity so moving a value cannot appear unchanged;
partial extraction cannot prove unchanged or removed requirements. Recognized
complete/partial originals download with .xlsx names, with five-language guidance
on literal values and limitations. Native owner/current-grant/retention checks,
immutable document revisions, source-specific collection rights and exact-byte
hashes remain authoritative. No source acquisition permission is added. Existing
OPC bounds, document store, comparison and reader are available dependencies;
Microsoft SpreadsheetML structure/shared-string/formula documentation defines the
format. Acceptance includes actual byte fixtures, hard negatives/quotas, literal
3-to-5 changes, moved cells/renamed sheets, formula/format unknowns, private HTTP
text/original/comparison and browser download/read/denial journeys, exact lint,
frontend build and backlog integrity. Finish the whole outcome before commit.
Live SIMAP documents/Q&A access, other formats and broader B2 acceptance remain open.

**XLSX verification:** 147 integrated checks and 73 final affected checks passed,
including actual XLSX HTTP comparison and a 3-to-5 replacement that preserves
the earlier decision and reopens review. Five-language reader/download checks,
36 browser axe checkpoints and the isolated frontend build passed.
See [scope, boundaries and evidence](docs/monitoring-v2/TENDER_XLSX.md).
Release activation is not yet verified.

**Dependencies:** [MV2-007](#mv2-007), [MV2-008](#mv2-008), [MV2-009](#mv2-009), [MV2-071](#mv2-071). **Requirements:** §§15.5,15.8,17.4,17.7,17.10.

**User outcome:** Changes to a file, requirement or Q&A remain visible after an earlier review.

**Work:** DocumentSetManifest: stable item ID, type, URL, hash, retrieval/version time and access status; add/replace/remove; link existing exact/legal diffs where applicable.

**Active scope (12 September):** B2 document-set reconciliation now includes local exact parsed-text comparisons and bounded PDF/UTF-8 parsing under [Tender Watch](docs/monitoring-v2/TENDER_WATCH.md). Binary and parsed fingerprints bind both private originals; missing rights, incomplete extraction and incompatible parsers never imply unchanged requirements. 61 document-set/comparison/parser tests and the full API Ruff gate passed. Private attachment originals now have scoped grants, bounded storage, current-rights read APIs and scheduled retention cleanup; the combined 260-test run passed. Public SIMAP search/detail access is verified; private immutable manifests now create material dossier revisions, preserve prior decisions, reopen review and create consented email intents; history/comparison APIs recheck grants and per-file denial. The integrated 243-test run and 67 final affected checks passed. The five-language attachment reader/comparison UI now covers exact originals, partial text, historical sets and denial recovery; its build and 30 browser checkpoints passed. Bounded DOCX parsing now includes referenced text stories, explicit partial/failed coverage and correct private original-download filenames; real package fixtures pass through storage, HTTP and exact comparisons. Unsupported Office/ZIP formats and live capture remain open. A pinned chronological review window now retains all revisions since the last decision, including explicit unavailable gaps and document links; final verification is recorded in the feature evidence. Authenticated documents/Q&A collection, provider-wide document-event normalization and the full user journey remain open. This local shared-contract work does not complete MV2-044 or B2.

**Acceptance criteria:**

1. New Q&A, a changed file at the same URL, document removal/withdrawal and changed conditions produce distinct deltas.
2. List reordering or a changed signed URL does not create a false material update.
3. Historical document sets and changed requirements link to exact permitted snapshots/locators; a denied attachment is unavailable, not removed.
4. Failed OCR/parsing does not invent content; the UI offers official evidence and identifies incomplete information.

**Verification:** Gold fixtures for document addition/replacement/removal/reordering/403, deadline versus body diffs and historical views.

**Execution evidence:** None yet; record the commit, tests/protocol, source/fixture version, reviewer and limitations at closure.

<a id="mv2-045"></a>

### MV2-045 — B2: Tender discovery, Today review and material updates

**15 September XLSX increment:** Already-permitted spreadsheet conditions now
retain sheet/cell evidence through private originals, exact comparisons and
material review reopening; see [acceptance](docs/monitoring-v2/TENDER_XLSX.md).
This closes the local XLSX format gap, with live documents/Q&A and broader B2
acceptance still open.

**Active whole-feature scope, 14 September 2026:** Add the missing Tender Today
and Impact Inbox entry across the owner's saved profiles, pending/following
filters, bounded public-summary cards and exact version links to the existing
evidence and internal decision workflow. Current restrictions and embargo apply
before pagination/counting. See [scope and acceptance](docs/monitoring-v2/TENDER_TODAY.md).
MV2-019/021 are scoped contributions; documents/Q&A access and broader B2 gates remain.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-022](#mv2-022), [MV2-042](#mv2-042), [MV2-043](#mv2-043), [MV2-044](#mv2-044). **Requirements:** §15; AC-B2-01…12.

**User outcome:** A company chooses Bid/No-bid/Monitor and sees changes to the conditions.

**Work:** Tender profile wizard, discovery candidates, follow tender, explanations of matched capabilities and gaps, explicit deadline, Q&A/document changes and owner.

**Active scope (12 September):** The local public-source journey now includes authenticated profile/lifecycle APIs, a five-language reader, private discovery/following/internal decisions, versioned originals and Monitoring Centre integration. Public evidence and common fields are deduplicated across lots; project CPV context never asserts verified lot relevance. Profile edits reassess unchanged publications and reopen review without rewriting prior decisions. Public-payload and private-version budgets now preserve all referenced history on capacity exhaustion; bounded cleanup checks references across tenants. Durable source restrictions gate retained reads, decisions and ingestion, including withdrawal during I/O and reuse of a restricted prior original for a diff. HTTP denials also carry no-store headers. HTTP and browser tests cover owner/tenant access, source gates, pagination, material updates, recovery and mobile accessibility. Owner-consented email now has separate immutable settings, exact-version intents, preview/send eligibility parity, quiet hours/DST, cross-monitor deduplication and current permission/review checks through the real job dispatcher. The five-language reader supports consent, unsubscribe, uncertainty, evidence deep links and paginated read-only profile history with current-profile differences; tests use fake SMTP only. Private document grants/storage/retention, material manifest revisions and the five-language original/text/comparison reader are implemented locally. Changes since the last decision have a separate chronological reader with current-rights gaps and pinned pagination. This remains unfinished whole-feature work: permitted live documents/Q&A collection, remaining-format coverage, semantic evaluation and live/human acceptance (including real email) are still required. The earlier unpublished/disabled state was superseded by the 13 September integrated publication and enabled production defaults; actual serving releases are verified separately. See [current evidence](docs/monitoring-v2/TENDER_WATCH.md).

**Acceptance criteria:**

1. AC-B2-01…12 are met; both discovery and following/updates are available.
2. A deadline change from 20→27, required references from 3→5 and Q&A v3 reopen the earlier review with the same tender ID.
3. Irrelevant opportunities are suppressed; explanations of matches and gaps link to evidence and do not promise eligibility.
4. BID/NO_BID/MONITOR records an internal decision; it never submits a bid; the digest includes new opportunities and material updates.
5. Without permitted capture/versioning/diffing of the required documents and Q&A, AC-B2-08 and the relevant part of AC-B2-06 remain BLOCKED; metadata alone or an unavailable badge does not satisfy this case.

**Verification:** End-to-end profile→publication→review→3-field revision→reopen→digest, negative cases and an unavailable attachment.

**Execution evidence, 14 September 2026:** Tender Today and Impact Inbox now provide a private queue across profiles with pending/following filters, bounded public-summary projections and exact version links into existing evidence/internal decisions. Current restriction/embargo gates precede pagination and counts; no source collection or decision occurs on read. Source publication, document and user acceptance gates remain open. See [verification and limits](docs/monitoring-v2/TENDER_TODAY.md).

<a id="mv2-046"></a>

### MV2-046 — B7: Official trademark publications and register updates

**Native acquisition scope, 14 September 2026 (before implementation):** Complete
durable native identity, atomic restartable page collection, retention-bound parent
evidence, publisher backoff and visible source readiness through the existing
private candidate journey. Repeated records during ascending traversal must not
be mistaken for a snapshot or complete coverage. See [scope, dependencies and
acceptance](docs/monitoring-v2/TRADEMARK_WATCH.md#native-acquisition-feature-scope--14-september-2026).
Actual IPI access/rights, production volume, calibration and human acceptance
remain open. Keep IN PROGRESS; publish only the completed user-facing feature.

**Native acquisition feature evidence, 14 September 2026:** The permitted native
IPI collector now reaches private candidates/review through durable identities,
atomic pages, restartable continuations, encrypted reusable OIDC tokens and
publisher backoff. The source-status panel is visible in all five languages and
production collection defaults to enabled while missing access stays explicit.
The final affected run passed 55 tests after the broader combined run; additional
boundary checks, 49 browser checkpoints and the root build passed. See
[implementation, exact checks and operational limits](docs/monitoring-v2/TRADEMARK_WATCH.md#native-acquisition-implementation-and-verification).
Real IPI access, catalogue volume/coverage, calibration, legal deadline rules,
human acceptance and actual release remain unverified. Status stays IN PROGRESS.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071). **Requirements:** §16; AC-B7-02,06,08,10.

**User outcome:** Publications and registration versions are supported by source evidence.

**Work:** Official IPI/Swissreg API after terms and account approval; mark/owner/representative/classes/goods-services/application/publication/registration/status. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Automated access, retention and permitted in-app/email uses are approved; the search UI is not used as evidence of an API licence.
2. Application, publication and registration dates are not interchangeable; Swiss jurisdiction and rights coverage are explicit.
3. Owner/representative/goods-services/renewal/cancellation/status updates preserve the previous state.
4. Missing mark fields are not inferred; publication evidence has a stable official ID.

**Verification:** Official API contract fixtures, multilingual goods/services, status/owner corrections and a rights-policy test.

**Active scope, 13 September 2026:** Implement the complete B7 direction under [Trademark Watch](docs/monitoring-v2/TRADEMARK_WATCH.md), including official source evidence, a versioned multi-brand portfolio, explained name/goods candidates and controlled IP review. Public IPI XML API documentation is available; signed terms/account access and notification/export rights remain unverified. Initial local contract and candidate work must preserve those gates and distinguish synthetic calibration from measured quality. Native acquisition, full user workflow and acceptance remain open; no source account or terms are changed.

**Local evidence, 13 September 2026:** Versioned internal trademark-facts contracts preserve supplied official IDs, original fields, separate dates and material fingerprints. Public XML API/schema documentation was verified; native acquisition remains unimplemented. The subsequent source-rights journal is described below. No signed access, current coverage or source activation is claimed. See [local evidence and remaining boundaries](docs/monitoring-v2/TRADEMARK_WATCH.md#local-implementation-evidence-13-september-2026). Status remains IN PROGRESS.

**Register journal, 13 September 2026:** Permission/generation-bound immutable register revisions, separate material/evidence sequences, idempotent receipts, rights-aware readers and background retention cleanup are implemented locally. Source/repository/migration checks passed (33); public XSD and official field mapping were inspected. Native item identity, XML/ZIP acquisition, publication-event mapping and completed traversal remain open. See [journal evidence](docs/monitoring-v2/TRADEMARK_WATCH.md#register-journal-and-native-contract-investigation-13-september-2026). No live access or activation is claimed; status remains IN PROGRESS.

**Offline native codec, 13 September 2026:** Bounded IPI XML/ZIP response and Swiss ST.96 field decoding is implemented, including full goods detail requests, opaque NextPage handling, separate publication/expiry/action dates and explicit business-number aliases. The request, record and response fixtures validate against official XSDs. Native/matcher/journal checks passed (112); two corrected integration checks also passed for owner changes and parent-document refresh. Durable identity resolution, page/traversal persistence, parent response retention and HTTP acquisition remain open. See [native codec evidence](docs/monitoring-v2/TRADEMARK_WATCH.md#offline-native-codec-13-september-2026). No live source access or completed coverage is claimed.

<a id="mv2-047"></a>

### MV2-047 — B7: Exact, lexical and phonetic candidates

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Backend + AI/domain reviewer · **Size:** L

**Dependencies:** [MV2-043](#mv2-043), [MV2-046](#mv2-046). **Requirements:** §16.4–16.7; AC-B7-01,03,04,05,07.

**User outcome:** Similar names can be found with an explanation of the matching basis.

**Work:** Multiple-brand portfolio, optional word variants/owners, Unicode normalization, exact/near lexical/phonetic matching, and class and goods/services overlap.

**Acceptance criteria:**

1. ALMORA/ALMORA exact, ALMORE/ALMORIA lexical and phonetic cases are reproducible; normalization and version are recorded.
2. Goods/services overlap affects priority; the same class code alone does not prove similarity or conflict.
3. False positives are measured by language; thresholds are calibrated on training/validation data and then frozen. MV2-051 performs the held-out evaluation; held-out data is not used for tuning.
4. The result is a candidate for IP review; it is never confirmed infringement, even with a perfect score.

**Verification:** Independent exact/near/phonetic/goods-services cases, accents/transliterations and unrelated-class negative cases.

**Active scope, 13 September 2026:** Implement the complete B7 direction under [Trademark Watch](docs/monitoring-v2/TRADEMARK_WATCH.md), including official source evidence, a versioned multi-brand portfolio, explained name/goods candidates and controlled IP review. Public IPI XML API documentation is available; signed terms/account access and notification/export rights remain unverified. Initial local contract and candidate work must preserve those gates and distinguish synthetic calibration from measured quality. Native acquisition, full user workflow and acceptance remain open; no source account or terms are changed.

**Local evidence, 13 September 2026:** 37 candidate/contract tests passed for exact, bounded lexical/word-extension and scoped English phonetic candidates, distinct goods/class evidence, five goods-description languages and calibration uncertainty. Reviewed calibration and held-out quality are not established; unsupported pronunciation/transliteration remains unavailable. The owner-private multi-brand portfolio and configuration revisions are locally implemented. See [implementation and checks](docs/monitoring-v2/TRADEMARK_WATCH.md#local-implementation-evidence-13-september-2026). Status remains IN PROGRESS.

<a id="mv2-048"></a>

### MV2-048 — B7: IP review, review deadlines, register changes and consented digest

**Active notification feature, 14 September 2026:** Complete the specification
§16.12 IP watch summary with explicit verified-owner immediate/daily consent,
quiet hours, saved-settings preview and durable delivery of new unread source
candidates/register changes. Recheck matching, rights, source/calibration,
recipient, ownership and review state before SMTP; preserve uncertain outcomes
without retries and never contact counsel. See the [complete feature evidence](docs/monitoring-v2/TRADEMARK_WATCH.md#private-ip-notifications--14-september-2026).

**Notification implementation verified:** The complete private settings→preview→
durable delivery feature passes 259 affected API/source/workflow/migration tests,
including real HTTP→worker→fake SMTP, plus the exact Ruff gate, root web build,
changed-file Prettier and 71 Chrome checks with four zero-violation axe audits.
Five-language controls preserve explicit owner consent, quiet hours, daily time,
opt-out, current source rights and private access. No source facts or legal dates
are copied into email and no counsel is contacted. Actual IPI access, approved
notification rights, quality/legal/pilot acceptance and production activation
remain unverified; this does not close the broader MV2-012/022 or MV2-048 gates.
All nine sections stay enabled; actual source access and human acceptance remain
independent. Finish UI/API/worker and all acceptance checks before publication.

**Deadline feature, 14 September 2026:** Delivered private explicit domicile/calendar
configuration, reviewed immutable rules, source-specific publication mapping,
traced Zurich calculations and current/history/Today/Inbox/counsel-packet readers
in five languages. Input revisions reopen review without erasing decisions; days
alone do not. Prepared exports recheck rules, calendars, rights and day at download.
The combined 56 server checks, 60 browser checkpoints and root build passed.
[Deadline evidence](docs/monitoring-v2/TRADEMARK_WATCH.md#reviewed-deadline-feature--14-september-2026)
keeps actual source, independent legal/calendar/quality reviews, release and human
acceptance open. Index and detail remain IN PROGRESS; all nine sections stay visible.

**Deadline feature scope, 14 September 2026 (before implementation):** Deliver
approved versioned source-to-publication rules and complete jurisdiction calendars,
an explicit private party/representative calendar choice, a traced timezone-aware
deadline calculation, candidate/history/Today/Inbox presentation and inspected
counsel export. Rule/calendar/publication changes must invalidate stale review and
export evidence; elapsed days alone must not reopen review. Preserve legacy
portfolios with no deadline context. Missing/ambiguous publication, unavailable
rule, missing domicile calendar and expired/revoked approvals produce no invented
date. No filing, new source permission or production legal-rule approval is implied.
Official IPI guidance distinguishes national Swissreg publication from the
international CH protection-extension publication in the WIPO Gazette. Independent
rule/calendar review and real source acceptance remain open.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

**Dependencies:** [MV2-013](#mv2-013), [MV2-016](#mv2-016), [MV2-017](#mv2-017), [MV2-019](#mv2-019), [MV2-020](#mv2-020), [MV2-021](#mv2-021), [MV2-046](#mv2-046), [MV2-047](#mv2-047). **Requirements:** §16; AC-B7-01…12.

**User outcome:** A brand owner receives a candidate and a controlled review workflow.

**Work:** Portfolio wizard, candidate evidence, deadline context/rule, review/relevant/not relevant/monitor/escalate decision and register updates.

**Acceptance criteria:**

1. AC-B7-01…12 are met; a high-priority candidate is available in the Impact Inbox.
2. A calculated review deadline has a source date, an approved applicable rule/version, a calculation trace and a verification warning; an unknown rule makes the deadline unavailable. days_remaining is displayed using the same timezone and rule revision.
3. A material change to owner/status/goods-services reopens the review while preserving the previous decision.
4. In v2, Send to counsel marks the item or prepares a permitted evidence export; external sending requires a separate user action.

**Verification:** End-to-end multiple-brand→candidate→review→register update, missing date/rule, deadline changes and export rights.

**Active scope, 13 September 2026:** Implement the complete B7 direction under [Trademark Watch](docs/monitoring-v2/TRADEMARK_WATCH.md), including official source evidence, a versioned multi-brand portfolio, explained name/goods candidates and controlled IP review. Public IPI XML API documentation is available; signed terms/account access and notification/export rights remain unverified. Initial local contract and candidate work must preserve those gates and distinguish synthetic calibration from measured quality. Native acquisition, full user workflow and acceptance remain open; no source account or terms are changed.

**Local evidence, 13 September 2026:** Private portfolio create/edit/history/archive/delete, CSRF and owner isolation are implemented; API/repository/Compose/migration checks passed (11), Monitoring Centre regression passed (18), and the root frontend build passed. The five-language form passed 17 synthetic browser checks and two axe scans (zero violations, existing Marvin contrast incomplete). Candidate review, register-change reopening, deadlines, Today/Inbox and permitted export/delivery remain unfinished. No source is activated and no incomplete feature is published. See [evidence](docs/monitoring-v2/TRADEMARK_WATCH.md#local-implementation-evidence-13-september-2026). Status remains IN PROGRESS.

**Private review feature, 14 September 2026:** Implemented permitted-source preview/start/pause, bounded scheduled candidate discovery, immutable private decisions, retained calibration provenance, register-change reopening and exact Today/Inbox evidence in all five languages. The 103 combined server checks plus two focused checks and 32 browser checkpoints passed; desktop/mobile axe audits reported zero violations. [Scope and acceptance evidence](docs/monitoring-v2/TRADEMARK_WATCH.md#private-register-review-journey--14-september-2026) distinguish this complete user-facing feature from real source/quality, legal deadline, export/delivery, activation and human acceptance requirements. Index and detail remain IN PROGRESS.

**Counsel packet feature, 14 September 2026:** Implemented prepare→inspect→explicit HTML download for a current candidate and optionally its selected register change. Every included source version is revalidated at download; preparation storage retains only references/hash. The 54 combined server checks, focused prior-permission check and 42 browser checkpoints passed, including exact downloaded bytes and revocation after preview. No sending or filing. [Scope and acceptance](docs/monitoring-v2/TRADEMARK_WATCH.md#counsel-packet-feature--14-september-2026) keep approved legal deadline rules, real source/human acceptance and release activation open. Index and detail remain IN PROGRESS.

<a id="mv2-049"></a>

### MV2-049 — B8: Official Ticino auctions

**Whole native acquisition scope, 14 September 2026:**
Implement bounded resumable official discovery/detail/status/document ingestion
into the existing journal/private tracking and material/reminder journey, with
five-language source readiness/status. Validate typed prices, explicit timestamp
basis, category provenance, stable IDs, byte changes, missing/partial listings,
lease/rate/rights/generation boundaries and native HTTP→private review behavior.
The [active source contract](docs/monitoring-v2/AUCTION_WATCH.md#required-outcome)
records inspected official read formats and remaining permissions/coverage.
Keep IN PROGRESS until all required B8 evidence is verified; no partial parser or
collector commit at a continuation boundary and no production licence is implied.

**Native collection evidence, 14 September 2026:** Complete bounded source
discovery/detail/status/PDF hashing now feeds private tracking, reopened review
and deadline-generation reminders, with durable leases/backoff/retention and a
five-language source-status panel. All 189 affected checks passed across combined
and focused runs; the isolated root build, exact API lint, formatting and 29
browser checkpoints (four axe audits with zero violations) passed. See
[native collection evidence](docs/monitoring-v2/AUCTION_WATCH.md#native-collection-and-visible-source-status--14-september-2026).
Source access/reuse, actual category coverage, operational capacity, verified
activation and human acceptance remain open. IN PROGRESS; all nine sections
and the implemented native collector remain enabled.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Integration · **Size:** L

**Dependencies:** [MV2-003](#mv2-003), [MV2-006](#mv2-006), [MV2-007](#mv2-007), [MV2-011](#mv2-011), [MV2-071](#mv2-071). **Requirements:** §17.3–17.7,17.11; AC-B8-02,05,06,11.

**User outcome:** An official opportunity has verified fields and a source.

**Work:** Official Ticino auction source contract; real estate/vehicles/equipment capability; auction/lot IDs, dates, documents, conditions, price type and status. Implementation of this domain starts after the first Pollen Watch is ready (MV2-071); source discovery in MV2-003 can proceed in parallel.

**Acceptance criteria:**

1. Automated access and reuse are confirmed; HTML availability is not presented as an API licence.
2. Current bid, estimate and starting/minimum price are stored as distinct types; missing bid_count/price/end is UNKNOWN.
3. Auctions and lots are not merged; cancellation/postponement/conditions/document updates are versioned.
4. Category coverage in Ticino is verified; unsupported categories/areas are clearly shown, without an unofficial fallback.

**Verification:** A bounded official sample, multiple-lot/unknown-field/cancellation fixtures and parser drift tests.

**Active scope, 13 September 2026:** Implement the complete Auction Watch direction under [the B8 implementation contract](docs/monitoring-v2/AUCTION_WATCH.md). Official public listing/detail fields and sale terms were inspected; automated reuse, native feed, category coverage and current source-state evidence remain unverified. Build private profiles, typed-price matching, retained auction/lot state, internal review and consented material/deadline delivery. No live acquisition or completed acceptance is claimed.

**Source-journal evidence, 14 September 2026:** Permission-scoped auction/lot versions, evidence integrity, generation/cursor admission, expiry/revocation redaction and cleanup now support private tracking. The 64 combined source/workflow/API/Centre checks passed. Native acquisition, current official rights and category coverage remain unverified. See [tracking evidence](docs/monitoring-v2/AUCTION_WATCH.md#private-source-backed-tracking--14-september-2026). Status remains IN PROGRESS.

<a id="mv2-050"></a>

### MV2-050 — B8: Auction profiles, price limits and ending-soon alerts

**Adapter-conformance evidence, 15 September 2026:** Seven integrated fixture
checks passed (33.21s) for TI/ZH admission-to-private-HTTP, scheduled projection,
review/history, price/terms/end changes, replacement reminders and cancellation,
plus unknown fields, identical publisher IDs and private/revoked access.
The domain implementation is unchanged. See [scope and evidence](docs/monitoring-v2/AUCTION_ADAPTER_CONFORMANCE.md).
This verifies normalized adapter output conformance, not a Zurich parser, source
rights, live rollout, broad B8 acceptance or production activation. IN PROGRESS.

**Active conformance scope, 15 September 2026:** Close the second-canton fixture
gap in AC-B8-12 at the normalized adapter boundary. Run the same complete private
HTTP journey for synthetic TI and ZH source outputs through the real permission
journal, scheduled projection, review/history, deadline reminders and cancellation.
Also verify unknown fields, colliding publisher identifiers and revoked/private
access. Dependencies are the existing MV2-049 journal and MV2-050 workflow; no
additional source credentials are needed for this isolated fixture verification.
Both fixtures use reserved `.invalid` URLs and explicit synthetic permissions.
Acceptance requires retained source identity, no duplicate events/reminders on
replay, and no second-canton live coverage or native-parser claim. Existing native
Ticino collector tests remain separate; live source and human gates remain open.

**Native-source integration evidence, 14 September 2026:** The complete native
collector now drives the existing private review/Today/reminder workflow.
Synthetic HTTP source changes replace the old deadline reminder, reopen review
for price/conditions/document changes and preserve owner-only access. Revoked
source rights remove stale feed/reminder facts. See the
[native feature validation](docs/monitoring-v2/AUCTION_WATCH.md#native-collection-and-visible-source-status--14-september-2026).
The broader task remains IN PROGRESS pending live source and human acceptance.

**Status:** IN PROGRESS · **Priority:** P1 · **Owner:** Frontend + Backend · **Size:** L

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

**Active scope, 13 September 2026:** Implement the complete Auction Watch direction under [the B8 implementation contract](docs/monitoring-v2/AUCTION_WATCH.md). Official public listing/detail fields and sale terms were inspected; automated reuse, native feed, category coverage and current source-state evidence remain unverified. Build private profiles, typed-price matching, retained auction/lot state, internal review and consented material/deadline delivery. No live acquisition or completed acceptance is claimed.


**Profile-management evidence, 13 September 2026:** The private five-language Auction Watch profile workflow, immutable settings, typed-price/budget rules and enabled ninth Centre entry are implemented. Final integrated checks passed (30), browser checks passed (17), exact-money reader checks passed (3), and the root frontend build passed. Native source access/persistence, auction review/following, Today/Inbox and durable delivery remain open. See [implementation and acceptance boundaries](docs/monitoring-v2/AUCTION_WATCH.md#private-profiles-and-deterministic-rules--13-september-2108-utc). This does not complete AC-B8-01…12.

**Private-tracking evidence, 14 September 2026:** Start/resume, scheduled projection, pause, explained lots, individual follow/unfollow, internal decisions, reopened review and retained source history are implemented in all five languages. Combined API/source/workflow/Centre checks passed (64); browser tracking (16) and existing profile (17) checkpoints, root build, exact Ruff and changed-file formatting passed. Current official acquisition/rights, Today/Inbox, durable reminders/email and human acceptance remain open. See [tracking evidence](docs/monitoring-v2/AUCTION_WATCH.md#private-source-backed-tracking--14-september-2026). Status remains IN PROGRESS.

**Today/Inbox evidence, 14 September 2026:** Private auction signals now link to exact before/at-change source versions and the current lot decision. Combined server checks (25), browser checkpoints (13) and the root frontend build passed. Reads recheck source rights, retention, membership and current state; no source collection, bid or email is implied. See [material-change feed evidence](docs/monitoring-v2/AUCTION_WATCH.md#today-inbox-and-exact-material-changes--14-september-2026). Official acquisition/rights, durable ending-soon delivery, consented email and human acceptance remain open; IN PROGRESS.

**Reminders and email evidence, 14 September 2026:** Private deadline-generation reminders, schedule/exact readers, Today/Inbox reminders and separately consented verified-owner email now form a complete UI/API/worker outcome for permitted journal records. The final integrated source/rules/feed/API/workflow/reminder/delivery/backlog suite passed (122), including HTTP-to-durable-worker fake-SMTP dispatch. The root build and 14 five-language desktop/mobile browser checkpoints passed with no runtime exceptions or axe violations. See [delivery evidence and remaining source/release boundaries](docs/monitoring-v2/AUCTION_WATCH.md#durable-reminders-and-consented-email--14-september-2026). Native official access, rights/category coverage, adapter conformance, activation and human acceptance remain open; index and detail stay IN PROGRESS.

## F6 — Quality evidence, pilot and release

<a id="mv2-051"></a>

### MV2-051 — Independent matching and local AI evaluation

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** AI + Independent domain reviewers · **Size:** L

**Dependencies:** [MV2-023](#mv2-023), [MV2-043](#mv2-043), [MV2-047](#mv2-047). **Requirements:** §§7,22,31,34; legacy HL-064,089,091–094,100.

**User outcome:** Semantic matching does not earn trust merely by returning valid JSON.

**Work:** Independent gold set, held-out partition, evaluation by case/language/negative example; approvals for local model/task/locale profiles; semantic benchmark before feature promotion.

**Acceptance criteria:**

1. At least 200 independently labelled match/nonmatch pairs, with ≥50 for each of B2/B7/B8; the held-out split, disagreements and adjudication are recorded.
2. Precision and recall are measured per case for calibrated business candidate ranking; proposed gates are ≥85% precision and ≥90% recall, with no claim of legal conflict accuracy.
3. 100% of checked citations refer to a permitted snapshot/field; there are zero invented facts/deadlines in the release-critical fixture set.
4. Without an approved profile, semantic mode is unavailable or extractive; deterministic results are not blocked; a measured score is not presented as a probability without calibration.

**Verification:** A reproducible offline benchmark with report/hash/config; independent review by people who did not author the same expected answers.

**Implemented complete feature scope, 15 September 2026 — business evaluation package:**
Provide an offline, reproducible B2/B7/B8 evaluation command and authoring schemas.
Reuse the existing bounded artifact, independent vote and confusion-matrix
primitives; preserve the separate HL-093 and Tender experiment contracts.
Bind frozen datasets, permitted source fields, captured outputs, configuration,
runtime revision, gold labels and independent output audits by exact hashes.
Report all three business cases, five languages, negative examples, missing
predictions, unresolved disagreements and unsupported citations without dropping
failed rows. Require 200 reviewed pairs and 50 per business case, held-out
positive/negative coverage and the stated precision/recall targets. Human audits
must inspect complete captured output for invented facts/deadlines; exact quote
checks cannot establish entailment. Synthetic fixtures never satisfy acceptance.
Dependencies: existing offline evaluation primitives and the implemented business
matchers; this reporting feature requires no source credentials, live calls or
model approval. Acceptance: usable schema-to-report CLI, deterministic bounded
private-file processing, tamper/leakage/reviewer/rights/denominator rejection,
explicit unmeasured outcomes and no runtime promotion or application writes.
Real independent labels, reviewer authenticity, target-machine runs, approved
profiles, live release and human acceptance remain open under this parent task.

**Execution evidence, 15 September 2026:** The complete offline business evaluation
workflow exports versioned authoring schemas, reads bounded hash-bound private
packages and produces reproducible reports with separate B2/B7/B8 and five-language
metrics, precise source-field citations and independent complete-output audits.
101 new/legacy evaluation checks and exact API/script lint passed. See
[operator procedure, evidence and remaining acceptance](docs/monitoring-v2/BUSINESS_MATCHING_EVALUATION.md).
No independent corpus, measured model quality, runtime approval, production
activation or human acceptance is claimed; the parent remains IN PROGRESS.

<a id="mv2-052"></a>

### MV2-052 — Operational metrics, degraded mode and source recovery

**23 September test-policy scope:** Implement the owner-requested standard
(platform smoke + functional), full (including integration) and one-shot hotfix
(tests explicitly skipped) profiles. Preserve all test cases in the full suite,
real fixture isolation, Git ancestry, release locking, configuration validation,
compilation, backup, activation probes and rollback. Record the selected policy
and skipped work in the exact attempt, including its administrator history view.
The inventory, bounded workers and failure/skip transitions must be verified;
timings and production activation will be recorded in `docs/TESTING.md`.
No external source readiness changes are needed; MV2-052 remains IN PROGRESS.
**Local acceptance:** The final 726-case standard gate passed in 35.59 seconds;
177 affected release/data/migration checks and 29 final policy/history/backlog
checks passed. Seventy desktop/mobile browser checkpoints cover all five locales,
including honest skipped-test status, the emergency reason and administrator
access. Exact Ruff and the root production web build pass. The final inventory
retains all prior cases and adds policy regressions. See [commands, limits and
activation evidence](docs/TESTING.md); full integration timing is not yet measured.

22 September production verification: `1890d66` completed all twelve deployment
stages and public readiness. Full QA passed 5,075 tests / 18 skips in 1h18m23s,
33.14% less elapsed time than the prior successful suite on this host. All 55
pilot watches and 15 enabled legal streams passed live checks; five comparisons,
three Ask examples, 30 relation reports and tenant/viewer boundaries were verified.
Native daily freshness, SIMAP cycle gaps and external source gates stay explicit.
See [production evidence](docs/BASELTECH_PILOT_VERIFICATION.md). MV2-052 remains
IN PROGRESS for its broader gates; these demo accounts do not complete MV2-058,
which remains PLANNED. C4 remains DEFERRED.

**Saved-citation navigation recovery, 22 September 2026 (before implementation):**
Live browser verification of AsylG Article 66 found that a correct old-version
citation jumps to Article 63 because the same passage number exists on the newer
side. Resolve the immutable version before locating the passage in both current
answers/reports and AI history. Unrelated versions, missing passages and ambiguous
matches must retain their exact saved-evidence URL rather than substitute another
row. Preserve in-place comparison navigation and existing tenant/identity gates.
Verify opposite-side collisions, unchanged and removed evidence, law-wide history
without a comparison context, frontend build and the real AsylG/IDG click paths.
This is scoped MV2-052 completion; independent legal-quality approval is separate.

The version-bound resolver passed four collision/fallback tests, nine existing
comparison/Ask checks and twelve real saved citation targets. The complete root
frontend build (351 checks and TypeScript) and required backlog check passed.
Normal deployment and real browser clicks remain the final release gate.

**Interest-brief configuration fixture recovery, 22 September 2026 (before
implementation):** The 01016c4 full gate reported failures in persisted model-
configuration tests. Local reproduction rejects the request at its initial
configuration check before the requested generation-time edit. The fixture
installs a synthetic reviewed registry only on the execution client's settings;
the persisted-settings reader resolves deployment-owned registry paths from the
unchanged environment. The answer fingerprint now correctly includes capability
policy. Model production's shared deployment policy in this fixture by aligning
those two private registry paths, not by removing the policy from fingerprints,
loosening configuration checks or adding a production grant. Require initial
configuration agreement, then rerun all interest execution, reader, policy, job
and configuration cases and affected relation freshness checks. Verify old-worker
fencing, revocation, history preservation and credential/transport-only reuse.
The user has authorized stopping this failed QA run after a tested correction is
published, so normal full QA can select the corrected descendant.

All interest-brief tests and the relation configuration, prompt and runtime
freshness regressions passed: 390 passed, five existing skips, in 686 seconds.
This includes all eleven full-run failures, initial persisted-policy agreement,
runtime/count/generation edits, queued-work refusal, historical reader behavior,
transport-only reuse, scope isolation and concurrent-attempt protection. Exact
API Ruff passed. A normal complete release gate remains required.

**SIMAP abandonment recovery, 22 September 2026 (before implementation):** The
IWB public collection recorded one `invalid_source_contract` gap for publication
34356-02 (7 July 2026). Its original passes publication validation but projection
expects `lot` or `lots`; SIMAP's official 1.5.1 specification instead defines
`abandonedLot` for this lifecycle type. Accept only a valid specific-lot
description with compatible `lotsType`, no competing lot container, and a
matching `referencingLotId` when supplied. Keep exact JSON-pointer evidence,
cancelled phase, immutable original hash and unknown procurement/location facts.
Do not infer whole-project lot membership or manufacture an open opportunity.
Validate malformed and conflicting records, original retention, discovery
exclusion, ordinary collector progress, sibling isolation and idempotent replay.
Inspect the four other pilot gaps rather than attributing them to this cause
without evidence. Source readiness is the existing permitted public API; private
SIMAP documents and Q&A are not covered. Existing source rights, leases, retry
budgets and saved failure evidence remain unchanged. Full-gate activation and
normal production recovery are separate acceptance requirements.

Read-only replay matched all four IT gap hashes to exact public records: three
specific-lot abandonments and one explicit whole-project abandonment. The official
schema defines null `abandonedLot` as the latter. Extend recovery to that case:
the public parser accepts the closed project without inventing lot IDs; ingestion
projects its cancelled phase only onto already stored, tenant/monitor/project
scoped dossiers permitted by the current work item. Preserve unknown lot titles,
procurement and geography, exact source locators and original hashes. Add bounded
identity selection, sibling/tenant exclusions, replay, malformed-reference and
historical-discovery regressions. This is interpretation of explicit published
scope, not inferred membership or a new opportunity.

**Execution evidence:** All 269 SIMAP/tender and required backlog checks passed
in 214 seconds, followed by 37 final malformed-scope, collector and backlog checks
in 25 seconds. Exact API Ruff passed. Four specific-lot and one whole-project real
originals passed read-only parser/material replay. Collector regressions completed
without gaps, preserved an open sibling and excluded cancelled discovery results.
Durable observation retained originals and prior versions, scoped cancellation to
permitted existing IDs and kept other monitors and organizations unchanged.
Full-gate activation and subsequent production recovery remain separate.

The user subsequently authorized restarting stale or failed deployments without
another permission request. Only verified isolated QA containers may be stopped;
the serving application and normal release gates remain protected. The obsolete
e66f272 run was stopped under that authorization; normal QA for 01016c4 began at
22:14 UTC on 21 September. Cancelled runs remain incomplete evidence.

**Measured release-test performance, 21 September 2026:** The successful
81f1476 gate completed 4,967 tests with 18 skips in 7,034.89 seconds; the current
suite collects 5,077 cases and runs serially. A local setup profile found about
2.5 seconds of migration work in a 3.5-second instrumented application setup.
The common HTTP fixture is used directly by 627 test functions before parameter
expansion. Build one empty schema per test session using the real migrations,
close its connection, then copy it to each test's own directory. Do not share
application objects, sessions, mutable data, settings, models or fetchers between
tests. Normal initialization must still execute, including the migration head
check. Dedicated migration/cold-start tests remain unchanged. Prove fresh-copy
isolation and foreign keys, run representative HTTP/identity and migration
regressions, and measure the same selection before/after. No tests are removed,
no production database is used, and full-suite duration remains unverified until
the next normal gate. Source permissions and AI capability gates are unaffected.

The user explicitly authorized cancellation of the obsolete 8993ce1 run at
21:47 UTC. Its exact target SHA, purpose label and read-only release mount were
verified before stopping only that QA container. The running site was untouched;
the manager cleaned up and the normal e66f272 run began at 21:48 UTC. The cancelled
check is incomplete evidence, not a passing test result. This one-time override
does not authorize interruption of the new run.

**Assessed offline-digest fixture:** The cancelled run's log retained a real
failure before interruption. It reproduced locally: after runtime recovery the
test expects a medium-severity event from an unreviewed relation model, whose
correct current result is unassessed. Use the already available synthetic
`approved_local_relation` fixture for this specific assessed recovery scenario.
Keep its failed-period/retry/no-duplicate assertions and the unapproved model
tests. Run all digest and relation-runtime/selected-evidence regressions. No
production capability grant, severity override or filtering exception is allowed.

Schema reuse verification passed the same 54 HTTP/identity cases before/after
in 95.97/50.98 seconds (46.9% less elapsed time). Fifteen additional isolation,
database lifecycle, migration/foreign-key, retained-history and backlog checks
passed. Fresh copies retain independent records, app doubles and enforced foreign
keys, while the original schema bytes remain unchanged. These measurements do
not establish the next full gate's time or complete the parent task.
The complete digest/runtime/selected-evidence selection passed 204 checks with
one existing skip in 341 seconds, including the original failed recovery case.
Exact API Ruff passed. The active e66f272 target still contains the reproduced
fixture failure; a corrected descendant must pass the normal full release gate.

**Measured-token release fixture, 21 September 2026:** The full 402b4ad run
reproduced three failures before any inference: importing the unnamed synthetic
multi-article fixture correctly returns `document_identity_unknown`. The fixture
must use the existing explicit assignment contract. Preserve identity rejection
for unconfirmed documents and all measured-coverage/cache assertions. Validate
the complete token-evidence tests and identity/workflow boundaries; no production
identity exception or model approval is part of this correction.

The original three failures reproduced before inference and passed after the
fixture explicitly confirmed assignment. All 55 token-evidence, identity,
guidance, workflow and backlog regressions passed with exact API Ruff. The
402b4ad automatic run also reached its original 7,200-second deadline at 93%.
The next normal run started with the previously configured 10,800-second budget;
no active check was interrupted or replaced. Final activation remains pending.

**Basel/Bern relation noise, 21 September 2026:** Read-only inventory of the
demonstration watches found 22 BaselTech and 60 personal active candidates. Many
personal candidates share only Riehen/Bettingen with the asylum contract; generic
intercantonal-agreement titles also link unrelated higher education and procurement
acts. These are jurisdiction/instrument context, not regulated subjects. Extend
the relation-only exclusion vocabulary for these demonstrated terms and their
generic jurisdiction/agreement counterparts without changing topic matching.
Increment the retrieval rule, preserve exact SR/RS and confirmed official paths,
and recheck retained pairs through the existing dry-run/apply workflow. Keep
source data, deliveries, reviews and old analyses; rejection means unsupported
retrieval, never a legal no-impact judgment. Verify meaningful subject matches
within Basel/Bern, multilingual agreement terminology, actual retained-pair
preflight and ordinary recovery after activation. No new source coverage or
semantic-quality approval is implied.

Revision v4 passed 94 relevant checks with one existing skip. Read-only replay of
all 82 retained pilot pairs kept eight BaselTech and twelve personal candidates;
fourteen and forty-eight respectively no longer meet retrieval evidence. Tests
cover topic geography, substantive multilingual subjects, exact norm references,
confirmed publisher relations and intact history through bounded dry-run/apply.
Production reprocessing remains pending normal activation; the parent stays
IN PROGRESS.

**Relation-analysis pilot recovery, 21 September 2026:** Live Basel/Ukraine
inboxes reproduce invalid structured replies and generated relation claims from
an unreviewed model. The relation path currently omits the capability scope used
by comparison reports and Ask. Add an independent `relation_impact` task scope;
existing report approval must not authorize relation interpretation. Without an
exact reviewed grant, request only bounded saved row numbers and render cited
evidence with explicit unassessed impact, no severity estimate or action advice.
Preserve confirmed official relations and organization review decisions as
separate facts. Use measured prompt allocation, stable row IDs and exact saved
quote windows; retain rejected replies as failures. Version result/cache rules
so older interpretations remain history. Dependencies are the existing runtime,
capability, evidence and tenant contracts. Acceptance covers small-context fit,
invalid/invented citations, capability revocation, locale/cross-tenant behavior,
truthful inbox status, actual Apertus execution and ordinary release activation.
Broader MV2-052 and independent model-quality acceptance remain open.
Verification: 220 expanded checks passed (one existing skip), exact API lint and
the isolated production web build passed. The two real saved dossiers fit the
observed 4,096-token runtime and each completed in one provider call. The prior
failed attempt and prior unsupported interpretation remain retained history;
ordinary production activation and replay are still separate acceptance steps.

**Specific-provision Ask recovery, 21 September 2026:** The live Basel IDG query
about Besoldung in § 39 was misclassified as a general change question and reused
unrelated cover/preamble excerpts. Recognize paragraph signs independently of
word boundaries, select the exact provision and its bounded neighbours, and
refresh the Ask router/cache revision. A reused partial impact report must retain
its original coverage limits rather than claim complete document coverage.
Acceptance requires numbered/suffixed provision routing, an unrelated-report
regression, absent-provision handling, consistent plan/execution coverage and the
real § 39 before/after replay. Preserve tenant/source binding, exact citations,
bounded runtime requests and the independent human interpretation-quality gate.
The existing saved-version and Ask contracts provide the required dependencies.
Local acceptance: 148 related Ask, report, capability and history tests plus the
backlog check passed. The retained real IDG versions select six bound passages,
including both complete § 39 bodies, in one bounded batch. Production replay and
independent interpretation review remain separate pending evidence.

**Selected-citation retention, 21 September 2026:** The real § 39 model call
selected six rows and quoted the provision body, but materialization retained
only the first four header/title citations. Align materialization with the
existing ten-row validated output contract so saved body quotations retain their
links. Preserve invalid-row rejection, deduplication, quote bounds and downstream
display/action limits. Acceptance requires more than four valid selected rows,
the old/new body citations and the real Apertus replay. No model-quality approval
or runtime context allowance is expanded.
The real running Apertus 8B returned all six bound citations after this repair
in one selected-evidence call. Ninety-four related tests passed; Ask revision v3
invalidates answers with the earlier citation limit. The original failed preflight
is retained privately. No serving checkout or model setting was changed by it.

**Viewer evidence scope, 21 September 2026:** The native selected-evidence reader
returns quoted existing fields with no model call or mutation, but its POST route
was incorrectly blocked by the viewer write guard. Add only this exact endpoint
to the read exception list. Preserve CSRF, current native source permissions,
tenant/private ownership, input binding, and administrator-only writes. Verify
HTTP access, citation resolution, stale binding and foreign-tenant denial under
both supported organization roles. Existing source and sharing contracts suffice.

**Source-language presentation and retrieval, 21 September 2026:** Real federal
news retained correct German artifacts but displayed the shared work's first-seen
Italian title. Use the exact bound expression title in Today, inbox, source
evidence, native comparison and brief inputs, falling back only when it is empty.
Keep scalar list queries bounded, work/tenant binding and multilingual work IDs.
The same live records revealed relation candidates supported only by Italian
articles such as `dei`. Filter these function words in relation retrieval and
increment its rule revision, preserving exact norm/official-relation paths and
topic matching's separate rule contract. Verify multilingual title provenance,
foreign-work rejection, meaningful Italian subject matches and non-matches from
function words. Recheck affected retained candidates through the existing bounded
operator recovery workflow; do not erase evidence or manufacture approvals.

The full release check exposed a constant fourteenth page read after expression
labels were added. Combine those scalar labels with the existing event metadata
query rather than widening the established thirteen-read acceptance budget.
Retain the hundred-candidate batch cap, absent-title fallback, expression-to-work
binding, private-work visibility and deferred document bodies. Verify both inbox
routes, one/fifty-event query counts, wrong-work expressions and tenant denial.
All 46 scoped checks passed locally, including the exact original query-budget
assertion and no heavy-document/expression hydration. Full automatic acceptance
and production activation remain pending.

**Full-suite host time budget, 21 September 2026:** Release 867d2a7 reached 99%
at the 7,200-second deadline without completing the API gate. Its known inbox
query-budget failure was fixed separately; timeout is not a passing result.
Use the existing validated `HELVETIC_LENS_API_TEST_TIMEOUT_SECONDS` operator knob
to allow 10,800 seconds for future scheduled runs on this host. Preserve the
two-minute cron schedule, deployment lock, all required tests and the observed
legacy QA resource configuration (no explicit container CPU/memory limit).
Record the exact cron change and retain a private rollback copy.
Never interrupt/restart an active run or alter its frozen test inputs. Acceptance
requires a naturally completed full API result and ordinary release activation.

**Direct Basel BPG metadata envelope, 21 September 2026:** The live official
730.100 response is 2,439,258 bytes because it includes the complete law XHTML.
The direct LexWork resolver's 2 MB metadata cap rejects this otherwise valid
current-version document. Raise only that bounded envelope cap to 4 MB, with a
specific size error and retained exact publisher/language/version/PDF checks.
Acceptance: a representative full-text envelope above 2 MB resolves the exact
official PDF; an envelope over 4 MB fails before PDF fetch; the actual Basel BPG
preflight succeeds. This does not assert complete cantonal catalogue coverage.

**Document/watch deletion with related history, 21 September 2026:** Removing the
pilot's wrong-language shared watch returned HTTP 500 because its organization
relation deliveries still referenced it. Under the existing explicit document
and history deletion action, remove that watch's own delivery records and their
dependent private reviews/analyses in the same transaction. Retain global work,
candidate, source version and other organizations' watches and reviews. Lock the
selected watch and reject active relation-analysis jobs with the existing 409
background-work guidance. Verify shared and private deletion, two populated
workspace histories and busy-work rollback with real foreign-key enforcement.

**Dated Fedlex relation targets, 21 September 2026:** All three enabled RSS
streams stopped at OC 2026/480 because its official relation points to
`eli/cc/2022/172/20260919`. Resolve this bounded date-suffixed JOLux resource to
its validated canonical parent for the relation target. Retain the original URI
and version token without inferring a legal effective date. Keep ordinary work
discovery strict, reject foreign/malformed/language/artifact paths, and omit
version-to-parent self-edges. Acceptance includes all three live language paths
and current RSS-page relation replay, not only the first discovered article.

**Guidance identity repair, 21 September 2026:** Production daily checks wrongly
interpreted bare dates and contents entries as federal SR numbers. Only explicitly
labelled SR/RS values may become these identifiers. Short factual document titles
and concise guidance cover headings must win over legal citations later in the
body. Refresh existing derived identity assessments through the revisioned
service path, retaining original artifacts and observations. Exact URL continuity
remains only probable for non-legal guidance; contradictory official identifiers,
wrong legal titles, cross-source assignment and existing tenant boundaries stay
blocked. Acceptance includes the Basel employment page, SEM instruction/factsheet,
Basel support guidelines and Bern leaflet, with a legacy-identity scan replay.

**Current source language in the registry, 21 September 2026:** A newly acquired
Ukrainian leaflet is correctly classified, but its work retains an older German
expression and the UI omits Ukrainian from its filter vocabulary. Display and
filter a monitored watch by its accessible current version's stated language
when known, falling back to corpus languages when it is unknown. Preserve the
historical corpus and event-language aggregation. Keep the list bounded, select
only scalar metadata, and reject a forged current-version binding across laws or
workspaces. Add Ukrainian to source-language filters without adding a UI locale.
Verify current-language filtering, cursor paging, tenant isolation and live UI.

**Native comparison guard, 21 September 2026:** Native corpus versions have
immutable official-version keys and cannot use the direct-watch derived-version
path. Reject comparisons between HTML versions with different extractor stamps,
retain compatible comparisons without invalidating them, and preserve source
versions and old comparison history. Test rejected selection without writes,
fail-closed existing selection/AI reads, and valid same-parser comparisons. The
existing native ownership and source grants remain prerequisites. This bounded
guard does not claim catalogue reprocessing or complete historical extraction.

**Ukrainian source-language scope, 21 September 2026:** The Bern Ukrainian
Status S leaflet is under a `/de/` asset directory and was labelled German.
Use a bounded predominantly Cyrillic sample with Ukrainian-specific letters
before the weak URL-path hint; ambiguous Cyrillic remains unknown. Explicit
verified publisher language metadata retains precedence. Verify German pages
quoting Ukrainian and ambiguous samples, preserve the five UI locales, and
re-acquire only the operator-created affected demo baselines after activation.
Existing evidence and confirmed identities are not globally rewritten.

The SEM Ukrainian information page also contains a large multilingual directory
after its Ukrainian introduction. Extend the bounded script check only when both
the actual title and the first eight passages are predominantly Cyrillic; require
Ukrainian-specific letters and preserve explicit publisher language precedence.
Reject a Ukrainian quotation on a German page and a Ukrainian title over a German
body. Use a new identity revision so existing saved assessments refresh without
replacing originals. Final pilot scans must refresh all current assignments.

**Extraction-transition scope, 21 September 2026:** The pilot's complete-text
repair must not compare a partial old extraction against a full new extraction.
For direct-document comparisons and scans, re-extract retained older HTML with
the current parser into a separate private derived version, recording its parent,
original observation and parser revision. Preserve the original version and bytes;
never substitute current network content for historical bytes. Exact-original
integrity failures stop comparison and retain the last good live pointer. Verify
unchanged originals, simultaneous real edits, immutable old evidence, idempotent
replay and missing/corrupt originals. Display the derived origin in all locales.
This does not rewrite existing native corpus events or claim complete historical
corpus reprocessing. Replace the federal-only act label with a neutral law label
because the same type includes cantonal laws. Existing source rights are sufficient.

**Scoped recovery, 21 September 2026 — IN PROGRESS:** Repair Basel-Stadt optional
publisher-version metadata, Fedlex manifestation dereferencing and consultation
artifact cardinality; exercise real shared-source acquisition and isolated
BaselTech/Ukraine workspaces. Acceptance requires exact saved official evidence,
successful replay, source-bound URL checks, real role/tenant checks and an honest
inventory of all nine native monitor source gates. Local checks, publication,
production activation and independent human pilot results are separate evidence.
No global credential, consent, source-rights or quality gate is relaxed. The
existing connector, authentication and durable job contracts are available;
restricted external APIs remain dependent on their existing approved access.

**Direct-law scope, 21 September 2026:** The owner explicitly requested Basel and
Bern cantonal law monitoring. Both official LexWork publishers expose the current
version and exact PDF through their public law metadata used by the publisher UI.
Accept only these two HTTPS publishers, validate the requested systematic number,
language and selected version, retain exact PDF/metadata provenance, and preserve
current-versus-historical selection. Repeated scans must re-resolve the current
version; external URLs, mismatched identities and unavailable PDFs fail closed.
Use the existing extraction, evidence, comparison and tenant contracts. Acceptance
requires mock negative boundaries, a two-version lifecycle and real current-law
probes. This bounded direct-URL repair does not activate the deferred MV2-066 pack.

**FAQ extraction scope, 21 September 2026:** The real SEM Ukraine FAQ contains
multiple article fragments inside `#content.main-content`. Selecting the first
article retained only 118 characters and omitted the questions and answers.
Prefer explicit main-content roots over embedded articles, retain collapsed
answer text, and keep navigation excluded. Verify sibling-answer changes and
discovery, record extraction provenance, and re-acquire affected demo baselines.
This is an extraction correction, not evidence of a legal amendment.

**Requested-edition scope, 21 September 2026:** Adding a German Fedlex DSG URL
reused a previously saved Italian baseline. Separate direct document identities
by requested language and explicit version date, with language/date-checked
fallback to legacy records. Preserve all existing IDs, artifacts and watches;
do not merge/delete records or change the native multilingual regulatory corpus.
Acceptance verifies different-language and pinned-date isolation plus alias
deduplication for both new and legacy records.
The ORM's official-host list must agree with the resolver, including the `www`
alias. Existing private records are not republished; only the requesting tenant
may reuse its own record, with its existing watch preferred over shared aliases.

**Small-context planning scope, 21 September 2026:** A real AsylG comparison with
the configured 4k-character evidence budget returned HTTP 500 because estimated
aggregate size still produced more than three actual batches. Fit whole change
units to the existing provider-call budget using the actual batch planner, retain
the complete exact diff, and report every coverage limitation. Keep runtime token
measurement, citations and independent explanation-quality gates unchanged.

**Direct-source identity scope, 21 September 2026:** Preserve verified LexWork
publisher/number/language/version provenance in artifact identity so Basel/Bern
scans and historical imports do not depend on translated display titles. For
ordinary non-legal, identifier-free pages, an exact watched URL may establish
probable page continuity only, never verified legal identity. Changed legal
titles, conflicting identifiers, foreign PDFs and unknown uploads retain the
existing quarantine/confirmation behavior. Verify real current/historical probes
and negative identity tests before activating daily document checks.

**Daily direct-document scope, 21 September 2026:** Official packs already have
scheduled collectors, but separately added Bern laws and FAQ pages had only a
manual scan button. Add an explicit per-watch daily-check switch, disabled for
all existing/new watches until selected. Enabling schedules a first real check;
subsequent checks are at least 24 hours apart. Use bounded tenant-scoped durable
scan jobs, skip busy/paused watches, and require an active organization admin at
enqueue and execution. Disabling suppresses queued automatic fetches. Preserve
source/identity gates, move any changed-document AI work to its existing queue,
and send no email. Expose status and next eligible check in all five interface
languages. Acceptance requires opt-in/tenant/role/pause/idempotence tests,
migration compatibility, frontend checks and a live scheduled pilot check.
Thirty-five affected API/migration/backlog checks, exact API Ruff and the full
frontend build passed. Local browser verification covered persisted opt-in,
pause/opt-out and mobile layout; production execution remains pending activation.

**Expanded Fedlex audit scope, 21 September 2026:** The live publication for
OC 2026/483 retained only 272 characters because its annex is a sibling of
`main#maintext` inside `#lawcontent`. Prefer the complete legal container and
retain preamble, annex tables and their citations, with an extraction revision.
The CC reconciliation query also returns dated members typed as JOLux Work;
bound discovery to canonical root work URIs before paging. Verify changed annex
rows and current official artifacts, preserve foreign URL rejection, and do not
present repaired pilot extraction baselines as newly enacted legal changes.
Retain one shared corpus work for direct Fedlex language/date editions while
keeping separate legacy watches/expressions. Catalogue binding must only use
shared mappings; private legacy documents remain private.
The same 26-stream audit found historical FGA files at the publisher-linked
Federal Archives endpoint and current Federal Criminal Court PDFs headed
`Entscheid vom`. Retain the exact archive reference as metadata without following
it or claiming extracted archive text; foreign references still fail closed.
Accept the verified German heading with regression tests for date/docket gates.

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Operations + Backend · **Size:** M

**Implemented whole-feature scope, 15 September 2026 — source attention inbox:**
Provide a platform-administrator attention list alongside the existing nine-source
operations overview. Derive actionable items from actual stored configuration,
permission-record expiry/revocation, failed or missing acquisition and invalid
clocks. Renewal windows are 30 days and 7 days; unknown remains unknown. Link to
each native connector/settings workflow without renewing access or collecting data.
An administrator may acknowledge only the exact currently observed issue; a
changed permission/source binding, severity, outcome or acquisition/retry clock
invalidates that acknowledgement. Acknowledged issues remain inspectable and
never become healthy by acknowledgement. Store only bounded per-administrator
issue keys, fingerprints and timestamps; account deletion removes these personal
receipts. Require fresh platform role, session/CSRF, no-store, strict request
binding, foreign-admin isolation and stale-write rejection. Existing source
metadata readers, auth, connector settings and additive migrations are available
dependencies; no external API access is needed for this workflow. Acceptance:
all nine categories/two transport channels, renewal boundaries, recovery/retry/
source replacement, no secrets/private monitor disclosure, bounded storage,
concurrent/idempotent acknowledgements, migration/deletion, five-language desktop/
mobile UI including access loss and late responses, exact lint/build and relevant
API/browser checks. Complete the full API/UI feature before commit. Historical lag
charts, queue/fairness measurement and independent operational acceptance remain
open under MV2-052; this inbox does not complete the parent task.

**Execution evidence, 15 September 2026:** The complete source-attention inbox now supports personal exact-state acknowledgements, renewal/failure review and connector links across all nine categories. 32 API checks, three observed PostgreSQL lock races, the full build and 24 five-language desktop/mobile axe checkpoints passed. See [behavior, verification and remaining gates](docs/monitoring-v2/SOURCE_ATTENTION.md). The index and detail remain IN PROGRESS; publication does not establish production activation or complete broader operational requirements.

**Implemented complete feature scope, 15 September 2026 — source history:**
Persist bounded metadata-only samples for all nine source categories and both
Commute channels every five minutes through the existing maintenance scheduler.
Provide platform-admin 24-hour/7-day/30-day history with accessible charts and
paginated numeric detail. Show acquisition/publication ages separately, source
binding changes, error/unknown samples and missing sampling intervals. Do not
infer transit/processing/delivery latency from unrelated timestamps, reconstruct
old outages, silently interpolate missing observations or assert source coverage.
Keep 30 days of operational metadata with bounded cleanup, separate from native
source evidence, delivered revisions and personal decisions. Same-slot retries
must be idempotent and cannot rewrite historical samples. APIs remain read-only,
no-store and platform-admin-only; no credentials, payloads or private monitors
enter samples. Accept only known category/channel/range selections. Test real
scheduler integration, concurrency, retention/time travel, source changes and
no-data/future-clock handling, five-language responsive chart/table interaction,
access loss, late responses, migration and exact build/lint/backlog gates. Available
dependencies are the existing metadata snapshots and maintenance worker; external
source credentials are unnecessary. Broader processing/delivery lag, recovery and
human/target-host acceptance remain separate MV2-052 obligations. Complete the
whole sampler/API/UI feature before publishing.

**Source-history evidence, 15 September 2026:** The sampler, no-store admin API and five-language chart/table reader are implemented for all nine categories/two Commute channels. 45 integrated API checks, an observed PostgreSQL unique-key race, migration/retention checks and 24 responsive browser/axe checkpoints passed. See [semantics, checks and remaining limits](docs/monitoring-v2/SOURCE_HISTORY.md). Publication and activation are distinct; broader latency/recovery/fairness requirements stay open.

**Dependencies:** [MV2-011](#mv2-011), [MV2-012](#mv2-012), [MV2-025](#mv2-025). **Requirements:** §§23,28,33.11–12,34; legacy HL-094,099.

**User outcome:** The administrator can see missing data and the reason for a delay.

**Work:** Per-source ingestion/matching/delivery lag, last good state, error taxonomy and coverage gaps; alerts for actionable source failures; access-renewal reminders.

**Acceptance criteria:**

1. Charts distinguish source publication lag, ingestion lag, processing lag and channel delivery lag; zero does not replace unknown.
2. When data is stale or a licence expires, the UI and jobs follow the policy; recovery backfills gaps without flooding users with historical alerts.
3. AI utilization/budget/reuse and fairness are measured; diagnostics have a short timeout and do not delay the response.
4. Logs contain no secrets, Home coordinates or complete user prompts; correlated job IDs are sufficient for support.

**Verification:** Failure injection for source/queue/provider/email/DB telemetry and regression checks for bounded diagnostic locking.

**Execution evidence, 14 September 2026:** Scoped source-operations overview implemented at `/admin/monitoring-sources` for all nine directions and four packs. The platform-admin-only metadata reader distinguishes configuration, permission-record validity, receipt/provider/retry clocks, errors and unknowns, excluding private monitors and secrets. Five-language mobile/keyboard and access-redaction checks pass. See [verification and remaining gates](docs/monitoring-v2/SOURCE_OPERATIONS.md). Broader policy/reprocessing, lag charts and operational acceptance remain open; this contribution does not complete the parent task.

<a id="mv2-053"></a>

### MV2-053 — Personal-location privacy and access control

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Backend + Security reviewer · **Size:** M

**Whole-feature scope, 14 September 2026 — account deletion:**
Add an authenticated preview and password-confirmed account deletion workflow.
Delete owned personal monitor state, conversations, sessions and account secrets;
preserve shared official corpus and colleagues' decisions. Shared business
monitors require explicit handover to a current administrator before the owner
can be deleted; no colleague's identity or consent may be borrowed. The last
administrator of a populated workspace must complete administrator handover.
Single-member workspaces require explicit private-workspace erasure in the
preview. Retained shared decisions/audit lose the personal actor link rather
than cascading away. Cancel/remove private queued work and prove that in-flight
work cannot restore private data after deletion. Source access is not needed;
physical deletion, migration/rollback limits, foreign keys, concurrent handover,
roles/CSRF/password checks and five-language browser confirmation all require
evidence before this feature is committed. Backup and third-party delivery
retention must be described honestly; no production account is deleted by
development/testing. Dependencies are the existing auth/native ownership,
business sharing, job and export contracts. Broader privacy and live/human gates
remain separate. Do not publish a partial deletion endpoint or schema substep.

**Execution evidence, account privacy:** `/account` now provides a current,
password-confirmed nine-category deletion preview and transactional online
private-state erasure. Native Tender/IP/Auction access panels support explicit
ownership handover while retaining decisions and revoking personal source/email
access. Foreign-key, migration, retained corpus/file, session/CSRF/role and late
assistant/job checks cover the actual deletion workflow. Six isolated PostgreSQL
concurrency scenarios, 15 account browser and 99 business-access browser workflow
and full-document axe checkpoints passed; five locales and two widths are covered.
Root build and exact Ruff gate passed. See [account privacy evidence and recovery
limits](docs/monitoring-v2/ACCOUNT_PRIVACY.md). Production activation, independent
privacy review, backup-aware recovery and broader parent acceptance remain open;
MV2-053 remains IN PROGRESS.

**Whole-feature scope, 14 September 2026:** Download current owned monitor
configurations from all nine categories in Monitoring settings, including saved
configuration revision, lifecycle state and explicit email preferences. Paginated
collection and a final ownership/content check must reject incomplete, changed or
revoked downloads. Include a versioned manifest with collection times and hashes.
This is a configuration export, not a historical evidence archive or import tool.
It reads existing private data without source access, credentials, collection or
model calls; disabled sources do not prevent users exporting their own settings.
Native ownership and configuration contracts are available dependencies. Verify
all nine mappings, pagination, private/shared ownership boundaries, current roles,
no source/secret inclusion and browser cancellation/download in five locales.
Account deletion, historical evidence retention and independent privacy review
remain open under this parent task.

**Dependencies:** [MV2-004](#mv2-004), [MV2-005](#mv2-005), [MV2-013](#mv2-013), [MV2-014](#mv2-014), [MV2-023](#mv2-023). **Requirements:** §§5,27,31; inherited personal/organization access contract.

**User outcome:** Private Home locations, commutes and business interests are not exposed to another workspace.

**Work:** Consent and data minimization, owner-only personal scope, retention/deletion/export of user configuration, cache isolation and role checks; secrets stay in the current provider store.

**Acceptance criteria:**

1. Session, CSRF and current-role checks cover new endpoints, jobs, exports and evidence; negative IDOR tests pass.
2. Personal coordinate precision is limited to what matching needs; the public corpus does not contain private subject definitions.
3. Deleting an account or monitor applies the private-state/decision policy without destroying shared official history used by other workspaces.
4. Cloud AI is disabled by default; explicit opt-in shows which data is transmitted, with no hidden location/profile disclosure.

**Verification:** API privacy-boundary tests, deletion/export workflow, revocation during a job and browser workspace switching.

**Execution evidence, 14 September 2026:** Current owned configuration export is
implemented in `/monitoring/settings` for all nine categories, including archived
monitors and saved email preferences. It uses current owner/membership checks,
paginated reads, exact payload hashes, final record verification and cancellable
browser downloads. The feature/shared configuration/backlog suite passed 62 API
checks; the root build and exact Ruff gate passed. The compiled-browser protocol
checks real JSON downloads and 25 full-document accessibility/workflow checkpoints
in five locales and two widths. See [scope, evidence and limits](docs/monitoring-v2/MONITORING_CONFIGURATION_EXPORT.md).
This is a current-configuration export; account deletion, historical evidence,
independent privacy review and exact release activation remain open.

<a id="mv2-054"></a>

### MV2-054 — Single-server capacity and queues with different priorities

**Runtime repair scope, 15 September 2026 — complete business-scan health:**
Two real migrated-database reproductions show that IP and Auction return
`current` after a clean final page even when an earlier page contained a corrupt
source original. Persist unavailable evidence counts with each private scan
cursor across worker sessions. Reset the count only when starting a new scan or
changing source permission/generation. Legacy unfinished cursors must rescan
instead of treating an unrecorded earlier prefix as clean. Acceptance requires
cross-session early-page failure, clean rescan recovery, legacy migration and
private-history preservation. This independently deployable correctness repair
is required before interpreting the capacity workload's final health results.

**Business-scan repair execution evidence, 15 September 2026:** Both original
early-page corruption cases reproduced `current` instead of `partial`. The
native business regression passed 459 tests; its two new migration assertions
were corrected to compare the full affected tables without unrelated unloaded
models. Final ordinary/legacy scan, bounded-source and backlog checks passed
7 tests in 33.83s, retaining real private decisions/reviews. Exact API Ruff passed.
A dedicated PostgreSQL roundtrip preserved 222 private items, 444 history events
and 222 cursor bindings. See [behavior, migration and complete evidence](docs/monitoring-v2/BUSINESS_SCAN_HEALTH.md).
Production activation, full workload latency and parent MV2-054 remain unverified.

**Runtime repair scope, 15 September 2026 — bounded native record processing:**
An isolated nominal archive exposed repeated queries for never-matching public
records: a Hazard projection took 12,001 queries and 77.297s. Filter only unseen
warnings with no native decision under a validated monitor/source/boundary batch;
retain canonical processing for positive or existing private history. Stream
bounded IP/Auction source pages with exact identity/hash/retention checks and
prefetch existing private keys before skipping definite nonmatches. Preserve
unknown results, ownership, current permissions, raw integrity, page limits,
cursor continuation, review/delivery history and final publication checks.
This is an independently deployable runtime repair discovered during the larger
capacity investigation; it does not publish the unfinished capacity generator,
measurement or report. See [behavior and verification](docs/monitoring-v2/MONITORING_PROJECTION_BATCHES.md).

**Runtime repair execution evidence, 15 September 2026:** The combined native
Hazard/IP/Auction regression passed 809 tests in 552.43s; final business history
transitions and backlog integrity passed 3 tests in 12.18s. The exact API Ruff
gate passed. A repeated isolated PostgreSQL projection of the same 999 warning
heads used 36 queries / 1.140s, preserving zero new events and zero unavailable
inputs. Business source reads use four queries for either one or fifty records;
native private history survives a previously omitted record entering and leaving
selection. Source rights, corruption checks and membership remain enforced.
This establishes the local runtime repair, not full archive catch-up, concurrent
read latency, live source acceptance or release activation. MV2-054 remains
IN PROGRESS; the separate capacity workload remains unpublished development.

**Whole-feature scope, 15 September 2026 — durable handoff fairness:** An isolated
SQL reproduction with 110 older ingestion jobs filled the first 100 handoffs
without admitting any new Pollen, Road or Auction-email job. Separate workers
alone do not fix this earlier admission stage. Give ready queue classes persistent
turns before the page limit, preserve full throughput for a lone queue, retain
AI tenant fairness/window limits, and age priority within each non-AI queue.
Verify noisy ingestion, default and one-item batches, restarts/equal clocks,
old queue records, delayed/terminal/locked work, broker retries and private scope.
Use the existing dispatch sequence/locks without a migration or source access.
This closes handoff starvation, not the full target-host capacity acceptance.

**Handoff evidence, 15 September 2026:** Queue-class heads are selected before
the outbox page limit and use existing persisted dispatch sequences for turns.
An isolated PostgreSQL 16 run passed all eight cases: a legacy 110-job prefix,
restart/equal-clock rotation, eligible priority aging, private scope, broker
retry, full AI-window throughput, row-lock ownership and the nonblocking
dispatcher lock. Its disposable container was removed after verification.
The final integrated SQLite regression passed 130 tests in 459.63s, covering
dispatch/queues, interest automation, topic history, Inbox, matrix and document
history; three PostgreSQL-only lock checks were skipped. Required lint and the
backlog guard passed. See [handoff behavior and verification](docs/monitoring-v2/MONITORING_QUEUE_ISOLATION.md#durable-handoff-turns).
Target-host latency and production activation remain unverified; MV2-054 stays
IN PROGRESS.

**Queue-isolation evidence, 15 September 2026:** Independent control,
operational-source, bulk-source, projection and delivery consumers run inside
the existing worker-cpu container, retaining compatibility with the pinned
production controller. Native jobs keep their identity, consent and retry
semantics. The broad native/routing suite passed 358 checks; the subsequent
supervisor/recovery checkpoint passed 117; final bulk isolation and affected
Tender checks passed 33. Real Linux stop/crash/ignored-signal scenarios stopped
all six consumer parents and their six child processes. Live ping readiness
covers every consumer. See [evidence and resource limits](docs/monitoring-v2/MONITORING_QUEUE_ISOLATION.md).
These overlapping local checks do not prove the full target-host workload,
production activation or MV2-056 rollback acceptance. The parent stays IN PROGRESS.

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Operations + Backend + AI · **Size:** L

**Whole-feature scope, 15 September 2026 — Monitoring queue isolation:** The
production CPU worker currently consumes ingestion, parsing and maintenance;
all periodic tasks, including outbox dispatch and nine-direction scheduling,
route to maintenance. An isolated real Celery worker experiment observed both
CPU slots occupied and the control task unable to start until their release
(1.015s controlled observation; no production job or broker touched).
Separate bounded control, operational source acquisition, bulk source work, deterministic projection and
consented delivery workers from legal ingestion and AI. Preserve all nine
directions, native source/ownership checks, job IDs, retry/idempotency semantics
and legacy queues during rolling recovery. Use independent consumer processes
inside the existing worker-cpu container: the separately pinned production
controller must stop every writer without knowing new service names. Include
production/development Compose, supervised shutdown/failure/recovery, existing
recovery-runner coverage and scheduler retention separation. Verify broker task progress while
ingestion is occupied, durable old/new queue dispatch/retry, complete task routing
and rendered service configuration. No additional source rights are required.
This is the queue-isolation feature within MV2-054; the full 1000-subject/1M-row
workload and measured target-host capacity, recovery and GPU gates remain open.

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

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** Backend + Operations · **Size:** M

**Whole-feature scope, 14 September 2026 — selected evidence downloads:**
Add a user-visible export of a selected current or historical native change in
all nine categories. The packet must preserve the selected old/new state,
source/provenance and configuration/rule binding, distinguish private decisions
from source facts, and include a versioned manifest and content hash. The browser
must recheck current membership, exact record binding and source export rights
before writing a download. Historical selection must never silently substitute
the current source head. Source outages must not invalidate permitted retained
evidence, while revoked/expired permissions and retention gaps require an explicit
unavailable result. Never redistribute ASTRA raw payloads or authenticated SIMAP
originals; apply explicit IPI/auction export rights. Preserve existing Pollen and
IP exports. The dependencies are native exact-version readers, source rights,
private ownership and browser download contracts. No collection/model call or
external account action is required. Acceptance includes all nine mappings,
historical before/after fixtures, source revocation between preview/download,
scope changes, private/shared/foreign access, content integrity, cancellation and
five-locale desktop/mobile browser checks. Finish the complete API and UI feature
before commit; telemetry compaction, source rights review and broader retention
and recovery acceptance remain separate open gates.

**Dependencies:** [MV2-003](#mv2-003), [MV2-007](#mv2-007), [MV2-020](#mv2-020), [MV2-044](#mv2-044). **Requirements:** §§27,29–30,38.

**User outcome:** History remains verifiable while data volume is controlled.

**Work:** Retention by source/data class, raw/normalized states, compaction/downsampling policy, evidence pinning for delivered revisions and export manifests.

**Acceptance criteria:**

1. Evidence for delivered developments and decisions is not lost through telemetry compaction; the old/new states required for diffs remain available in a permitted form.
2. A retention/rights conflict requires a durable permitted raw or normalized snapshot with provenance sufficient for historical comparison. An expiry notice or link does not replace evidence; if a sufficient form cannot be stored, G(case) and the affected AC remain BLOCKED.
3. ASTRA raw-data export/API redistribution is blocked, SIMAP originals and commentary are separated, and IP permissions are enforced.
4. History exports reproduce provenance/state/rule/decision revisions; personal data is available only within the authorized scope.

**Verification:** Retention time travel, restoration of archived evidence, prohibited raw-export checks and negative cross-tenant export tests.

**Execution evidence:** Selected-evidence downloads are implemented in all nine native readers and explicit Tender/IP/Auction historical versions. The versioned private packet, signed preview and fresh authorized download passed 57 API/native cases, five isolated PostgreSQL cases (including observed source/scope revocation lock races), and 129 real browser downloads/full-document accessibility checkpoints across five locales and desktop/mobile widths. Cancellation, late replies, revoked/changed access, corrupted bytes and historical binding are verified. The complete root build and exact API Ruff gate passed. [Feature acceptance evidence](docs/monitoring-v2/MONITORING_EVIDENCE_EXPORT.md) records reproducible checks and source limits. Main publication uses the complete tested feature; production activation is not yet verified. Broader retention, recovery, source-rights and human acceptance remain open.

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

**Status:** IN PROGRESS · **Priority:** P0 · **Owner:** QA + Domain reviewers · **Size:** L

**Complete protocol scope and evidence, 15 September 2026:** The
[acceptance protocol](docs/monitoring-v2/ACCEPTANCE_PROTOCOL.md) now supplies one
concrete reviewer procedure for each of the 116 active AC, plus native suite
entry points, source prerequisites and required evidence fields. It covers all
nine directions and cross-domain CORE checks. The original traceability table
links each active row to its exact protocol anchor while preserving NOT VERIFIED,
all criterion wording and the ten deferred C4 rows. This is a completed review
preparation artifact, not a completed acceptance run or a test-coverage claim.
All 116 unique anchors and local suite/document references were checked. The
audit identified that B8's existing second-canton check compares rule outputs
only. MV2-050 now adds [complete normalized-adapter fixture conformance](docs/monitoring-v2/AUCTION_ADAPTER_CONFORMANCE.md);
live source, release and human acceptance remain separate requirements.
Live source evidence, actual executions, independent human review, the 79
supplemental requirements and broader task/legacy obligations remain open.

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

**Release regression scope, 15 September 2026:** Repair inherited Inbox/matrix
query-budget checks after connector settings added one bounded HTTP setup read.
Reproduce both reported failures and the 51-document matrix boundary, then assert
exactly one read per each of the four configuration tables independently of the
original page budgets: at most 13 Inbox reads for both one/fifty events, six
single-batch matrix reads, ten reads for 51 documents and four per history page.
Preserve heavy-body exclusion, correct saved report selection, tenant isolation,
history ordering and no model/source calls. Reuse the assertion in the existing
document-history regression; do not increase page budgets, skip tests or change
runtime behavior. These checks require no source credentials or human labels.
Full 116-AC traceability, independent review protocols, live source evidence and
release acceptance remain open; this repair does not complete the parent task.

**Execution evidence, 15 September 2026:** All three stale query-count assertions
reproduced, and all 31 Inbox-context, matrix-selection and document-history tests
passed after the repair (111.31s). Exact API lint passed. See
[release regression evidence](docs/monitoring-v2/DEPLOYMENT_STATUS.md#inbox-and-matrix-query-budget-repair--15-september-2026).
Full-suite success, activation and broader 116-AC acceptance remain unverified.

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

**Separate user direction, 22 September 2026:** [Influence Graph IG-001/002](BACKLOG_INFLUENCE_GRAPH.md)
scopes a political/corporate evidence explorer with private workspace authoring,
version history and editorial review. The user explicitly requested the complete
module and deployment through main. This separate workstream does not promote the
legal relation graph, change review variants, or complete this task's experiment.
Its source readiness, acceptance and pending release gates are recorded separately.

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
