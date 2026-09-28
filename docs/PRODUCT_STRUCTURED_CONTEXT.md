# Structured dossier context — release 1.31

Status: IN PROGRESS. Scope recorded before code on 28 September 2026.
This continues C03/C33 of the Unified Target Architecture and MV2-002/020/023.

## User outcome

Save optional, distinct subject fields on the existing dossier: products, active
substances, indications and markets for Pharma; jurisdictions, parties, courts,
authorities, laws/articles/cases and relevant dates for Legal. Read the saved
context as part of the dossier and edit through one shared, schema-driven form.
Names and identifiers remain user-provided context, not resolved entities or
verified regulatory/legal facts. Existing free-form work context is preserved.

## Contract and compatibility

Add one non-null JSON object column on ProductDossier, default empty,
separate from strict product_operations.Context. Pin domain, pack revision and
context schema ID in its saved envelope. Reuse dossier row revision, organization
mutation lock, current EDITOR authorization and DossierEntry audit. Existing
records start empty without inferring drug identity or jurisdiction from names.
Keep old clients and API aliases operational. The common internal registry owns
both bounded schemas; no dynamic plugin loading or copied domain service.

This step does not apply context to monitoring queries, external searches or AI
prompts. No automatic source selection, inference or public projection follows
saving it. Exact identity resolution, templates, applicability, Market Access
source packs and full DomainPack/GENERAL remain open. Source readiness unchanged.

## Acceptance

1. Both domain schemas accept optional bounded typed lists/text/dates, reject
   unknown and wrong-domain fields, and retain substance/product/market separation.
2. Save/read/reload/clear are durable, revision fenced and audited with actor and
   exact context envelope. Duplicate retries must not append duplicate history.
3. Viewer/contributor, foreign organization, revoked guest/session and anonymous
   access fail appropriately. Existing owners and invited editors can update.
4. Public projections/reuse never copy this private context implicitly. Private
   JSON export and printable brief retain it with safe escaping; erasure follows
   its containing dossier and normal audit attribution rules.
5. Additive migration preserves existing dossier data; old work/context writes
   cannot erase the new fields. Rollback uses old code over the additive column;
   no production down-migration. Unknown schema revisions fail safely in the
   context panel without breaking the rest of the dossier.
6. The 1.30 document structure remains calm. Saved context is a readable section;
   the shared editor opens explicitly, preserves unsaved input on failure and
   exposes optional fields without pretending they are source facts.
7. Meaningful API/migration/access/privacy and client rendered/form tests pass,
   exact API Ruff and client test/lint/type/build gates pass, then main sources,
   normal native activation and exact existing Sites artifacts are verified.

## Evidence

Implementation is present in both clients and the shared Core. The internal
LegalPack/PharmaPack revision is 1.1.0; context schema IDs are legal-context/v1 and
pharma-context/v1. Migration 07d495bef125 adds only domain_context_json, defaults
existing rows to empty and refuses a destructive downgrade once context exists.
Rolling back application code leaves this additive column intact.

GET/PUT /products/{product}/dossiers/{id}/domain-context reuses current dossier
access and the organization mutation lock. Writes share the existing work
revision and retain a replay key, actor and exact before/after envelope in
DossierEntry. Field lists are bounded to 30 items of 240 characters, 12,000 total;
only exact duplicates are removed. Dates are validated without applicability
inference. Existing work settings, queries and source policies are independent.

The document shows recorded subject details and an explicit editor. Folded history
uses the existing loaded dossier entries, with author, date and before/after
values; older history uses the existing pagination. Unknown context schemas stay
retained and leave the rest of the dossier readable. Private print/export retains
context, while public projections and copied public dossiers exclude it.

Local client validation: 173 tests each (five new subject checks), lint, types and
Sites production builds passed. Eight actual rendered/helper checks include the
existing dossier reading regressions. API regression passed: 105 checks (104 integration, including 22 new context
cases, and one backlog smoke check), 550.77 seconds. Exact API Ruff and
protected-value/source-parity checks passed. Production activation and exact
artifact verification remain pending.
Full architecture, source readiness and human professional/usability acceptance
remain open.
