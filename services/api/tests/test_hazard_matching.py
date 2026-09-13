from dataclasses import replace
from datetime import date

import pytest
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, box
from test_hazard_boundaries import load, point_from_lv95

from helvetic_lens.hazard_cap import CAPArea
from helvetic_lens.hazard_contracts import MunicipalityLocation
from helvetic_lens.hazard_matching import CANTON, COMMUNE, COUNTRY, Projector, match_location

TODAY = date(2026, 9, 13)
MUNICIPALITY = MunicipalityLocation(kind="municipality", canton="BE", municipality_code="1")
EMPTY = CAPArea("Synthetic warning", (), (), (), None, None)


def ring(x1, y1, x2, y2):
    convert = Transformer.from_crs(2056, 4326, always_xy=True, allow_ballpark=False, only_best=True)
    return tuple((lat, lon) for lon, lat in (convert.transform(x, y) for x, y in box(x1, y1, x2, y2).exterior.coords))


def check(areas, location=MUNICIPALITY, catalogue=None, version="2026-01", day=TODAY):
    return match_location(areas, location, load() if catalogue is None else catalogue,
                          on_date=day, geocode_version=version)


def test_municipality_intersects_interior_polygon_but_not_remote_warning():
    inside = replace(EMPTY, polygons=(ring(2600400, 1200400, 2600600, 1200600),))
    remote = replace(EMPTY, polygons=(ring(2603000, 1203000, 2604000, 1204000),))
    assert check((inside,)).state == "match"
    assert check((inside,)).basis == "explicit_geometry"
    assert check((remote,)).state == "no_match"
    assert check((remote, inside)).state == "match"


def test_administrative_filters_do_not_enlarge_explicit_polygon_for_a_house():
    home = point_from_lv95(2600500, 1200500).model_copy(update={"radius_km": 0})
    remote = replace(EMPTY, polygons=(ring(2600100, 1200100, 2600200, 1200200),),
                     geocodes=((COMMUNE, "1"), (CANTON, "BE"), (COUNTRY, "CH")))
    assert check((remote,), home).state == "no_match"
    assert check((remote,), home, version=None).state == "no_match"
    assert check((replace(remote, polygons=(ring(2600400, 1200400, 2600600, 1200600),)),), home).state == "match"


def test_named_municipality_can_match_filter_but_exact_house_remains_unconfirmed():
    area = replace(EMPTY, geocodes=((COMMUNE, "1"),))
    municipality = check((area,))
    assert municipality.state == "match" and municipality.basis == "administrative_filter"
    home = point_from_lv95(2600500, 1200500).model_copy(update={"radius_km": 0})
    point = check((area,), home)
    assert point.state == "unavailable"
    assert point.reason == "administrative_filter_without_precise_extent"
    assert check((area,), version=None).state == "unavailable"
    assert check((area,), version="2025-01").state == "unavailable"


def test_broad_canton_and_country_only_filters_do_not_confirm_a_specific_municipality():
    for codes in (((CANTON, "BE"),), ((COUNTRY, "CH"),), ((CANTON, "CH"),)):
        assert check((replace(EMPTY, geocodes=codes),)).state == "unavailable"
    for codes in (((COUNTRY, "LI"),), ((CANTON, "FL"),)):
        assert check((replace(EMPTY, geocodes=codes),)).state == "no_match"


@pytest.mark.parametrize("code", [(COMMUNE, "01"), (COMMUNE, "9999"), (CANTON, "be"),
                                  (COUNTRY, "ZZ"), ("WARNREGIONSCH", "WRNr100"), ("BFS", "1")])
def test_unknown_obsolete_or_alias_codes_are_not_guessed(code):
    assert check((replace(EMPTY, geocodes=(code,)),)).state == "unavailable"


def test_explicit_unknown_warning_region_cannot_prove_a_negative_but_positive_union_survives():
    home = point_from_lv95(2600500, 1200500).model_copy(update={"radius_km": 0})
    remote = replace(EMPTY, polygons=(ring(2603000, 1203000, 2604000, 1204000),),
                     geocodes=(("HYDROREGIONCH", "123"),))
    assert check((remote,), home).state == "unavailable"
    inside = replace(EMPTY, polygons=(ring(2600400, 1200400, 2600600, 1200600),))
    assert check((remote, inside), home).state == "match"


def test_municipal_hole_does_not_receive_a_warning_inside_the_excluded_area():
    catalogue = load()
    outer = box(2600000, 1200000, 2601000, 1201000)
    hole = box(2600300, 1200300, 2600700, 1200700)
    geometry = MultiPolygon([Polygon(outer.exterior.coords, [hole.exterior.coords])])
    entry = replace(catalogue.municipalities["1"], geometry=geometry)
    catalogue = replace(catalogue, municipalities={"1": entry})
    warning = replace(EMPTY, polygons=(ring(2600400, 1200400, 2600600, 1200600),))
    assert check((warning,), catalogue=catalogue).state == "no_match"
    outside_hole = replace(EMPTY, polygons=(ring(2600050, 1200050, 2600150, 1200150),))
    assert check((outside_hole,), catalogue=catalogue).state == "match"


def test_circle_entirely_inside_or_crossing_edge_matches_even_without_contained_vertices():
    middle = point_from_lv95(2600500, 1200500)
    inside = replace(EMPTY, circles=((middle.latitude, middle.longitude, 0.05),))
    assert check((inside,)).state == "match"
    zero = replace(EMPTY, circles=((middle.latitude, middle.longitude, 0),))
    assert check((zero,)).state == "match"
    south = point_from_lv95(2600500, 1199900)
    crossing = replace(EMPTY, circles=((south.latitude, south.longitude, 0.2),))
    assert check((crossing,)).state == "match"
    miss = replace(EMPTY, circles=((south.latitude, south.longitude, 0.05),))
    assert check((miss,)).state == "no_match"


def test_radius_intersects_named_filter_outside_its_centre_without_becoming_an_exact_house_hit():
    catalogue = load()
    neighbor = replace(catalogue.municipalities["1"], code="2", name="Neighbor",
                       geometry=MultiPolygon([box(2601100, 1200000, 2602000, 1201000)]))
    catalogue = replace(catalogue, municipalities={**catalogue.municipalities, "2": neighbor})
    home = point_from_lv95(2600500, 1200500).model_copy(update={"radius_km": 0})
    warning = replace(EMPTY, geocodes=((COMMUNE, "2"),))
    assert check((warning,), home, catalogue=catalogue).state == "no_match"
    nearby = home.model_copy(update={"radius_km": 1})
    result = check((warning,), nearby, catalogue=catalogue)
    assert result.state == "unavailable" and result.reason == "administrative_filter_without_precise_extent"
    assert check((warning,), catalogue=catalogue).state == "no_match"


def test_geometry_boundary_band_expiry_altitude_and_work_limit_remain_unknown(monkeypatch):
    touching = replace(EMPTY, polygons=(ring(2601000, 1200000, 2601100, 1200100),))
    assert check((touching,)).state == "unavailable"
    inside = replace(EMPTY, polygons=(ring(2600400, 1200400, 2600600, 1200600),))
    assert check((replace(inside, altitude=0),)).state == "unavailable"
    assert check((inside,), day=date(2027, 1, 1)).state == "unavailable"
    assert check((inside,) * 65).reason == "geometry_limit"
    assert check(()).state == "unavailable"

    original = Projector.__init__

    def exhausted(self):
        original(self)
        self.remaining = 0

    monkeypatch.setattr(Projector, "__init__", exhausted)
    assert check((inside,)).state == "unavailable"
