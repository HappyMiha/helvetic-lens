"""Numeric rule orchestration using synthetic evidence, no notification send."""

from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_pollen_thresholds import NOW, SERIES, sample

from helvetic_lens.pollen_numeric import NumericBinding, NumericDecision, NumericState, evaluate_numeric
from helvetic_lens.pollen_thresholds import PollenSeries


def binding(mode="both", **changes):
    rule = {"period": SERIES.period}
    if mode in {"both", "threshold"}:
        rule["threshold"] = {"trigger_at_or_above": "10", "reset_at_or_below": "5"}
    if mode in {"both", "rapid"}:
        rule["rapid_increase"] = {"minimum_increase": "5", "window_hours": 2}
    return NumericBinding.model_validate({"organization_id": "org-a", "owner_id": "owner-a",
        "subject_id": "subject-a", "configuration_revision": 1, "series": SERIES, "rule": rule, **changes})


def evaluate(current, baseline=None, prior=None, mode="both"):
    return evaluate_numeric(binding(mode), current, baseline=baseline, as_of=current.fetched_at, prior=prior)


def test_combined_crossings_produce_one_material_update_with_both_reasons():
    initial = evaluate(sample("4", 2), sample("0"))
    crossed = evaluate(sample("10", 3), sample("0", 1), initial.state)
    assert initial.material_id is None
    assert crossed.reasons == ("threshold_triggered", "rapid_triggered")
    assert crossed.material_id and crossed.threshold.transition_id and crossed.rapid.comparison_id
    assert crossed.previous_rapid == initial.rapid
    ongoing = evaluate(sample("20", 4), sample("4", 2), crossed.state)
    assert ongoing.reasons == () and ongoing.material_id is None
    reset = evaluate(sample("4", 5), sample("10", 3), ongoing.state)
    assert reset.reasons == ("threshold_reset", "rapid_reset")
    assert reset.material_id != crossed.material_id
    threshold_only_change = evaluate(sample("10", 6), sample("20", 4), reset.state)
    assert threshold_only_change.reasons == ("threshold_triggered",)
    rapid_only_change = evaluate(sample("30", 7), sample("4", 5), threshold_only_change.state)
    assert rapid_only_change.reasons == ("rapid_triggered",)


def test_overlapping_rapid_matches_are_one_condition_until_an_eligible_reset():
    prior = None
    decisions = []
    for hour, value, base in [(2, "10", "0"), (3, "20", "0"), (4, "30", "10"),
                              (5, "4", "20"), (6, "25", "30"), (7, "30", "4")]:
        decision = evaluate(sample(value, hour), sample(base, hour - 2), prior, mode="rapid")
        decisions.append(decision)
        prior = decision.state
    assert [d.rapid_disposition for d in decisions] == ["baseline", "stable", "stable", "reset", "stable", "triggered"]
    assert len([d for d in decisions if d.material_id]) == 2
    assert all(d.threshold is None for d in decisions)


def test_missing_rapid_baseline_does_not_hide_valid_threshold_transition():
    first = evaluate(sample("0"))
    crossed = evaluate(sample("10", 1), prior=first.state)
    assert crossed.reasons == ("threshold_triggered",) and crossed.material_id
    assert crossed.rapid.reason == "baseline_missing" and crossed.state.rapid.matched is None
    ready = evaluate(sample("15", 2), sample("0"), crossed.state)
    assert ready.rapid_disposition == "baseline" and ready.material_id is None


def test_rapid_unavailability_retains_condition_and_recovery_is_silent():
    first = evaluate(sample("10", 2), sample("0"), mode="rapid")
    missing = evaluate(sample("15", 3), prior=first.state, mode="rapid")
    assert missing.rapid_disposition == "unavailable" and missing.state.rapid.matched is True
    assert missing.state.rapid.last_good == first.rapid and missing.material_id is None
    recovered = evaluate(sample("0", 4), sample("10", 2), missing.state, mode="rapid")
    assert recovered.rapid_disposition == "recovered" and recovered.state.rapid.matched is False
    assert recovered.material_id is None
    crossed = evaluate(sample("30", 5), sample("15", 3), recovered.state, mode="rapid")
    assert crossed.reasons == ("rapid_triggered",)


def test_threshold_reset_does_not_claim_the_still_matching_rapid_rule_resolved():
    # A configured minimum of one allows rapid rise while absolute value is low.
    configured = binding(rule={**binding().rule.model_dump(), "rapid_increase": {"minimum_increase": "1", "window_hours": 2}})
    first = evaluate_numeric(configured, sample("20", 2), baseline=sample("0"), as_of=NOW + timedelta(hours=2))
    reset = evaluate_numeric(configured, sample("4", 3), baseline=sample("0", 1),
                             as_of=NOW + timedelta(hours=3), prior=first.state)
    assert reset.reasons == ("threshold_reset",)
    assert reset.state.threshold.active is False and reset.state.rapid.matched is True
    assert not hasattr(reset.state, "resolved")


@pytest.mark.parametrize("mode", ["both", "threshold", "rapid"])
def test_json_restart_replay_and_same_checkpoint_retry_do_not_duplicate_material_update(mode):
    baseline = sample("0") if mode != "threshold" else None
    initial = evaluate(sample("4", 2), baseline, mode=mode)
    next_baseline = sample("0", 1) if mode != "threshold" else None
    current = sample("10", 3)
    crossed = evaluate(current, next_baseline, initial.state, mode)
    restored = NumericState.model_validate_json(crossed.state.model_dump_json())
    replay = evaluate(current, next_baseline, restored, mode)
    assert replay.material_id is None and replay.reasons == ()
    retried = evaluate(current, next_baseline, NumericState.model_validate_json(initial.state.model_dump_json()), mode)
    assert retried.material_id == crossed.material_id
    assert NumericDecision.model_validate_json(crossed.model_dump_json()) == crossed


@pytest.mark.parametrize("endpoint", ["current", "baseline"])
def test_latest_source_or_baseline_correction_rebaselines_without_fake_crossing(endpoint):
    baseline, current = sample("0"), sample("10", 2)
    initial = evaluate(current, baseline)
    if endpoint == "current":
        current = sample("0", 2, source_revision=2, artifact_hashes=("b" * 64,))
    else:
        baseline = sample("10", source_revision=2, artifact_hashes=("b" * 64,))
    corrected = evaluate(current, baseline, initial.state)
    assert corrected.rapid_disposition == "revised" and corrected.material_id is None
    assert corrected.state.rapid.matched is False
    assert corrected.previous_rapid == initial.rapid


def test_conflicting_baseline_revision_and_older_receipts_are_not_silently_reused():
    first = evaluate(sample("10", 2), sample("0"))
    with pytest.raises(ValueError, match="Conflicting content"):
        evaluate(sample("10", 2), sample("1"), first.state)
    revised = evaluate(sample("10", 2), sample("0", source_revision=2, artifact_hashes=("b" * 64,)), first.state)
    old = evaluate(sample("10", 2), sample("0"), revised.state)
    assert old.disposition == "history_required" and old.state == revised.state and old.material_id is None
    historical = evaluate_numeric(binding(), sample("0", 1), as_of=NOW + timedelta(hours=2), prior=revised.state)
    assert historical.disposition == "history_required" and historical.state == revised.state


def test_policy_rebaseline_and_expired_prior_state_do_not_replay_historical_change():
    first = evaluate(sample("0", 2), sample("0"))
    changed = evaluate(sample("20", 3, policy_version="v2"), sample("0", 1, policy_version="v2"), first.state)
    assert changed.rapid_disposition == changed.threshold.disposition == "policy_rebaseline"
    assert changed.material_id is None
    gap = evaluate(sample("20", 6), sample("0", 4), first.state)
    assert gap.rapid_disposition == gap.threshold.disposition == "recovered"
    assert gap.material_id is None


def test_revoked_current_does_not_clear_either_condition():
    first = evaluate(sample("10", 2), sample("0"))
    unavailable = evaluate(sample("10", 2, rights="revoked"), sample("0"), first.state)
    assert not unavailable.state.threshold.available and not unavailable.state.rapid.available
    assert unavailable.state.threshold.active and unavailable.state.rapid.matched
    assert unavailable.material_id is None
    recovered = evaluate(sample("10", 2), sample("0"), unavailable.state)
    assert recovered.rapid_disposition == recovered.threshold.disposition == "recovered"
    assert recovered.material_id is None


@pytest.mark.parametrize("field,value", [("organization_id", "org-b"), ("owner_id", "owner-b"),
    ("subject_id", "subject-b"), ("configuration_revision", 2)])
def test_prior_private_binding_cannot_be_reused(field, value):
    first = evaluate(sample("0", 2), sample("0"))
    with pytest.raises(ValueError, match="private binding"):
        evaluate_numeric(binding(**{field: value}), sample("10", 3), baseline=sample("0", 1),
                         as_of=NOW + timedelta(hours=3), prior=first.state)


def test_unsupported_category_and_inconsistent_serialized_components_are_rejected():
    with pytest.raises(ValidationError):
        binding(rule={**binding().rule.model_dump(), "category_change": True})
    first = evaluate(sample("10", 2), sample("0"))
    damaged = first.state.model_dump()
    damaged["rapid"]["comparison"]["binding"]["owner_id"] = "different-owner"
    with pytest.raises(ValidationError):
        NumericState.model_validate(damaged)
    with pytest.raises(ValueError):
        evaluate(sample("0"), sample("0"), mode="threshold")


def test_combined_forecast_uses_one_issue_and_preserves_future_valid_times():
    series = PollenSeries(source_id="forecast", method_version="density-v1", station_id="PBS",
        allergen="ragweed", period="forecast_instant", forecast={"model": "icon", "grid": "grid-a",
            "member": "control", "layer": "80", "cell": 42, "issue_at": NOW})
    configured = binding(series=series, rule={**binding().rule.model_dump(), "period": "forecast_instant"})
    first = evaluate_numeric(configured, sample("4", series=series, valid_at=NOW + timedelta(hours=6)),
                             baseline=sample("0", series=series, valid_at=NOW + timedelta(hours=4)), as_of=NOW)
    current = sample("10", series=series, valid_at=NOW + timedelta(hours=7), fetched_at=NOW + timedelta(minutes=1))
    crossed = evaluate_numeric(configured, current, baseline=sample("0", series=series, valid_at=NOW + timedelta(hours=5)),
                               as_of=current.fetched_at, prior=first.state)
    assert crossed.reasons == ("threshold_triggered", "rapid_triggered")
    assert crossed.state.rapid.comparison.current.series.forecast == series.forecast
    with pytest.raises(ValueError, match="private binding"):
        evaluate_numeric(configured, sample("10"), as_of=NOW)
