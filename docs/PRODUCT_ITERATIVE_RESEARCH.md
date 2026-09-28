# Iterative dossier research — 1.34

Status: VERIFYING production activation. Scope recorded before implementation, 28 September 2026.
Normative owner input: [Investigation Engine](INVESTIGATION_ENGINE_SPEC.md), exact
attachment SHA-256: 79bffc35f960a4709ed1a499a2f17ff808dfd1b2307fe486f890f2e466112675.
This is the first vertical slice in sections 42–43, not full global coverage or
completion of the unified architecture. Parent MV2-002/020/023 remain IN PROGRESS.

## Section 47: architecture found before changes

| Area | Existing implementation | Actual limit / reuse decision |
|---|---|---|
| Dossier | ProductDossier owns LegalMonitoringProfile, entries, team access, domain context and templates | Reuse identity and permissions; research must not require activating monitoring |
| Monitoring | Native topic matching, source/page watchers, separate monitoring and recurring-web policies/triggers | Keep these pipelines and standing-authority limits unchanged |
| Search | decision_search federates Search1API Google/Bing and Pharma Europe PMC, URL dedup and reciprocal-rank fusion | Reuse adapters; current rank does not reject unrelated candidates |
| Jev | decision_engines.JevEngine, hosted TypeSafe SystemOne jev-latest | Reuse structured choices for a three-way pre-fetch gate; no accuracy/truth claims |
| Laya | decision_engines.LayaEngine, operator-owned local multilingual SystemOne | Reuse fallback on unavailable Jev; disclose engine/error, uncertainty must not become acceptance |
| Apertus routing | service.organization_runtime resolves saved ApertusConfiguration into the common ai.ModelClient | Use configured model for planning, uncertain-candidate assessment and accepted-source extraction/reflection; record actual configured provider/model, never assume Apertus by name |
| Sources/evidence | InvestigationSource retains bounded excerpts/hash; ClaimEvidence requires exact quote/locator and contained FKs | Keep snippets out of evidence; retain existing source rights, exclusions and source-class uncertainty |
| Entities/claims | Run-scoped DossierEntity mentions, DossierRelationship quotes and revisioned DossierClaim | Existing names are unresolved; add conservative identifier-based resolution, evidence-linked edge metadata and persistent questions |
| Jobs/workers | Native ai_background job, one step per delivery, lease/generation/inflight fencing and access checks before/after calls | Extend phases; retain durable checkpoints, no automatic repeat of interrupted paid calls |
| UI | Shared client Investigation/Findings/SourceCard inside readable dossier chapters; global Ask; five-step monitoring wizard | Add question-first creation and open-question reader; preserve separate source/AI/discussion surfaces and folded diagnostics |

## Bounded implementation and acceptance

Dependencies: existing scoped investigations, decision adapters, safe anonymous
reader, configured workspace inference, current session/role access, Sites clients.
Source readiness is dynamic: configured providers and legally accessible pages are
not a promise of complete internet, private archives, OCR or independent truth.

- Add a version-pinned iterative mode to new explicitly requested research. Legacy
  and standing monitoring/contribution runs keep their historical execution rules.
- Persist configurable cumulative budgets, a real question decomposition, branches,
  evidence-grounded gaps and their child searches. A child must produce new source
  evidence and update the same claim in the end-to-end fixture.
- Gate each candidate with Jev/local Laya before fetch; reject unrelated candidates,
  separately assess uncertain ones; provider failure never implies relevant.
- Reuse exact citations and claim revisions. Resolve only explicit matching public
  identifiers; retain unresolved same-name mentions. Graph edges link claims and
  literal evidence, with qualified source classification/period/amount metadata.
- Stop for limits, duplicate work, absent new evidence or access loss. Pause/resume
  preserves work; explicit continuation can add a bounded budget without repeating
  interrupted paid operations. Private saved context never enters search/planner.
- Title + research question starts without monitoring setup. Both clients show
  findings, source evidence, relationships, open questions and follow-up provenance.
- Required checks: real native worker end-to-end with controlled external adapters,
  irrelevant-canton regression, uncertainty/fallback, invalid evidence, duplication,
  budgets, restart/pause, current roles and migration retention. Fixture research is
  labelled fixture; live-provider/source acceptance is separate. Keep an exact run
  trace and concrete quality signals, never a fabricated truth score.
- Run API lint, affected tests and backlog invariant, client tests/lint/types/build;
  publish exact validated main and verify native + both existing Sites releases.

## Limits and further work

Full cross-run canonical entity registry, unrestricted source traversal, every
source connector, independently calibrated relevance/quality and professional
human acceptance remain open. Native jobs remain bounded serialized deliveries;
independent planned branches do not imply simultaneous expensive model execution.

## Evidence

Implementation and controlled execution checks are recorded below. Publication/activation is still pending; this is not yet a production completion claim.

## Implementation report (sections 42–43 and final-report checklist)

1. **Existing architecture:** the section 47 table above records the inspected baseline before edits.
2. **Reused:** ProductDossier, current roles/guest scope, native job/outbox and lease control, Search1API/Europe PMC adapters, SystemOneEngine, safe anonymous reader, exact citations, claims/history, exports, cross-run comparison and document chapters.
3. **Added:** `product_iterative_research` for typed plans, questions, budgets and identity/evidence handling; `product_iterative_steps` adds phases to the existing worker; `product_research_gate` supplies three-way decisions. Both clients add question-first creation, question provenance and explicit budget continuation.
4. **Schema:** additive `09d495bef125` adds non-null `product_investigations.research_state` JSON with `{}` for retained runs. New questions, limits and usage are versioned within the contained run; branches and citations use existing tables. Migration refuses to discard nonempty new state. Old runs, source history and monitoring triggers are not reinterpreted.
5. **Jev:** existing hosted TypeSafe adapter evaluates public candidate titles/snippets before fetch. Default order remains Jev then Laya, following the earlier owner choice; optional local-first reverses that order. Provider-reported confidence is not measured accuracy.
6. **Laya:** existing operator-owned local adapter makes the same structured decision. It is selectable first and can fall back to hosted Jev; total provider failure prevents candidate reading. No new account, service, key or inference stack was created.
7. **Apertus/configured model:** the existing organization ModelClient handles decomposition, selective uncertain-candidate assessment, extraction of accepted source excerpts and evidence-grounded reflection. Successful new model phases record the configured provider/model and an explicit response-identity limitation. The new end-to-end fixtures use controlled completions, not a claim that a live Apertus 8B/70B run passed. Automatic size-based 8B/70B routing is not added.
8. **Execution:** durable plan → independent question branches → federated candidates → Jev/Laya gate → uncertain escalation if needed → safe read → exact-quote claims/entities/edges → cited gap → new branch/search → new evidence on the same claim. Each network/model step is checkpointed before the call; lease, generation and current access are checked again before saving results.
9. **Follow-ups:** reflection sees only that branch's captured public excerpts, their public-supported claims and prior public questions. Every proposed gap must reference an exact public quote/locator and an in-scope claim when supplied. Private saved content is analysed separately and never enters public planning/reflection.
10. **Safeguards:** cumulative reserved search/fetch/decision/model budgets; active-time deadlines; configurable branch/depth bounds; normalized query dedup preserving word order; URL/attempt dedup; identical document bytes retained with a dependency link but not re-extracted or counted as new claim support. No new source/evidence means no recursive follow-up. Interrupted paid calls are not automatically repeated; explicit retry restarts only the unavailable phase. Complete identifiers require a cited issuer and jurisdiction before mentions can be grouped. Names alone and incomplete namespaces remain unresolved.
11. **UI:** New dossier accepts title + question + public-search consent. Monitoring setup stays separate. The Research chapter presents claims/citations, typed connections, source identity evidence and open questions with the original discovery and new evidence links. Counts link to real sections. Routing, source decisions and resource controls are folded. Existing chapters, permissions and human discussion remain separate.
12. **Tests:** native-worker scenarios for Pharma and Legal, uncertain escalation, Jev failure/Laya fallback, local-first ordering, total provider failure, budget/continuation, private-query isolation, invalid follow-up citation, pause/restart/inflight recovery, access revocation, migration retention, directional query dedup, cantonal-health/motorway rejection, failed-planner retry, document-copy independence and incomplete identifier scope. Both clients exercise actual rendered markup and continuation helpers alongside existing gateway/access tests.
13. **End-to-end result:** passed on the real API/native worker with controlled external adapters. This proves durable orchestration and validated evidence mutation, not live provider accuracy or public-source coverage. Exact saved receipts: [Pharma](research-evaluations/2026-09-28-iterative-pharma-fixture.json) and [Legal](research-evaluations/2026-09-28-iterative-legal-fixture.json).
14. **Known limits:** independent branches use serialized native worker deliveries; no fixed parallel-agent fleet. Entity grouping is run-local and source-asserted, not a cross-dossier registry determination. Only bounded anonymous HTML/text/PDF excerpts are available. OCR, authenticated archives, OpenSearch/pgvector deployment, universal source traversal, full temporal/amount normalization, independent human acceptance and measured live-model relevance remain open. Existing monitoring/contribution runs retain their earlier bounded contract; no silent standing-authority expansion. Claim support remains machine-linked source evidence.
15. **Next iteration:** a bounded authorized public-source evaluation using current live providers, followed by reviewed cross-run entity identity and source-dependency/temporal contracts. Broader source/index/model infrastructure from the diagrams must retain separate implementation and activation evidence.

## Exact execution path of the controlled research run

This is a real saved coordinator run with **fictional fixture records**, not a live
investigation of a real foundation. No private production dossier was used and no
paid provider call was made by these tests.

- Run `9e60022f-d371-4601-b525-3b2bac4b3831`: `Investigate Alpine Foundation funding, recipients, amounts, periods and documentary evidence.`.
- Branch `54a8fc5f-e1fd-4d18-85a9-3f7da56a06ef`: `Alpine Foundation legal identity` → search:completed, gate:completed, gate:completed, read:completed, extract:completed, reflect:completed.
- Branch `c4e8336b-30d9-4b40-9138-34c733472cb0`: `Alpine Foundation grants report` → search:completed, gate:completed, gate:completed, read:completed, extract:completed, reflect:completed.
- Branch `87baa050-6a40-4e4e-b62f-bce5d65e287e`: `River Trust Alpine Foundation recipient disclosure 2024 grant amount` → search:completed, gate:completed, gate:completed, read:completed, extract:completed, reflect:completed.
- Public source `9b1d40a4-c478-4a9c-acf1-0aacbc2686f9`, locator `p1`, triggered question `4ad7ca86-e99f-4e76-bc64-8ec880f6cd79`: **Does River Trust disclose the same amount for 2024?**.
- Follow-up query: `River Trust Alpine Foundation recipient disclosure 2024 grant amount`; parent `c4e8336b-30d9-4b40-9138-34c733472cb0` → child `87baa050-6a40-4e4e-b62f-bce5d65e287e`.
- Existing claim `ad8d748f-d951-41a3-a85c-7b0e6b258281`: revision 1 SUPPORTED (quoted CHF 50,000) → revision 2 CONTESTED (new quoted CHF 40,000). Both source excerpts remain linked; the statement was not rewritten.

Concrete quality signals: two planned directions, one evidence-triggered follow-up
at depth 1, three distinct captured fixture bodies, three pre-fetch rejections,
one retained claim with two revisions, two identifier-grouped entities with five
cited mentions, one typed relationship linked to that claim, exact source hashes
and locators on all evidence, and a visible amount contradiction. All fixture
URLs use example.org: independent publisher diversity and factual accuracy were
**not measured**. The separate duplicate-body test proves that a second URL with
identical bytes cannot strengthen the claim. Source classifications in this run
are controlled model outputs with quotes, not verified primary-source status.

## Supplied target diagrams

The Pharma/Legal diagrams supplied on 28 September agree with the shared Core:
source adapters → retrieval/indexes → fast decisions → selective analysis → dossier,
with a separate update-monitoring path and common access/audit controls. Iterative
research adds a return edge from evidence gaps to planning/search. Provider order
is now configurable. The illustrations are a target map; their OCR, OpenSearch,
pgvector and automatic Apertus model-size routing boxes are not asserted as newly
installed or production-verified by this release.


## Local validation before publication

64 distinct API checks passed across the affected suites: 15 iterative cases,
46 existing investigation/search/backlog cases and 3 contribution retry cases.
The final budget/restart refinement passed its two affected checks again.
Required API lint and diff checks passed. Both clients passed 189 tests, lint,
type checking and final Sites builds. Seventeen shared client paths match;
the protected-value scan passed across Core, both clients and emitted artifacts.
Two actual native worker traces with controlled external adapters are retained.
No production private dossier, browser interaction, paid inference probe or
independent model-quality evaluation was performed. Exact production activation
and assets are the next gate.
