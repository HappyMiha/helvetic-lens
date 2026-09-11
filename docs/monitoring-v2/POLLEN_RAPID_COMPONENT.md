# Pollen exact-window rapid comparison v1

MV2-070 C02b1, 11 September 2026. Internal pure implementation:
`helvetic_lens.pollen_rapid.compare_rapid_increase`. Uses the C02a immutable
source/sample contracts and their lossless content identity. It has no endpoint,
source admission, authorization, persistent state, rollout or delivery.

`RapidBinding` records organization/owner/subject/configuration revision, exact
source series and a rapid-only v1 rule. Threshold/category combinations are
explicitly rejected until the rule coordinator exists. Daily periods cannot use
an hourly rapid rule. The existing configuration contract bounds the interval
to 1–24 hours and requires a positive absolute minimum increase in `number/m3`.

The caller supplies one baseline (or none), current record and an explicit aware
evaluation time. Both samples must belong to the identical source, method,
station, allergen, period and unit. Forecasts also share model/grid/member/layer/
cell/issue. The difference between their source valid times must equal the exact
configured interval; there is no nearest-point tolerance, interpolation or use of
fetch time instead. Future forecast valid times are allowed within one issue and
remain forecast evidence, never claimed as observed concentrations.

Current quality must be usable, rights approved and freshness unexpired at the
evaluation instant; both retrievals must have happened by then. Baseline quality
and rights must also remain usable/approved under the same policy/parser revision.
An approved historical baseline may naturally be past its former live freshness
deadline. That age alone does not invalidate a historical comparison; explicit
stale/missing quality or revoked rights does. The future adapter/ledger must
recheck current policy eligibility for both records and verify their provenance.
The two endpoints define this absolute-change rule; no claim is made about
intermediate measurements or the shape of the curve between them.

For eligible exact endpoints, `delta = current - baseline` is computed with a
private Decimal context sufficient for the source contract's full precision.
`matches` is inclusive `delta >= minimum_increase`. Real zero is a valid baseline,
and zero/negative differences remain valid non-matches. Nothing is divided by a
baseline or rounded into a match. Ambient low precision or Inexact traps do not
change the answer.

`RapidComparison` retains evaluator version, full private binding, both records,
evaluation time, signed delta, match status and canonical comparison ID. Ineligible
inputs have a structured reason, `delta=None`, `matches=None` and no comparison
ID. Reasons distinguish missing baseline, quality/rights, expired current data,
unequal windows, parser changes and policy changes. Invalid source identity or
time input fails validation rather than silently omitting a record.

Comparison identity includes evaluator revision, canonical private binding, both
source content/revisions and policy version. Equivalent decimal spelling and
refetch metadata preserve it; a correction to either input changes it even when
the numeric result is unchanged. The evaluation instant is retained as evidence,
but does not make an unchanged comparison new. Serialization replay yields the
same ID. This is not a transition/notification ID or an exactly-once guarantee.

C02b2 must coordinate initial state, overlap between matching windows, reset/
recovery, corrections, combined threshold+rapid rules and historical recomputation.
The C02a threshold evaluator continues to reject unsupported combined rules.
Categories require approved source scales; C02c still must implement the atomic
state/evidence ledger and outbox. A first matched comparison must not implicitly
authorize a new-change alert. Source-backed Start and mail remain disabled.

The tests are synthetic arithmetic/identity checks. Source coverage, permission,
period alignment, model accuracy, UX and real-user acceptance remain separate.
