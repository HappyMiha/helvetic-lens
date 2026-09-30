# Helvetic Lens project map

One agent develops complete features on **main**, following [the development cycle](docs/DEVELOPMENT.md).
The shared platform is **helveticlens.ch on HappySnowman**, including Monitoring features.

The owner's 28 September [Unified Target Architecture](docs/UNIFIED_TARGET_ARCHITECTURE_SPEC.md)
sets one Core with LegalPack and PharmaPack. Start with the
[current-state audit](docs/architecture/current-state.md),
[target map and nine-question proposal](docs/architecture/target-architecture.md),
[capability gap matrix](docs/architecture/core-gap-analysis.md),
[Legal audit](docs/domains/legal-current-state.md) and
[Pharma implementation plan](docs/domains/pharma-implementation-plan.md).
Phase 0 documents reality and the migration path; target implementation and
domain acceptance remain open. The first bounded implementation is
[domain-aware dossier setup](docs/PRODUCT_DOMAIN_SETUP.md), followed by
[readable dossier chapters](docs/PRODUCT_DOSSIER_CLARITY.md) and
[structured subject context](docs/PRODUCT_STRUCTURED_CONTEXT.md) and
[versioned dossier templates](docs/PRODUCT_DOSSIER_TEMPLATES.md) and
[readable source coverage](docs/PRODUCT_DOSSIER_COVERAGE.md) and
[iterative dossier research](docs/PRODUCT_ITERATIVE_RESEARCH.md), with
[bounded research evaluation](docs/PRODUCT_RESEARCH_EVALUATION.md) and
[research reader recovery](docs/PRODUCT_RESEARCH_REPAIR.md) and
[honest uncertainty and local gate evaluation](docs/PRODUCT_RESEARCH_GATE_POLICY.md) and
[captured-source relationships](docs/PRODUCT_SOURCE_RELATIONSHIPS.md) and
[reviewed entity mentions](docs/PRODUCT_ENTITY_IDENTITY.md) and
[source-pinned human finding review](docs/PRODUCT_CLAIM_REVIEW.md) and
[current human review in saved search](docs/PRODUCT_REVIEWED_SEARCH.md) and
[consented claim-grounded research](docs/PRODUCT_CLAIM_SYNTHESIS.md) and
[reviewed domain claim kinds](docs/PRODUCT_CLAIM_INTERPRETATION.md) and
[source-specific editor roles](docs/PRODUCT_SOURCE_AUTHORITY.md) and
[explicit reviewed context for AI research](docs/PRODUCT_REVIEWED_SYNTHESIS.md) and
[quoted saved text versus AI interpretation](docs/PRODUCT_SOURCE_ANALYSIS.md). Existing product client repositories and working
native workflows are preserved during incremental migration.

The new default entry uses [research before monitoring](docs/PRODUCT_RESEARCH_FIRST.md):
bounded exploration, cited orientation and an explicit next direction; no recurrence
is inferred from the first question.
[Selected direction context](docs/PRODUCT_SELECTED_DIRECTION.md) is VERIFYING production activation: retain the chosen rationale and earlier passage in the existing planner and reader.
[Optional early clarification](docs/PRODUCT_EARLY_CLARIFICATION.md) is verified within scope: one consequential source-backed choice through existing pause/reply.
[Early cited orientation](docs/PRODUCT_EARLY_ORIENTATION.md) adds a tentative reading
while that bounded episode continues; its release evidence remains separate.
[Evidence-directed reinterpretation](docs/PRODUCT_ADAPTIVE_ORIENTATION.md) connects
new passages to actual follow-up research; release evidence is tracked separately.
[Selected-question assessment](docs/PRODUCT_QUESTION_ASSESSMENT.md) adds the bounded research outcome; Core and both clients verified.
[Read-informed reflection](docs/PRODUCT_INFORMED_RESEARCH.md) is verified in Core and both clients: current per-question assessments inform existing requests and preserve the early snapshot.
[Usefulness of read passages](docs/PRODUCT_READ_RELEVANCE.md) is verified in Core and both clients: source-contained assessments and bounded next candidates.
[Bounded query reformulation](docs/PRODUCT_QUERY_RECOVERY.md) is verified in Core and both clients for successful but unproductive public searches.
[Bounded source recovery](docs/PRODUCT_SOURCE_RECOVERY.md) checks already retrieved alternatives after failed public reads within existing budgets; Core and both clients verified.
[Purpose of the current check](docs/PRODUCT_RESEARCH_PURPOSE.md) is verified within scope: explain the saved rationale within the existing activity.
[Current research activity](docs/PRODUCT_RESEARCH_ACTIVITY.md) binds visible work to a current worker receipt and expires stale activity; Core and both clients verified.
[Observed research scope](docs/PRODUCT_RESEARCH_SCOPE.md) explains captured passages and unfinished work beside the conclusion; Core and both clients verified.
[Episode progress](docs/PRODUCT_EPISODE_PROGRESS.md) distinguishes repeated and changed captured material across continued research; Core and both clients verified.
[Useful research updates](docs/PRODUCT_RESEARCH_UPDATES.md) are verified within scope: surface a saved cited assessment while research continues.
[Optional question-update recovery](docs/PRODUCT_BRIEFING_RECOVERY.md) is verified within scope; preserve an independently valid research summary.
[Question assessment renewal](docs/PRODUCT_QUESTION_RENEWAL.md) is verified within scope; later evidence can inform the existing final briefing.
[Branch question assessment](docs/PRODUCT_BRANCH_ASSESSMENT.md) is verified within scope; capture counts remain separate from an evidence-bound tentative answer.
[Ordinary open-question continuation](docs/PRODUCT_OPEN_CHECK_CONTINUATION.md) is verified in Core and both clients; new fully recorded checks do not require early reinterpretation.
[Saved-check continuation](docs/PRODUCT_SAVED_CHECK_CONTINUATION.md) adds an explicit
next episode for a source-contained unfinished check; Core and both clients verified.

The owner authorized separate Pharma and Legal product clients; Legal is the confirmed name from 28 September 2026.
see [delivery and release evidence](docs/PRODUCT_DOSSIERS.md).
The [test and release policy](docs/TESTING.md) separates platform smoke, functional
and integration suites. The deployment page supports saved defaults and a
next-attempt override, including an explicitly selected hotfix with a reason.

| Activity | Queue | State |
|---|---|---|
| Monitoring v2 | [Active backlog](BACKLOG_MONITORING_V2.md) | Pollen, River / Lake and Basel Air code released on the main site; applicable acceptance remains open |
| Legal Hackathon 2026 | [Hackathon](docs/workstreams/HACKATHON_2026.md) | Optional partner adapters and technical activation guide; live access and acceptance remain open; frozen MVP preserved |
| Legal monitoring profiles | [Reference analysis and acceptance](docs/LEGAL_MONITORING_PROFILES.md) | `/monitoring-profiles`: five-step persisted legal setup, native topics, source subscriptions and personal delivery |
| Influence Graph | [Usage and architecture](docs/INFLUENCE_GRAPH.md), [acceptance](BACKLOG_INFLUENCE_GRAPH.md) | `/influence`: evidence explorer, private workspace dossiers, immutable revisions and reviews; release verification pending; legal relation-graph promotion remains gated |
| Support and infrastructure | [Support](docs/workstreams/SUPPORT.md) | Parked pending the user's explicit start |

| Instance | Code | Website |
|---|---|---|
| Main product and Monitoring features (HappySnowman) | main | helveticlens.ch |
| Pharma client (Sites, shared native core) | [helveticlens-pharma/main](https://github.com/HappyMiha/helveticlens-pharma) | [pharma.helveticlens.ch](https://pharma.helveticlens.ch) |
| Legal client (Sites, shared native core) | [helveticlens-legal/main](https://github.com/HappyMiha/helveticlens-legal) | [legal.helveticlens.ch](https://legal.helveticlens.ch) |

The user retired `monitoring.helveticlens.ch` on 12 September 2026. Do not restart
its HappyDucky02 deployment, Windows task, `helvetic-lens-v2` Docker project, tunnel
or hostname. Retained private data and deployment evidence must not be deleted or
transferred as part of routine development.

The active Monitoring backlog is the file on main. Older integration/task branches
and host aliases are historical, not development routes. Customs/C4 remain deferred.
Keep scoped task acceptance distinct from broader shared-contract and human pilot gates.

The [Monitoring Centre](docs/monitoring-v2/MONITORING_CENTRE.md) at `/monitoring`
provides the shared entry point for saved Pollen, River/Lake and Air monitors and
nine honestly gated scenario choices. Its code verification and release boundary
are recorded separately; the broader MV2-017/018 tasks remain in progress.

Platform administrators can inspect all nine directions and four source packs at
`/admin/monitoring-sources`; see [source operations evidence](docs/monitoring-v2/SOURCE_OPERATIONS.md).
Configuration, permission records and acquisition are distinct from verified coverage.
The [source history reader](docs/monitoring-v2/SOURCE_HISTORY.md) adds 24-hour,
7-day and 30-day sampled charts with explicit gaps and paginated hourly detail.

The [Monitoring settings hub](docs/monitoring-v2/MONITORING_SETTINGS.md) at
`/monitoring/settings` groups all nine native monitor editors with source connections.
Platform administrators can save encrypted API credentials and native collector
options, select existing permissions and explicitly test saved access. Requests
and workers adopt new settings without a restart; source coverage remains separate.

[Monitoring worker isolation](docs/monitoring-v2/MONITORING_QUEUE_ISOLATION.md)
separates operational acquisition, bulk feeds, private projection, scheduling
and email from legal ingestion and AI. Persistent queue turns also prevent an
old ingestion prefix from hiding new Monitoring work before broker handoff.
All CPU consumers share the existing
deployment-managed container lifecycle. Local verification and target-host
capacity/activation evidence are recorded separately.

All nine native editors offer [natural-language configuration drafts](docs/monitoring-v2/MONITORING_CONFIGURATION_DRAFTS.md).
An explicit proposal opens as unsaved native fields for review. Reviewed model
capability and source identity boundaries remain in force; manual editing is
available when inference is unavailable.

Users can [download owned current monitor settings](docs/monitoring-v2/MONITORING_CONFIGURATION_EXPORT.md)
from `/monitoring/settings` for all nine categories or the selected category.
The private JSON export includes configuration revisions and email preferences,
with pagination, integrity checks and final ownership/content verification.
Historical evidence, source credentials and colleagues' monitors are excluded.

The [account privacy workflow](docs/monitoring-v2/ACCOUNT_PRIVACY.md) at `/account`
previews deletion across all nine monitor categories and requires the current
password and explicit confirmations. Shared business monitors have owner handover
in their native access panels. Shared history, source and backup retention limits
are documented separately from online private-state erasure.

The native [Hazard wind/thunderstorm workflow](docs/monitoring-v2/HAZARD_WATCH.md#native-source-activation-and-complete-vertical-workflow-14-september-2026)
uses the public Swiss MeteoAlarm channel and pinned swisstopo geometry through
the normal collector. Existing operator decisions remain authoritative. Other
hazard coverage, exact production activation and live/human acceptance stay open.

The shared `/related-developments` view groups owner-private Hazard, River and
Road events using reviewed geography and explicit source times. Exact source
identities, decisions and deliveries remain independent; see
[workflow and acceptance evidence](docs/monitoring-v2/RELATED_DEVELOPMENTS.md).
Its release activation and permitted live/human acceptance remain separate gates.

Today includes a [shared review-count overview](docs/monitoring-v2/TODAY_COUNTS.md)
for all nine active directions and the legal feed, with native visibility rules,
complete-count boundaries and direct section links. Code checks are distinct from
source coverage, large-workspace capacity and exact production activation.

See [deployment evidence](docs/monitoring-v2/DEPLOYMENT_STATUS.md) for exact active
commits and selector migration. A push is not proof of a successful release.
Preserve the [frozen MVP tag](https://github.com/HappyMiha/helvetic-lens/releases/tag/v1.0.0-hackathon-mvp)
and [legacy obligations](docs/monitoring-v2/LEGACY_DISPOSITION.md).

Tender, IP and Auctions support [explicit workspace sharing and monitor responsibility](docs/monitoring-v2/BUSINESS_MONITOR_SHARING.md), plus [individual item responsibility and decision comments](docs/monitoring-v2/BUSINESS_ITEM_WORK.md). Assigned-to-me/unassigned filters lead to native item histories pinned to the reviewed evidence. Shared native review retains source gates; personal email and authenticated SIMAP documents stay owner-private. Physical account deletion, broader review-state coverage and exact production/human acceptance remain open.

All nine native readers expose [word matching in selected saved evidence](docs/monitoring-v2/MONITORING_EVIDENCE_ASK.md), with literal extracts and authenticated references to the same evidence. This model-independent feature adds no source collection, monitoring actions or outgoing messages. Generative conclusions, natural-language drafts and broader MV2-023 acceptance remain open.

The [offline business evaluation workflow](docs/monitoring-v2/BUSINESS_MATCHING_EVALUATION.md)
prepares and checks independent B2/B7/B8 relevance evidence, source-field citations
and complete-output factual audits. Reproducible reports retain failed/missing
rows and separate business/language results. It never promotes a model; real
reviewer evidence and broader MV2-051 acceptance remain open.

[Acceptance procedures for all nine directions](docs/monitoring-v2/ACCEPTANCE_PROTOCOL.md)
cover the 116 active criteria with source prerequisites, concrete reviewer steps
and existing test entry points. The traceability table links each criterion;
procedures and test references remain distinct from executed acceptance evidence.


The Pharma/Loyer [visual-language reference](docs/PRODUCT_VISUAL_LANGUAGE.md)
ships shared light/dark tokens, a global Ask/Search and an evidence-first dossier
in release 1.9. Its exact client production proof is separate from the ongoing
[dynamic investigation engine](docs/PRODUCT_INVESTIGATION_ENGINE.md) and the
remaining native-platform page migration.

Cross-investigation [evidence evolution](docs/PRODUCT_CLAIM_EVOLUTION.md) adds
independent comparison jobs, exact citation pairs and visibility-safe editor
review in the shared core and both Pharma/Loyer readers. Stage 4b monitoring
reopening remains separate from this release's acceptance.

[Monitoring-triggered dossier research](docs/PRODUCT_MONITORING_RESEARCH.md)
connects explicitly enabled private native topic-match follow-up to the same
investigation and evidence-evolution engine in Pharma and Loyer. Its standing
account authority, bounded usage and exact production acceptance remain explicit.


[Saved-page research](docs/PRODUCT_WATCHED_PAGE_RESEARCH.md) extends the same
standing private research policy with an explicit scope choice, exact retained
page versions, paired change excerpts and revision-safe source readers in both
products. Its scoped acceptance remains separate from recurring open-web discovery.

[Recurring public-web research](docs/PRODUCT_WEB_RESEARCH.md) adds an explicit
standing public question and daily/weekly cadence in both products. Separate
revisioned policy/occurrence receipts, shared query reservations and current-role
fences drive the existing private investigation engine. Unchanged captured bodies
and excerpts skip analysis; new evidence is independently compared with prior
findings. Local functional checks and exact native/both-client production
acceptance pass within the linked scoped release; the full specifications remain open.

[Private saved-evidence search](docs/PRODUCT_EVIDENCE_SEARCH.md) brings local Laya
meaning search and model-free word search to retained passages and claim citations
in both products. Current dossier and paired-source permissions precede counts,
ranking and paging; direct semantic windows retain uncertain candidates rather
than hiding evidence behind an uncalibrated classifier threshold.

[Personal research updates](docs/PRODUCT_RESEARCH_NOTIFICATIONS.md) project
completed source-bearing investigations into the existing Pharma/Loyer Following
journey, with opt-in private subscriptions, public living-research markers,
current-audience history and exact source/comparison links. Native source review
and consented external delivery remain separate.

[Whole-dossier saved-evidence retrieval](docs/PRODUCT_CORPUS_SEARCH.md) adds
resumable local preparation, an exact-input source-contained cache and complete
permission-filtered ranking in Pharma/Loyer. Independent multilingual sample
results, model limits, source rights and scoped release acceptance are explicit;
pgvector and broader professional-quality approval remain separate gates.


[Shared product navigation](docs/PRODUCT_NAVIGATION.md) links Pharma, Loyer and
the native Monitoring platform through fixed public destinations, retaining
current work and destination permissions. The native H identity and navigation
frame adopt Brandbook v1.0; remaining native page themes and human acceptance
stay separate.


[Reading themes](docs/PRODUCT_READING_THEMES.md) migrate native evidence/work
surfaces and login to shared Brandbook palettes. The native platform and both
clients use the same device-local preference behavior. Scoped local and exact
production acceptance are distinct from the remaining full visual/product gates.


[Global Ask/Search](docs/PRODUCT_GLOBAL_ASK.md) adds a native entry for authorized
saved readers, author-published product knowledge and conflict-safe preparation
in existing Marvin context. Both product commands retain dismissed questions and
share safe keyboard ownership. Context transitions reset only the command; full
visual/product acceptance remains separate.

[Source reading and inspectable provenance](docs/PRODUCT_SOURCE_READING.md) aligns
native saved/corpus evidence and both product readers with Brandbook hierarchy.
Exact scoped release verification passes; broader source-editor and visual
acceptance stays open.

[Saved comparison clarity and selection safety](docs/PRODUCT_SAVED_COMPARISONS.md)
separates native baseline drafts from persisted evidence and makes both product
page-change captures inspectable. Server receipts and exact saved-version actions
retain existing access and revision boundaries. Scoped exact production acceptance
passes; full visual and professional review gates remain open.

## Saved document context and Legal naming (1.27)

The owner confirmed **Helvetic Lens Legal**, canonical `legal.helveticlens.ch`,
repository `HappyMiha/helveticlens-legal`. Legacy Loyer URLs and the internal
`loyer` key remain compatible with the same records and rights. See
[Legal rename](docs/PRODUCT_LEGAL_RENAME.md) and
[saved document context](docs/PRODUCT_VERSION_CONTEXT.md). Supplied specifications
and historical release receipts retain their original spelling. Both slices
are DONE within scope with exact production evidence in release 1.27; full
investigation/visual specifications remain IN PROGRESS.

[Evidence read recovery](docs/PRODUCT_READ_RECOVERY.md) is DONE within verified 1.28 scope: scoped retry, request ownership and server-authoritative comparison results. Full specifications remain IN PROGRESS.

The owner’s [Investigation Engine specification](docs/INVESTIGATION_ENGINE_SPEC.md)
is being implemented through [iterative research 1.34](docs/PRODUCT_ITERATIVE_RESEARCH.md).
The section 47 audit precedes additive code changes; full acceptance remains open.

[Shared source-change journey verification](docs/PRODUCT_SHARED_JOURNEY.md) composes
Legal and Pharma template/context, native page acquisition, worker, typed claim
review, cited Ask and source-failure coverage using fictional fixtures. It does
not establish live Market Access source readiness or human acceptance.
