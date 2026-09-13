import hashlib
import sqlite3
import struct
from contextlib import closing
from dataclasses import replace
from datetime import date

import pytest
import shapely
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, box

from helvetic_lens.hazard_boundaries import (
    BoundaryError,
    decode_geometry,
    load_geopackage,
)
from helvetic_lens.hazard_contracts import MunicipalityLocation, PointLocation

TODAY = date(2026, 9, 13)
EXPIRY = date(2027, 1, 1)


def blob(geometry, crs=2056):
    return b"GP\x00\x01" + struct.pack("<i", crs) + shapely.to_wkb(geometry)


def package(*, missing_canton=False, duplicate=False, foreign=False, invalid_schema=False):
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE gpkg_geometry_columns(table_name,column_name,geometry_type_name,srs_id,z,m)")
        db.execute("CREATE TABLE tlm_hoheitsgebiet(bfs_nummer,kantonsnummer,name,geom,icc,objektart)")
        db.execute("CREATE TABLE tlm_kantonsgebiet(kantonsnummer,geom,icc)")
        db.execute("CREATE TABLE tlm_landesgebiet(geom,icc)")
        for table in ("tlm_hoheitsgebiet", "tlm_kantonsgebiet", "tlm_landesgebiet"):
            db.execute("INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,?,?)",
                       (table, "geom", "MULTIPOLYGON", 4326 if invalid_schema else 2056, 1, 0))
        area = blob(MultiPolygon([box(2600000, 1200000, 2601000, 1201000)]))
        db.execute("INSERT INTO tlm_hoheitsgebiet VALUES (1,2,'Synthetic municipality',?,'CH','Gemeindegebiet')", (area,))
        if duplicate:
            db.execute("INSERT INTO tlm_hoheitsgebiet SELECT * FROM tlm_hoheitsgebiet")
        if foreign:
            db.execute("INSERT INTO tlm_hoheitsgebiet VALUES (2,2,'Foreign',?,'LI','Gemeindegebiet')", (area,))
            db.execute("INSERT INTO tlm_hoheitsgebiet VALUES (3,2,'Lake',?,'CH','Kantonsgebiet')", (area,))
        for canton in range(1, 26 if missing_canton else 27):
            db.execute("INSERT INTO tlm_kantonsgebiet VALUES (?,?,?)", (canton, area, "CH"))
        db.execute("INSERT INTO tlm_landesgebiet VALUES (?,'CH')", (area,))
        db.commit()
        return db.serialize()


def load(payload=None, **kwargs):
    payload = package() if payload is None else payload
    return load_geopackage(payload, sha256=hashlib.sha256(payload).hexdigest(),
                           version="2026-01", expires_on=EXPIRY, **kwargs)


def test_native_schema_requires_unique_swiss_political_municipalities_and_cantons():
    catalogue = load(package(foreign=True))
    assert list(catalogue.municipalities) == ["1"]
    assert len(catalogue.cantons) == 26
    for options in ({"missing_canton": True}, {"duplicate": True}, {"invalid_schema": True}):
        with pytest.raises(BoundaryError):
            load(package(**options))


def test_geo_package_holes_and_multipart_areas_are_not_flattened():
    from shapely.geometry import Point

    outer = [(2600000, 1200000), (2601000, 1200000), (2601000, 1201000), (2600000, 1201000)]
    hole = [(2600400, 1200400), (2600600, 1200400), (2600600, 1200600), (2600400, 1200600)]
    geometry = MultiPolygon([Polygon(outer, [hole]), box(2602000, 1202000, 2602100, 1202100)])
    restored = decode_geometry(blob(geometry))
    assert not restored.covers(Point(2600500, 1200500))
    assert restored.covers(Point(2600400, 1200500))  # Hole boundary is included.
    assert restored.covers(Point(2602050, 1202050))
    assert restored.equals(geometry)


@pytest.mark.parametrize("payload", [b"not a database" * 20, b"SQLite format 3\x00" + b"\x00" * 300])
def test_hashed_malformed_database_is_controlled_failure(payload):
    with pytest.raises(BoundaryError):
        load(payload)


def test_modified_asset_invalid_headers_crs_and_geometry_are_rejected():
    payload = package()
    with pytest.raises(BoundaryError, match="hash"):
        load_geopackage(payload + b"altered", sha256=hashlib.sha256(payload).hexdigest(),
                        version="2026-01", expires_on=EXPIRY)
    valid = blob(MultiPolygon([box(2600000, 1200000, 2601000, 1201000)]))
    for malformed in (valid[:3] + b"\x21" + valid[4:], valid[:3] + b"\x11" + valid[4:],
                      valid[:3] + b"\x0f" + valid[4:], valid[:10], valid[:4] + struct.pack("<i", 4326) + valid[8:],
                      blob(MultiPolygon([box(0, 0, 1, 1)])), blob(Polygon([(2600000, 1200000),
                           (2601000, 1201000), (2600000, 1201000), (2601000, 1200000)]))):
        with pytest.raises(BoundaryError):
            decode_geometry(malformed)


def test_municipality_revision_expiry_and_canton_are_not_guessed():
    catalogue = load()
    place = MunicipalityLocation(kind="municipality", canton="BE", municipality_code="1")
    proof = catalogue.verify_location(place, on_date=TODAY)
    assert proof.state == "verified" and proof.municipality_name == "Synthetic municipality"
    assert proof.sha256 == catalogue.sha256 and proof.version == "2026-01"
    assert not proof.radius_coverage_verified
    assert catalogue.verify_location(place.model_copy(update={"canton": "JU"}), on_date=TODAY).reason == "municipality_canton_mismatch"
    assert catalogue.verify_location(place.model_copy(update={"municipality_code": "2"}), on_date=TODAY).state == "unavailable"
    for day in (date(2025, 12, 31), EXPIRY, None):
        assert catalogue.verify_location(place, on_date=day).reason == "boundary_version_outside_review"


def point_from_lv95(x, y):
    lon, lat = Transformer.from_crs(2056, 4326, always_xy=True, allow_ballpark=False, only_best=True).transform(x, y)
    return PointLocation(kind="point", canton="BE", latitude=lat, longitude=lon, radius_km=5)


def test_local_point_projection_respects_borders_and_does_not_prove_radius_coverage():
    catalogue = load()
    middle = catalogue.verify_location(point_from_lv95(2600500, 1200500), on_date=TODAY)
    assert middle.state == "verified" and middle.municipality_code == "1"
    assert not middle.radius_coverage_verified
    assert catalogue.verify_location(point_from_lv95(2600000, 1200500), on_date=TODAY).reason == "national_border_uncertain"
    assert catalogue.verify_location(point_from_lv95(2599900, 1200500), on_date=TODAY).reason == "outside_switzerland"
    incomplete = replace(catalogue, municipalities={})
    assert incomplete.verify_location(point_from_lv95(2600500, 1200500), on_date=TODAY).state == "unavailable"


def test_projection_with_network_enabled_or_unavailable_does_not_access_remote_grids(monkeypatch):
    import helvetic_lens.hazard_boundaries as boundaries

    catalogue = load()
    point = point_from_lv95(2600500, 1200500)
    monkeypatch.setattr(boundaries.network, "is_network_enabled", lambda: True)
    assert catalogue.verify_location(point, on_date=TODAY).reason == "boundary_projection_network_enabled"
    monkeypatch.setattr(boundaries.network, "is_network_enabled", lambda: False)

    def unavailable(*args, **kwargs):
        raise RuntimeError("Local projection unavailable")

    monkeypatch.setattr(boundaries.Transformer, "from_crs", unavailable)
    assert catalogue.verify_location(point, on_date=TODAY).reason == "boundary_projection_unavailable"
