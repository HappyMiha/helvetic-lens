# Conservative research rejection — 1.37

Status: implementation/evaluation complete; VERIFYING normal production publication.
Scope and criteria were recorded before implementation.
Parents MV2-002/020/023/051 and full architecture/professional acceptance remain OPEN.

## User outcome and existing contract

A weak local model decision must not silently discard a useful source. Develop
an auditable Laya-only guard that converts low-score unrelated decisions into
uncertain for the existing bounded review phase. Never turn uncertain into
relevant automatically. Jev routing and the underlying model/prompt stay unchanged.
A final uncertain workspace review remains uncertain in both stored decisions
and activity; it must not generate a misleading candidate_rejected event.

Reuse existing Laya adapter, pinned NoMIRACL public cache, three-way prompt,
immutable plan/journal, worker lease, budgets and permission fences. No new model,
source adapter, private production record, hosted API or client publication.
Native deployment still pauses API/tunnel for consistent backup.

## Predeclared measurement

- Development: dev split, hash offsets 12–13, two queries per relevance subset
  in English/German/French, every judged candidate. Exclude all prior project IDs.
- Fresh validation: test split, hash offsets 42–43, same allocation. Freeze IDs
  before inference; inspect labels/results only after development selection.
- Verify cached file hashes against retained immutable source manifest. Inputs
  stay at 240 title / 600 snippet characters and original same question/branch.
- Maximum 121 development and 120 validation calls, 240 seconds per stage,
  12 seconds/call, serial local inference. Total 241 calls / 480 seconds. Persist interrupted reservations and
  never repeat; no paid probes, web search, source downloads or reasoning calls.
- Record full three-way scores as uncalibrated telemetry, raw and guarded outcomes,
  all denominators, failure/uncertainty counts and additional review burden.
  Full-passage relevance labels versus snippet topical relevance remain imperfect.
  These measurements do not establish professional or end-to-end accuracy.

## Fixed rule and selection

For the pinned Laya multilingual model, change raw unrelated to uncertain when
its selected probability is below a threshold. Relevant and uncertain remain
unchanged. Candidate thresholds: 0.50, 0.65, 0.80, 0.90, 0.95.

Select on development only: zero positive hard exclusions, at least half the
baseline negative hard exclusions retained, extra uncertainty <=20% of planned
cases. Prefer the most retained negative exclusions, then the lowest threshold.
If none qualifies, do not select/promote a policy. Freeze the selection and its
input hashes before collecting/reporting validation.

Promote only if fresh validation is complete on the same pinned model, positives
have no more exclusions than baseline and <=5% exclusions, >=50% of baseline
negative exclusions remain, extra uncertainty <=20%, and at least one rejection
is deferred. Otherwise retain the current production classifier and record the
failed promotion gate. Do not retune on validation or start a replacement test
slice in this cycle. Unknown compute cost stays null.

## Acceptance

- Tests cover selection without test labels, disjoint immutable inputs, raw/guarded
  outcome preservation, budget/cancellation/restart behavior and failed promotion.
- Production candidate decisions retain model choice, scores, policy version and
  the reason for deferral; existing source/model budgets remain authoritative.
- Final uncertain review events remain uncertain, never accepted or rejected.
- Exact API lint, affected integration/unit tests and backlog invariant pass.
- Publish complete code/evidence to main, observe normal native activation and
  verify unchanged clients by their existing source/assets receipt.
- No UI/browser/private-record/paid-model probe; human acceptance remains OPEN.

## Pre-inference sample-size correction

Cache preparation stopped before any model call because one selected development
query has 11 judged candidates; the frozen allocation has 121 development and 120
validation candidates. Only per-query candidate counts were inspected, no model
outputs or validation labels. Preserve every judgment and change the predeclared
call budget to 121 + 120 = 241, keeping the same queries, thresholds and 480-second
time budget. No model call, prior held-out replay or validation-driven tuning has
occurred at this point. The original 1.35 runner's default 120-call budget remains.

## Measured development result and failed promotion

Frozen study `0ec4a6f3b78003a43ecc9375f38e9e1eec790462642b97a42058b0c02ffed7e1`
contains 121 development pairs and 120 validation pairs, twelve distinct questions
per split and no overlap with earlier project queries or the other split.
The same pinned two-CPU/4-GiB local Laya image completed all 121 development
requests, no failures, in 68.358 seconds of caller time (mean 564.94 ms, p95
709.613 ms). Forty-seven source prefixes are truncated. Local compute cost is
unknown; hosted/search/source-fetch/reasoning calls are zero.

Baseline: 21 positive full-passage labels yielded 10 relevant, 10 uncertain and
1 unrelated decision. The 100 negatives yielded 15 relevant, 60 uncertain and
25 unrelated decisions. These are snippet/full-passage proxy disagreements, not
professional accuracy or a factual truth score.

| Minimum unrelated score | Positive hard exclusions | Negative hard exclusions retained | Extra uncertain reviews |
|---|---:|---:|---:|
| 0.50 | 1 | 20 of 25 | 5 of 121 |
| 0.65 | 1 | 16 of 25 | 9 of 121 |
| 0.80 | 0 | 11 of 25 | 15 of 121 |
| 0.90 | 0 | 5 of 25 | 21 of 121 |
| 0.95 | 0 | 4 of 25 | 22 of 121 |

**No candidate met the development criteria.** The 0.80 rule removes the one
positive exclusion but retains only 44% of the useful negative exclusions,
below the predeclared 50% requirement. Higher thresholds worsen that tradeoff.
Do not relax the requirement after seeing these results. Selection was frozen
as null in `0ad116e9b0cea6df8f8c08eac72913aa3607c7563b03fa820194d14de34262ab`.
Validation was not called or reported beyond its predeclared 120-pair size; its
labels and outcomes remain unopened for selection. No production rejection guard
is enabled. The [measurement receipt](research-evaluations/2026-09-28-research-gate-policy.json)
retains IDs, labels, model scores, hashes and all denominators; it contains no raw
questions/passages or credentials. A future protocol must be recorded separately;
do not repeat these calls or retune this study on its held-out set.

## Production improvement delivered

The existing worker previously emitted candidate_rejected after an uncertain
workspace review or an unavailable provider decision. Activity now retains
candidate_uncertain / candidate_unavailable, including the actual processing
phase. These candidates are neither accepted nor silently counted as unrelated;
no source is fetched until relevance is established. Existing model/source
budgets, permission fences and failure recovery remain authoritative.

The unchanged three-way gate also retains raw_verdict, its three uncalibrated
provider probabilities, selected_probability and policy_version=topical-snippet/v1
with existing model/latency/usage provenance. It explicitly states that scores do
not establish accuracy. This is audit telemetry, not the rejected experimental
threshold policy. Jev order, the local model and both prompts are unchanged.
The existing client reads the corrected activity/decision payload; no frontend
source or Sites publication is necessary.

## Verification

65 distinct affected cases passed: 26 policy/protocol cases, 21 evaluation cases,
17 existing/new iterative worker cases, and the required backlog invariant.
The two new worker cases first exposed a fixture assertion assuming an unused
budget key existed; they pass after checking the contract's implicit zero. The
other 15 worker cases passed unchanged. Exact API lint and both runner lint gates
passed. Tests prove unresolved/unavailable events, no premature source reads,
raw production verdict/telemetry retention, no experimental promotion, cancellation,
immutable/disjoint selection, source tampering, lock exclusion and no inference
before selection. No private production workflow or paid call was used.

A report can inspect the historical frozen runtime contract without new inference;
collect/resume still requires exact current code/prompt hashes. The original 1.35
runner retains its default 120-call budget and existing receipts unchanged.
Normal Core activation and unchanged-client/source checks remain the release gate.
