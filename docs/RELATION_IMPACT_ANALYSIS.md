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

The persisted `relation-impact-v4` contract accepts `supported=false`, with no proposed relation or actions. A model-authored negative may have no citations; a downgraded unassessed result retains its selected evidence for inspection, never as proof of a positive impact. A supported result contains:

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

### Same-ID evidence corrections (HL-100, 6 September 2026)

Planner `relation-impact-plan-v4` binds the actual candidate, event, both works,
both saved corpus versions, the target's accessible legacy version and any linked
official relation to their database evidence revisions. This is independent of a
document ID or a caller-maintained content hash. Correcting passages, source URLs,
work scope/lifecycle, event facts, retrieval reasons or official evidence under the
same IDs makes previous assessments history-only. Their original timestamps,
result and citation snapshots are retained; no read silently rewrites a report or
starts inference. The next explicit/scheduled request receives a distinct cache
and durable-job identity. A failed new attempt cannot revive the prior assessment.

Migration `c3a5be941872` adds six revision columns and SQLite/PostgreSQL triggers.
The triggers compare the stored evidence-bearing fields and advance the revision
on an actual change, including bulk/direct SQL updates outside ORM callbacks.
Health, analysis state, usage and fetching/update timestamps are excluded. Assigning
the same stored value does not advance a revision. JSON formatting/order changes
can conservatively advance it; this is a correction identity, not semantic
equivalence. Reverting changed text or IDs does not roll the revision backward.
The target's legacy revision is conservatively bound whenever an accessible legacy
link exists, including when native passages currently make fallback unnecessary.
Foreign private legacy IDs/revisions are excluded even in privileged sessions.

A separate migration epoch binds the counter incarnation. Downgrade/re-upgrade
cannot accidentally revive an old report because a fresh counter again equals
one. The epoch is a lifecycle marker, not an external attestation. Database
administrators can still alter history, disable triggers or restore an old backup;
this is not a defense against a hostile database administrator. Operator deployment
must apply the migration with the matching API code. Do not run it on production
as a side effect of publishing this commit. Old reports lacking the new binding
remain inspectable but cannot establish current applicability; no bulk reanalysis
or notification is created by the migration.

Preparation compares compact bindings before and after collecting the dossier.
A concurrent correction returns `409 relation_evidence_changed` before creating
a job or sending a prompt; the caller can retry against the corrected evidence.
A correction during generation retains the result as stale history and leaves the
candidate pending for an explicit reassessment. Normal fresh reads recheck the
binding. These checks do not lock all source/settings changes globally throughout
an HTTP response or establish model-runtime freshness.

Inbox selection compares scalar revisions in SQL before hydrating only selected
history payloads; it does not read/hash all historical documents in Python. Both
legacy/paged inbox readers and final digest selection use this predicate. An
AI-only severity from corrected evidence cannot authorize delivery, while
independently recorded official urgency remains available. Relation-history reads
reuse one compact binding for the candidate; pagination of that endpoint's full
retained history is a separate remaining read-boundary task.

Remaining HL-100 work includes actual runtime/artifact freshness on reads,
candidate refresh/backfill, independent relevance/entailment acceptance and
historical digest catch-up. Revision integrity does not establish factual support
or the usefulness of an AI explanation.

`GET /api/relation-candidates/{organization_candidate_id}/analyses` returns every successful and failed attempt, the latest attempt, and the latest valid current report. A failed reanalysis therefore cannot replace a previous valid conclusion.

An identical successful result is reused only when all of these inputs match:

- organization delivery and event identity;
- source and target version identity;
- evidence revision bindings and their migration epoch;
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


## Observed local runtime freshness — 6 September 2026

Relation queue selection, generation and current reads share the same gateway
observation used by comparison Ask/Impact. The gateway's `/v1/runtime` response
supplies the validated runtime cache identity; model-manager inventory is still
used for startup/warm-up, never as proof of which model generated a report.

The `relation-runtime-v2` fingerprint includes the provider/endpoint/served model
and, for Docker, the runtime cache identity and capability-policy fingerprint.
The runtime identity includes immutable weights/revision, tokenizer, chat template,
runtime digest and hardware profile, served alias, context/output budget and token
measurement protocol. Complete immutable identity can reuse a result after a
restart. Without complete identity, reuse is limited to the same deployment binding.
Neither mechanism independently certifies model quality, semantic entailment or a
provider's honesty. Cloud conclusions retain configuration/prompt freshness; we do
not attest immutable remote weights behind a cloud model name.

A relation operation makes one bounded runtime metadata observation (two-second
probe ceiling, outside write transactions), then uses the existing pinned request
and response-header verification. A queued known binding must still match at
execution; otherwise the job reports `runtime_binding_changed` before generation.
Request a new analysis to use the new runtime. Old inventory-based queued bindings
also need a new request. An unverified/stopped local model can still enter the
existing durable warm-up path; matching pending offline requests coalesce. A
completed unbound request is never reused as proof of today's running model.
Background fanout shares one observation per recipient organization in its batch.

Current relation history, both inbox routes and digest previews perform a bounded
metadata probe, not inference. Missing/changed local identity makes existing AI
conclusions stale: original text, sources and timestamps remain readable, but AI
severity/actions are not current. Pure citation reads do not probe. Correlated SQL
selection checks the fingerprint before hydrating the selected history records.
Historical results without the new fingerprint remain history-only locally; there
is no migration, relabelling, automatic reassessment or cloud approval change.

Digest runtime observations carry the recipient organization and public
configuration fingerprint. The final reader resolves the current organization
configuration itself and refuses observations from another organization or old
configuration. Each preparation checkpoint records the runtime fingerprint; a
change restarts selection. The worker observes again before the final delivery
transaction and rejects a now-obsolete selection. An unavailable runtime fails
preparation/delivery without advancing `last_sent_at`. No model generation or
credential decryption is added to digest readers. Existing explicit event urgency
and human/official relation judgments remain independent of AI freshness.

These are point-in-time observations, not a distributed lock over a model during
an entire read/send operation. A subsequent gateway change belongs to the next
observation; actual generation additionally has request/response binding checks.
The runtime change alone does not solve late candidate refresh, historical
reassessment or catch-up delivery of an event after an earlier period was already
consumed. The retained-pair maintenance path below addresses explicit candidate
refresh; the other boundaries remain open along with independent semantic and
hardware tests.

## Controlled retained-candidate reprocessing — 6 September 2026

Updating retrieval rules must not silently preserve an obsolete candidate as
current evidence. Relation history, inbox/digest selection and new AI requests now
require the deployed candidate rule revision and a non-rejected candidate. Earlier
successful reports remain readable with their original text, citations, versions
and timestamps; they cannot supply current AI severity or actions. Existing
official-relation urgency, explicit event importance and organization reviews
remain independent.

The platform administrator can explicitly recheck **retained candidate pairs**:

1. Read `GET /api/admin/relation-reprocessing` for the deployed rule revision,
   25-candidate batch size and default preview mode.
2. Submit `POST /api/admin/relation-reprocessing` with
   `{"dry_run": true, "request_id": "<new UUID>"}`. The default is preview when
   `dry_run` is omitted. Use the existing authenticated session and CSRF header.
3. Read `GET /api/jobs/<returned job ID>` until the job finishes. Its result shows
   the captured cutoff, processed/eligible counts, retained/rejected/skipped and
   changed counts, and up to ten changed examples with old/new scores and reasons.
   These are retrieval decisions, not legal conclusions or independent labels.
4. To apply, explicitly submit another request with `dry_run: false`. Preview and
   apply are separate runs against then-current metadata, not an approved frozen
   change set. Repeating the same UUID, mode and rule returns the same job within
   the initiating organization; use a new UUID for a fresh recheck.
5. Existing `POST /api/jobs/<id>/cancel` and `/retry` stop or resume the job. Retry
   preserves the cutoff and committed cursor; it does not restart prior batches.

These API routes require a platform administrator. Maintenance jobs and their
examples are also hidden from ordinary users on generic job list/detail/cancel/
retry routes, including after the initiating user's platform role is revoked.
Job ownership still follows the initiating organization. The explicit anonymous
development allowance is unchanged; it must not be enabled for public deployment.
The administrator screen described below uses these same routes. Production uses
the existing durable `maintenance` queue/outbox; inline test mode executes one batch
per invocation and needs another invocation to continue a larger run.

The job captures an admission timestamp, counts eligible rows once and scans
candidate IDs in increasing order, hydrating at most 25 candidates per batch.
Later-created rows are excluded; deleted rows are reported at exhaustion. The
source/target work metadata, saved event references, exact confirmed relation and
latest saved version IDs feed the same scoring policy as live discovery. Neither
full document text, passage arrays nor historical AI payloads are needed. Existing
database evidence revisions invalidate old analysis bindings when a candidate
changes. A currently valid pair remains a no-op even on its first recheck: a
bookkeeping marker alone cannot invalidate its usable report. Subsequent identical
applies also preserve the evidence revision and reuse of saved AI answers.

Missing/inconsistent work/event/version inputs and reserved terminal states set
outside this maintenance path are counted as skipped, not silently repaired.
Expired candidates are not renewed. A lead rejected by this job may be retained
by a future rule; rejection means only that current retrieval rules do not support
the pair. Its inbox explanation explicitly says this is **not a legal no-impact
judgment**. No candidate, official/proposed relation, delivery, organization review
or historical analysis is deleted; this job changes candidate metadata only.

Candidate updates and their checkpoint commit together. A failed batch rolls both
back; cancellation retains earlier committed batches. Row locks serialize repeated
enqueue intents and concurrent edits of the same candidate. Successful batches
yield through the existing outbox without spending the failure-retry budget. A
different deployed rule supersedes the remaining run; a new explicit preview is
required. Malformed checkpoints fail visibly rather than silently restarting.

This is not a transaction-wide snapshot of the corpus: each batch uses currently
saved metadata, which can change again afterward. It does not discover new pairs,
run a semantic model, create new deliveries, send notifications or reassess old
reports automatically. A retained refreshed pair can be explicitly analysed using
the existing AI flow; a rejected or old-rule pair receives a clear reprocessing
error before inference. No deployment/startup/migration triggers this job. New-pair
backfill, catch-up digest delivery, independent relevance/claim
evaluation and target-hardware capacity remain separate work.

### Administrator reprocessing page

Open **Platform admin → Recheck saved leads** at
`/admin/relation-reprocessing`. The page is available in DE/FR/IT/RM/EN and is
restricted to platform administrators, including its data subscriptions. Start
with **Preview changes**, inspect the retained/rejected/skipped/changed counts and
expand up to ten labelled examples. These labels describe saved documents and
retrieval decisions, not new model conclusions. Source titles/reasons remain in
their saved language; they are not translated by inference.

Only a successfully completed preview with the currently displayed rule and at
least one actual change enables **Review and apply**. The inline confirmation
states the platform-wide scope, possible differences from the earlier preview,
history invalidation and the fact that cancellation preserves completed batches.
It requires an explicit acknowledgement before the apply button is enabled.
No-change previews retain usable AI results and need no apply operation. An old
rule, superseded job or unreadable/inconsistent result requires a fresh preview
or recovery rather than an optimistic apply.

The result URL contains the saved job ID. Reloading or leaving/reopening the page
does not start another job. The history lists the latest 20 maintenance jobs in
the initiating organization, independently of newer unrelated jobs, with mode,
state and a precise timestamp in Europe/Zurich. Other platform administrators in
the same organization can inspect those jobs through the same authorized routes.
History is intentionally a bounded recent list, not a complete cross-organization
audit browser. A saved direct URL can still reopen an older accessible job.

While a run is active, its counts refresh in place without reloading the page.
Cancel and resume use the existing durable checkpoint; they do not undo or repeat
committed batches. A stopped/superseded run remains visibly distinct from a fully
completed one. Examples show saved source/target titles, old/new retrieval scores
and the recorded rule explanation. Scores are retrieval signals, not confidence
in a legal conclusion. Generic job result links also return to this page.

UI cancellation/resume uses the narrowly scoped
`POST /api/admin/relation-reprocessing/jobs/<id>/cancel` and `/retry` routes. They
require a platform administrator, the current organization, a maintenance job and
the existing CSRF token. A platform administrator can therefore manage this
platform operation even when their organization membership is read-only, without
gaining mutation rights over unrelated organization jobs.

Before submission the browser stores only a UUID, mode and original rule revision
in session storage scoped to user and organization. If the reply is lost, **Recover
submitted request** resends that same identity, including after a reload. It never
automatically retries an apply while opening the page. The server accepts an
optional `rule_revision` with the maintenance POST: replaying an already accepted
old-rule request returns its original job; an unknown request for an obsolete
rule fails with `relation_reprocess_rule_changed` before creating work. A new
preview is then required. Session storage must be available to start a new UI
request. Clearing browser storage or closing the browser session can lose this
local recovery pointer; inspect recent runs or a saved result URL before starting
another operation. The durable job itself is not stored in the browser.

No page read, preview, apply or recovery action invokes AI, sends notifications,
downloads models, or deploys code. The page is an operator tool for the existing
retained-pair maintenance path, not a new-pair discovery or AI-reassessment tool.
Five-language rendering and automated keyboard/responsive checks do not replace
independent native-language, assistive-technology or real-operator usability review.
