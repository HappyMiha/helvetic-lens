# Pollen numeric threshold component v1

MV2-070 C02a, 11 September 2026. `helvetic_lens.pollen_thresholds` is an internal
pure component, without endpoint, database, source polling, rollout or delivery.
Inputs must come from a future accepted adapter. Fields do not establish source
approval, workspace membership or notification consent.

## Identity and evidence

`ThresholdBinding` binds organization, owner, subject, configuration revision,
exact `PollenSeries` and the v1 `PollenRule`. Only a threshold without rapid/category
rules is accepted; unsupported combinations fail instead of partial evaluation.
Source, method version, public station, allergen, period and `number/m3` must match.
Forecast identity also includes model/grid/member/layer/cell/issue. Each issue is
its own series; cross-issue comparison is later work.

`PollenSample` retains source revision, valid time, Decimal value, quality, rights
status/policy version, parser version, one to eight artifact hashes, retrieval and
a policy-derived freshness deadline. Timestamps must be aware and normalize to
UTC. Observation cannot follow retrieval; forecast validity/retrieval cannot
precede issue. Usable values must be finite, nonnegative and present. Decimal text,
Decimal and integers are accepted; binary floats are rejected. The technical source
bound is 60 digits / 40 fractional digits, separate from configuration precision.
There is no display rounding or inference of allergological categories.

The accepted adapter must validate actual period alignment, derive freshness from
observation/issue time and an approved versioned policy, verify bytes/conversion,
and assign increasing source revisions for changed content at the same source
time. Value/artifact/parser conflicts under the same revision fail. Retrieval,
quality and rights can change independently; a same-revision/same-policy refetch
cannot extend freshness. Already expired samples retain their earlier deadline.

## State transitions

`evaluate_threshold(binding, sample, as_of=..., prior=...)` returns immutable
`ThresholdDecision` and `ThresholdState`. Time is explicit and cannot precede
retrieval or the prior evaluation. A changed private/configuration/source binding
requires a new baseline; identities must be authorized by the caller.

| Condition | Result |
|---|---|
| First usable value | `baseline`, including initial high; no invented change or transition ID |
| Inactive value reaches inclusive trigger | `triggered`, deterministic transition ID |
| Active value reaches inclusive reset | `reset`, deterministic transition ID |
| Value between boundaries | `stable`, preserve previous condition |
| Missing/stale/unavailable/unapproved/revoked or at/after freshness deadline | `unavailable`, retain last-good value/condition; never resolve or substitute zero |
| Usable after unavailable/expired prior state | `recovered`, current baseline without historical crossing flood |
| Higher revision at latest source time | `revised`, rebaseline with prior/current evidence |
| Changed rights policy | `policy_rebaseline`, no source-change transition |
| Same usable source content/revision | `duplicate`, no second transition |
| Older time, lower latest revision or older receipt of the same revision | `history_required`, return input without changing current state |

The first value in the hysteresis band is inactive. Later band values preserve
the previous condition, including through interruptions/corrections. Initial
missing data has neither last-good value nor known threshold condition. Quality
and rights are rechecked even when source bytes/revision are unchanged.

Every decision contains current input and prior last-good evidence; state retains
the full binding. Retention is internal: authorized display/export/deletion and
rights enforcement are still required before exposing any private evidence.

Transition IDs hash canonical private binding + incoming content + transition kind.
Decimal canonicalization preserves every digit independently of arithmetic context.
Same-checkpoint retries yield the same ID; applying that source revision to its
serialized resulting state yields no new transition. This does not establish
exactly-once persistence or delivery.

## Remaining integration

C02b must implement exact-window rapid increase, approved category semantics,
historical correction/recomputation and cross-issue forecast revisions.
`history_required` is a handoff, not permission to drop older corrections. Latest
corrections are history/review evidence even without a temporal-crossing ID.

C02c must atomically append evidence, compare-and-swap state and deduplicate outbox
bindings; preserve past decisions, handle replay and recheck rights/permissions/
consent. Source-backed Start, MV2-030/031 and delivery remain gated. The generic
ledger can reuse this component without placing private thresholds in legal data.

Tests use synthetic identities/concentrations. They establish no live pollen
coverage, source rights, model accuracy, medical scale or user-testing readiness.
