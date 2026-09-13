from dataclasses import replace

import pytest
from pydantic import ValidationError
from test_road_feed import first

from helvetic_lens import road_topology
from helvetic_lens.road_feed import RoadLocation
from helvetic_lens.road_topology import CorridorFlow, TmcPoint, TmcTopology, TopologyDefinition, TopologyError


def topology(*, unknown_lengths=False, version="synthetic-1"):
    # Numeric codes intentionally do not follow the positive coding direction.
    # This is a synthetic reviewed projection, not any Swiss road or native table.
    return TmcTopology(TopologyDefinition(country="4", table="9", version=version, points=(
        TmcPoint(code=90, positive=20, distance_to_positive_m=None if unknown_lengths else 100),
        TmcPoint(code=20, positive=70, negative=90, distance_to_positive_m=None if unknown_lengths else 200),
        TmcPoint(code=70, positive=10, negative=20, distance_to_positive_m=None if unknown_lengths else 300),
        TmcPoint(code=10, negative=70),
        TmcPoint(code=700, positive=800, distance_to_positive_m=100), TmcPoint(code=800, negative=700),
    )))


def location(*, primary=10, secondary=90, direction="positive", primary_offset=0, secondary_offset=0):
    return RoadLocation("4", "9", "synthetic-1", direction, primary, secondary, primary_offset, secondary_offset)


def flow(graph, points=(90, 20, 70, 10), *, key="southbound", start=0, end=0):
    return graph.resolve_corridor(CorridorFlow(key=key, points=points, start_offset_m=start, end_offset_m=end))


def test_compass_label_is_reviewed_independently_of_coding_and_numeric_point_order():
    graph = topology()
    south = flow(graph)
    north = flow(graph, (10, 70, 20, 90), key="northbound")
    assert graph.intersection(location(), south).state == "match"
    assert graph.intersection(location(), north).state == "no_match"
    negative = location(primary=90, secondary=10, direction="negative")
    assert graph.intersection(negative, north).state == "match"
    assert graph.intersection(negative, south).state == "no_match"
    assert graph.intersection(negative, north).edges == ((20, 70), (70, 10), (90, 20))


@pytest.mark.parametrize("reverse", [False, True])
def test_both_directions_match_the_same_physical_extent(reverse):
    graph = topology()
    event = location(primary=90 if reverse else 10, secondary=10 if reverse else 90, direction="both")
    assert graph.intersection(event, flow(graph)).state == "match"
    assert graph.intersection(event, flow(graph, (10, 70, 20, 90))).state == "match"


def test_disconnected_road_with_known_valid_extent_is_excluded():
    graph = topology()
    result = graph.intersection(location(primary=800, secondary=700), flow(graph))
    assert result.state == "no_match" and not result.edges


@pytest.mark.parametrize("changes,reason", [
    ({"version": "new-version"}, "location_topology_mismatch"),
    ({"table": "10"}, "location_topology_mismatch"),
    ({"country": "5"}, "location_topology_mismatch"),
    ({"primary": 999}, "location_point_unknown"),
    ({"direction": "unknown"}, "location_direction_unknown"),
    ({"direction": "northbound"}, "location_direction_unknown"),
    ({"direction": "negative"}, "location_path_unresolved"),
    ({"primary_offset_m": -1}, "location_offset_invalid"),
    ({"primary_offset_m": 0.5}, "location_offset_invalid"),
])
def test_missing_or_inconsistent_coverage_stays_unknown(changes, reason):
    graph = topology()
    result = graph.intersection(replace(location(), **changes), flow(graph))
    assert result.state == "unknown" and result.reason == reason


def test_primary_and_secondary_offsets_trim_inward_across_multiple_links():
    graph = topology()
    event = location(secondary_offset=150, primary_offset=350)  # Physical range 150..250 on length600.
    assert graph.intersection(event, flow(graph, (20, 70))).edges == ((20, 70),)
    assert graph.intersection(event, flow(graph, (90, 20))).state == "no_match"
    assert graph.intersection(event, flow(graph, (70, 10))).state == "no_match"
    reverse = location(primary=90, secondary=10, direction="negative", primary_offset=150, secondary_offset=350)
    assert graph.intersection(reverse, flow(graph, (70, 20))).edges == ((20, 70),)


def test_corridor_offsets_and_event_offsets_must_have_actual_overlap():
    graph = topology()
    corridor = flow(graph, start=150, end=350)  # 150..250.
    assert graph.intersection(location(secondary_offset=200, primary_offset=350), corridor).state == "match"
    assert graph.intersection(location(secondary_offset=250, primary_offset=250), corridor).state == "no_match"
    assert graph.intersection(location(secondary_offset=300, primary_offset=200), corridor).state == "no_match"


def test_zero_length_point_extent_and_named_point_match_without_fabricating_a_span():
    graph = topology()
    point = location(primary=20, secondary=20)
    assert graph.intersection(point, flow(graph, (20, 70))).state == "match"
    assert graph.intersection(point, flow(graph, (70, 10))).state == "no_match"
    assert graph.intersection(point, flow(graph, (70, 20))).state == "no_match"
    assert graph.intersection(point, flow(graph, start=150, end=0)).state == "no_match"
    between = location(secondary_offset=175, primary_offset=425)  # A point inside the second link.
    assert graph.intersection(between, flow(graph, (20, 70))).state == "match"
    assert graph.intersection(between, flow(graph, (90, 20))).state == "no_match"


def test_unknown_link_distance_only_allows_untrimmed_topological_extent():
    graph = topology(unknown_lengths=True)
    assert graph.intersection(location(), flow(graph)).state == "match"
    assert graph.intersection(location(primary_offset=1), flow(graph)).reason == "topology_offset_distance_unknown"
    with pytest.raises(TopologyError, match="topology_offset_distance_unknown"):
        flow(graph, start=1)


def test_offsets_cannot_expand_beyond_referenced_endpoints():
    graph = topology()
    assert graph.intersection(location(primary_offset=601), flow(graph)).reason == "topology_offsets_outside_extent"
    assert graph.intersection(location(primary=20, secondary=20, primary_offset=1), flow(graph)).state == "unknown"


def test_circular_extent_is_unknown_until_direction_sense_is_supported():
    graph = TmcTopology(TopologyDefinition(country="4", table="9", version="synthetic-1", points=(
        TmcPoint(code=1, positive=2, negative=3, distance_to_positive_m=100),
        TmcPoint(code=2, positive=3, negative=1, distance_to_positive_m=100),
        TmcPoint(code=3, positive=1, negative=2, distance_to_positive_m=100),
    )))
    corridor = flow(graph, (1, 2))
    for direction in ("positive", "negative", "both"):
        result = graph.intersection(location(primary=2, secondary=1, direction=direction), corridor)
        assert result.reason == "location_circular_extent" and result.state == "unknown"


@pytest.mark.parametrize("points,error", [
    ((TmcPoint(code=1), TmcPoint(code=1)), "topology_duplicate_point"),
    ((TmcPoint(code=1, positive=1),), "topology_self_link"),
    ((TmcPoint(code=1, positive=2),), "topology_nonreciprocal_link"),
    ((TmcPoint(code=1, positive=2), TmcPoint(code=2)), "topology_nonreciprocal_link"),
    ((TmcPoint(code=1, distance_to_positive_m=20),), "topology_distance_without_link"),
])
def test_invalid_projection_cannot_be_used(points, error):
    with pytest.raises(TopologyError, match=error):
        TmcTopology(TopologyDefinition(country="4", table="9", version="synthetic-1", points=points))


def test_flow_must_be_exact_ordered_known_adjacent_points():
    graph = topology()
    for points, code in (((90, 70), "topology_nonadjacent_path"), ((90, 20, 90), "corridor_repeated_point"),
                         ((90, 999), "corridor_point_unknown")):
        with pytest.raises(TopologyError, match=code):
            flow(graph, points)
    with pytest.raises(TopologyError, match="corridor_empty_extent"):
        flow(graph, start=600)
    with pytest.raises(ValidationError):
        CorridorFlow(key="northbound", points=(True, 20))


def test_hash_binds_topology_version_geometry_and_projection_not_input_order():
    graph = topology()
    reordered = TmcTopology(TopologyDefinition(country="4", table="9", version="synthetic-1",
        points=tuple(reversed(tuple(graph._points.values())))))
    assert graph.sha256 == reordered.sha256
    assert topology(version="different").intersection(location(), flow(graph)).reason == "corridor_topology_mismatch"
    assert topology(unknown_lengths=True).intersection(location(), flow(graph)).reason == "corridor_topology_mismatch"


def test_path_budget_is_unknown_not_truncated_partial_match(monkeypatch):
    graph = topology()
    corridor = flow(graph)
    monkeypatch.setattr(road_topology, "MAX_PATH_POINTS", 3)
    result = graph.intersection(location(), corridor)
    assert result.state == "unknown" and result.reason == "topology_path_limit"


def test_existing_decoder_location_requires_matching_reviewed_points():
    graph = topology()
    assert graph.intersection(first().location, flow(graph)).reason == "location_point_unknown"
