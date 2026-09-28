# Dynamic dossier investigation implementation

Status: IN PROGRESS. User direction received 27 September 2026.
Authoritative product specification: [complete supplied document](DYNAMIC_DOSSIER_SPEC.md).

## Reuse and architecture

ProductDossier and its native monitoring profile remain the central objects.
DossierEntry retains existing contributions/files/references and original blobs.
ProductPublication remains the explicit public boundary for existing dossiers;
private material must never be copied implicitly into that projection. Native
organizations/sessions, PostgreSQL, Job/JobStep/outbox and worker dispatch remain
in place. A coordinator and capability/source registries orchestrate durable
research; models, workers and branch count are implementation details.

The existing Influence document is a bounded domain-specific graph snapshot,
not a first-class dynamic claim ledger. Reuse its evidence/version principles,
not a second dossier container. New investigation/claim/branch/evidence records
must be contained by ProductDossier with composite organization foreign keys.
Entity types and relationship predicates are extensible strings. Similarity and
machine output are proposals, never proof of identity or fact.

## Delivery sequence and acceptance

1. DONE, scoped release 1.8: Ask / Investigate within an existing dossier, persisted coordinator
   plan/branch/step state and existing job dispatch, automatic available-source
   routing, bounded public query search/inspection and existing saved evidence,
   evidence-linked claims/entities/relationships and revision history, dynamic
   evidence-triggered branches with preserved plan versions, live structured
   activity and cancel/resume. Replace the default technical-panel experience
   with a dossier-first research surface; retain existing tools in an expandable
   section. Both product clients, failure/privacy/restart tests and exact release
   verification are required before this slice is complete.
2. DONE, scoped private contribution stage 2a in release 1.10: unified URL/file/
   comment/correction/research-request ingestion using retained originals. Scoped
   stage 2b1 workspace teams are DONE in release 1.11: four dossier roles,
   account-bound invitations and collaborative drafts across native access paths.
   See [team architecture and acceptance](PRODUCT_TEAMS.md). Scoped members-only
   active monitoring is DONE in 1.12; dossier-only outside-workspace invitations
   are DONE in 1.13 as scoped stage 2b3, preserving native organization isolation.
   See [guest architecture and acceptance](PRODUCT_GUEST_ACCESS.md).
   Before this stage, apply the owner's visual-language steering to both clients'
   reference dossier and global interaction foundation (see VISUAL_LANGUAGE_SPEC.md).
3. DONE, scoped public research stage 3 in release 1.14: public living view with
   stable human-readable slugs and claim/source anchors,
   anonymous search across public knowledge, same coordinator/UI, public
   contributions and scoped research. Existing published snapshots remain explicit;
   owner-selected living publication authorizes updates within the public scope.
   See [public-research architecture and acceptance](PRODUCT_PUBLIC_RESEARCH.md).
4. Monitoring observations/contributions trigger bounded material-change review,
   claim supersession/contradictions and research reopening, reusing native jobs
   and consented delivery. Full specification acceptance is required before DONE.

No stage marks the complete feature done by implementing only its own contract.
The supplied twenty-step Definition of Done remains open until every step has
native integration, both-client and production evidence. No synthetic fixture or
model confidence substitutes for independent professional quality validation.

## Source and model readiness

Search1API Google/Bing and Europe PMC, hosted Jev, pinned local multilingual
Laya and the configured Apertus planner are verified in 1.6/1.7. They can discover
and inspect permitted public sources beyond a fixed catalogue. Capabilities for
unavailable registries, authenticated documents, patents, OCR or new providers
must be recorded as unavailable; do not invent connector access. Respect current
robots/access/size/source-rights gates. No new provider registration is needed.
Private contents are never automatically converted into public external queries.
Use only the user's deliberately submitted public-search question for external
retrieval, and source text from permitted external results for further queries.
Existing private saved material stays inside its access-scoped research context.

## Verification contract for the active slice

- Native create/read/cancel/resume is current-account and dossier scoped, with
  CSRF, explicit request identity and no duplicate paid work on exact retry.
- Plan before research; dynamically choose from available capabilities, preserve
  unavailable/partial states, finite step/source/model/query budgets and stop reason.
- Restart-safe job checkpoints and actor/access rechecks before/after network;
  failures cannot promote missing evidence or discard completed branches.
- Important statements link to immutable captured excerpts/locations/hashes.
  Quote validation rejects fabricated citations. Contradictions remain visible;
  status/version history never silently converts hypotheses into facts.
- A real native integration fixture discovers a new entity, adds a branch based
  on its evidence, records a changed plan and retains the original reason/history.
- SSE emits stored observable activity only, validates access throughout streaming,
  supports reconnect, and never returns internal model reasoning.
- No new emails, publications, source approvals or permission changes are implied
  by pressing Investigate. Audience and delivery are explicit dossier settings.

## Evidence

Release 1.8 implements the first scoped vertical slice. It adds nine contained
research tables under migration `fac495bef124`, the native `product_investigation`
job type, one committed step per delivery and the existing outbox/recovery loop.
Plans are saved before retrieval. Up to three public branches, three inspected
sources per branch and three saved snapshots bound each run. Unavailable branches
retain their evidence and failures. A committed in-flight request is never blindly
repeated after a worker crash; recovery advances with an explicit interruption.
A generation fence discards late results after pause/cancel/resume, and exhausted
native recovery pauses the investigation rather than leaving it running forever.

The root question and exact public-source entity names are the only external query
inputs. Current native session, membership, draft visibility, source exclusions
and worker lease are rechecked around network operations. Private generic job
endpoints cannot expose or control these investigations. SSE checks current access
on every batch, uses persisted sequence cursors and contains observable events only.
Native dossier JSON export includes all investigation evidence within its documented
interactive limit. Original question authorship is separate from the current
resuming editor; account erasure nulls the actor references.

The new Pharma and Loyer surface provides one Ask / Investigate form, claims with
source quotes and contested history, unresolved entity mentions/relationships,
source capture provenance, versioned plans, live activity and durable controls.
The previous complete dossier tools remain available in an expandable section.
Neither research execution nor resumption publishes anything or changes delivery.

Validation: the broad affected native suite passed 300 tests (3 smoke, 297
integration), including existing product, job, foreign-key and account-erasure
contracts. The added investigation integration cases prove real native HTTP/DB/job
flow, new-entity replanning, preserved contradictions, quote forgery rejection,
source retention, scoped external queries, revocation/cancellation races, stream
rechecks, recovery, shared spend limits and schema equivalence. A focused final
run passed 53 cases after the additional immutable-authorship fix. There are 15
new native investigation integration cases. Both clients pass 70 tests,
source lint, strict type checking and final Sites production builds. Exact
deployment verification is recorded separately below when complete.

A single real configured-model probe used an explicitly artificial excerpt:
Swisscom `swiss-ai/Apertus-v1.5-70B` returned schema-valid findings with exact quotes
in 3,917 ms. This verifies transport/contract compatibility, not factual accuracy
or a professional pilot. [Sanitized receipt](product-releases/2026-09-27-investigation-model-probe.json).

Full-spec status remains IN PROGRESS. Per-dossier membership/invitations, unified
file/contribution ingestion, stable living public URLs/search and automatic
monitoring/contribution-triggered reopening remain the next stages. Claims are
currently grouped by their durable investigation within the existing dossier;
cross-investigation claim reconciliation remains part of automatic reopening.
No vector retrieval capability or comprehensive internet coverage is claimed.
Production release `git-f67af9885d07` activated on 27 September at 14:29:33  UTC.
Pharma `0d8bba9257610a9e1c0c644a28401dafb2303318` and Loyer
`414857e04cf4315b6611b01d27051ad09f61c0dd` are both published as Sites version 10
at their existing public custom domains. Both GitHub CI runs succeeded. Each
production origin passed 46 HTTP/gateway/guide checks and 36 exact JS/CSS asset
hash comparisons. Eleven native deployed modules match the validated source;
migration `fac495bef124` and all nine research tables are present. Native API and
CPU worker health checks pass; the AI worker is running (it has no configured
Docker health check). Its live Celery control reply confirms consumption of
`ai_interactive` and `ai_background`; local Laya is healthy.

[Exact release receipt](product-releases/2026-09-27-1.8.0.json). Verification used
anonymous HTTP, source hashes, schema and process health. No authenticated
production user records were created or read; no browser interaction QA or
independent factual-quality pilot is claimed. The first slice is complete; the
full specification and next three delivery stages remain IN PROGRESS.


The owner's later visual brief adds a validated two-client research interface.
Release 1.9 now provides the global Ask/Search, reference dossier, token-based
light/dark themes, source/provenance reader and real checkpoint Lens activity;
see [visual implementation and exact acceptance](PRODUCT_VISUAL_LANGUAGE.md).
This is a frontend-only slice on the same 1.8.1 native code. Contribution ingestion,
per-dossier access, living public research and automatic material-change reopening
remain IN PROGRESS. The visual reference is ready for those next capabilities.


Stage 2a contribution ingestion is DONE as a scoped release 1.10, with exact
native and both-client production verification. Both clients provide a unified composer; original
text/files/author identity feed bounded private investigations with a serialized
queue and explicit failed-step retry. Native scopes, source exclusions, original
integrity and no-public-discovery boundaries are verified. See
[implementation, bounds and acceptance](PRODUCT_CONTRIBUTIONS.md). This delivers
private contribution-triggered analysis, not the full stage 2 roles/invitations or
stage 4 cross-investigation reconciliation. Those and the remaining visual/native
migration remain IN PROGRESS.


Release 1.11 adds the workspace collaboration portion of stage 2b: creator-enabled
OWNER/EDITOR/CONTRIBUTOR/VIEWER roles, account-bound invitations, ownership
handover and retained private collaborative drafts. Local checks and exact
production activation pass for both products and the shared native core. Activated monitoring keeps its disclosed
workspace audience. See [bounds and acceptance](PRODUCT_TEAMS.md).


Release 1.12 completes scoped stage 2b2, members-only active monitoring, with
exact native and both-client production verification. New private topics, native readers, recipient feeds and consented
digests share current dossier membership. Legacy workspace audiences remain
unchanged. Shared AI briefs exclude private topics; workspace page watches are
explicitly unavailable in private dossiers. See [architecture, bounds and release
acceptance](PRODUCT_PRIVATE_MONITORING.md). Outside-workspace invitations and
the remaining stages are still IN PROGRESS.

Release 1.13 implements dossier-only invitations for existing verified accounts,
scoped guest readers, original-session research authorization and both clients.
Local and exact production acceptance pass for the core and both public clients. The updated
Brandbook v1.0 governs both shells. Living public dossiers and the remaining
stages remain IN PROGRESS.

[Release 1.13 production evidence](product-releases/2026-09-27-1.13.0.json) records
370 native cases, both 85-test client gates, Sites 16,33 native hashes and 66 HTTP
checks plus 39 exact assets per client. The existing hourly heartbeat remains ACTIVE
for the remaining full-spec outcomes; no browser/human visual acceptance is claimed.

Release 1.15 implements scoped stage 4a, source-linked evidence evolution across
independently extracted investigations. Both products retain the earlier finding
and exact citations, show later-evidence status separately, and support current
editor dismiss/restore with visible history. Public/private audience containment
and source withdrawal apply before comparison inputs and reader counts. See
[architecture, bounds and release acceptance](PRODUCT_CLAIM_EVOLUTION.md).
Exact native and both-client production acceptance passed; see the linked record
and [release receipt](product-releases/2026-09-27-1.15.0.json). Monitoring-triggered reopening
(stage 4b), recurring discovery, private semantic indexing, independent evaluation
and full native visual migration remain open; the full specifications remain
IN PROGRESS.

Stage 4b1 is DONE within scoped production acceptance in release 1.16: standing private research authority
connects new native topic-match metadata to durable investigations, independently
extracted evidence and paired-citation comparisons in both clients. See
[architecture, limits and acceptance](PRODUCT_MONITORING_RESEARCH.md). Changed-page
body triggers, recurring web discovery, semantic indexing and the full-spec gates
remain distinct; this does not complete stage 4 or either full specification.


Stage 4b2 is DONE within scoped release 1.17 production acceptance: explicit standing-policy scope researches future
retained changes from linked workspace page watches. Existing topic-only
authorizations stay unchanged; members-only dossiers retain their page-watch
restriction. Exact typed receipts, old/new version references and bounded change
excerpts connect the same private extraction and independent comparison engine.
See [architecture and scoped acceptance](PRODUCT_WATCHED_PAGE_RESEARCH.md).

Stage 4c recurring public-web discovery is DONE within scoped release 1.18
local and exact native/both-client production acceptance. An
explicit question/cadence/standing policy schedules the same durable coordinator
for author drafts, invited teams and workspace dossiers. Private text never expands
the query, uncertain paid work is not automatically retried, and unchanged source
captures skip extraction. Independent later evidence uses stage 4a comparison.
See [bounds and acceptance](PRODUCT_WEB_RESEARCH.md). Broader private semantic
indexing, independent professional evaluation and full native visual migration
remain separate open outcomes.

Stage 4d private saved-evidence search is DONE within scoped release 1.19;
[bounded local comparison and exact citations](PRODUCT_EVIDENCE_SEARCH.md) keep
uncertain candidates visible and preserve the conditional MV2-063 index gate.

Stage 4e personal research updates are DONE within scoped release 1.20, with
local and exact native/both-client production acceptance. Existing
completion/evidence records feed private/public following, current-permission
history and personal read markers in both clients. See the pre-implementation
[scope and acceptance contract](PRODUCT_RESEARCH_NOTIFICATIONS.md). This does not
complete native email/noise controls, source review or either full specification.

Stage4f whole-dossier retrieval is IN PROGRESS pending exact production acceptance.
The [implementation and independent sample](PRODUCT_CORPUS_SEARCH.md) recover
older evidence across the current private ledger, with source-contained local
preparation, unchanged-input reuse and current-rights ranking. The full product,
professional evaluation and native visual migration remain open.
