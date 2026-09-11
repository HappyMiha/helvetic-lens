"""Synthetic state/rule acceptance, not source or live delivery evidence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from helvetic_lens.pollen_thresholds import (
    PollenSample,
    PollenSeries,
    ThresholdBinding,
    ThresholdState,
    evaluate_threshold,
)

NOW = datetime(2026, 9, 11, 8, tzinfo=UTC)
SERIES = PollenSeries(source_id="synthetic-observations", method_version="automatic-v1",
                      station_id="PBS", allergen="grasses", period="observation_hourly")


def binding(series=SERIES, **overrides):
    return ThresholdBinding.model_validate({"organization_id": "org-a", "owner_id": "owner-a",
        "subject_id": "subject-a", "configuration_revision": 1, "series": series,
        "rule": {"period": series.period, "threshold": {"trigger_at_or_above": "10", "reset_at_or_below": "5"}},
        **overrides})


def sample(value, hour=0, **overrides):
    stamp = NOW + timedelta(hours=hour)
    return PollenSample.model_validate({"series": SERIES, "valid_at": stamp,
        "source_revision": 1, "value": value, "quality": "usable", "rights": "approved",
        "policy_version": "synthetic-policy-v1", "parser_version": "synthetic-parser-v1",
        "artifact_hashes": ("a" * 64,), "fetched_at": stamp,
        "fresh_until": stamp + timedelta(hours=3), **overrides})


def step(value, hour=0, prior=None, **overrides):
    current = sample(value, hour, **overrides)
    return evaluate_threshold(binding(), current, as_of=current.fetched_at, prior=prior)


def test_inclusive_boundaries_and_hysteresis_emit_only_material_transitions():
    previous = None
    results = []
    for hour, value in enumerate(["0", "9.999999", "10", "10.000001", "7", "5", "5", "10"]):
        result = step(value, hour, previous)
        results.append(result)
        previous = result.state
    assert [r.disposition for r in results] == ["baseline", "stable", "triggered", "stable", "stable", "reset", "stable", "triggered"]
    assert [r.state.active for r in results] == [False, False, True, True, True, False, False, True]
    identities = [r.transition_id for r in results if r.transition_id]
    assert len(identities) == len(set(identities)) == 3
    crossing = results[2]
    assert crossing.previous.value == Decimal("9.999999")
    assert crossing.current.value == Decimal("10")
    assert crossing.state.binding.configuration_revision == 1
    assert crossing.current.artifact_hashes == ("a" * 64,)


def test_initial_high_state_is_a_baseline_without_invented_crossing():
    first = step("50")
    assert first.disposition == "baseline" and first.state.active and first.transition_id is None
    assert first.previous is None and first.state.last_good.value == 50
    assert step("50", 1, first.state).disposition == "stable"


@pytest.mark.parametrize("quality,rights,value", [
    ("missing", "approved", None), ("stale", "approved", "0"),
    ("unavailable", "approved", None), ("usable", "unverified", "0"), ("usable", "revoked", "0"),
])
def test_unavailable_never_resolves_active_state_or_replaces_good_evidence(quality, rights, value):
    first = step("20")
    missing = step(value, 1, first.state, quality=quality, rights=rights)
    assert missing.disposition == "unavailable" and not missing.state.available
    assert missing.state.active and missing.state.last_good == first.current
    assert missing.transition_id is None
    recovered = step("0", 2, missing.state)
    assert recovered.disposition == "recovered" and recovered.state.active is False
    assert recovered.transition_id is None and recovered.previous == first.current
    assert step("20", 3, recovered.state).disposition == "triggered"


def test_initial_missing_then_first_good_has_no_zero_baseline():
    first = step(None, quality="missing")
    assert first.state.active is None and first.state.last_good is None
    current = step("20", 1, first.state)
    assert current.disposition == "baseline" and current.previous is None and current.transition_id is None


def test_freshness_boundary_rechecks_duplicate_and_recovery_does_not_flood():
    first = step("0")
    expired = evaluate_threshold(binding(), first.current, as_of=NOW + timedelta(hours=3), prior=first.state)
    assert expired.disposition == "unavailable" and expired.state.last_good == first.current
    assert expired.state.active is False
    assert step("20", 4, expired.state).disposition == "recovered"
    # No missing poll is needed to recognize an expired prior state.
    assert step("20", 4, first.state).disposition == "recovered"


def test_replay_and_serialized_restart_preserve_identity_without_second_transition():
    baseline = step("0").state
    crossed = step("10", 1, baseline)
    restarted = ThresholdState.model_validate_json(crossed.state.model_dump_json())
    replay = step("10.000", 1, restarted)
    assert replay.disposition == "duplicate" and replay.transition_id is None and replay.state.active
    retried = step("10.000", 1, ThresholdState.model_validate_json(baseline.model_dump_json()))
    assert retried.transition_id == crossed.transition_id
    alternate = binding(rule={"period": SERIES.period,
                             "threshold": {"trigger_at_or_above": "10.0", "reset_at_or_below": "5.00"}})
    assert evaluate_threshold(alternate, crossed.current, as_of=crossed.current.fetched_at,
                              prior=baseline).transition_id == crossed.transition_id


def test_refetch_same_source_revision_can_refresh_transport_metadata_without_alert():
    initial = step("0")
    refreshed = sample("0", fetched_at=NOW + timedelta(minutes=10))
    result = evaluate_threshold(binding(), refreshed, as_of=refreshed.fetched_at, prior=initial.state)
    assert result.disposition == "duplicate" and result.transition_id is None
    assert result.state.latest.fetched_at == refreshed.fetched_at
    older_receipt = evaluate_threshold(binding(), initial.current, as_of=refreshed.fetched_at, prior=result.state)
    assert older_receipt.disposition == "history_required" and older_receipt.state == result.state


def test_successful_refetch_of_old_measurement_does_not_make_it_fresh():
    first = step("20")
    fetched_late = sample("20", fetched_at=NOW + timedelta(hours=5))
    expired = evaluate_threshold(binding(), fetched_late, as_of=fetched_late.fetched_at, prior=first.state)
    assert expired.disposition == "unavailable" and expired.state.active
    assert expired.state.last_good == first.current and expired.transition_id is None
    with pytest.raises(ValueError, match="Freshness deadline"):
        evaluate_threshold(binding(), sample("20", fetched_at=fetched_late.fetched_at,
                           fresh_until=NOW + timedelta(hours=8)), as_of=fetched_late.fetched_at, prior=first.state)


def test_latest_correction_rebaselines_and_older_input_requires_history_handling():
    first = step("0")
    corrected = step("20", prior=first.state, source_revision=2, artifact_hashes=("b" * 64,))
    assert corrected.disposition == "revised" and corrected.state.active and corrected.transition_id is None
    assert corrected.previous == first.current
    older_revision = evaluate_threshold(binding(), first.current, as_of=NOW, prior=corrected.state)
    assert older_revision.disposition == "history_required" and older_revision.state == corrected.state
    newer = step("20", 1, corrected.state)
    historical = evaluate_threshold(binding(), corrected.current, as_of=NOW + timedelta(hours=1), prior=newer.state)
    assert historical.disposition == "history_required" and historical.state == newer.state


def test_conflicting_same_revision_bytes_fail_without_losing_decimal_precision():
    first = step("1.000000000000000000000000000001")
    with pytest.raises(ValueError, match="Conflicting content"):
        step("1.000000000000000000000000000002", prior=first.state)
    with pytest.raises(ValueError, match="Conflicting content"):
        step(str(first.current.value), prior=first.state, artifact_hashes=("b" * 64,))


def test_policy_change_cannot_manufacture_a_pollen_crossing():
    initial = step("0")
    changed = step("20", 1, initial.state, policy_version="synthetic-policy-v2")
    assert changed.disposition == "policy_rebaseline" and changed.state.active and changed.transition_id is None


@pytest.mark.parametrize("field,value", [("organization_id", "org-b"), ("owner_id", "owner-b"),
                                         ("subject_id", "subject-b"), ("configuration_revision", 2)])
def test_prior_state_cannot_cross_private_binding_or_rule_revision(field, value):
    prior = step("0").state
    with pytest.raises(ValueError, match="binding must match"):
        evaluate_threshold(binding(**{field: value}), sample("20", 1), as_of=NOW + timedelta(hours=1), prior=prior)


def test_forecast_identity_and_observation_series_are_never_interchangeable():
    forecast = PollenSeries(source_id="synthetic-forecast", method_version="density-v1", station_id="PBS",
        allergen="ragweed", period="forecast_instant", forecast={"model": "icon", "grid": "grid-a",
            "member": "control", "layer": "80", "cell": 42, "issue_at": NOW})
    forecast_binding = binding(forecast)
    current = sample("1", series=forecast, valid_at=NOW + timedelta(hours=6))
    first = evaluate_threshold(forecast_binding, current, as_of=NOW)
    assert first.disposition == "baseline"
    with pytest.raises(ValueError, match="binding must match"):
        evaluate_threshold(binding(), current, as_of=NOW)
    for key, value in [("member", "perturbed-1"), ("grid", "grid-b"), ("cell", 43),
                       ("issue_at", NOW + timedelta(hours=1))]:
        changed = forecast.model_dump()
        changed["forecast"][key] = value
        changed_series = PollenSeries.model_validate(changed)
        with pytest.raises(ValueError, match="binding must match"):
            evaluate_threshold(binding(changed_series), current, as_of=NOW, prior=first.state)


@pytest.mark.parametrize("changes", [
    {"value": "NaN"}, {"value": "Infinity"}, {"value": "-0.1"}, {"value": None},
    {"value": 0.1}, {"value": True},
    {"valid_at": NOW.replace(tzinfo=None)}, {"valid_at": NOW + timedelta(seconds=1)},
    {"fresh_until": NOW - timedelta(seconds=1)}, {"artifact_hashes": ()},
    {"source_revision": True}, {"artifact_hashes": ("invalid",)},
])
def test_invalid_samples_are_rejected(changes):
    with pytest.raises(ValidationError):
        sample(**{"value": "0", **changes})


def test_unknown_rules_and_mixed_units_or_periods_fail_closed():
    for changes in [{"rapid_increase": {"minimum_increase": "1", "window_hours": 1}},
                    {"category_change": True}, {"unit": "kg-1"}, {"period": "forecast_instant"}]:
        with pytest.raises(ValidationError):
            binding(rule={**binding().rule.model_dump(), **changes})
    with pytest.raises(ValidationError):
        PollenSeries.model_validate({**SERIES.model_dump(), "period": "forecast_instant"})


@pytest.mark.parametrize("field,value", [("station_id", "BER"), ("source_id", "another-source"),
    ("method_version", "manual-v1"), ("allergen", "birch"), ("period", "observation_daily_00_24_utc")])
def test_noncomparable_observation_series_cannot_share_prior_state(field, value):
    changed = PollenSeries.model_validate({**SERIES.model_dump(), field: value})
    with pytest.raises(ValueError, match="binding must match"):
        evaluate_threshold(binding(changed), sample("20", 1, series=changed),
                           as_of=NOW + timedelta(hours=1), prior=step("0").state)


def test_clock_cannot_move_backwards_or_admit_a_future_fetch():
    first = step("0")
    for clock in [NOW.replace(tzinfo=None), NOW - timedelta(seconds=1)]:
        with pytest.raises(ValueError):
            evaluate_threshold(binding(), first.current, as_of=clock, prior=first.state)
