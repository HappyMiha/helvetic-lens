# AI-triage and relation-review operational metrics

The platform control room exposes a bounded aggregate over the newest 1,000 Impact records, 1,000 Ask records, 1,000 comparisons, and 2,000 review-decision events. The aggregation is read-only, contains no prompt or source passage text, and does not create high-cardinality metric labels.

## Definitions

| Measure | Definition |
| --- | --- |
| Deterministic overview p50/p95/max | Recorded processing time for a newly computed complete comparison diff. This measures machine latency; it does not show when a user found, understood, or acted on a useful insight. |
| Human time to first useful insight | Observed time from beginning a defined review task until the participant correctly explains the material change, its possible relevance, and supporting evidence. Record task, participant cohort, success criteria, and failures in moderated research. Do not derive this measure from diff latency or evidence-link clicks. |
| Provider queue p50/p95/max | Sum of provider-reported queue wait for records that made at least one provider call. Zero-call deterministic or cached answers do not dilute this measure. |
| Inference p50/p95/max | Sum of measured model request durations for records that made at least one provider call. |
| Calls and tokens | Totals from saved inference provenance. Token fields are retained separately because OpenAI-compatible providers do not all report the same usage keys. |
| Cache hit rate | Reuses divided by original saved requests plus reuses. A repeated valid answer increments `use_count` without creating a provider call. |
| Citation acceptance | Saved model attempts with validation events whose complete validation trace was accepted. Network failures without a validation event are excluded. |
| Limited and failed rates | Limited coverage or terminal failure divided by saved Impact and Ask records in the bounded window. |
| Action outcomes | Accepted and dismissed/not-applicable decision events divided by all saved review-decision events. Assignment and scheduling remain visible in the denominator and are not mislabelled as acceptance. |
| Relation review time | p50/p95/max time from opening the evidence-first review panel to saving a confirm/reject decision. Annotations and legacy unmeasured rows do not dilute the latency sample. |
| Review evidence-open rate | Measured relation-review entries that opened the saved evidence link divided by all measured entries. It is a workflow signal, not proof that evidence was understood. |
| Relation review by variant | Decision time, decision count, sample count, and evidence-open rate split by allowlisted workflow variant so a prototype cannot claim gains from a blended aggregate. |

The API returns the recorded operational and review aggregates under `ai_triage` from `/api/admin/status`. The localized platform dashboard shows the four primary rates/latencies and compact totals for calls, tokens, failures, limited results, and human action outcomes.

### Compatible machine-metric contract (HL-093, 5 September 2026)

`ai_triage.latency.deterministic_overview` is the canonical machine-processing latency. The platform dashboard already uses this field and explicitly labels it as deterministic overview in all five locale catalogues. It is not observed human comprehension.

For existing API consumers, `latency.time_to_first_useful_insight` remains a deprecated alias with unchanged timing values and `source=deterministic_overview`. It now includes `deprecated=true`, `replacement=latency.deterministic_overview`, and `measurement_kind=machine_processing_latency`. New consumers must use the canonical field; the TypeScript contract makes the obsolete alias optional. Existing persisted `diff.metrics.overview_ms` is unchanged, so no data rewrite is necessary.

The release evaluator emits `hl064.release.v2` and names its machine check `deterministic_overview_latency_measured`. It accepts canonical current reports and older reports with an explicitly typed legacy alias. The canonical field takes precedence even when empty/null; a legacy alias cannot conceal absent current samples. Human acceptance still requires the separately observed comprehension fields and bound review evidence. Fast processing or opening a citation alone cannot satisfy it.

Only finite, nonnegative numeric measurements enter deterministic-overview/provider-queue/inference latency samples. Missing, boolean, string, negative or nonfinite values are omitted rather than counted as 0 ms; measured zero remains valid. Sample counts, not saved-record counts, are the latency denominators. An entirely unmeasured series returns zero samples and null percentiles. Nonfinite moderator timings are also rejected by the usability validator.

This compatibility correction does not supply the independent labelled gold set, semantic evaluation or participant review required by the remaining HL-093 criteria.

Historical comparisons created before this measurement was introduced have no deterministic-overview sample. Historical relation reviews have no workflow duration or evidence-open sample. They remain valid records but do not become artificial zero-latency or unopened-evidence samples. Relation-review aggregates contain no notes, source text, user/organization names, or candidate identifiers. Target-host benchmark evidence must record the server, clean Git revision, GPU/model profile, corpus revision, and observation window alongside these aggregates. `scripts/check_ai_triage_release.py` verifies that the usability round names the exact capacity-report hash rather than accepting metrics copied from another run. `scripts/check_relation_graph_experiment.py` independently validates the randomized list-versus-graph trial before any graph can be promoted.
