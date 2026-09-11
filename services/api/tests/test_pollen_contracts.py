"""Configuration boundaries, not source availability or live delivery acceptance."""

from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from helvetic_lens.pollen_contracts import PollenConfiguration


def configuration():
    return {"station_id": "PBS", "selections": [
        {"allergen": "birch", "rules": [{"period": "observation_hourly", "threshold": {
            "trigger_at_or_above": "20.125", "reset_at_or_below": "15.125",
        }}]},
        {"allergen": "grasses", "rules": [{"period": "forecast_instant", "rapid_increase": {
            "minimum_increase": "10.5", "window_hours": 3,
        }}]},
    ]}


def test_configuration_json_roundtrip_preserves_decimal_and_no_email_default():
    config = PollenConfiguration.model_validate(configuration())
    assert config.selections[0].rules[0].threshold.trigger_at_or_above == Decimal("20.125")
    assert config.delivery.email == "off"
    assert PollenConfiguration.model_validate_json(config.model_dump_json()) == config
    with pytest.raises(ValidationError):
        config.station_id = "PZH"


@pytest.mark.parametrize("key,value", [
    ("contract_version", 2), ("contract_version", True), ("template_version", "1"),
    ("station_id", "home address"), ("station_id", "PBS\n"),
    ("workspace_id", "foreign-workspace"), ("source_ready", True),
    ("timezone", "../Europe/Zurich"), ("timezone", "Not/AZone"),
])
def test_rejects_unknown_versions_private_authority_fields_and_invalid_location(key, value):
    data = configuration()
    data[key] = value
    with pytest.raises(ValidationError):
        PollenConfiguration.model_validate(data)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "0.0000001"])
def test_rejects_invalid_threshold(value):
    data = configuration()
    data["selections"][0]["rules"][0]["threshold"]["trigger_at_or_above"] = value
    with pytest.raises(ValidationError):
        PollenConfiguration.model_validate(data)


def test_rejects_reset_equal_to_trigger_and_duplicate_selections_or_periods():
    data = configuration()
    data["selections"][0]["rules"][0]["threshold"]["reset_at_or_below"] = "20.125"
    with pytest.raises(ValidationError):
        PollenConfiguration.model_validate(data)
    data = configuration()
    data["selections"].append(deepcopy(data["selections"][0]))
    with pytest.raises(ValidationError):
        PollenConfiguration.model_validate(data)
    data = configuration()
    data["selections"][0]["rules"] *= 2
    with pytest.raises(ValidationError):
        PollenConfiguration.model_validate(data)


@pytest.mark.parametrize("period", ["observation_daily_00_24_utc", "observation_daily_06_06_utc"])
def test_hourly_increase_does_not_apply_to_daily_averages(period):
    data = configuration()
    data["selections"][1]["rules"][0]["period"] = period
    with pytest.raises(ValidationError):
        PollenConfiguration.model_validate(data)


@pytest.mark.parametrize("delivery", [
    {"email": "daily_digest"}, {"email": "off", "digest_at": "09:00"},
    {"email": "daily_digest", "digest_at": "24:00"},
    {"quiet_hours": {"start": "22:00", "end": "22:00"}},
])
def test_rejects_ambiguous_delivery_schedule(delivery):
    with pytest.raises(ValidationError):
        PollenConfiguration.model_validate({**configuration(), "delivery": delivery})


def test_overnight_quiet_hours_and_explicit_digest_are_preserved():
    data = {**configuration(), "delivery": {"email": "daily_digest", "digest_at": "09:30",
            "quiet_hours": {"start": "22:00", "end": "07:00"}}}
    config = PollenConfiguration.model_validate(data)
    assert config.delivery.quiet_hours.end == "07:00"
    assert config.delivery.digest_at == "09:30"


def test_current_state_only_draft_does_not_require_an_alert_rule():
    config = PollenConfiguration(station_id="PBS", selections=[{"allergen": "birch"}])
    assert config.selections[0].rules == ()


def test_threshold_can_reset_at_zero():
    data = configuration()
    data["selections"][0]["rules"][0]["threshold"]["reset_at_or_below"] = "0"
    config = PollenConfiguration.model_validate(data)
    assert config.selections[0].rules[0].threshold.reset_at_or_below == Decimal("0")
