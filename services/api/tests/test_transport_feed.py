from dataclasses import replace
from datetime import timedelta

import pytest
from google.transit import gtfs_realtime_pb2 as gtfs
from test_commute_contracts import NOW, evaluate, leg

from helvetic_lens.transport_feed import ALERTS, TRIPS, decode_feed, project_entity, snapshot_changes


def feed(*, second=0):
    result = gtfs.FeedMessage()
    result.header.gtfs_realtime_version = "2.0"
    result.header.incrementality = gtfs.FeedHeader.FULL_DATASET
    result.header.timestamp = int(NOW.timestamp()) + second
    result.header.feed_version = "20260909"
    return result


def trip_feed(*, delay=600, second=0, cancelled=False):
    result = feed(second=second)
    entity = result.entity.add(id="provider-entity")
    update = entity.trip_update
    update.trip.trip_id = "trip"
    update.trip.start_date = "20260914"
    update.trip.route_id = "route"
    update.trip.direction_id = 0
    if cancelled:
        update.trip.schedule_relationship = gtfs.TripDescriptor.CANCELED
    else:
        stop = update.stop_time_update.add(stop_sequence=10, stop_id="board")
        if delay is not None:
            stop.departure.delay = delay
    return result


def alert_feed(*, second=0):
    result = feed(second=second)
    alert = result.entity.add(id="notice").alert
    alert.informed_entity.add(route_id="route", direction_id=0)
    alert.header_text.translation.add(language="de", text="Unterbruch")
    alert.header_text.translation.add(language="fr", text="Interruption")
    alert.description_text.translation.add(language="en", text="Official source text <script>not HTML</script>")
    alert.effect = gtfs.Alert.UNKNOWN_EFFECT
    return result


def decode(message, source=TRIPS):
    return decode_feed(message.SerializeToString(), source=source, received_at=NOW + timedelta(hours=1))


def project(message, source=TRIPS, resolved=None):
    snapshot = decode(message, source)
    return project_entity(snapshot, snapshot.entities[0], resolved or replace(leg(), stop_sequences=(10, 20, 30)))


def test_binary_delay_cancellation_restoration_and_entity_rename_share_development():
    previous = None
    results, ids = [], []
    for i, (delay, cancelled) in enumerate(((60, False), (240, False), (600, False), (None, True), (0, False))):
        message = trip_feed(delay=delay, cancelled=cancelled, second=i)
        message.entity[0].id = f"changing-provider-id-{i}"
        projection = project(message)
        assert projection.observation is not None
        result = evaluate(projection.observation, previous)
        previous = result["checkpoint"]
        ids.append(previous.stream_id)
        results.append(result)
    assert len(set(ids)) == 1
    assert [r["delivery"] for r in results] == ["none", "none", "immediate", "immediate", "immediate"]
    assert results[-1]["checkpoint"].condition == "restored"


def test_absent_departure_does_not_become_zero_or_use_arrival_or_trip_delay():
    message = trip_feed(delay=None)
    message.entity[0].trip_update.delay = 0
    message.entity[0].trip_update.stop_time_update[0].arrival.delay = 0
    assert project(message).observation is None
    message.entity[0].trip_update.stop_time_update[0].departure.delay = 0
    assert project(message).observation.delay_seconds == 0


def test_absolute_departure_time_takes_precedence_over_conflicting_delay():
    message = trip_feed(delay=0)
    message.entity[0].trip_update.stop_time_update[0].departure.time = int(leg().departure.timestamp()) + 720
    assert project(message).observation.delay_seconds == 720


def test_real_measurement_timestamp_stays_stale_when_feed_is_new():
    message = trip_feed()
    message.entity[0].trip_update.timestamp = int(NOW.timestamp()) - 600
    observation = project(message).observation
    assert observation.observed_at == NOW - timedelta(minutes=10)
    result = evaluate(observation, now=NOW)
    assert result["checkpoint"].availability == "stale" and result["delivery"] == "none"
    message.header.timestamp += 60
    assert project(message).observation == observation


def test_skip_alighting_is_partial_but_skipped_intermediate_does_not_cancel():
    message = trip_feed(delay=0)
    update = message.entity[0].trip_update
    stop = update.stop_time_update.add(stop_sequence=20, stop_id="middle")
    stop.schedule_relationship = gtfs.TripUpdate.StopTimeUpdate.SKIPPED
    assert project(message).observation.kind == "delay"
    stop = update.stop_time_update.add(stop_sequence=30, stop_id="alight")
    stop.schedule_relationship = gtfs.TripUpdate.StopTimeUpdate.SKIPPED
    projected = project(message).observation
    assert projected.kind == "skipped_stop" and projected.selectors[0].stop_id == "alight"


def test_zero_boarding_delay_cannot_restore_a_still_unconfirmed_skipped_alighting():
    cancelled = trip_feed(delay=0)
    stop = cancelled.entity[0].trip_update.stop_time_update.add(stop_sequence=30, stop_id="alight")
    stop.schedule_relationship = gtfs.TripUpdate.StopTimeUpdate.SKIPPED
    previous = evaluate(project(cancelled).observation)["checkpoint"]
    assert previous.disrupted_stop_ids == ("alight",)
    resumed = trip_feed(delay=0, second=1)
    result = evaluate(project(resumed).observation, previous)
    assert result["checkpoint"].condition == "partial_disruption" and result["delivery"] == "none"
    assert result["reason"] == "skipped_stop_resumption_unconfirmed"
    resumed.header.timestamp += 1
    resumed.entity[0].trip_update.stop_time_update.add(stop_sequence=30, stop_id="alight").arrival.delay = 0
    result = evaluate(project(resumed).observation, result["checkpoint"])
    assert result["checkpoint"].condition == "restored" and result["delivery"] == "immediate"
    assert result["checkpoint"].disrupted_stop_ids == ()


def test_replacement_snapshot_replay_missing_and_static_switch_are_distinct():
    first = decode(trip_feed(cancelled=True))
    replay = snapshot_changes(first, first)
    assert replay["state"] == "replay" and not replay["missing"]
    renamed = trip_feed(cancelled=True, second=1)
    renamed.entity[0].id = "new-id"
    second = decode(renamed)
    assert not snapshot_changes(first, second)["missing"]
    empty = decode(feed(second=2))
    missing = snapshot_changes(second, empty)
    assert missing["state"] == "replacement" and len(missing["missing"]) == 1
    assert "restored" not in str(missing)
    assert snapshot_changes(second, first)["state"] == "older"
    changed = trip_feed(second=2)
    changed.header.feed_version = "next"
    assert snapshot_changes(second, decode(changed))["state"] == "static_version_changed"
    with pytest.raises(ValueError, match="Conflicting"):
        snapshot_changes(first, decode(trip_feed(delay=0)))
    with pytest.raises(ValueError, match="different"):
        snapshot_changes(first, decode(alert_feed(), ALERTS))


@pytest.mark.parametrize("mutation,reason", [
    (lambda f: setattr(f.header, "feed_version", "unknown"), "static_version_unverified"),
    (lambda f: f.header.ClearField("feed_version"), "static_version_unverified"),
    (lambda f: setattr(f.entity[0].trip_update.trip, "route_id", "opposite"), "unrelated_journey"),
    (lambda f: setattr(f.entity[0].trip_update.trip, "direction_id", 1), "unrelated_journey"),
    (lambda f: setattr(f.entity[0].trip_update.trip, "start_date", "20260915"), "unrelated_journey"),
    (lambda f: setattr(f.entity[0].trip_update.trip, "start_time", "06:00:00"), "trip_start_time_mapping_required"),
    (lambda f: setattr(f.entity[0].trip_update.trip, "schedule_relationship", gtfs.TripDescriptor.ADDED), "unsupported_trip_relationship"),
    (lambda f: setattr(f.entity[0].trip_update.stop_time_update[0], "stop_id", "alight"), "conflicting_stop_identity"),
    (lambda f: f.entity[0].trip_update.stop_time_update[0].ClearField("stop_sequence"), "stop_sequence_mapping_required"),
    (lambda f: setattr(f.entity[0].trip_update.stop_time_update[0], "schedule_relationship", gtfs.TripUpdate.StopTimeUpdate.NO_DATA), "boarding_prediction_unavailable"),
    (lambda f: setattr(f.entity[0].trip_update.stop_time_update[0].stop_time_properties, "assigned_stop_id", "new-platform"), "stop_change_mapping_required"),
    (lambda f: setattr(f.entity[0].trip_update.trip_properties, "trip_id", "replacement-trip"), "trip_properties_mapping_required"),
])
def test_unsupported_or_unrelated_facts_never_become_on_time(mutation, reason):
    message = trip_feed()
    mutation(message)
    result = project(message)
    assert result.observation is None and result.reason == reason


def test_same_stop_id_with_other_sequence_is_not_selected_boarding():
    message = trip_feed()
    message.entity[0].trip_update.stop_time_update[0].stop_sequence = 1
    assert project(message).reason == "boarding_prediction_unavailable"
    assert project(trip_feed(), resolved=leg()).reason == "stop_sequence_mapping_required"


def test_alert_preserves_source_languages_open_periods_and_cannot_infer_cancellation():
    result = project(alert_feed(), ALERTS)
    assert result.observation.kind == "notice"
    assert result.header == (("de", "Unterbruch"), ("fr", "Interruption"))
    assert "<script>" in result.description[0][1]
    assert result.active_periods == ()
    message = alert_feed()
    message.entity[0].alert.effect = gtfs.Alert.NO_SERVICE
    assert project(message, ALERTS).observation.kind == "notice"


def test_alert_scope_constraints_are_never_dropped():
    message = alert_feed()
    message.entity[0].alert.informed_entity[0].route_type = 3
    result = project(message, ALERTS)
    assert result.observation is None and result.reason == "unsupported_alert_selector"
    message.entity[0].alert.informed_entity[0].ClearField("route_type")
    message.entity[0].alert.informed_entity[0].trip.trip_id = "trip"
    assert project(message, ALERTS).reason == "unsupported_alert_selector"


def test_alert_disjoint_periods_do_not_bridge_gap_containing_journey():
    message = alert_feed()
    alert = message.entity[0].alert
    alert.active_period.add(start=int(NOW.timestamp()) - 3600, end=int(leg().departure.timestamp()))
    alert.active_period.add(start=int(leg().arrival.timestamp()), end=int(NOW.timestamp()) + 7200)
    assert project(message, ALERTS).reason == "outside_journey_time"
    alert.active_period[0].end += 60
    result = project(message, ALERTS)
    assert result.observation.valid_until == leg().departure + timedelta(minutes=1)
    assert len(result.active_periods) == 2


@pytest.mark.parametrize("mutation", [
    lambda f: setattr(f.header, "gtfs_realtime_version", "1.0"),
    lambda f: f.header.ClearField("incrementality"),
    lambda f: setattr(f.header, "incrementality", gtfs.FeedHeader.DIFFERENTIAL),
    lambda f: f.header.ClearField("timestamp"),
    lambda f: setattr(f.header, "timestamp", int(NOW.timestamp()) + 7200),
    lambda f: setattr(f.entity[0], "is_deleted", False),
    lambda f: f.entity.add().CopyFrom(f.entity[0]),
    lambda f: f.entity[0].alert.SetInParent(),
    lambda f: setattr(f.entity[0].trip_update.trip, "start_date", "20260230"),
    lambda f: f.entity[0].trip_update.trip.ClearField("trip_id"),
    lambda f: setattr(f.entity[0].trip_update, "timestamp", int(NOW.timestamp()) + 1),
    lambda f: f.entity[0].trip_update.stop_time_update.add(stop_sequence=10, stop_id="middle"),
    lambda f: setattr(f.entity[0].trip_update.stop_time_update[0].departure, "uncertainty", -1),
])
def test_invalid_full_snapshot_rejects_atomically(mutation):
    message = trip_feed()
    mutation(message)
    with pytest.raises(ValueError):
        decode(message)


def test_duplicate_trip_with_different_provider_id_is_rejected():
    message = trip_feed()
    copy = message.entity.add()
    copy.CopyFrom(message.entity[0])
    copy.id = "different"
    with pytest.raises(ValueError, match="same trip"):
        decode(message)


@pytest.mark.parametrize("payload", [b"", b"<html>login required</html>", b"\x0a\xff", b"\x00"])
def test_malformed_binary_is_not_empty_snapshot(payload):
    with pytest.raises(ValueError):
        decode_feed(payload, source=TRIPS, received_at=NOW)


def test_unknown_wire_fields_do_not_fall_back_to_scheduled_enum_defaults():
    # Unknown top-level field 100, varint 1; protobuf normally preserves it.
    payload = trip_feed().SerializeToString() + b"\xa0\x06\x01"
    with pytest.raises(ValueError, match="Unsupported GTFS fields"):
        decode_feed(payload, source=TRIPS, received_at=NOW)


def test_payload_bound_and_entity_membership(monkeypatch):
    import helvetic_lens.transport_feed as module
    monkeypatch.setattr(module, "MAX_BYTES", 8)
    with pytest.raises(ValueError, match="oversized"):
        decode(trip_feed())
    monkeypatch.setattr(module, "MAX_BYTES", 32768)
    first, second = decode(trip_feed()), decode(feed(second=1))
    with pytest.raises(ValueError, match="does not belong"):
        project_entity(second, first.entities[0], leg())


def test_alert_invalid_period_duplicate_language_and_no_scope_rejected():
    for scenario in ("period", "language", "scope"):
        message = alert_feed()
        alert = message.entity[0].alert
        if scenario == "period":
            alert.active_period.add(start=100, end=100)
        elif scenario == "language":
            alert.header_text.translation.add(language="de", text="conflict")
        else:
            alert.ClearField("informed_entity")
        with pytest.raises(ValueError):
            decode(message, ALERTS)
