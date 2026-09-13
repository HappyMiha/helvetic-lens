from dataclasses import replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_road_feed import NOW, feed, first, record
from test_road_topology import flow, location, topology

from helvetic_lens.road_evaluation import RoadMateriality, evaluate_record, temporal_state
from helvetic_lens.road_feed import RoadPeriod
from helvetic_lens.road_topology import RoadIntersection


def evaluate(item=None, *, now=NOW, match=None, preferences=None):
    return evaluate_record(item or first(), match or RoadIntersection("match", "synthetic-reviewed"),
                           preferences or RoadMateriality(), now=now)


def period(a, b):
    return RoadPeriod(None if a is None else NOW + timedelta(hours=a), None if b is None else NOW + timedelta(hours=b))


def scheduled(*, start=-2, end=5, periods=(), exceptions=(), **changes):
    item = first()
    return replace(item, validity=replace(item.validity, overall=period(start, end),
        periods=tuple(period(*p) for p in periods), exceptions=tuple(period(*p) for p in exceptions), **changes))


@pytest.mark.parametrize("kind", ["road_closure", "carriageway_closure", "lane_restriction", "accident", "roadworks"])
def test_missing_delay_does_not_suppress_explicit_noncongestion_events(kind):
    item = replace(first(), kind=kind, delay_seconds=None)
    assert evaluate(item).state == "eligible"


@pytest.mark.parametrize("delay,state", [(None, "unknown"), (899.5, "filtered"), (900, "eligible"), (1500, "eligible"), (0, "filtered")])
def test_fifteen_minute_threshold_is_only_applied_to_known_numeric_delay(delay, state):
    item = first(feed(record(source_type="AbnormalTraffic", code="queuingTraffic", delay=delay)))
    assert evaluate(item).state == state


def test_zero_threshold_still_does_not_turn_unknown_delay_into_zero():
    prefs = RoadMateriality(minimum_delay_seconds=0)
    item = replace(first(), kind="congestion", delay_seconds=None)
    assert evaluate(item, preferences=prefs).state == "unknown"
    assert evaluate(replace(item, delay_seconds=0), preferences=prefs).state == "eligible"


def test_opposite_and_unrelated_corridor_records_are_filtered_with_real_matching():
    graph = topology()
    item = replace(first(), location=location())
    assert evaluate(item, match=graph.intersection(item.location, flow(graph))).state == "eligible"
    assert evaluate(item, match=graph.intersection(item.location, flow(graph, (10, 70, 20, 90)))).state == "filtered"
    other = replace(item, location=location(primary=800, secondary=700))
    assert evaluate(other, match=graph.intersection(other.location, flow(graph))).state == "filtered"
    unknown = replace(item, location=replace(item.location, version="unreviewed"))
    assert evaluate(unknown, match=graph.intersection(unknown.location, flow(graph))).state == "unknown"


def test_planned_closure_reschedule_changes_exact_upcoming_window():
    initial = scheduled(start=2, end=8)
    shifted = scheduled(start=26, end=32)
    before, after = evaluate(initial), evaluate(shifted)
    assert before.state == after.state == "eligible"
    assert before.temporal.phase == after.temporal.phase == "planned"
    assert before.temporal.window == period(2, 8) and after.temporal.window == period(26, 32)
    assert initial.semantic_hash != shifted.semantic_hash
    assert evaluate(initial, preferences=RoadMateriality(include_planned=False)).state == "filtered"


def test_disjoint_night_windows_and_exception_overrides_at_exact_boundaries():
    item = scheduled(start=-4, end=10, periods=((-3, -1), (1, 5), (6, 9)), exceptions=((2, 3), (7, 8)))
    assert temporal_state(item, now=NOW).window == period(1, 2)
    assert temporal_state(item, now=NOW).phase == "planned"
    assert temporal_state(item, now=NOW + timedelta(hours=1)).phase == "active"
    blocked = temporal_state(item, now=NOW + timedelta(hours=2))
    assert blocked.phase == "planned" and blocked.window == period(3, 5)
    assert temporal_state(item, now=NOW + timedelta(hours=3)).phase == "active"
    assert temporal_state(item, now=NOW + timedelta(hours=9)).phase == "expired"


def test_periods_are_clipped_to_overall_bounds_and_overlaps_merged():
    item = scheduled(start=-2, end=4, periods=((-5, 1), (0, 3), (2, 10)), exceptions=((-8, -3), (1, 2)))
    assert temporal_state(item, now=NOW).window == period(-2, 1)
    assert temporal_state(item, now=NOW + timedelta(hours=1)).window == period(2, 4)
    assert temporal_state(item, now=NOW + timedelta(hours=4)).phase == "expired"


def test_open_ended_intervals_and_complete_exception_are_explicit():
    item = scheduled(start=-2, end=None)
    assert temporal_state(item, now=NOW).window == period(-2, None)
    excluded = scheduled(start=-2, end=None, exceptions=((None, None),))
    assert temporal_state(excluded, now=NOW).phase == "inactive"
    future = scheduled(start=-2, end=None, exceptions=((None, 1),))
    assert temporal_state(future, now=NOW).window == period(1, None)


def test_active_and_suspended_explicitly_override_the_schedule():
    assert temporal_state(scheduled(start=20, end=30, status="active"), now=NOW).phase == "active"
    assert temporal_state(scheduled(start=-20, end=-10, status="active"), now=NOW).phase == "active"
    assert temporal_state(scheduled(status="suspended"), now=NOW).phase == "suspended"
    assert temporal_state(scheduled(start=-20, end=-10, overrunning=True), now=NOW).reason == "source_overrunning"
    assert temporal_state(scheduled(status="suspended", overrunning=True), now=NOW).phase == "unknown"


@pytest.mark.parametrize("change,phase", [({"cancelled": True}, "withdrawn"), ({"ended": True}, "ended")])
def test_explicit_end_and_withdrawal_need_previous_context_and_never_claim_open(change, phase):
    decision = evaluate(replace(first(), **change))
    assert decision.state == "transition" and decision.temporal.phase == phase
    assert decision.reason == "requires_previous_event_context"


def test_validity_expiry_and_clearance_are_transitions_not_new_all_clear_alerts():
    assert evaluate(scheduled(start=-3, end=-1)).state == "transition"
    assert evaluate(first(feed(record(code="roadCleared")))).state == "transition"


@pytest.mark.parametrize("unsupported", ["validity", "recurring_period", "validity_period", "record_fields", "location_direction"])
def test_unsupported_capabilities_cannot_produce_an_eligible_alert(unsupported):
    assert evaluate(replace(first(), unsupported=(unsupported,))).state == "unknown"


def test_event_filter_and_invalid_preferences():
    assert evaluate(preferences=RoadMateriality(event_kinds=("congestion",))).state == "filtered"
    for values in ({"event_kinds": ()}, {"event_kinds": ("road_closure", "road_closure")},
                   {"minimum_delay_seconds": -1}, {"minimum_delay_seconds": True}):
        with pytest.raises(ValidationError):
            RoadMateriality(**values)
    with pytest.raises(ValueError, match="aware"):
        evaluate(now=NOW.replace(tzinfo=None))


def test_restricted_record_does_not_disclose_its_schedule_in_a_decision():
    decision = evaluate(replace(first(), confidentiality="restrictedToAuthorities"))
    assert decision.state == "unknown" and decision.temporal.window is None
    assert decision.temporal.phase == "unknown"


def test_explicit_active_override_ignores_unused_recurring_schedule_only():
    item = replace(scheduled(status="active"), unsupported=("recurring_period",))
    assert evaluate(item).state == "eligible"
    assert evaluate(replace(item, unsupported=("validity",))).state == "unknown"


def test_source_probability_is_not_promoted_to_confirmed_impact():
    assert evaluate(replace(first(), probability="riskOf")).reason == "potential_material_road_event"
    assert evaluate(replace(first(), probability="probable")).reason == "potential_material_road_event"
    assert evaluate(replace(first(), probability="futureCode")).state == "unknown"
