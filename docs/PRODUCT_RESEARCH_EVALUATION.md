# Bounded research evaluation — 1.35

Status: implementation and measurements complete; VERIFYING normal publication.
Scope recorded before code, 28 September 2026.
Parents MV2-002/020/023/051 remain IN PROGRESS. This stage evaluates the shared
1.34 research contract; it does not publish a new client or change provider routing.

## Existing components and reuse

`scripts/evaluate_dossier_retrieval.py` already pins NoMIRACL input files and
implements corpus retrieval evaluation. Its cached public TSV/JSONL files and
recorded SHA-256 manifest can be reused without downloading data again.
`product_research_gate` supplies the current three-way instructions/criteria;
`decision_engines.LayaEngine` supplies the validated local System One adapter.
The two saved 1.34 native-worker fixture receipts supply actual citation and
follow-up records for an independent deterministic audit. Reuse the production
exact-quote validator. Do not create another research engine or evidence store.

## Scope, readiness and budgets

1. Freeze a new deterministic NoMIRACL slice before inference: English, German,
   French; test offset 40; two answerable and two non-answerable queries per
   language; retain every judged candidate for those queries. This is disjoint
   from the earlier project test slices at offsets 0 and 20. Model pretraining
   contamination remains unknown. No prompt or threshold tuning in this stage.
2. Verify cached source hashes against the earlier pinned manifest. Preserve
   original binary relevance labels. The production gate receives a title up to
   240 characters and a 600-character passage prefix as a candidate snippet.
   Labels assess full passages; prefix truncation is explicit and limits what
   agreement means. No overall/branch decomposition is evaluated here.
3. Actual inference is local Laya only, at its existing fixed loopback endpoint.
   Maximum 120 calls, one at a time, total 240 seconds, maximum 12 seconds per
   call. Hosted Jev, web search, source fetching and generative reasoning are
   disabled in this evaluation runner. Interrupted calls remain recorded and
   are never silently repeated. Unknown local compute cost remains null.
4. Report relevant/unrelated/uncertain/unavailable separately, positive retention,
   negative rejection, harmful positive rejection, false admissions, undecided
   counts, label denominators, provider latency and caller wall time. Never turn
   uncertainty or failures into correct negatives. No invented combined quality
   score or confidence-to-accuracy conversion. Missing cases stay visible.
5. Audit only the explicitly supplied public fictional 1.34 fixture receipts:
   exact quote/locator, contained IDs, duplicate body hashes, same-claim
   contradiction and follow-up-to-new-evidence linkage. This measures structural
   integrity, not entailment, independent publisher diversity or factual truth.
6. Publish only IDs, hashes, labels and metrics; raw third-party passages, queries
   and credentials remain outside Git. The dataset's Apache-2.0 declaration and
   underlying Wikipedia attribution/share-alike rights remain distinct.

Readiness: the cached public data and local service are available; validate their
actual hashes/response model before claiming a completed measurement. No private
production dossiers, browser/DOM/screenshot actions or paid probes in this
background cycle. Hosted comparison and live end-to-end professional-source
evaluation remain OPEN. An unavailable provider is a reported measurement gap.

## Acceptance recorded before implementation

- A saved immutable input plan identifies sources, sample IDs, gate code/prompt
  hashes and limits before any model request.
- The local runner cannot call a hosted provider, resume under changed inputs or
  exceed cumulative call/time limits; a partial run produces an explicit report.
- Metrics expose all outcomes and denominators; no confidence or missing usage
  is represented as accuracy or free compute.
- Tampered cache/plan, repeated IDs, malformed output, interrupted calls and
  altered/foreign citations have meaningful deterministic regression tests.
- Both saved fixture traces are audited without modifying their original files.
- Required API lint, affected tests, script lint and backlog invariant pass;
  exact main is pushed immediately and normal native activation is verified.
- Existing clients remain at the verified 1.34 source/assets; no unchanged Sites
  publication. Full research quality, professional acceptance and architecture
  acceptance stay OPEN regardless of benchmark results.

## Source and interpretation

[NoMIRACL dataset card](https://huggingface.co/datasets/miracl/nomiracl) documents
human binary relevance judgments and answerable/non-answerable candidate pools.
Use the immutable revision and file hashes already retained in
[the prior experiment](PRODUCT_CORPUS_SEARCH.md). These selected encyclopedia
passages do not establish Legal/Pharma performance or whole-internet recall.


## Measured result and decision

Frozen plan `b4c84b4b96360a9ef69181991e8585854f47a50e15550e4726445ac1b0b89ac2`
selected 12 queries / 120 candidate pairs, 40 per language, with zero overlap
against the retained earlier project query IDs. 22 full passages have positive
human labels; 98 have negative labels. 48 candidate inputs truncate their source
passage/title. Overall and branch question are identical in this evaluation;
branch decomposition and multi-source reasoning are not measured.

The actual existing local Laya service completed all 120 requests in 66.249 seconds
of summed caller time, with no errors or skipped cases. Mean caller latency was
552.08 ms, nearest-rank p95 665.097 ms. Response model and the observed two-CPU,
4 GiB image identity are frozen in the [measurement receipt](research-evaluations/2026-09-28-research-gate-laya.json).
This is serial local inference timing, not a production dossier latency promise.

| Full-passage human label | Admitted | Uncertain | Rejected |
|---|---:|---:|---:|
| Relevant (22) | 10 | 10 | 2 |
| Non-relevant (98) | 29 | 54 | 15 |

There is substantial disagreement with the dataset labels. In this selected
sample, 2/22 positives were rejected and 29/98 negatives were admitted. Both
rejected positive passages fit the input limit without truncation. 64/120
candidates need a separate uncertainty decision. Do not promote a stronger Laya
quality claim, change thresholds based on this test slice, treat uncertainty as
success, or generalize these ratios to Legal/Pharma. The production gate measures
broad research relevance from short snippets, while NoMIRACL labels whether the
full passage is relevant to the original question; this is an imperfect proxy.
Model pretraining contamination and source-prefix answer retention are unmeasured.
A future improvement must use development data and a fresh disjoint validation
slice. The supplied production router remains unchanged by this measurement.

Hosted Jev comparison, live search recall, reasoning/extraction entailment,
source publisher independence, local compute price and end-to-end professional
accuracy remain unmeasured. Hosted/web/generative request counts are zero.
Confidence is retained as provider telemetry only. Unknown cost remains null.

## Saved-run integrity audit

The [offline trace audit](research-evaluations/2026-09-28-iterative-trace-audit.json)
checked both original 1.34 fictional receipts without altering them. Each passed
14 citation links, one follow-up with new evidence updating the same claim, and
one preserved contradiction. Each retained one unresolved question. Recorded
body hashes distinguish three fixture bodies; raw originals and factual truth
were not independently re-fetched or verified. Exact quote containment is not
entailment. Publisher independence remains unknown; all fixture URLs use example.org.

## Reproduce

Use the native API Python environment with `PYTHONPATH=.:services/api`:

```sh
python -B scripts/evaluate_iterative_research.py prepare --cache /path/to/verified-public-cache --directory /tmp/research-gate-evaluation
python -B scripts/evaluate_iterative_research.py run-local --directory /tmp/research-gate-evaluation --credentials-file /protected/operator-credentials.json
python -B scripts/evaluate_iterative_research.py report --directory /tmp/research-gate-evaluation --output /tmp/research-gate-report.json
python -B scripts/evaluate_iterative_research.py audit --output /tmp/research-trace-audit.json
```

Preparation verifies the existing pinned public files and freezes all input hashes
before any inference. An existing plan is reused, never overwritten. The runner
uses only the fixed loopback Laya adapter; there is no hosted-provider argument
or automatic fallback. One exclusive lock prevents parallel attempts. A durable
pre-call reservation prevents interrupted calls being repeated on resume. The
journal counts interrupted reservations against both call and time budgets.
Reports omit source/query text. A report can expose incomplete measurements
without running any more inference. Do not remove the journal to manufacture a
fresh budget for the same evaluation. Treat the outside-Git directory as the
retained local evaluation record.

## Validation and remaining work

21 evaluation cases plus the required backlog invariant pass. They exercise
label denominators, missing/uncertain/failed cases, cache and plan tampering,
real cancellation deadlines, cumulative limits, concurrent invocation, restart
without duplicated calls, model mismatch, fabricated citations, foreign IDs,
duplicate evidence and retained contradiction/follow-up structure. Required API
lint and the runner lint pass. The retained 1.34 runtime and clients are unchanged.
Normal Core activation and final clean main/source checks remain the release gate.

Next quality work: review candidate-relevance versus answerability objectives,
then develop and validate a policy that avoids discarding useful evidence while
bounding uncertain-candidate analysis. Use development data and a new untouched
test slice. A paid hosted comparison is outside background-cycle authority.
Continue independent Source/Version/identity/review work while that live gate
remains open. Full MV2 parents and architecture/human acceptance remain OPEN.
