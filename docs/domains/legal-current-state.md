# Legal current state and applicability boundary

Phase 0 audit, 28 September 2026; baseline commits and limits are in
[current state](../architecture/current-state.md). Target requirements are
[§32–43 and §73](../UNIFIED_TARGET_ARCHITECTURE_SPEC.md).

## What exists

Post-audit implementation update, 28 September: [release 1.31](../PRODUCT_STRUCTURED_CONTEXT.md)
adds optional Legal subject fields, including jurisdictions, parties, laws/cases,
procedural stage and relevant dates. Saved schemas and before/after history are
retained under current dossier roles. These remain human-provided context, not
an applicability decision or verified authority classification.

Helvetic Lens Legal already uses the common product Dossier API, persistent
investigation/claim models, source readers, monitoring policies and collaborative
roles. The canonical host is `legal.helveticlens.ch`; public `legal` API routes
resolve to the historical `loyer` key through
[ProductAliasMiddleware](../../services/api/helvetic_lens/product_identity.py).
Keep those records, URLs, idempotency scopes and grants intact.

Native Legal/general workflows have deeper regulatory models than the product
wrapper. Reuse [RegulatoryWork, RegulatoryExpression, RegulatoryDocumentVersion,
RegulatoryDate and native comparisons](../../services/api/helvetic_lens/models.py).
[regulatory_corpus.py](../../services/api/helvetic_lens/regulatory_corpus.py)
retains typed dates including effective-from/effective-to;
[Fedlex](../../services/api/helvetic_lens/fedlex_connector.py) and
[Basel-Stadt](../../services/api/helvetic_lens/basel_stadt_connector.py)
populate relevant source dates. Recorded dates are not, by themselves, a finding
that a rule applies to a particular person, place or event.

The repository also contains
[Federal Supreme Court](../../services/api/helvetic_lens/federal_court_connector.py),
[Federal Criminal Court](../../services/api/helvetic_lens/federal_criminal_court_connector.py),
[Parliament](../../services/api/helvetic_lens/parliament_connector.py),
[official notices](../../services/api/helvetic_lens/official_notices_connector.py)
and other official-stream adapters. Their
[capability contracts](../../services/api/helvetic_lens/source_capabilities.py)
record scope, language, known gaps and fixture/live evidence. A module or catalogue
entry is not verified nationwide, municipal or historical coverage.

[decision_report.py](../../services/api/helvetic_lens/decision_report.py) and
[analysis.py](../../services/api/helvetic_lens/analysis.py) already model
organization applicability, activity references, conditions and citations.
Unknown applicability cannot justify `no_action_now`. Preserve that behaviour;
it is useful partial capability, not the full target Legal Applicability Engine.

Public Legal dossiers are authored projections with moderated contributions.
Private dossiers use the same engine with current roles and evidence boundaries.
The target does not require another Legal collaboration or Ask service.

## Embedded assumptions and their proper destination

| Current assumption | Migration destination |
|---|---|
| `legal_profiles.ProfileConfig` reused for both products | Preserve legacy reader/writer adapter; select domain context through Core |
| `suggest_topics` explicitly asks for legal monitoring topics | LegalPack prompt/task policy; Pharma gets its own scoped instruction |
| RegulatoryWork legal document-kind constraint | Keep in legal corpus adapter; do not make medicines fictional legal works |
| Native source pack identifiers and source capabilities | Reuse Source Registry entries with domain tags and explicit readiness |
| Product claim statement plus evidence-status enum | Add Legal claim types and separate interpretation/review semantics |
| Product context as free-text jurisdiction/category | Optional structured Legal context; retain unknown and unresolved values |

## Missing applicability contract

Add optional typed country/canton/municipality, territorial and subject scope,
legal level, effective interval, procedural context, relevant dates and parties.
Link applicability to the exact source/work/expression/version and supporting
passage. Preserve publication, retrieval and effective dates as distinct facts.

Represent `amends`, `implements`, `superseded_by` and `interpreted_by` with scoped
references and provenance. Existing relationship machinery is a reuse candidate;
do not introduce a new graph database. If identity/date/scope is unresolved,
return unknown or a review requirement instead of choosing a plausible canton
or treating a retrieved page as current law.

Register authority categories from the specification: PRIMARY_BINDING,
PRIMARY_NON_BINDING, CASE_LAW, OFFICIAL_GUIDANCE, PARLIAMENTARY_MATERIAL,
SECONDARY_COMMENTARY, USER_DOCUMENT, USER_STATEMENT and AI_INTERPRETATION.
They need an explicit source-backed classification, separate from a publisher
name or search-engine position. Bind classification to source/version context;
do not assume every page on an official domain is binding law.

Register claim types that distinguish statutory rule, court holding, fact, party
argument, interpretation, exception, procedural requirement, jurisdiction rule
and AI analysis. A cited quotation and an inference about its application must
remain separately inspectable. Human acceptance and factual support stay separate.

## Smallest Legal control journey

Use an existing Legal dossier with two retained versions of a permitted official
source. Exercise the same Core scan manifest, deterministic difference, Finding,
review and Claim contracts proposed for Pharma. Link the exact applicable version
and explicitly unknown jurisdiction/authority dimensions. A contravening source
must remain visible. The Basel courtyard example is a future acceptance scenario,
not a legal conclusion produced by this audit.

Required regression cases:

1. Same content creates no duplicate version or Finding; older evidence reopens.
2. A changed effective date differs from a changed publication/retrieval date.
3. Wrong canton, repealed rule and unresolved procedural scope are flagged.
4. Commentary, party argument and generated analysis cannot become binding law.
5. Supersession preserves the historical claim, dates, review and evidence.
6. Public and private control cases use the same Core while excluding private
   passages, counts, caches and generated claims from anonymous/public readers.

Retain existing tests in `test_legal_profiles.py`, `test_law_history_metadata.py`,
`test_product_identity.py`, `test_product_investigations.py`,
`test_product_claim_evolution.py` and publication/guest suites. Add targeted tests
for the new applicability contract; existing source retrieval tests do not prove
legal correctness. No independent assessment of legal correctness is claimed;
this does not prevent implementing and testing the requested contracts.
