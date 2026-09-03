# AI-triage and relation-review operational metrics

The platform control room exposes a bounded aggregate over the newest 1,000 Impact records, 1,000 Ask records, 1,000 comparisons, and 2,000 review-decision events. The aggregation is read-only, contains no prompt or source passage text, and does not create high-cardinality metric labels.

## Definitions

| Measure | Definition |
| --- | --- |
| Deterministic overview p50/p95/max | Wall time saved with a newly computed complete comparison diff. This is also the current machine-measured **time to first useful insight**, because the deterministic overview is available before AI. |
| Provider queue p50/p95/max | Sum of provider-reported queue wait for records that made at least one provider call. Zero-call deterministic or cached answers do not dilute this measure. |
| Inference p50/p95/max | Sum of measured model request durations for records that made at least one provider call. |
| Calls and tokens | Totals from saved inference provenance. Token fields are retained separately because OpenAI-compatible providers do not all report the same usage keys. |
| Cache hit rate | Reuses divided by original saved requests plus reuses. A repeated valid answer increments `use_count` without creating a provider call. |
| Citation acceptance | Saved model attempts with validation events whose complete validation trace was accepted. Network failures without a validation event are excluded. |
| Limited and failed rates | Limited coverage or terminal failure divided by saved Impact and Ask records in the bounded window. |
| Action outcomes | Accepted and dismissed/not-applicable decision events divided by all saved review-decision events. Assignment and scheduling remain visible in the denominator and are not mislabelled as acceptance. |
| Relation review time | p50/p95/max time from opening the evidence-first review panel to saving a confirm/reject decision. Annotations and legacy unmeasured rows do not dilute the latency sample. |
| Review evidence-open rate | Measured relation-review entries that opened the saved evidence link divided by all measured entries. It is a workflow signal, not proof that evidence was understood. |

The API returns these values under `ai_triage` from `/api/admin/status`. The localized platform dashboard shows the four primary rates/latencies and compact totals for calls, tokens, failures, limited results, and human action outcomes.

Historical comparisons created before this measurement was introduced have no deterministic-overview sample. Historical relation reviews have no workflow duration or evidence-open sample. They remain valid records but do not become artificial zero-latency or unopened-evidence samples. Relation-review aggregates contain no notes, source text, user/organization names, or candidate identifiers. Target-host benchmark evidence must record the server, clean Git revision, GPU/model profile, corpus revision, and observation window alongside these aggregates. `scripts/check_ai_triage_release.py` verifies that the usability round names the exact capacity-report hash rather than accepting metrics copied from another run.
