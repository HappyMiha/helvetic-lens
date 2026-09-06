# Relation impact analysis

HL-045 turns an explainable cross-document candidate into an organization-specific review aid. It does not make a legal relationship authoritative. Exact official relations and AI proposals use different fields and retain different provenance.

## Execution contract

`POST /api/relation-candidates/{organization_candidate_id}/analyse-jobs` persists work before dispatching it to `ai_background`. Interactive Ask jobs use priority 8; relation analysis uses the normal background priority 5. Inline development mode executes the same durable job contract immediately.

The three persisted stages are:

1. prepare relation evidence;
2. analyse possible organizational impact;
3. validate evidence and save the conclusion.

The job exposes queued, running, retrying, waiting-for-model, succeeded, failed, and cancelled states. Its analysis record separately exposes coverage, whether evidence was limited, the planned and actual provider-call count, and terminal validation status. A model outage never removes the registry event, relation candidate, official metadata, saved versions, or evidence.

## Bounded evidence dossier

The server builds one bounded dossier from:

- a confirmed official relation, when present;
- exact event metadata and its saved source version;
- deterministic candidate score components and reasons, explicitly labelled as retrieval facts rather than legal evidence;
- the monitored work's current lifecycle and metadata;
- saved passages from the event source and monitored work; and
- the active organization's profile revision and business areas.

Mandatory facts enter first. Remaining passages are ranked deterministically and selected within the configured context allowance. The saved coverage record states available and included rows/characters and whether selection was limited. The plan uses one generation request and allows one structured-output repair inside a hard five-call ceiling.

## Validated result

The persisted `relation-impact-v3` contract accepts `supported=false`, with no proposed relation or actions. A model-authored negative may have no citations; a downgraded unassessed result retains its selected evidence for inspection, never as proof of a positive impact. A supported result contains:

- a proposed `potentially_impacts`, `implements`, `cites`, or `interprets` relation;
- potential severity, kept separate from evidence strength;
- a concise explanation and affected business areas;
- zero to five review suggestions with an owner role, affected area, applicability condition, honest due basis and optional source-stated date; and
- numeric references to supplied evidence rows.

The model cannot propose authoritative `amends`, `repeals`, or `replaces` facts. The server validates JSON and schema, permits one constrained repair, rejects out-of-range row numbers, creates stable action keys, removes duplicate actions, and turns accepted row numbers into links under `/api/relation-analyses/{analysis_id}/evidence/{evidence_id}`. Only those persisted rows can become displayed quotations.

A positive conclusion and each action must independently cite saved passages from **both** the event source and the correct monitored work, with version/passage identity, or the exact confirmed official-relation row. Retrieval rationale (`candidate_fact`), event metadata and lifecycle fields alone are insufficient. This is a structural evidence floor, **not** an entailment/semantic-quality guarantee; independent HL-093 evaluation remains required.

Missing evidence bridges or known generic/contradictory model text produce `assessment_status=needs_review`, `supported=false`, no AI-derived severity/actions, explicit validation issues and a localized unassessed explanation. In the inbox, this is “Needs re-analysis” with unknown AI importance, not a claim that there was no impact. Independently recorded event urgency and confirmed official facts are retained. Each action is checked against its own citations; another action or the report cannot lend it evidence.

When official metadata already confirms a relation, `result.official_relation` keeps its exact type, authority, evidence fingerprint, and provenance. `result.proposed_relation_type` remains a separately labelled AI assessment. Inference never updates the confirmed corpus relation.

## History and cache boundaries

`GET /api/relation-candidates/{organization_candidate_id}/analyses` returns every successful and failed attempt, the latest attempt, and the latest valid current report. A failed reanalysis therefore cannot replace a previous valid conclusion.

An identical successful result is reused only when all of these inputs match:

- organization delivery and event identity;
- source and target version identity;
- selected evidence IDs, contents, and authority flags;
- official-relation evidence fingerprint;
- organization profile revision;
- prompt fingerprint;
- provider, endpoint, model, context and output settings;
- local runtime/model artifact/hardware fingerprint; and
- planner and result schema versions.

The v3 result revision invalidates the cache. Results from earlier result-rule revisions remain unchanged in history with `stale=true`, and cannot be selected as the current inbox/history conclusion. Reanalysis uses the existing delivery and event, preventing duplicate inbox entries. Automatic bounded candidate backfill and complete read-time evidence/runtime freshness are still tracked by HL-100/099; this change does not silently rewrite or bulk reprocess historical data.

Profile freshness is checked on every relation-history and inbox read: a succeeded
report is current only if its saved `analysis_plan.execution.profile_revision`
matches the profile of **that report's organization**. Missing or malformed profile
provenance is history-only. Inbox selectors apply this inside their scalar SQL
selection, before hydrating only the latest/current records; they never load the
entire evidence archive to compare revisions. The digest preview/worker share this
selection, so a stale AI severity cannot make a development eligible for a digest.
Official event urgency and confirmed relations remain independent of AI freshness.

After a profile edit, the old text/citations stay accessible as stale history, but
its organization-specific explanation/actions/severity no longer supply the current
inbox conclusion. A failed new attempt cannot revive the previous profile's report;
a failed attempt under the **same** profile still preserves an older valid result.
The profile form also invalidates cached relation histories and digest previews.
Reads do not enqueue inference, increment reuse counts, rewrite history or send mail.

Relation request identity also includes product ID and every configured sampling/
output control: temperature, top-p, presence penalty, reasoning effort and JSON
mode, in addition to the existing provider/endpoint/model/context/token limits.
The five generation controls are saved under
`analysis_plan.execution.generation_parameters`, so a retained report states the
configuration used for it. No credentials are saved there. API-key rotation,
request timeout/retry and batch concurrency changes intentionally preserve a
successful request's identity; none changes the requested semantic inputs.
Existing cache keys from before this addition miss once on the next explicit or
scheduled analysis, without rewriting/deleting those reports or scheduling a
bulk rerun.

Relation history and legacy/paged inbox reads now also require
`analysis_plan.execution.configuration_fingerprint` to match the resolved current
provider/product/endpoint/model/context/output and generation configuration. The
same predicate is applied in SQL before history payload hydration. Credentials,
request timeout/retries and batch concurrency are excluded. Returning to exactly
the old configuration can reuse its still-valid report; failed attempts under a
new configuration cannot revive old applicability. Official facts remain separate.
The settings form invalidates relation-history and digest preview caches on save
or reset.

Digest preparation and final delivery resolve public settings for the recipient's
organization without loading/decrypting its saved credential. A fingerprint is
included in the preparation checkpoint: a configuration change restarts bounded
selection, and an already completed selection is rejected before sending if its
configuration no longer matches. Existing checkpoints without it restart safely.
Delivery uses existing saved reports only; it never generates explanations.

**Upgrade limit:** reports without this new fingerprint are retained as stale
history, with citations accessible. They cannot reliably prove the full original
configuration. No backfill, migration, data deletion or automatic bulk inference
runs. Cache identity changes once so the next explicit/scheduled request can create
a report with the new provenance. This does not yet detect changing evidence or replacement of a local model
artifact behind the same configured model name. Those HL-100 freshness boundaries remain open. Reads use the configuration
snapshot available to the request; this is not a global transactional lock against
an administrator changing settings concurrently.

Effective prompts are checked as well. New plans persist
`analysis_plan.execution.prompt_fingerprint`, shared with relation cache identity.
Only `impact_instructions` and `repair_instructions` participate: relation analysis
does not use Ask, batch synthesis or Ask context-mode controls. Editing those
unrelated controls alone must not invalidate a valid report or spend tokens again.
The fingerprint compares content, not revision numbers; the same revision number
in a platform default and an organization override does not establish equivalence.
Organization overrides win in full, then platform defaults, then built-in defaults.
Resetting an override follows the same inheritance rules as actual generation.

The SQL history selector checks this fingerprint without hydrating archived
prompts/evidence. History remains inspectable and failed new attempts cannot revive
an old prompt's applicability. Reports predating prompt provenance conservatively
remain stale until a new explicit/scheduled request; no bulk inference or mutation
occurs on reads. Returning to the same effective instructions can reuse a report
whose other freshness checks still pass.

Digest preparation and final delivery resolve effective prompts for the recipient's
organization, even in privileged sessions. Changed prompt fingerprints restart
bounded selection and reject stale completed checkpoints before sending. Historical
sent digests are not rewritten. Prompt save/reset invalidates relation-history and
digest client caches; existing sessions observe changes on their next fresh read,
not via a new cross-client push channel.

Planner v2 also records `execution.version_binding` for the candidate's exact source
and target document-version IDs. An explicit empty value means the candidate had no corresponding corpus version
ID; a missing binding is not accepted as proof of that state.
Current inbox/history selection compares both IDs to the same organization
candidate. A refreshed or removed version ID makes the old assessment history-only,
while the original result and citations remain accessible. A failed fresh attempt
cannot revive applicability from different versions. Official event urgency and
confirmed relations remain independent.

The predicate uses correlated scalar SQL before bounded history hydration. The
history endpoint reads only the candidate's two version-ID columns in addition to
its existing history read. Digest final selection reuses the predicate, so prepared
events lose eligibility if their only matching importance was an obsolete AI
assessment. No version is deleted or amended by these reads, and no inference is
queued. Planner identity changes once to allow new provenance on the next
explicit/scheduled analysis.

This binding does **not** yet detect content/metadata corrections under an unchanged
version ID, changed legacy fallback evidence while the candidate ID remains absent,
a newer corpus version before candidate refresh, or
runtime artifact replacement. Nor does it restart an entire digest
traversal for every candidate mutation; late/newly relevant events may wait for a
later traversal. Complete evidence freshness and catch-up remain separate backlog
items, not claims made by this narrower correction.

This is revision-based invalidation, not a semantic test of profile similarity;
unmanaged database edits that bypass the profile revision are outside this contract.

Changing any dependency creates a new durable job and history record when analysis is explicitly requested or scheduled. Reusing an identical request increments saved use metadata without another provider call.

## Official-relation corrections on reads — 6 September 2026

Planner v3 records `execution.official_relation_binding`, shared with request/cache
identity. It contains the linked relation's ID, state, type, authority, provenance
method, evidence fingerprint, subject/object work IDs and source version ID.
Proposed/rejected relations are recorded as such; storing their state does not
turn them into authoritative facts. An explicit all-empty binding records no
linked relation, distinct from missing provenance.

History, legacy/paged inbox and their shared digest selectors compare these
scalar fields to the current relation attached to the same organization candidate.
Corrected fields, attachment/detachment or a missing binding make an old successful
AI report history-only. Original report text, citations, provenance and failed
attempts remain inspectable. Returning to exactly the same inputs permits reuse
when the other freshness checks also pass; a failed analysis against corrected
inputs cannot revive an old conclusion. Request identity includes all these fields,
so a type/authority correction changes the next explicit request even if evidence
text or its fingerprint did not change.

Older reports without this binding conservatively become stale. There is no
background migration, bulk inference, notification or history rewrite. A new
explicit/scheduled request uses planner v3 and saves the needed provenance.
Prepared digests repeat current selection before delivery and exclude obsolete
AI-only severity. Official/deterministic urgency remains independent of the AI
report. This does not restart all prior digest traversal for a newly eligible event.

The SQL predicate performs a correlated relation-ID join before bounded history
hydration. History reads nine scalar relation fields alongside candidate version
IDs, without loading the relation evidence body solely to decide freshness.
Regression evidence includes changed/rejected/proposed relations, all bound fields,
attachment/detachment, missing provenance, restored input reuse, failed/fresh
requests, and a prepared digest whose only matching importance was obsolete AI.

Remaining limits: evidence JSON edited without updating its fingerprint, broader
same-version content/metadata corrections, legacy fallback evidence, local runtime
artifact replacement and candidate refresh/reprocessing lag are not solved here.
Endpoint/direction consistency is checked by the follow-up below; freshness
binding alone does not validate a new official claim. No independent
entailment/relevance or target-host capacity claim follows from these regressions.

## Exact pair and direction — 6 September 2026

A linked relation is authoritative only when confirmed and its subject/object are
exactly the candidate's two distinct source/target work IDs, in either direction.
Missing, unrelated or self endpoints are not official evidence for that candidate.
The model context omits their official evidence row, and result finalization
independently checks the pair before accepting an official-row bridge. A valid
source/target passage pair can still support a possible review lead; these identity
checks do not prove semantic entailment.

The official object records both endpoint IDs and `outgoing`/`incoming` relative
to the candidate source. A `replaces` subject is always the successor, regardless
of which endpoint produced the event. Inbox labels, links and monitored state
follow that direction. An invalid pair cannot supply official confirmation,
replacement-derived urgency or the monitor-successor action. The action rejects
before fetching or creating a watch. Explicit event importance and independent
human review remain separate. Prepared digests reselect before delivery and drop
items whose only matching urgency came from the now-invalid replacement.

Result schema v4 invalidates older successful reports through the existing
history/current-selection gates; planner v3 and its relation binding stay in use.
No migration, automatic reanalysis or history/citation rewrite is performed.
An explicit request gets the current schema identity and can reuse a subsequent
identical completed request. Candidate refresh/reprocessing and same-version,
evidence-fingerprint and runtime-artifact corrections remain separate work.

## Verification

The API suite covers background priority, stage persistence, the five-call ceiling, exact evidence links, repeat-cache reuse, profile invalidation, successful/failed history, one repair followed by rejection of invalid citations, unsupported results with zero actions, and protection of confirmed official relations. The migration creates an organization-scoped analysis table with foreign keys and status constraints.
