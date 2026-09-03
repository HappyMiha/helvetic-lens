# HL-051 relation-candidate benchmark

## Decision

Keep pgvector disabled. The versioned `hl051-labelled-v1` gate reached **100% recall and 100% precision** on 10 relevant and 5 unrelated multilingual pairs after two bounded deterministic fixes. It issued no embedding requests, added no disk usage, and kept every similarity-only hit in the existing proposed/evidence-required state.

This is a release gate for the current source mix, not a claim of universal semantic recall. Re-run it when labelled production review data contains a meaningful class of missed relations.

## Set and baseline

The checked-in fixture covers German, French, Italian, Romansh, and English titles; bills, initiatives, consultation and regulator notices, and court decisions; exact cross-language SR/RS references; and five unrelated controls. The baseline mirrors production candidate discovery:

1. confirmed official relations and exact SR/RS references;
2. PostgreSQL `simple` full-text prefix candidates from normalized official titles;
3. the existing bounded explainable score and proposed-relation threshold.

The first run found one false negative: `Datenschutzgesetzes` did not match `Datenschutz`. The fix adds transparent German legal-instrument suffix variants while retaining the original token. A second fix makes exact SR/RS references seed retrieval even when source and target titles use different national languages.

## Measured result

Run on 3 September 2026 with `python scripts/benchmark_relation_candidates.py`:

| Metric | Result |
| --- | ---: |
| Relevant pairs | 10 |
| Unrelated controls | 5 |
| Recall | 100% |
| Precision | 100% |
| False negatives / false positives | 0 / 0 |
| Mean / p95 in-process candidate latency | 0.08 ms / 0.16 ms |
| Peak Python allocation for the gate | 4,952 bytes |
| Added persistent disk | 0 bytes |
| Embedding requests | 0 |
| Evidence-policy compliance | 100% |

Timing is a small local deterministic measurement and should not be extrapolated to an entire production catalogue. The production path remains bounded by indexed full-text retrieval, per-event and per-organization candidate limits, and the durable ingestion queue.

## Evidence and citation correctness

Candidate similarity is never converted into evidence. Exact official relations retain their official metadata; title/full-text matches remain `proposed`, record the score components and rule revision, and explicitly carry `similarity_is_not_evidence=true`. Downstream AI still has to cite exact saved passages under the existing validation contract. The benchmark therefore checks evidence-policy correctness rather than inventing citation rows for a retrieval-only stage.

## Reopen threshold

Start a semantic embedding trial only if a larger reviewed set drops below 90% recall at 85% precision, or shows a repeated high-value multilingual miss that exact identifiers, official metadata, and safe title normalization cannot solve. Any trial must use versioned embeddings in the existing PostgreSQL database, run through durable jobs, and demonstrate improved recall plus acceptable latency, RAM, disk, and citation correctness before it can be enabled.
