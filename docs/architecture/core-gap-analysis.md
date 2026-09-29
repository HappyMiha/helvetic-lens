# Core gap analysis

Baseline and evidence: [current state](current-state.md), 28 September 2026.
Normative requirements: [owner specification](../UNIFIED_TARGET_ARCHITECTURE_SPEC.md).
Implementation proposal: [target map](target-architecture.md).

`EXISTS` means the stated bounded capability has an inspected implementation.
`PARTIAL` means useful implementation exists but does not satisfy the whole row.
`TODO` means the target contract/workflow needs implementation or verification.
`BLOCKED` identifies an external acceptance prerequisite, not difficult work.
`NOT_NEEDED` means the specification excludes the addition from this migration.
These statuses are not new live-source or professional-acceptance results.

Implementation update, 28 September 2026: [domain-aware setup 1.29](../PRODUCT_DOMAIN_SETUP.md),
[readable dossier 1.30](../PRODUCT_DOSSIER_CLARITY.md) and
[structured subject context 1.31](../PRODUCT_STRUCTURED_CONTEXT.md) and
[versioned templates 1.32](../PRODUCT_DOSSIER_TEMPLATES.md) and
[readable coverage 1.33](../PRODUCT_DOSSIER_COVERAGE.md) and
[reviewed entity mentions 1.39](../PRODUCT_ENTITY_IDENTITY.md) and
[source-pinned human claim review 1.40](../PRODUCT_CLAIM_REVIEW.md) extend the
Phase 0 baseline. Rows below identify those bounded additions; the frozen audit
receipt remains historical. Full target and human acceptance remain open.

## Component matrix

Paths below are relative to `services/api/helvetic_lens` unless stated otherwise.
The linked [current-state map](current-state.md) locates the corresponding code.

| ID | Target component / specification sections | State | Current evidence and remaining work |
|---|---|---|---|
| C01 | Shared Legal/Pharma Dossier service (§0,4,5,54) | EXISTS | `product_api.py`, `product_models.ProductDossier`: same routes, schema and persistence for both products |
| C02 | Full common GENERAL/LEGAL/PHARMA model (§5,69) | PARTIAL | Product dossiers share profiles and registered Legal/Pharma packs; saved context and template guidance pin pack/schema/template revisions. Native Influence dossiers remain separate; explicit GENERAL adaptation remains open |
| C03 | Typed domain context (§5.2,33,45) | PARTIAL | 1.31 adds optional validated Legal/Pharma context, pinned schemas, editor authorization and before/after history through `product_domain_context.py`. Legacy work context remains intact; resolved entity identities and applicability remain open |
| C04 | Public/private/shared audience (§6,41,42,61) | EXISTS | Product publication projections, current dossier membership, guest grants and scoped research; preserve separate publication consent |
| C05 | Organisation enterprise mode (§6) | PARTIAL | Organizations, roles and tenant scope exist; internal connectors and full enterprise policy/audit coverage remain separate |
| C06 | Evidence graph (§7) | PARTIAL | ClaimEvidence, DossierEntity/Relationship and ClaimChange use relational containment. 1.39 adds contained cross-run pair reviews without merging originals; no unified Finding/Review/Note graph projection |
| C07 | Versioned evidence and originals (§8,9,60) | PARTIAL | Version/regulatory versions/artifacts and InvestigationSource snapshots exist; no one typed evidence/source/version reference across every representation |
| C08 | Retained native versions and comparisons (§9,20) | EXISTS | `models.Version`, `RegulatoryDocumentVersion`, `NativeDocumentComparison`, `product_document_history.py`, `law_history.py` |
| C09 | Durable structured claims (§10) | PARTIAL | DossierClaim/ClaimEvidence persist assertion and evidence links. 1.40 adds a separate source-pinned human acceptance axis on the same claim via ClaimReview; typed subject/predicate/object and validity remain open |
| C10 | Domain claim types / fact versus interpretation (§11,39) | PARTIAL | 1.43 registers Legal/Pharma type choices and stores versioned editor classifications in existing evidence-pinned ClaimReview records; source/user/AI distinctions, unknown legacy state and protected history reach review/search/export. 1.46 adds explicit SOURCE_QUOTE versus AI_INTERPRETATION output with strict literal quotation checks and retained labels; extraction classification, semantic entailment and authority/applicability remain open |
| C11 | Finding lifecycle (§12) | PARTIAL | 1.40 treats existing extracted DossierClaim proposals as findings with explicit pending/accepted/dismissed/needs-more-evidence review. General materiality, domain types and source-change lifecycle remain open |
| C12 | Human Review service (§13,50) | PARTIAL | Answer, source, relationship and native match reviews exist. 1.39 records append-only editor decisions for exact cited entity pairs with evidence fingerprints and reviewer erasure; 1.40 adds explicit acceptance/dismissal/more-evidence decisions on retained claims with source/comparison fingerprints, append-only history, public consent and erasure-aware reviewers. Known extraction routes are pinned; historical missing versions stay unknown. General/domain review policies remain open |
| C13 | Accepted finding creates/updates claim (§13,71.4) | PARTIAL | `product_claim_review_api.apply_review` atomically records a revision/evidence-pinned ClaimReview and claim_reviewed event on the existing extracted DossierClaim; human state is projected separately from machine evidence status. 1.43/1.44 add explicit typed review/source roles. This corrects the stale pre-1.40 audit; no duplicate Finding/Claim model is required. Required domain review policy, canonical claim validity and explicit cross-run supersession remain open. [Shared journey verification](../PRODUCT_SHARED_JOURNEY.md) records the bounded composed proof |
| C14 | Source Registry / adapter interface (§14) | PARTIAL | SourceCapability, SourcePackDefinition, connectors and subscriptions exist. Unify discovery/document/version/health capabilities and domain membership |
| C15 | Skill Registry (§15,37,48) | PARTIAL | Explicit deterministic functions and reviewed AI capability profiles exist; no general versioned domain task registry with input/output contracts |
| C16 | Tool Router / AI Gateway (§16–18) | PARTIAL | `analysis.py`, `decision_engines.py`, capability gates and search adapters exist. Routing is caller-specific, not one deterministic/API-first policy |
| C17 | Jev / Laya typed decision adapters (§17) | EXISTS | System One request/response validation, bounded transport, actual model labels, measurements and explicit fallback are implemented |
| C18 | Full provider/skill/pack execution receipt (§17,23,65,67) | PARTIAL | DecisionSearchRun, job/checkpoint events and native runtime fingerprints exist; every execution does not yet share all target provenance fields |
| C19 | Apertus synthesis integration (§18) | EXISTS | Existing configured generative client/runtime settings, grounding and capability mechanisms; availability and professional quality are separate |
| C20 | Incremental monitoring (§19) | PARTIAL | Native scheduler, connector cursors, page watches and product policy/trigger workers exist; unify scan-to-Finding lifecycle and complete manifest |
| C21 | Deterministic change detection (§20) | EXISTS | `diffing.py`, retained content hashes and native version comparisons; no inference needed for identity/hash/basic diff |
| C22 | All target change types/materiality (§20,57) | PARTIAL | Native change/event and evidence-comparison types exist; domain explainable materiality and unified typed findings need work |
| C23 | Coverage Manifest (§21) | PARTIAL | 1.33 `product_coverage` composes current topic revisions, selected pack state, watched pages and recurring-search metadata in both dossier readers. This is saved operational state; durable historical per-scan manifests remain open |
| C24 | Source Health (§22) | PARTIAL | 1.33 exposes last attempt/success separately and retains missing/inactive selected packs and unsupported stream IDs. Page, feed and search states remain separate. Full normalized rate-limit/auth/source-version states remain open |
| C25 | Audit / Provenance (§23) | PARTIAL | DossierEntry audits, immutable publication revisions, InvestigationEvent and review histories; unify target-reference/version semantics |
| C26 | Universal dossier Ask / Search (§24,59) | PARTIAL | Shared product Ask, saved local retrieval and external search exist. 1.41 adds current human review to all private saved-search modes, separate machine/citation labels and bounded review freshness checks. 1.42 adds explicitly consented claim groups with accepted-first ordering inside a bounded candidate set and retained-answer freshness/visibility. 1.43 adds editor classification to current search metadata; type edits invalidate research dependencies while model input categories stay unchanged. 1.44 adds source-specific reviewed roles to results with the same dependency protections; reasons and assessment history stay outside inference. 1.45 explicit reviewed-input synthesis is verified; it preserves old consent scopes and pins related review dependencies. 1.46 optional source-analysis output is verified with explicit format consent, retained provenance and inherited source privacy. Whole-ledger accepted ranking and cross-source coverage integration remain incomplete |
| C27 | Structured dossier memory (§25) | PARTIAL | Claims/entities/evidence/history/preferences persist outside chat; 1.40 persists accepted/rejected/unresolved human claim projections and review history; 1.41 reads current projections in search without embedding human decisions or reusing stale acceptance. 1.42 pins selected claim context into research notes and prevents obsolete reconfirmation or unavailable-source reads/exports. 1.43 versions domain claim classifications in the existing review basis; untyped legacy records remain unclassified. Durable cross-run aliases and generic/domain Findings remain open |
| C28 | Collaboration (§26) | EXISTS | Shared comments/contributions/files, source suggestions, assignments, questions and dossier roles. New Finding review requests can extend this |
| C29 | Shared frontend source (§27,54) | PARTIAL | 152/153 common tracked component/lib TypeScript files identical; still copied across repositories, not one versioned package |
| C30 | Visual direction (§28) | PARTIAL | Brandbook tokens, themes, Lens state and global Ask delivered in scoped releases; all-page and human visual acceptance remain open |
| C31 | Common trust panel (§29) | PARTIAL | Exact source readers, timeline, transparency and source comparisons exist; 1.41 shows citation relationship, current human decision and bounded conflict/context warnings in saved search; 1.42 carries exact support/contradiction quotes and separate human/machine state through preview and retained notes; 1.43 distinguishes editor-classified source statements, user assertions and AI interpretation without inferring authority; 1.44 adds exact-source role, editor rationale and capture/version basis to folded review/history, with source-specific search display; full applicability/review/coverage/path composition is missing |
| C32 | Contradictions and supersession (§30,65) | PARTIAL | SUPPORTS/CONTRADICTS and cross-run links/status/history exist; typed reviewed claim supersession must preserve both original evidence chains |
| C33 | DomainPack contract/registry (§31,64) | PARTIAL | `domain_packs.py` registers LegalPack/PharmaPack 1.4.0, domain instructions, capabilities, context schema IDs, registered template IDs, editor claim types and source-role categories. `dossier_templates.py` defines versioned guidance. Full GENERAL/skill/source/review-policy contract remains open |
| C34 | Legal context and applicability (§32–35) | PARTIAL | RegulatoryDate, source metadata and organization-applicability analysis exist; no full dossier-level territory/level/subject/procedure/time contract |
| C35 | Legal source packs (§36) | PARTIAL | Fedlex, parliamentary/court/official and Basel-Stadt connector modules; each stream has bounded readiness. Requested countries/municipalities are not implied coverage |
| C36 | Registered Legal skills (§37) | PARTIAL | Retrieval, version comparison, citation/impact analysis functions exist; explicit skill versions and applicability/holding interpretation contracts are missing |
| C37 | Legal authority classification (§38,39) | PARTIAL | 1.44 adds explicit Legal source-role assessments to the existing ClaimReview basis, pinned to each exact capture/citation with retained editor reasons/history; mixed-source claims never receive blanket authority. Review/search display and dependency invalidation are implemented; 1.45 explicitly consented claim/source metadata input is verified; 1.46 separates literal saved quotation from AI interpretation without granting authority. Source-wide inheritance, authority ranking, canonical typed Findings and legal applicability remain open |
| C38 | Legal change-to-reviewed-claim journey (§40,73,76) | PARTIAL | Native monitoring and product investigation operate; 1.40 proves controlled extraction→comparison→human review on both product aliases; typed applicability and the complete live Legal journey remain open |
| C39 | Pharma uses existing Core (§44) | EXISTS | Existing Pharma client uses ProductDossier and shared investigation/search/monitoring engine |
| C40 | Pharma product/substance/indication identity (§45,48) | PARTIAL | 1.31 separates user-provided product/substance/indication/country names and regulatory/market-access/trial identifiers. 1.39 permits source-cited exact-namespace pair suggestions and explicit same/different/unresolved editor review within one dossier/audience; a canonical identity registry and general alias resolution remain open |
| C41 | Pharma monitoring-first workflow (§46) | PARTIAL | Saved page, topic and recurring-web research exist; template-driven domain findings/review are incomplete |
| C42 | Configurable verified Pharma source pack (§47,51) | PARTIAL | Europe PMC discovery and suggested public Swissmedic/EMA/FDA page watches exist. Dedicated BAG/SL and domain-specific authoritative source contracts are not verified here |
| C43 | Registered Pharma skills (§48) | TODO | No typed substance/label/reimbursement/safety skill registration with task evaluations |
| C44 | Market Access Dossier template (§49,55,71.7–8,77) | PARTIAL | 1.32 persists selected Market Access guidance and revisions with suggested subject fields and research questions. Source-backed monitoring, Finding/Review/Claim and a validated Swiss Market Access journey remain open |
| C45 | Domain-specific mandatory review (§50) | TODO | Roles/review mechanisms exist; high impact, conflict, match uncertainty and incomplete coverage need versioned policy with enforcement |
| C46 | Existing-system/internal evidence connections (§52,53,60) | PARTIAL | Uploaded evidence is supported; internal enterprise APIs and shortage connectors are not established by upload support |
| C47 | Supply prediction / enterprise-system replacement (§52,53,78) | NOT_NEEDED | Not a first-slice goal; do not build an ERP replacement, parallel shortage database or prediction promise |
| C48 | Configurable templates/composable capabilities (§55,56) | PARTIAL | 1.32 provides six registered Legal/Pharma templates, versioned retained guidance, explicit choice/change/clear and history. Source/skill/monitoring/review-policy capability composition remains open |
| C49 | Explainable relevance (§57) | PARTIAL | Matching rationale, citations, BM25/fusion and decision measurements exist. Legal applicability and exact Pharma identity/materiality factors need typed evidence |
| C50 | Meaningful notifications (§58) | PARTIAL | In-app Following updates and separate native daily/weekly digest consent exist; not all target immediate/digest modes for reviewed Findings and coverage warnings |
| C51 | API targets (§62) | PARTIAL | Existing product dossier/research/evidence/team/publication APIs and the 1.33 shared saved-coverage reader cover much of the intent. 1.40 adds audience-fenced claim review pages/writes on existing product routes. Generic pack discovery and complete per-scan manifests remain open |
| C52 | Full historical dossier reconstruction (§65) | PARTIAL | Retained versions, snapshots, plan/claim/publication histories exist; not one tested “everything known at date X” query across all object types |
| C53 | Observability (§67) | PARTIAL | Jobs, scan health, inference measurements and history exist; consistent scan→finding→review→claim aggregate metrics are missing |
| C54 | Incremental performance (§68) | PARTIAL | Hash/dedup, bounded jobs, source cache and E5 cache exist; proposed unified flows need no-op/duplicate/cost regression tests |
| C55 | Safe incremental migration (§69) | PARTIAL | 1.31/1.32 add context/template columns in migrations 07d495bef125 and 08d495bef125 with empty defaults, preserved legacy content, revision fences and refusal of destructive downgrade after saved data exists. 1.39 adds the contained entity review table in 0ad495bef125, preserving originals and refusing destructive downgrade of retained reviews. 1.40 adds ClaimReview in 0bd495bef125 without rewriting machine statuses, with guarded downgrade. Broader target migrations/flags/rollback coverage remain open |
| C56 | Guaranteed professional correctness/certification (§66) | NOT_NEEDED | Explicitly outside the target promise. Implement human review (C12/C45); neither fixtures nor HTTP success confer professional certification |
| C57 | New graph DB, copied engines, fixed lens services (§7,56,78) | NOT_NEEDED | Relational contained models and common engine already provide the foundation |

## Acceptance traceability

This is a gap map, not a checked release checklist. Keep all new target acceptance
open until implementation, tests and its required release/domain evidence exist.

| Target acceptance group | Matrix coverage | Additional proof needed |
|---|---|---|
| §72 Dossier | C01–C05, C33 | Registered domain selection, legacy compatibility and audience matrix |
| §72 Evidence | C06–C08, C11 | Every target Finding resolves exact retained source/version under current access |
| §72 Claims | C09–C13, C32 | Typed fact/interpretation, contradictions and accepted/superseded history |
| §72 Monitoring | C20–C24 | No-op and duplicate tests; failed configured source remains visible |
| §72 Coverage | C23–C24 | Source-by-source scan receipt, last success and explicit incomplete status |
| §72 AI | C15–C19, C26 | No LLM for deterministic work; full receipts and evidence-grounded answers |
| §72 Human review | C11–C13, C25 | Revision-pinned acceptance/dismissal and atomic claim update |
| §73 Legal | C34–C38, C32 | Applicable authority/version/jurisdiction, typed claims and unchanged Legal workflows |
| §74 Pharma | C39–C45 | Configurable Market Access, real source readiness, reviewed claim and cited Ask |
| §75 Tests | C04, C08–C24, C34–C45 | Existing tests plus explicitly new domain/review/coverage cases below |

## Existing tests to retain, not replace

All paths are under [services/api/tests](../../services/api/tests).
These are inspected regression entry points, not tests newly executed in Phase 0.

| Existing tests | Useful established boundary | Missing target assertion |
|---|---|---|
| `test_product_dossiers.py`, `test_product_identity.py`, `test_legal_profiles.py` | Existing creation/profile and alias contracts | Pack/template selection and typed context preserve old clients |
| `test_product_investigations.py` | Restart, quote validation, contradictions, tenant scope and bounded paid retry | Versioned skills and normalized durable Finding |
| `test_product_document_history.py`, `test_law_history_metadata.py` | Retained source versions and metadata | Uniform cross-source evidence reference |
| `test_product_claim_evolution.py`, `test_product_claim_review.py` | Independent comparisons and source-pinned human decisions on the same durable claim; source/publication/guest boundaries, stale evidence and reviewer erasure | Domain typing, reviewed semantic supersession and end-to-end live acceptance |
| `test_product_source_health.py`, `test_topic_coverage.py` | Last success survives failure; explicit saved source state | All configured sources in one durable scan manifest |
| `test_product_monitoring_research.py`, `test_product_page_research.py`, `test_product_web_research.py` | Scoped repeat monitoring and source-change research | Domain materiality and reviewed-Finding notifications |
| `test_product_publications.py`, `test_product_public_research.py`, `test_product_guests.py` | Public projection and current source/member boundaries | Mixed-source derived Claim cannot become public implicitly |
| `test_product_decision_search.py` | Same-input comparison, provider failure, unknown usage and partial federation | Deterministic/API-first task router and full execution receipt |
| `test_product_corpus_search.py`, `test_product_evidence_search.py` | Local retrieval, revocation and retained citations | Accepted-claim plus contradictory-evidence retrieval priority |

New domain tests must explicitly cover Legal wrong jurisdiction/version and
primary versus secondary authority; Pharma substance/product alias collisions,
market/indication mismatch, changed reimbursement evidence and high-impact
review. Do not treat a keyword match as any of these outcomes.

## Next bounded scope

Preserve bounded setup, subject context and versioned template guidance. Continue
the remaining Phase 1 contracts, starting from shared source/scan coverage and
retained evidence/version references needed by Findings and Review. Record the
next complete user outcome, compatibility and acceptance before code. Template
configuration alone cannot establish a validated Market Access journey or full DomainPack.
