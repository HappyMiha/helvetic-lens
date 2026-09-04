# Bounded monitoring-topic matching

HL-075 extends the existing normalized event, evidence, relation-candidate, and source-pack pipeline. A topic match means that a saved public event is relevant to an organization's stated interest. It is never presented as proof that one legal work amends, repeals, or otherwise legally affects another.

## Retrieval contract

Matching begins only after connector evidence is committed and organization event state has been fanned out. It therefore considers only organizations entitled to see the event. For each event the production query uses exact SR/RS and article references plus PostgreSQL `simple` full-text search over the current active topic revision. Controlled filters then enforce the selected source packs, document and event kinds, jurisdiction, language, importance floor, and exclusions. The final signals record exact concepts, synonyms, official identifiers, article references, or normalized full-text terms.

The existing HL-044 normalizers provide title tokens and legal-reference extraction. pgvector remains disabled: the checked-in five-language positive and noise cases do not establish a measured recall gap that would justify embeddings. Ambiguous AI expansion is also disabled at the current threshold. If a later labelled evaluation enables it, `TOPIC_MATCH_AI_CANDIDATES_PER_EVENT` is the hard ceiling after deterministic filtering; the default is three and the normal deterministic path makes zero model calls.

## Persistence and bounds

`TopicEventMatch` stores the organization and topic revision, immutable event/work/expression/document-version references, reason signals, exact source and official-identifier evidence, evidence and rule fingerprints, confidence band, review decision, model provenance when applicable, and timestamps. Repeating the same event and fingerprints reuses the row. Changed event evidence updates the candidate and returns its decision to `pending`; editing a topic creates a new immutable revision and therefore a new match identity.

Defaults are explicit and configurable:

| Bound | Default |
| --- | ---: |
| Organizations considered per event | 100 |
| Current topics considered per organization/event | 50 |
| Persisted matches per organization/event | 20 |
| Saved events examined by a topic backfill | 500 |
| Ambiguous AI candidates per event | 3 (currently unused) |
| Pending/rejected/muted match retention | 180 days |

Creating, editing, or resuming a topic enqueues one idempotent `topic_match_backfill` job for that revision on the ingest queue. A job examines only the organization's already-visible saved events and records whether the bounded window has more data. Connector runs match only their committed event batch. This avoids a deployment-wide topic/artifact Cartesian scan. Worker failures use the existing durable retry and operations history and do not create a user alert or partial match.

`GET /api/monitoring-topics/{topic_id}/matches` returns at most 200 evidence-linked candidates in newest-first order. Expired pending, rejected, and muted candidates are removed by bounded operational cleanup; confirmed decisions remain reviewable.

## Evaluation gate

The automated labelled set covers a relevant and irrelevant example in German, French, Italian, Romansh, and English, exact official-reference evidence, exclusions, paused topics, fingerprint reuse, tenant isolation, durable backfill, and the 100-organization cap. Current deterministic test results are 5/5 relevant examples retained and all explicit noise/exclusion controls rejected. These are regression results, not a production precision claim.

Before changing thresholds or enabling AI/pgvector, record on a representative reviewed sample:

- precision/noise and missed relevant items by language and source;
- evidence-open rate;
- confirm and reject rates;
- mute rate;
- the share of topics refined after reviewing results.

HL-076 will expose shared review decisions and interaction measures in the unified interest feed. Until that measured sample exists, defaults stay fixed.
