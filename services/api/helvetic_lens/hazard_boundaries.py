"""Offline, hash-pinned swissBOUNDARIES3D GeoPackage catalogue.

Only public administrative geometry enters this loader. It performs no downloads,
geocoding, approvals or activation. Callers supply reviewed version/expiry and the
hash of the unpacked asset, after verifying the archive against official STAC.
Private coordinates stay local. Border uncertainty is not Swiss membership proof.
"""

import hashlib
import math
import re
import sqlite3
import struct
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

import shapely
from pyproj import Transformer, network
from shapely.geometry import Point

from .hazard_contracts import MunicipalityLocation, PointLocation

MAX_PACKAGE_BYTES = 128 * 1024 * 1024
MAX_GEOMETRY_BYTES = 16 * 1024 * 1024
ATTRIBUTION = "Federal Office of Topography swisstopo"
CANTONS = dict(enumerate(("ZH", "BE", "LU", "UR", "SZ", "OW", "NW", "GL", "ZG", "FR", "SO", "BS",
                         "BL", "SH", "AR", "AI", "SG", "GR", "AG", "TG", "TI", "VD", "VS", "NE", "GE", "JU"), 1))
TABLES = ("tlm_hoheitsgebiet", "tlm_kantonsgebiet", "tlm_landesgebiet")


class BoundaryError(ValueError):
    pass


def decode_geometry(blob):
    """GP header + native WKB; preserve multipart outlines and interior holes."""
    if not isinstance(blob, bytes) or not 13 <= len(blob) <= MAX_GEOMETRY_BYTES or blob[:3] != b"GP\x00":
        raise BoundaryError("boundary_geometry_invalid")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope > 4:
        raise BoundaryError("boundary_geometry_unsupported")
    endian = "<" if flags & 1 else ">"
    if struct.unpack_from(endian + "i", blob, 4)[0] != 2056:
        raise BoundaryError("boundary_crs_unsupported")
    offset = 8 + (0, 32, 48, 48, 64)[envelope]
    try:
        geometry = shapely.from_wkb(blob[offset:], on_invalid="raise")
    except (ValueError, shapely.errors.GEOSException) as exc:
        raise BoundaryError("boundary_geometry_invalid") from exc
    if geometry.geom_type != "MultiPolygon" or geometry.is_empty or not geometry.is_valid:
        raise BoundaryError("boundary_geometry_invalid")
    # The dataset's Z is terrain elevation, not an airspace applicability limit.
    # Administrative membership is explicitly two-dimensional.
    bounds = geometry.bounds
    if not all(math.isfinite(v) for v in bounds) or not (2400000 <= bounds[0] <= bounds[2] <= 2900000
                                                         and 1000000 <= bounds[1] <= bounds[3] <= 1400000):
        raise BoundaryError("boundary_region_unsupported")
    return shapely.force_2d(geometry)


@dataclass(frozen=True)
class Municipality:
    code: str
    canton: str
    name: str
    geometry: object


@dataclass(frozen=True)
class LocationProof:
    state: str
    reason: str
    version: str
    sha256: str
    attribution: str = ATTRIBUTION
    municipality_code: str | None = None
    municipality_name: str | None = None
    # This proves the centre/municipality selection, not source warning coverage
    # or that the whole configured radius lies inside Switzerland.
    radius_coverage_verified: bool = False


@dataclass(frozen=True)
class BoundaryCatalogue:
    version: str
    sha256: str
    valid_from: date
    expires_on: date
    municipalities: object
    cantons: object
    country: object

    def verify_location(self, location, *, on_date):
        def result(state, reason, municipality=None):
            return LocationProof(state, reason, self.version, self.sha256,
                municipality_code=municipality.code if municipality else None,
                municipality_name=municipality.name if municipality else None)

        if type(on_date) is not date or not self.valid_from <= on_date < self.expires_on:
            return result("unavailable", "boundary_version_outside_review")
        if isinstance(location, MunicipalityLocation):
            entry = self.municipalities.get(location.municipality_code)
            if entry is None:
                return result("unavailable", "municipality_not_in_version")
            if entry.canton != location.canton:
                return result("no_match", "municipality_canton_mismatch")
            return result("verified", "municipality_in_version", entry)
        if not isinstance(location, PointLocation):
            return result("unavailable", "location_not_supported")
        if network.is_network_enabled():
            return result("unavailable", "boundary_projection_network_enabled")
        try:
            projection = Transformer.from_crs(4326, 2056, always_xy=True, allow_ballpark=False, only_best=True)
            if projection.accuracy < 0 or projection.accuracy > 5:
                return result("unavailable", "boundary_projection_accuracy_unknown")
            x, y = projection.transform(location.longitude, location.latitude, errcheck=True)
        except Exception:
            return result("unavailable", "boundary_projection_unavailable")
        point = Point(x, y)
        tolerance = projection.accuracy + 0.5  # Dataset's stated positional accuracy.
        if self.country.boundary.distance(point) <= tolerance:
            return result("unavailable", "national_border_uncertain")
        if not self.country.covers(point):
            return result("no_match", "outside_switzerland")
        canton = self.cantons.get(location.canton)
        if canton is None:
            return result("unavailable", "canton_not_in_version")
        if canton.boundary.distance(point) <= tolerance:
            return result("unavailable", "canton_border_uncertain")
        if not canton.covers(point):
            return result("no_match", "point_canton_mismatch")
        matches = [m for m in self.municipalities.values() if m.canton == location.canton and m.geometry.covers(point)]
        if len(matches) != 1 or matches[0].geometry.boundary.distance(point) <= tolerance:
            return result("unavailable", "municipality_border_or_unassigned_area")
        return result("verified", "point_in_municipality", matches[0])


def load_geopackage(payload, *, sha256, version, expires_on):
    """Load an explicitly reviewed immutable edition; never silently choose latest."""
    if (not isinstance(payload, bytes) or not 100 <= len(payload) <= MAX_PACKAGE_BYTES
            or not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
            or hashlib.sha256(payload).hexdigest() != sha256):
        raise BoundaryError("boundary_asset_hash_invalid")
    if not isinstance(version, str) or re.fullmatch(r"\d{4}-\d{2}", version) is None:
        raise BoundaryError("boundary_version_invalid")
    try:
        valid_from = date.fromisoformat(version + "-01")
    except ValueError as exc:
        raise BoundaryError("boundary_version_invalid") from exc
    if type(expires_on) is not date or expires_on <= valid_from:
        raise BoundaryError("boundary_review_expiry_invalid")
    municipalities, cantons, countries = {}, {}, []
    # Deserialize exactly the hashed bytes; avoid changing a pathname between
    # hash verification and a subsequent SQLite read. No extensions or source SQL.
    with closing(sqlite3.connect(":memory:")) as db:
        try:
            db.deserialize(payload)
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA query_only=ON")
        except sqlite3.Error as exc:
            raise BoundaryError("boundary_package_invalid") from exc
        work = [20000]

        def progress():
            work[0] -= 1
            return int(work[0] < 0)

        db.set_progress_handler(progress, 1000)
        try:
            for table in (*TABLES, "gpkg_geometry_columns"):
                if db.execute("SELECT type FROM sqlite_master WHERE name=?", (table,)).fetchall() != [("table",)]:
                    raise BoundaryError("boundary_schema_invalid")
            for table in TABLES:
                schema = db.execute("SELECT column_name,geometry_type_name,srs_id,z,m FROM gpkg_geometry_columns WHERE table_name=?", (table,)).fetchall()
                if schema != [("geom", "MULTIPOLYGON", 2056, 1, 0)]:
                    raise BoundaryError("boundary_schema_invalid")
            rows = db.execute("SELECT bfs_nummer,kantonsnummer,name,geom FROM tlm_hoheitsgebiet WHERE icc='CH' AND objektart='Gemeindegebiet' LIMIT 3001").fetchall()
            if not 1 <= len(rows) <= 3000:
                raise BoundaryError("boundary_municipality_limit")
            for code, canton, name, blob in rows:
                if (type(code) is not int or not 1 <= code <= 9999 or str(code) in municipalities
                        or canton not in CANTONS or not isinstance(name, str) or not 1 <= len(name) <= 100):
                    raise BoundaryError("boundary_municipality_invalid")
                municipalities[str(code)] = Municipality(str(code), CANTONS[canton], name, decode_geometry(blob))
            for code, blob in db.execute("SELECT kantonsnummer,geom FROM tlm_kantonsgebiet WHERE icc='CH' LIMIT 27"):
                if code not in CANTONS or CANTONS[code] in cantons:
                    raise BoundaryError("boundary_canton_invalid")
                cantons[CANTONS[code]] = decode_geometry(blob)
            if set(cantons) != set(CANTONS.values()):
                raise BoundaryError("boundary_canton_coverage_incomplete")
            countries = db.execute("SELECT geom FROM tlm_landesgebiet WHERE icc='CH' LIMIT 2").fetchall()
            if len(countries) != 1:
                raise BoundaryError("boundary_country_invalid")
            country = decode_geometry(countries[0][0])
        except sqlite3.Error as exc:
            raise BoundaryError("boundary_package_invalid") from exc
    return BoundaryCatalogue(version, sha256, valid_from, expires_on,
        MappingProxyType(municipalities), MappingProxyType(cantons), country)
