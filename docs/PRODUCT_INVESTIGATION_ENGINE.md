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

1. VERIFYING release 1.8: Ask / Investigate within an existing dossier, persisted coordinator
   plan/branch/step state and existing job dispatch, automatic available-source
   routing, bounded public query search/inspection and existing saved evidence,
   evidence-linked claims/entities/relationships and revision history, dynamic
   evidence-triggered branches with preserved plan versions, live structured
   activity and cancel/resume. Replace the default technical-panel experience
   with a dossier-first research surface; retain existing tools in an expandable
   section. Both product clients, failure/privacy/restart tests and exact release
   verification are required before this slice is complete.
2. Private dossier member roles OWNER/EDITOR/CONTRIBUTOR/VIEWER with invitation
   boundaries, unified URL/file/comment/correction/research-request contributions
   and source extraction using retained originals. Existing workspace-wide access
   must be migrated deliberately, without losing existing access or exposing drafts.
3. Public living view with stable human-readable slugs and claim/source anchors,
   anonymous search across public knowledge, same coordinator/UI, public
   contributions and scoped research. Existing published snapshots remain explicit;
   owner-selected living publication authorizes updates within the public scope.
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
Production activation remains VERIFYING until the release receipt is recorded.
