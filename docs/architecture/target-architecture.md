# Target architecture and migration proposal

Status: Phase 0 proposal, 28 September 2026. No production implementation is
claimed by this document. Read [the actual architecture](current-state.md),
[the gap matrix](core-gap-analysis.md) and
[the unchanged owner specification](../UNIFIED_TARGET_ARCHITECTURE_SPEC.md).

## Responsibility map

| Target responsibility | Reuse first | Planned extension |
|---|---|---|
| Dossier service | ProductDossier, LegalMonitoringProfile, product API | Explicit pack/domain/template metadata without changing existing identity |
| DomainPack registry | Product identity adapter and client product configuration | Small internal typed registry with versioned schemas and policies |
| Source registry | SourceCapability, SourcePackDefinition, subscriptions, connectors | Common adapter capabilities, domain tags and transparent unsupported entries |
| Evidence store / versions | Version, regulatory versions, InvestigationSource, artifact storage | Common scoped references and retained extraction/version provenance |
| Graph / claims | DossierClaim, ClaimEvidence, entity/relationship and ClaimChange tables | Domain types, separate review state, durable aliases and explicit supersession |
| Findings / reviews | Existing research and review histories | Durable Finding lifecycle and immutable Review records linked to exact inputs |
| Monitoring / coverage | Scheduler, policies/triggers, connector state, watches | Per-scan manifest across every configured source; incremental findings |
| Skills / router | Deterministic processors, generative client, decision adapters, capability gate | Versioned task registry, explicit routing policy and uniform execution receipts |
| Ask / search | Existing saved evidence, local retrieval, external discovery and research | Dossier-first resolution, accepted-claim semantics and domain interpretation |
| UI / collaboration | Existing product components, publication and role boundaries | Shared package/configuration; Coverage, Review and trust views over common contracts |

These are logical modules within the current deployment, not new microservices.
The target adds no graph database, autonomous legal/medical decision service or
mandatory new provider. Existing native/general workflows continue to operate.

## Smallest safe DomainPack introduction

Introduce an internal registry, conceptually `domain_packs.py`, with immutable,
validated definitions for GENERAL, LEGAL and PHARMA. This filename is proposed.
Registration is application-owned, not executable user plugins. Pack metadata
includes ID/version, context schema, entity/claim types, source-pack references,
skill references, templates, relevance/review policies and safe UI labels.

Resolve existing `pharma` to PHARMA and `legal`/`loyer` to LEGAL at the current
product identity boundary. Keep storage keys and public routes stable. A GENERAL
definition does not automatically migrate all native or Influence dossiers.

First move topic instructions, declared capabilities and source suggestions
behind this registry; use the same existing API handlers/jobs for both packs.
An unknown pack/type is rejected rather than silently selecting Legal. Source
availability comes from actual adapter readiness, not pack membership.

Do not add pack keys directly to `ProductDossier.context_json`: the present strict
Context validator would reject them or writers could erase them. When persisted
typed context is introduced, use additive nullable `domain`, `pack_version`,
`template_id` and a separately validated `domain_context_json` or a contained
extension table. Choose the migration form after checking update/erase paths.
Maintain a read adapter for existing generic work context and profiles.

## Compatibility and state rules

1. Add schemas/nullable fields and compatibility reads before switching writers.
   Backfill only deterministic mappings with counts and resumable checkpoints.
   Never infer a medicine, jurisdiction or accepted claim from a free-text label.
2. Pin pack/template/schema revisions on new records and jobs. Old records retain
   their old semantics until an explicit migration, including unknown metadata.
3. Preserve IDs, composite tenant foreign keys, source visibility, artifact keys,
   public projections, guest grants and the historical `loyer` storage identity.
4. Keep evidence status and human acceptance as separate axes. `SUPPORTED`
   remains evidence status. Add a review decision rather than relabelling it as
   ACCEPTED. Old unreviewed claims remain visibly unreviewed.
5. Findings point to existing evidence/version identities. Reviews retain target
   revision, actor, decision, comment and source/skill/model references. A stale
   review fails safely; acceptance plus claim update commits atomically.
6. Reuse ClaimChange for cross-run comparison provenance. An explicit supersession
   link must preserve the old claim and all contradictory evidence. Dismissal
   retains history; it does not delete source material or prove falsity.
7. Public derived material may use only its authorized evidence audience. A
   separate reviewed public projection requires author consent; a flag is not
   permission to copy private evidence into public search or remote inference.
8. Introduce per-slice flags/defaults only where they create a practical rollback.
   Disable new writers while retaining readers and additive data on rollback.
   Test upgrade/rollback/re-upgrade and old/new mixed clients; avoid destructive
   down-migrations in production.

## Sources, coverage and execution

A configured source gets a manifest entry even when it is disabled, unsupported,
unconnected, rate-limited or failed. Capture scan identity, attempt/success/change
times, source and query scope, adapter revision and error category. Preserve last
success when a new attempt fails. Candidate indexes, document fetches and full
source feeds have different coverage scopes and must remain distinguishable.

Lookup and deterministic processing precede inference. A proposed routing receipt
contains task/skill/version, domain/pack revision, authorized input references,
selected provider/model/tool version, output reference, measured latency, usage,
estimated cost basis or unknown, fallback reason and timestamp. Reuse current
decision measurements and runtime identities; do not replace them with brand names.
Provider failure cannot turn incomplete coverage into an empty successful scan.

Two target sections give slightly different ordering for claims and evidence.
Interpret both as a dossier-local retrieval tier before external discovery:
retrieve accepted claims together with their supporting/contradicting evidence,
then exact source versions and entity/event context. Expand through configured
sources and broader permitted search only for unresolved gaps. Acceptance does
not make a claim permanently true or override fresher contrary evidence.

## Phases and release gates

| Phase | Complete outcome | Required evidence before advancing |
|---|---|---|
| 0 | Five audited documents and explicit migration path | Source links resolve, target input hash matches, every capability classified; current code distinguished from proposals |
| 1 | Pack-aware creation/setup on the existing common engine | Both clients choose correct domain context/instructions; old drafts/URLs/access work; no extra model call for deterministic selection |
| 2 | Legal context, authority and applicability proposal with exact versions | Wrong canton/version/date is unknown or flagged; source fact and interpretation separate; existing Legal regressions pass |
| 3 | Shared incremental scans and visible coverage | Same input adds no duplicate version/finding; change creates retained version; configured failure remains visible with last success |
| 4 | Findings, human review and structured accepted claims | Atomic acceptance, preserved dismissal/conflict/supersession, revision conflict and role/audience tests |
| 5 | One dossier-aware Ask contract | Claims/evidence/version citations, contradiction and incomplete-coverage output, no cross-audience retrieval |
| 6 | Auditable deterministic-first routing | Lookup/diff calls no LLM; actual model/skill/pack identity captured; failure fallback and unknown cost remain honest |
| 7 | Configurable Pharma Market Access template | Verified source contracts, substance/product/indication/market distinction and review policy; missing adapters shown |
| 8 | Legal control journey and Swiss Pharma vertical slice | End-to-end evidence in both clients, exact released revisions, verified source readiness and functioning human review |

Phases may reuse existing completed capability; they are not instructions to
rewrite it. Keep the existing Monitoring backlog authoritative for its nine
directions, recording related MV2 scope before implementation. Phase 0 changes
only documentation. Full architecture acceptance remains OPEN.

## Answers to the owner's nine implementation questions

1. **Existing Core:** product models/access/publication, research coordinator and
   jobs, shared source/version readers, corpus search, monitoring policies,
   collaboration and review histories already belong to Core. Native extraction,
   diff, auth, storage and provider transports are also reuse foundations.
2. **Embedded Legal assumptions:** the profile foreign key/base input classes,
   legal-only topic prompt, fixed source enums, legal regulatory work kinds,
   Pharma-specific branches and generic string context. Keep genuinely Legal
   corpus logic behind LegalPack rather than broadening its meaning silently.
3. **Smallest DomainPack:** an internal typed registry resolved from existing
   product identity; first consume it in setup/source recommendations. Add
   persisted domain context compatibly only when a complete UI outcome needs it.
4. **Extend existing models:** ProductDossier and profile compatibility; existing
   evidence/version tables; DossierClaim, ClaimEvidence, ClaimChange and entity
   relations. Add missing Finding/Review/scan-manifest records only where current
   histories cannot express the required stable identity and transaction.
5. **Shared UI:** reuse wizard/workspace, source and version readers, investigation,
   graph/claim display, trust panel, team/publication controls and global Ask.
   Consolidate copied clients into one versioned source package with thin site
   configuration; preserve gateway and native-shell behaviour during adoption.
6. **Legal Applicability:** typed jurisdiction/territory/level/subject/time and
   procedural context linked to authoritative source versions, amendment/
   supersession relations, authority classification and evidence-backed rules
   for matching. Reuse RegulatoryDate and organization-applicability analysis;
   neither currently proves full dossier-level applicability.
7. **Pharma Market Access:** typed substance/product/indication/market IDs and
   aliases; real BAG/SL and Swissmedic source contracts; configurable literature
   and supporting sources; reviewable domain claim types, coverage and template.
   Existing “Market access” example text is not that implemented template.
8. **Useful Jev/Laya:** keep their validated System One relevance/strategy
   adapters and same-input comparison; local Laya can classify permitted saved
   evidence without hosted disclosure. Reuse pinned E5 for corpus embeddings.
   Recheck licence/terms and task accuracy when extending use; do not use either
   as a factual authority, crawler or universal reasoning engine.
9. **Smallest proving journey:** one versioned-source Legal dossier and one
   Semaglutide–Switzerland Market Access dossier share creation, scan manifest,
   version/diff, finding, review, accepted claim and cited Ask. Include unchanged
   rescan, source failure, contradictory update, late/stale review and private
   access tests. Synthetic fixtures prove mechanics; real authorized source
   readiness and actual human decisions remain distinct from fixture results.
   This plan adds no new approval requirement for routine tested development.
