# Versioned dossier templates — release 1.32

Status: IN PROGRESS. Scope recorded before code on 28 September 2026.
Bounded C33/C44/C48 contribution; MV2-002/020/023. Depends on verified 1.29
pack selection, 1.30 document UX and 1.31 optional structured subject context.

## User outcome

Choose an optional registered template during creation or explicitly change it
later on an existing dossier. Start with Legal Question, Legislative Monitor,
Case / Dispute, Market Access, Regulatory Monitor or Safety. The common registry
supplies a description, optional context-field suggestions, research questions
and an editable question/sector starter. The saved dossier shows its original
versioned guidance; later registry edits must not reinterpret existing choices.
The calm document layout and separate research/source/discussion chapters remain.

## Contract and boundaries

Add a default-empty JSON template snapshot on ProductDossier, preserving old
records and strict legacy work context. Pin template/schema/domain/pack revisions.
Catalogue uses existing authenticated product APIs. Selection changes reuse
current editor authorization, organization locking, dossier revision and actor-
attributed before/after DossierEntry history. Creation keeps old no-template
replay; a supplied template reference must match the original creation selection
on retry even after a later template change. Private print/export retains it.
Unknown retained formats stay readable/exportable without silent overwriting.

Templates provide research guidance only. Selection must never silently change
existing questions, subject values, source choices, monitoring, consent, review
status or visibility; no search or model call follows selection. No new source
adapter, source approval or Market Access factual result is established. Current
public projections and public-copy workflows omit private template metadata.
A validated end-to-end Market Access journey and full DomainPack/GENERAL remain
open. Rollback uses old application code over the additive column; destructive
downgrade is refused after template data exists.

## Acceptance

1. Same immutable registry configures both products; wrong domain, unknown IDs
   and unavailable versions fail without creating or modifying a dossier.
2. Create/read/reload/change/clear retain exact selected guidance and audit;
   retries remain idempotent and stale or reused requests fail explicitly.
3. Current editor/guest roles, revocation, foreign organization, CSRF and anonymous
   access are enforced; public projections/reuse do not copy private settings.
4. Additive migration retains old dossier content; private print escapes text;
   schema drift preserves saved bytes and the rest of the dossier remains usable.
5. Optional shared UI handles catalogue loading/failure, preserves drafts on
   failed save and supports explicit conflict recovery and read-only roles.
6. Meaningful API/migration/privacy and rendered/client helper tests, exact API
   Ruff, both full client test/lint/type/build gates and backlog invariant pass.
7. Finished sources immediately pushed to main, normal Core activation and exact
   existing Sites artifacts verified. Browser/private production/paid probes are
   excluded in this heartbeat; human and full architecture acceptance stay open.

## Evidence

Implementation is present in Core and both clients. LegalPack/PharmaPack 1.2.0
expose three registered template IDs each. Migration 08d495bef125 adds only a
non-null default-empty template_json column. Template guidance is selected from
the server registry, not trusted from a client payload, and is retained verbatim
with dossier-template/v1 plus pack/template/context schema identifiers.

Creation audits the original selection with the existing actor. An exact creation
retry still resolves that original selection after later changes or catalogue
updates; old no-template retries remain compatible. PUT selection shares current
editor rights and work revision, supports explicit clearing and request-key
replay, and retains before/after history. It does not mutate profile configuration,
subject details or source choices. Public projections/reuse omit the setting;
private export preserves even unknown saved formats and print escapes content.

The shared UI offers optional selection during creation, an explicit action to
fill only empty starter fields, a folded guidance reader, editor-only changes
and attributed history. Existing drafts can change their template from the dossier.
Unknown formats and stale saves remain explicit. Current resource readers fence
late catalogue responses and session changes.

Initial API tests: 11 passed in 63.23 seconds after repairing two fixture
assertions (new UUID/default normalization and anonymous CSRF helper usage).
Both client suites: 179 passed each, lint/types and Sites builds passed. Six new
checks cover actual template rendering, retained versions, empty-field-only
starters, history, roles and same-product gateway boundaries. Exact API Ruff,
source parity and protected-value checks passed. Full affected API regression passed: 116 checks (115 integration and
one backlog smoke) in 610.88 seconds. Production verification remains pending.
