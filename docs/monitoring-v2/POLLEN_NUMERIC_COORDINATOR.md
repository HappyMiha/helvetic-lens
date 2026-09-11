# Numeric rule coordinator v1

MV2-070 C02b2, 11 September 2026. `helvetic_lens.pollen_numeric` coordinates
threshold-only, rapid-only and combined threshold+rapid rules. Category rules
remain rejected. It is pure internal code without authorization, source admission,
database, rollout or notification sending.

The full private/source/configuration binding is immutable. Threshold and rapid
sub-bindings are derived from that same rule revision, retaining source/period and
forecast identity. The caller supplies current input and, when rapid is configured,
the exact-window baseline from the future versioned ledger. Component state is
serialized with its binding and evaluation time; mismatched components fail.

## Transitions and recovery

Threshold behavior follows C02a. Rapid comparison follows C02b1, with a retained
matched condition on top: a first eligible comparison establishes a silent baseline;
false-to-true produces `rapid_triggered`; true-to-false produces `rapid_reset`.
Reset requires an eligible window whose delta is strictly below the inclusive
minimum. Consecutive overlapping matching windows keep the same condition and
produce no repeat transition. This is an overlap rule, not a configurable cooldown.

Missing/invalid rapid coverage preserves the last-good condition with availability
false. It does not block a separately valid threshold transition. First availability,
recovery after missing/expired data, policy changes and latest source/baseline
corrections establish a silent rapid baseline. Corrections retain previous/current
comparison evidence and are not disguised as a new temporal crossing.

The coordinator shares C02a source-order/content validation. Older current records
or older receipts/revisions for a known baseline return `history_required` without
advancing any component. Same-revision conflicting content fails. It checks baseline
identities known to the latest checkpoint; checking every historical revision,
recomputing downstream state and resolving historical corrections remain ledger
obligations. An unseen baseline must not be assumed authoritative merely because
its fields validate.

## One material update, explicit reasons

Each input may return zero or one `material_id`, with all component reasons:
`threshold_triggered`, `threshold_reset`, `rapid_triggered`, `rapid_reset`.
Simultaneous transitions share that update while preserving their component
evidence. Conditions remain separate; resetting one never labels the whole monitor
resolved while another condition is active or unavailable.

The ID binds coordinator version, full private configuration, source content,
ordered reasons and rapid comparison identity when rapid caused a transition.
Same-checkpoint retry produces the same ID. Replaying an input after JSON restart
returns no new transition. Return values retain threshold previous/current evidence,
rapid current/baseline evidence and the prior last-good rapid comparison.

C02c must atomically append evidence and compare-and-swap state, deduplicate the
outbox, enforce source/privacy/retention rules and preserve user review decisions.
No material ID grants delivery consent. Pause/resume and replay generation require
their own admission policy; full historical recomputation and category scales are
still open. C01/030/031 must connect the component to accepted sources and the UI.
Synthetic tests establish no live coverage or real-user readiness.
