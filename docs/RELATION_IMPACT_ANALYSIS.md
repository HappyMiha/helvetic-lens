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

This is revision-based invalidation, not a semantic test of profile similarity;
unmanaged database edits that bypass the profile revision are outside this contract.

Changing any dependency creates a new durable job and history record when analysis is explicitly requested or scheduled. Reusing an identical request increments saved use metadata without another provider call.

## Verification

The API suite covers background priority, stage persistence, the five-call ceiling, exact evidence links, repeat-cache reuse, profile invalidation, successful/failed history, one repair followed by rejection of invalid citations, unsupported results with zero actions, and protection of confirmed official relations. The migration creates an organization-scoped analysis table with foreign keys and status constraints.
