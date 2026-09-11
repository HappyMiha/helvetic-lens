"""Synthetic exact-window comparisons; no source admission or notification."""

from datetime import timedelta
from decimal import Decimal, Inexact, localcontext

import pytest
from pydantic import ValidationError
from test_pollen_thresholds import NOW, SERIES, sample

from helvetic_lens.pollen_rapid import RapidBinding, RapidComparison, compare_rapid_increase
from helvetic_lens.pollen_thresholds import PollenSample, PollenSeries


def binding(series=SERIES, **overrides):
    return RapidBinding.model_validate({"organization_id": "org-a", "owner_id": "owner-a",
        "subject_id": "subject-a", "configuration_revision": 1, "series": series,
        "rule": {"period": series.period, "rapid_increase": {"minimum_increase": "5", "window_hours": 2}},
        **overrides})


def compare(base, current, **kwargs):
    return compare_rapid_increase(binding(), base, current, as_of=current.fetched_at, **kwargs)


@pytest.mark.parametrize("previous,current,delta,matched", [
    ("0", "5", "5", True), ("10", "14.999999", "4.999999", False),
    ("10", "15", "5", True), ("10", "15.000001", "5.000001", True),
    ("10", "10", "0", False), ("10", "4", "-6", False),
])
def test_absolute_increase_inclusive_boundary_zero_and_falling_values(previous, current, delta, matched):
    baseline, latest = sample(previous), sample(current, 2)
    result = compare(baseline, latest)
    assert result.delta == Decimal(delta) and result.matches is matched
    assert result.reason == ("matched" if matched else "below_minimum")
    assert result.baseline == baseline and result.current == latest and result.binding == binding()
    assert result.evaluated_at == latest.fetched_at
    assert result.comparison_id is not None
    assert not hasattr(result, "transition_id")  # Calculation identity is not an alert episode.


@pytest.mark.parametrize("offset", [-3600, -0.000001, 0.000001, 3600])
def test_nearest_but_unequal_window_is_not_used(offset):
    stamp = NOW + timedelta(hours=2, seconds=offset)
    result = compare(sample("0"), sample("20", 2, valid_at=stamp, fetched_at=stamp))
    assert result.reason == "window_mismatch"
    assert result.delta is result.matches is result.comparison_id is None


@pytest.mark.parametrize("hours", [1, 24])
def test_minimum_and_maximum_windows_accept_exact_historical_endpoint(hours):
    rule_binding = binding(rule={"period": SERIES.period,
        "rapid_increase": {"minimum_increase": "5", "window_hours": hours}})
    current = sample("5", hours)
    result = compare_rapid_increase(rule_binding, sample("0"), current, as_of=current.fetched_at)
    assert result.matches and result.delta == 5


def test_expired_live_deadline_does_not_invalidate_approved_historical_baseline():
    baseline = sample("0", fresh_until=NOW + timedelta(minutes=20))
    result = compare(baseline, sample("5", 2))
    assert result.matches and result.baseline.fresh_until < result.current.fetched_at


@pytest.mark.parametrize("side,changes,reason", [
    ("baseline", {"value": None, "quality": "missing"}, "baseline_unavailable"),
    ("baseline", {"quality": "stale"}, "baseline_unavailable"),
    ("baseline", {"rights": "revoked"}, "baseline_rights"),
    ("baseline", {"rights": "unverified"}, "baseline_rights"),
    ("current", {"value": None, "quality": "unavailable"}, "current_unavailable"),
    ("current", {"quality": "stale"}, "current_unavailable"),
    ("current", {"rights": "revoked"}, "current_rights"),
    ("current", {"rights": "unverified"}, "current_rights"),
    ("current", {"policy_version": "policy-v2"}, "policy_mismatch"),
    ("current", {"parser_version": "parser-v2"}, "parser_mismatch"),
])
def test_ineligible_inputs_do_not_become_zero_or_matches(side, changes, reason):
    baseline = sample(**{"value": "0", **(changes if side == "baseline" else {})})
    current = sample(**{"value": "5", "hour": 2, **(changes if side == "current" else {})})
    result = compare(baseline, current)
    assert result.reason == reason and result.delta is result.matches is result.comparison_id is None


def test_missing_baseline_and_expired_current_are_distinct_unavailable_reasons():
    current = sample("5", 2)
    missing = compare(None, current)
    assert missing.reason == "baseline_missing" and missing.matches is None
    expired = compare_rapid_increase(binding(), sample("0"), current, as_of=current.fresh_until)
    assert expired.reason == "current_expired" and expired.matches is None


def test_subtraction_and_identity_are_exact_under_low_ambient_precision_and_traps():
    baseline = sample("10.000000000000000000000000000000000001")
    current = sample("15", 2)
    normal = compare(baseline, current)
    with localcontext() as context:
        context.prec = 6
        context.traps[Inexact] = True
        actual = compare(baseline, current)
    assert actual == normal and actual.matches is False
    assert actual.delta == Decimal("4.999999999999999999999999999999999999")


def test_serialized_retry_and_decimal_spelling_keep_comparison_identity():
    baseline, current = sample("0"), sample("5", 2)
    first = compare(baseline, current)
    restored_binding = RapidBinding.model_validate_json(binding().model_dump_json())
    restored_baseline = PollenSample.model_validate_json(baseline.model_dump_json())
    retry = compare_rapid_increase(restored_binding, restored_baseline, sample("5.000", 2), as_of=current.fetched_at)
    assert retry.comparison_id == first.comparison_id
    assert RapidComparison.model_validate_json(first.model_dump_json()) == first
    refetched = sample("5", 2, fetched_at=current.fetched_at + timedelta(minutes=1))
    assert compare(baseline, refetched).comparison_id == first.comparison_id
    alternate = binding(rule={"period": SERIES.period, "rapid_increase": {"minimum_increase": "5.00", "window_hours": 2}})
    assert compare_rapid_increase(alternate, baseline, current, as_of=current.fetched_at).comparison_id == first.comparison_id


@pytest.mark.parametrize("side", ["baseline", "current"])
def test_source_correction_changes_comparison_identity_with_complete_evidence(side):
    baseline, current = sample("0"), sample("5", 2)
    original = compare(baseline, current)
    if side == "baseline":
        baseline = sample("0", source_revision=2, artifact_hashes=("b" * 64,))
    else:
        current = sample("5", 2, source_revision=2, artifact_hashes=("b" * 64,))
    corrected = compare(baseline, current)
    assert corrected.matches and corrected.comparison_id != original.comparison_id
    assert getattr(corrected, side).source_revision == 2


@pytest.mark.parametrize("field,value", [("organization_id", "org-b"), ("owner_id", "owner-b"),
    ("subject_id", "subject-b"), ("configuration_revision", 2)])
def test_comparison_identity_is_private_binding_specific_not_an_access_grant(field, value):
    baseline, current = sample("0"), sample("5", 2)
    first = compare(baseline, current)
    changed = compare_rapid_increase(binding(**{field: value}), baseline, current, as_of=current.fetched_at)
    assert changed.comparison_id != first.comparison_id


@pytest.mark.parametrize("field,value", [("source_id", "source-b"), ("method_version", "manual-v1"),
    ("station_id", "BER"), ("allergen", "birch"), ("period", "observation_daily_00_24_utc")])
def test_noncomparable_source_baseline_is_rejected(field, value):
    changed = PollenSeries.model_validate({**SERIES.model_dump(), field: value})
    with pytest.raises(ValueError, match="exact bound source series"):
        compare(sample("0", series=changed), sample("20", 2))


def test_forecasts_compare_within_one_issue_member_and_grid_only():
    series = PollenSeries(source_id="synthetic-forecast", method_version="density-v1", station_id="PBS",
        allergen="ragweed", period="forecast_instant", forecast={"model": "icon", "grid": "grid-a",
            "member": "control", "layer": "80", "cell": 42, "issue_at": NOW})
    baseline = sample("0", series=series, valid_at=NOW + timedelta(hours=4))
    current = sample("5", series=series, valid_at=NOW + timedelta(hours=6))
    first = compare_rapid_increase(binding(series), baseline, current, as_of=NOW)
    assert first.matches and first.delta == 5
    for field, value in [("member", "perturbed"), ("grid", "grid-b"), ("layer", "79"),
                         ("cell", 43), ("issue_at", NOW - timedelta(hours=1))]:
        changed = series.model_dump()
        changed["forecast"][field] = value
        other = PollenSeries.model_validate(changed)
        with pytest.raises(ValueError, match="exact bound source series"):
            compare_rapid_increase(binding(series), sample("0", series=other), current, as_of=NOW)


@pytest.mark.parametrize("changes", [{"threshold": {"trigger_at_or_above": "10", "reset_at_or_below": "5"}},
    {"category_change": True}, {"period": "observation_daily_00_24_utc"}, {"unit": "kg-1"},
    {"rapid_increase": {"minimum_increase": "5", "window_hours": 0}},
    {"rapid_increase": {"minimum_increase": "5", "window_hours": 25}}])
def test_unsupported_or_combined_rules_fail_instead_of_partial_evaluation(changes):
    with pytest.raises(ValidationError):
        binding(rule={**binding().rule.model_dump(), **changes})


def test_naive_clock_and_future_retrieval_cannot_be_used():
    baseline, current = sample("0"), sample("5", 2)
    for clock in [current.fetched_at.replace(tzinfo=None), NOW]:
        with pytest.raises(ValueError):
            compare_rapid_increase(binding(), baseline, current, as_of=clock)
    with pytest.raises(ValueError):
        compare(sample("0", fetched_at=NOW + timedelta(hours=3)), current)
