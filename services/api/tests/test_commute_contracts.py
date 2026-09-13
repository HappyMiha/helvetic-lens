from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from helvetic_lens.commute_contracts import (
    Affected,
    CommuteCheckpoint,
    CommuteConfiguration,
    TransportObservation,
    evaluate_commute,
    evaluate_journey,
)
from helvetic_lens.transport_reference import VerifiedLeg
from helvetic_lens.transport_static import ResolvedLeg

DAY = date(2026, 9, 14)
NOW = datetime(2026, 9, 14, 5, 30, tzinfo=UTC)
REFERENCE, MONITOR = uuid4(), uuid4()


def configuration(**changes):
    return CommuteConfiguration(name="Basel commute", leg_reference_ids=(REFERENCE,), weekdays=(0, 1, 2, 3, 4),
                                window_start="07:00", window_end="09:00", delay_threshold_minutes=10,
                                delay_reset_minutes=8, **changes)


def leg(**changes):
    return ResolvedLeg(**{"reference": VerifiedLeg("20260909", "agency", "route", "trip", DAY, 0,
                                                   ("board", "middle", "alight"), ("station",)),
                          "archive_sha256": "a" * 64, "departure": NOW + timedelta(minutes=30),
                          "arrival": NOW + timedelta(minutes=50), "boarding_name": "Basel origin",
                          "alighting_name": "Basel destination", "route_name": "Fixture route", **changes})


def event(step=0, *, kind="delay", seconds=0, selectors=None, **changes):
    return TransportObservation(**{
        "source": "swiss_gtfs_trip_updates", "entity_id": "trip-event", "revision_sha256": f"{step:064x}",
        "observed_at": NOW + timedelta(seconds=step), "feed_version": "20260909", "kind": kind,
        "delay_seconds": seconds if kind == "delay" else None,
        "valid_from": NOW - timedelta(minutes=30), "valid_until": NOW + timedelta(minutes=90),
        "selectors": selectors or (Affected(trip_id="trip", service_day=DAY, stop_id="board"),), **changes})


def evaluate(observation, previous=None, *, config=None, resolved=None, now=None, **changes):
    return evaluate_commute(config or configuration(), REFERENCE, resolved or leg(), observation,
                             monitor_id=MONITOR, now=now or observation.observed_at,
                             max_age_seconds=180, previous=previous, **changes)


def test_minor_updates_threshold_hysteresis_improvement_and_explicit_restoration_share_history():
    state = None
    deliveries, conditions = [], []
    for step, seconds in enumerate((0, 60, 120, 180, 240, 599, 600, 660, 540, 480, 300, 0, 0)):
        result = evaluate(event(step, seconds=seconds), state)
        state = result["checkpoint"]
        deliveries.append(result["delivery"])
        conditions.append(state.condition)
    assert [i for i, delivery in enumerate(deliveries) if delivery == "immediate"] == [6, 9, 11]
    assert conditions[8] == "delay_material" and conditions[9] == "delay_minor"
    assert conditions[-2:] == ["restored", "restored"]
    assert not state.episode_active
    assert CommuteCheckpoint.model_validate_json(state.model_dump_json()) == state


def test_cancellation_missing_expiry_staleness_and_recovery_never_invent_restoration():
    cancelled = evaluate(event(kind="cancelled"))
    assert cancelled["delivery"] == "immediate" and cancelled["priority"] == "urgent"
    missing = evaluate(event(1, kind=None, availability="missing"), cancelled["checkpoint"])
    assert missing["checkpoint"].condition == "cancelled" and missing["transition"] == "unavailable"
    assert missing["delivery"] == "none"
    fresh = evaluate(event(2, kind="cancelled"), missing["checkpoint"])
    assert fresh["delivery"] == "none"  # Source recovery must not repeat the same cancellation.
    expired = evaluate(event(3, kind=None, availability="expired"), fresh["checkpoint"])
    assert expired["checkpoint"].condition == "cancelled" and expired["delivery"] == "none"
    stale = evaluate(event(4, kind="cancelled"), expired["checkpoint"], now=NOW + timedelta(minutes=4))
    assert stale["checkpoint"].availability == "stale" and stale["delivery"] == "none"
    restored = evaluate(event(300, seconds=0), stale["checkpoint"])
    assert restored["transition"] == "restored" and restored["delivery"] == "immediate"


@pytest.mark.parametrize("selector", [
    Affected(trip_id="other", service_day=DAY, stop_id="board"),
    Affected(trip_id="trip", service_day=DAY + timedelta(days=1), stop_id="board"),
    Affected(trip_id="trip", service_day=DAY, direction_id=1, stop_id="board"),
    Affected(trip_id="trip", service_day=DAY, route_id="elsewhere", stop_id="board"),
    Affected(trip_id="trip", service_day=DAY, stop_id="middle"),
    Affected(trip_id="trip", service_day=DAY, stop_id="station"),
])
def test_delay_needs_the_exact_boarding_trip_date_direction_and_stop(selector):
    result = evaluate(event(seconds=900, selectors=(selector,)))
    assert result["delivery"] == "none" and result["reason"] == "no_journey_intersection"


def test_skipped_intermediate_stop_is_not_a_cancelled_selected_boarding_or_alighting():
    irrelevant = evaluate(event(kind="skipped_stop", selectors=(Affected(trip_id="trip", service_day=DAY, stop_id="middle"),)))
    assert irrelevant["delivery"] == "none"
    relevant = evaluate(event(kind="skipped_stop", selectors=(Affected(trip_id="trip", service_day=DAY, stop_id="alight"),)))
    assert relevant["delivery"] == "immediate" and relevant["checkpoint"].condition == "partial_disruption"


def test_event_outside_actual_journey_but_inside_broad_commute_window_is_irrelevant():
    result = evaluate(event(kind="cancelled", valid_until=NOW + timedelta(minutes=10)))
    assert result["reason"] == "no_journey_intersection" and result["delivery"] == "none"


@pytest.mark.parametrize("feed_version", [None, "20260916"])
def test_unknown_or_different_static_version_never_matches_by_station_name(feed_version):
    result = evaluate(event(kind="cancelled", feed_version=feed_version))
    assert result["checkpoint"].availability == "unmapped" and result["delivery"] == "none"


def test_outside_window_digest_is_opt_in_and_first_window_entry_emits_only_once():
    before = NOW - timedelta(minutes=31)
    observation = event(kind="cancelled", observed_at=before)
    ignored = evaluate(observation)
    assert ignored["delivery"] == "none"
    opted = evaluate(observation, config=configuration(outside_window="digest"))
    assert opted["delivery"] == "digest_candidate"
    inside = event(0, kind="cancelled", observed_at=before + timedelta(minutes=2))
    initial = evaluate(inside, ignored["checkpoint"])
    assert initial["delivery"] == "immediate"
    replay = evaluate(inside, initial["checkpoint"])
    assert replay["delivery"] == "none"


def test_pause_today_mute_and_notification_choices_do_not_rewrite_source_state():
    observation = event(kind="cancelled")
    for options in ({"paused_on": DAY}, {"muted": True}, {"config": configuration(cancellations=False)}):
        result = evaluate(observation, **options)
        assert result["checkpoint"].condition == "cancelled" and result["delivery"] == "none"
    paused = evaluate(observation, paused_on=DAY)
    resumed = evaluate(event(1, kind="cancelled"), paused["checkpoint"])
    assert resumed["delivery"] == "immediate"


def test_older_future_conflicting_and_foreign_private_checkpoints_cannot_rewind_state():
    current = evaluate(event(2, kind="cancelled"))
    state = current["checkpoint"]
    assert evaluate(event(1), state)["checkpoint"] == state
    assert evaluate(event(5), state, now=NOW)["reason"] == "future_observation"
    with pytest.raises(ValueError, match="Conflicting"):
        evaluate(event(2, seconds=0), state)
    with pytest.raises(ValueError, match="another private"):
        evaluate(event(3), state, config=configuration(cancellations=False))


def test_swiss_service_alerts_are_not_interpreted_as_cancellations_or_restoration():
    with pytest.raises(ValidationError, match="structured"):
        event(kind="cancelled", source="swiss_gtfs_service_alerts")
    notice = event(kind="notice", source="swiss_gtfs_service_alerts", selectors=(Affected(route_id="route"),))
    result = evaluate(notice)
    assert result["checkpoint"].condition == "notice" and result["priority"] == "normal"


@pytest.mark.parametrize("changes", [
    {"name": " "}, {"weekdays": [True]}, {"weekdays": [7]}, {"weekdays": [0, 0]},
    {"window_start": "25:00"}, {"window_end": "07:00"}, {"delay_threshold_minutes": True},
    {"delay_reset_minutes": 10}, {"outside_window": "send_anytime"},
])
def test_invalid_commute_settings_are_rejected(changes):
    value = configuration().model_dump(mode="json")
    value.update(changes)
    with pytest.raises(ValidationError):
        CommuteConfiguration.model_validate(value)


def test_multileg_journey_emits_one_candidate_and_keeps_its_development_on_restoration():
    second = uuid4()
    values = configuration().model_dump(mode="json")
    values["leg_reference_ids"].append(str(second))
    config = CommuteConfiguration.model_validate(values)
    references = {REFERENCE: leg(), second: leg()}
    observed = event(kind="cancelled")
    result = evaluate_journey(config, references, observed, monitor_id=MONITOR, now=NOW, max_age_seconds=180)
    assert result["delivery"] == "immediate" and result["priority"] == "urgent"
    assert len(result["contributions"]) == 2
    states = {identifier: result["contributions"][str(identifier)]["checkpoint"] for identifier in references}
    replay = evaluate_journey(config, references, observed, monitor_id=MONITOR, now=NOW,
                               max_age_seconds=180, previous=states)
    assert replay["delivery"] == "none"
    restored = evaluate_journey(config, references, event(1), monitor_id=MONITOR,
                                 now=NOW + timedelta(seconds=1), max_age_seconds=180, previous=states)
    assert restored["delivery"] == "immediate" and restored["development_id"] == result["development_id"]
    with pytest.raises(ValueError, match="exactly"):
        evaluate_journey(config, {REFERENCE: leg()}, observed, monitor_id=MONITOR, now=NOW, max_age_seconds=180)


def test_overnight_window_uses_start_weekday_and_spring_gap_stays_unavailable():
    values = configuration().model_dump(mode="json")
    values.update(window_start="23:00", window_end="02:00", weekdays=[0])
    config = CommuteConfiguration.model_validate(values)
    overnight = datetime(2026, 9, 14, 23, tzinfo=UTC)  # Tuesday 01:00 Zurich, Monday-start window.
    resolved = leg(departure=overnight, arrival=overnight + timedelta(minutes=20))
    observation = event(kind="cancelled", observed_at=overnight - timedelta(minutes=10),
                        valid_from=overnight - timedelta(hours=1), valid_until=overnight + timedelta(hours=1))
    result = evaluate(observation, config=config, resolved=resolved)
    assert result["delivery"] == "immediate"
    values.update(window_start="02:30", window_end="04:00", weekdays=[6])
    spring = datetime(2026, 3, 29, 1, 15, tzinfo=UTC)
    resolved = leg(reference=replace(leg().reference, service_day=spring.date()),
                   departure=spring, arrival=spring + timedelta(minutes=20))
    observation = event(kind="cancelled", observed_at=spring, valid_from=spring - timedelta(hours=1),
                        valid_until=spring + timedelta(hours=1),
                        selectors=(Affected(trip_id="trip", service_day=spring.date()),))
    result = evaluate(observation, config=CommuteConfiguration.model_validate(values), resolved=resolved)
    assert result["checkpoint"].availability == "invalid_window" and result["delivery"] == "none"


def test_resolved_leg_cannot_claim_departures_from_a_different_service_date():
    with pytest.raises(ValueError, match="service-day offsets"):
        evaluate(event(), resolved=leg(departure=NOW - timedelta(days=10), arrival=NOW - timedelta(days=9)))


def test_normalized_swiss_feed_profiles_do_not_invent_selector_shapes():
    with pytest.raises(ValidationError, match="multiple service-day"):
        event(selectors=(Affected(trip_id="trip", service_day=DAY, stop_id="board"),
                         Affected(trip_id="other", service_day=DAY, stop_id="board")))
    with pytest.raises(ValidationError, match="Trip selectors"):
        event(kind="notice", source="swiss_gtfs_service_alerts")
