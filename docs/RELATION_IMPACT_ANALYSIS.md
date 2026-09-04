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

The v3 result revision invalidates the cache. Results from earlier result-rule revisions remain unchanged in history with `stale=true`, and cannot be selected as the current inbox/history conclusion. Reanalysis uses the existing delivery and event, preventing duplicate inbox entries. Automatic bounded candidate backfill and complete read-time profile/runtime freshness are still tracked by HL-100/099; this change does not silently rewrite or bulk reprocess historical data.

Changing any dependency creates a new durable job and history record. Reusing an identical request increments saved use metadata without another provider call.

## Verification

The API suite covers background priority, stage persistence, the five-call ceiling, exact evidence links, repeat-cache reuse, profile invalidation, successful/failed history, one repair followed by rejection of invalid citations, unsupported results with zero actions, and protection of confirmed official relations. The migration creates an organization-scoped analysis table with foreign keys and status constraints.
