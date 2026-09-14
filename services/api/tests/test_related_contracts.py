"""Independent association examples; no live coverage or authority approval claim."""
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from helvetic_lens.related_contracts import (
    AuthorityReference,
    EventFact,
    EventReference,
    PlaceBinding,
    associate,
    story_associations,
)

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def fact(domain, index, *, place="2701", start=NOW, end=NOW + timedelta(hours=2), state="active"):
    feature = AuthorityReference(namespace={"warnings": "cap:area", "river": "bafu:station", "traffic": "tmc:reviewed_slice"}[domain],
        identifier=f"feature-{index}")
    return EventFact(reference=EventReference(domain=domain, monitor_id=UUID(int=index),
            event_id=UUID(int=index + 100), revision=1, evidence_hash=f"{index:064x}"),
        authority=AuthorityReference(namespace={"warnings": "alertswiss:cap", "river": "bafu:measurement", "traffic": "astra:situation"}[domain],
            identifier=f"source-{index}"), source_feature=feature, source_revision="a" * 64,
        availability="available", source_state=state, time_kind="interval", starts_at=start, ends_at=end,
        place=PlaceBinding(id=UUID(int=index + 200), source_feature=feature, source_revision="a" * 64,
            place_namespace="swisstopo:bfs_municipality", place_id=place, boundary_version="2026-v1",
            boundary_hash="b" * 64, evidence_hash=f"{index + 10:064x}",
            accepted_at=NOW - timedelta(days=1), valid_until=NOW + timedelta(days=1)))


def test_three_authorities_retain_ids_and_only_possible_relationship():
    events = (fact("warnings", 1), fact("river", 2, state="danger_increased"), fact("traffic", 3, state="road_closed"))
    original = [item.model_dump_json() for item in events]
    links = story_associations(events, now=NOW)
    assert len(links) == 3 and {item.state for item in links} == {"possible"}
    assert {item.reference for item in events} == {ref for link in links for ref in (link.left, link.right)}
    assert all(link.place_key[1] == "2701" and link.overlap_end == NOW + timedelta(hours=2) for link in links)
    assert len({link.proof_hash for link in links}) == 3
    assert [item.model_dump_json() for item in events] == original
    assert associate(events[0], events[1], now=NOW).proof_hash == associate(events[1], events[0], now=NOW).proof_hash


def test_nearby_distinct_municipality_and_clock_coincidence_do_not_link():
    warning = fact("warnings", 1)
    nearby = fact("traffic", 3, place="2771")
    assert associate(warning, nearby, now=NOW).reason == "different_places"
    unknown_place = nearby.model_copy(update={"place": None})
    assert associate(warning, unknown_place, now=NOW).reason == "geography_unavailable"


@pytest.mark.parametrize("kind", ["missing", "expired", "future", "revoked", "new_boundary", "new_source", "foreign_feature", "denied_source"])
def test_unverified_or_changed_bindings_never_supply_association_provenance(kind):
    warning, road = fact("warnings", 1), fact("traffic", 3)
    changes = {"expired": {"valid_until": NOW}, "future": {"accepted_at": NOW + timedelta(minutes=1)},
        "revoked": {"revoked_at": NOW}, "new_boundary": {"boundary_hash": "c" * 64},
        "new_source": {"source_revision": "d" * 64},
        "foreign_feature": {"source_feature": warning.source_feature}}
    if kind == "missing":
        road = road.model_copy(update={"place": None})
    elif kind == "denied_source":
        road = road.model_copy(update={"availability": "unavailable"})
    else:
        road = road.model_copy(update={"place": road.place.model_copy(update=changes[kind])})
    result = associate(warning, road, now=NOW)
    assert result.state == "unknown"
    assert result.left is result.right is result.bindings is result.proof_hash is None


def test_half_open_intervals_unknown_time_and_transitive_chain():
    warning = fact("warnings", 1, end=NOW + timedelta(hours=1))
    river = fact("river", 2)
    road = fact("traffic", 3, start=NOW + timedelta(hours=1))
    links = story_associations((warning, river, road), now=NOW)
    assert [link.state for link in links].count("possible") == 2
    assert [link.reason for link in links].count("different_times") == 1
    assert associate(warning, road.model_copy(update={"starts_at": None}), now=NOW).reason == "time_unknown"


def test_correction_changes_proof_and_cancellation_does_not_close_other_events():
    warning, river, road = fact("warnings", 1), fact("river", 2, state="danger_increased"), fact("traffic", 3, state="road_closed")
    original = associate(warning, road, now=NOW)
    corrected = road.model_copy(update={"reference": road.reference.model_copy(update={"revision": 2, "evidence_hash": "e" * 64})})
    assert associate(warning, corrected, now=NOW).proof_hash != original.proof_hash
    cancelled = warning.model_copy(update={"source_state": "cancelled"})
    assert len(story_associations((cancelled, river, road), now=NOW)) == 3
    assert river.source_state == "danger_increased" and road.source_state == "road_closed"
    assert associate(cancelled, road, now=NOW).proof_hash != original.proof_hash


def test_same_authority_event_in_two_monitors_is_not_two_sources():
    first = fact("warnings", 1)
    alias = first.model_copy(update={"reference": first.reference.model_copy(update={"monitor_id": UUID(int=999)})})
    assert associate(first, alias, now=NOW).reason == "same_event"
    with pytest.raises(ValueError):
        story_associations((first, first), now=NOW)


def test_invalid_time_or_constructed_payload_cannot_bypass_contract():
    warning, road = fact("warnings", 1), fact("traffic", 3)
    with pytest.raises(ValueError):
        associate(warning, road, now=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        associate(warning, road.model_copy(update={"ends_at": NOW - timedelta(days=1)}), now=NOW)


def test_equivalent_timezone_offsets_do_not_create_new_association_evidence():
    warning, road = fact("warnings", 1), fact("traffic", 3)
    offset = timezone(timedelta(hours=2))
    same = road.model_copy(update={"starts_at": road.starts_at.astimezone(offset),
        "ends_at": road.ends_at.astimezone(offset), "place": road.place.model_copy(update={
            "accepted_at": road.place.accepted_at.astimezone(offset),
            "valid_until": road.place.valid_until.astimezone(offset)})})
    assert associate(warning, road, now=NOW).proof_hash == associate(warning, same, now=NOW).proof_hash


def test_river_observation_can_match_event_window_without_inventing_persistence():
    warning = fact("warnings", 1)
    river = fact("river", 2).model_copy(update={"time_kind": "instant", "ends_at": None})
    link = associate(warning, river, now=NOW)
    assert link.state == "possible" and link.overlap_kind == "instant"
    assert link.overlap_start == link.overlap_end == NOW
    future_road = fact("traffic", 3, start=NOW + timedelta(minutes=1))
    assert associate(river, future_road, now=NOW).reason == "different_times"
    ending_warning = warning.model_copy(update={"starts_at": NOW - timedelta(hours=1), "ends_at": NOW})
    assert associate(ending_warning, river, now=NOW).reason == "different_times"
    unknown = river.model_copy(update={"time_kind": "unknown"})
    assert associate(warning, unknown, now=NOW).reason == "time_unknown"
