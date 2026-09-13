from dataclasses import replace

import pytest

from helvetic_lens.hazard_cap import CAPArea
from helvetic_lens.hazard_geometry import canonical_polygon, match_point, match_radius, valid_polygon

RING = ((47.5, 7.5), (47.5, 7.7), (47.65, 7.7), (47.65, 7.5), (47.5, 7.5))
AREA = CAPArea("Synthetic area", (RING,), (), (), None, None)


@pytest.mark.parametrize(("point", "expected"), [
    ((47.56, 7.59), "match"), ((47.5, 7.5), "match"), ((47.5, 7.6), "match"),
    ((47.65, 7.7), "match"), ((47.49, 7.6), "no_match"), ((47.7, 7.8), "no_match"),
    ((7.59, 47.56), "unavailable"), ((float("nan"), 7.59), "unavailable"),
    ((True, 7.59), "unavailable"), (("47.56", 7.59), "unavailable"),
])
def test_boundary_included_axis_order_and_unknown_coordinates(point, expected):
    assert match_point((AREA,), latitude=point[0], longitude=point[1]).state == expected


def test_simple_ring_validation_and_unchanged_canonical_shape():
    assert valid_polygon(RING)
    assert valid_polygon(tuple(reversed(RING)))
    assert canonical_polygon(RING) == canonical_polygon(tuple(reversed(RING)))
    assert not valid_polygon(RING[:-1])
    assert not valid_polygon(((47, 7), (48, 8), (47, 8), (48, 7), (47, 7)))
    assert not valid_polygon(((47, 7), (47, 8), (47, 7.5), (48, 8), (47, 7)))
    assert not valid_polygon(((47, 7), (47, 8), (47, 9), (47, 7)))


def test_unresolved_geocodes_altitude_or_absence_never_become_an_outside_result():
    for areas in ((), (replace(AREA, polygons=()),), (replace(AREA, altitude=100),),
                  (replace(AREA, geocodes=(("unknown", "123"),)),)):
        assert match_point(areas, latitude=46, longitude=8).state == "unavailable"
    # A matching member proves intersection of the union despite another unknown.
    assert match_point((replace(AREA, polygons=()), AREA), latitude=47.56, longitude=7.59).state == "match"


def test_cap_circles_use_kilometres_and_zero_radius_means_only_centre():
    circle = replace(AREA, polygons=(), circles=((47.56, 7.59, 1),))
    assert match_point((circle,), latitude=47.565, longitude=7.59).state == "match"
    assert match_point((circle,), latitude=47.58, longitude=7.59).state == "no_match"
    point = replace(circle, circles=((47.56, 7.59, 0),))
    assert match_point((point,), latitude=47.56, longitude=7.59).state == "match"
    assert match_point((point,), latitude=47.56001, longitude=7.59).state == "no_match"


def test_distant_or_self_intersecting_geometry_is_unknown_not_a_guessed_match():
    malformed = replace(AREA, polygons=(((47, 7), (48, 8), (47, 8), (48, 7), (47, 7)),))
    assert match_point((malformed,), latitude=47.56, longitude=7.59).state == "unavailable"
    remote = replace(AREA, polygons=(), circles=((0, 0, 10),))
    assert match_point((remote,), latitude=47.56, longitude=7.59).state == "unavailable"
    assert match_point((AREA,) * 65, latitude=47.56, longitude=7.59).state == "unavailable"


def test_radius_intersects_edge_even_when_centre_and_all_vertices_are_outside():
    # Home is 1.11 km south of a long edge; each vertex is over 7 km away.
    assert match_point((AREA,), latitude=47.49, longitude=7.6).state == "no_match"
    assert match_radius((AREA,), latitude=47.49, longitude=7.6, radius_km=1).state == "no_match"
    for ring in (RING, tuple(reversed(RING))):
        assert match_radius((replace(AREA, polygons=(ring,)),), latitude=47.49,
                            longitude=7.6, radius_km=2).state == "match"


def test_radius_contains_whole_warning_and_circle_tangency_is_included():
    assert match_radius((AREA,), latitude=47.3, longitude=7.6, radius_km=50).state == "match"
    # Exact north/south separation on the same sphere used by CAP circles.
    import math

    from helvetic_lens.hazard_geometry import EARTH_KM

    circle = replace(AREA, polygons=(), circles=((47.56, 7.59, 1),))
    tangent_latitude = 47.56 - math.degrees(3 / EARTH_KM)
    assert match_radius((circle,), latitude=tangent_latitude, longitude=7.59, radius_km=2).state == "match"
    assert match_radius((circle,), latitude=tangent_latitude - 0.00001,
                        longitude=7.59, radius_km=2).state == "no_match"


@pytest.mark.parametrize("radius", [-1, 51, float("nan"), float("inf"), True, "1", None])
def test_invalid_radius_is_unavailable_even_for_an_inside_point(radius):
    assert match_radius((AREA,), latitude=47.56, longitude=7.59, radius_km=radius).state == "unavailable"


def test_radius_preserves_unknown_members_and_vertical_restrictions():
    unresolved = replace(AREA, polygons=(), geocodes=(("unverified", "1"),))
    assert match_radius((unresolved,), latitude=47.56, longitude=7.59, radius_km=50).state == "unavailable"
    assert match_radius((replace(AREA, altitude=1),), latitude=47.56,
                        longitude=7.59, radius_km=50).state == "unavailable"
    assert match_radius((unresolved, AREA), latitude=47.49, longitude=7.6, radius_km=2).state == "match"


def test_bounded_edge_work_returns_unknown_not_outside(monkeypatch):
    import helvetic_lens.hazard_geometry as geometry

    assert geometry._edge_within_radius(RING[0], RING[1], (47.49, 7.6), 2, [0]) is None
    monkeypatch.setattr(geometry, "_edge_within_radius", lambda *args: None)
    assert match_radius((AREA,), latitude=47.49, longitude=7.6, radius_km=2).state == "unavailable"


def test_circle_count_is_bounded_before_matching():
    many = replace(AREA, polygons=(), circles=((47.56, 7.59, 1),) * 2001)
    assert match_radius((many,), latitude=47.56, longitude=7.59, radius_km=1).reason == "geometry_limit"
