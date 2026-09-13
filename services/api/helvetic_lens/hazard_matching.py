"""Private locations versus CAP areas, with native administrative topology.

CAP Suisse administrative codes are filters and may name only partly affected
territory. They must never enlarge a supplied polygon to a whole municipality or
turn a point candidate into an exact hit. A whole-municipality watch can match its
explicit code, with administrative_filter basis rather than a fabricated outline.
"""

import math
import re
from dataclasses import dataclass, replace

import shapely
from pyproj import Transformer, network
from pyproj.exceptions import ProjError
from shapely.geometry import Point, Polygon

from .hazard_contracts import MunicipalityLocation, PointLocation
from .hazard_geometry import EARTH_KM, match_radius, valid_polygon

COMMUNE = "Swiss official commune register"
CANTON = "Cantonabbreviations"
COUNTRY = "ISO 3166-1 alpha-2"
ADMIN_CODES = {COMMUNE, CANTON, COUNTRY}
MAX_PROJECTED_POINTS = 200_000


@dataclass(frozen=True)
class HazardMatch:
    state: str
    reason: str
    basis: str
    boundary_version: str
    boundary_sha256: str


class ProjectionUnavailable(ValueError):
    pass


class Projector:
    """Bounded local projection with densely sampled CAP curves.

    No source polygon is repaired. Joint dataset/projection precision controls
    the near-boundary unknown band; projected interpolation is refined to 5 cm
    with a maximum 0.001-degree segment span. Circle chords are sampled to a
    5 cm sagitta before this refinement. Resource limits remain unknown.
    """
    def __init__(self):
        if network.is_network_enabled():
            raise ProjectionUnavailable()
        self.transformer = Transformer.from_crs(4326, 2056, always_xy=True,
                                               allow_ballpark=False, only_best=True)
        if not 0 <= self.transformer.accuracy <= 5:
            raise ProjectionUnavailable()
        self.margin = self.transformer.accuracy + 0.6
        self.remaining = MAX_PROJECTED_POINTS

    def point(self, position):
        self.remaining -= 1
        if self.remaining < 0:
            raise ProjectionUnavailable()
        lat, lon = position
        coordinates = self.transformer.transform(lon, lat, errcheck=True)
        if not all(math.isfinite(value) for value in coordinates):
            raise ProjectionUnavailable()
        return coordinates

    def polygon(self, ring):
        output = []

        def segment(a, b, aa, bb, depth=0):
            middle = tuple((x + y) / 2 for x, y in zip(a, b))
            mm = self.point(middle)
            error = math.hypot(mm[0] - (aa[0] + bb[0]) / 2, mm[1] - (aa[1] + bb[1]) / 2)
            if max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 0.001 and error <= 0.05:
                output.append(aa)
                return
            if depth >= 20:
                raise ProjectionUnavailable()
            segment(a, middle, aa, mm, depth + 1)
            segment(middle, b, mm, bb, depth + 1)

        for a, b in zip(ring, ring[1:]):
            segment(a, b, self.point(a), self.point(b))
        geometry = Polygon(output)
        if geometry.is_empty or not geometry.is_valid:
            raise ProjectionUnavailable()
        return geometry

    def circle(self, latitude, longitude, radius_km):
        if (not all(math.isfinite(v) for v in (latitude, longitude, radius_km))
                or not 44 <= latitude <= 49 or not 4 <= longitude <= 12 or not 0 <= radius_km <= 1000):
            raise ProjectionUnavailable()
        if radius_km == 0:
            return Point(self.point((latitude, longitude)))
        count = max(16, math.ceil(math.pi * math.sqrt(radius_km * 1000 / 0.1)))
        if count > self.remaining:
            raise ProjectionUnavailable()
        lat, lon, angular = math.radians(latitude), math.radians(longitude), radius_km / EARTH_KM
        points = []
        for index in range(count):
            bearing = 2 * math.pi * index / count
            y = math.asin(math.sin(lat) * math.cos(angular) + math.cos(lat) * math.sin(angular) * math.cos(bearing))
            x = lon + math.atan2(math.sin(bearing) * math.sin(angular) * math.cos(lat),
                                math.cos(angular) - math.sin(lat) * math.sin(y))
            points.append((math.degrees(y), math.degrees(x)))
        return self.polygon((*points, points[0]))


def _intersection(target, source, margin):
    if target.distance(source) > margin:
        return "no_match"
    if source.geom_type == "Point":
        if target.covers(source) and target.boundary.distance(source) > margin:
            return "match"
    elif target.buffer(-margin).intersects(source.buffer(-margin)):
        return "match"
    return "unavailable"


def match_location(areas, location, catalogue, *, on_date, geocode_version=None):
    def result(state, reason, basis="geography"):
        return HazardMatch(state, reason, basis, catalogue.version, catalogue.sha256)

    proof = catalogue.verify_location(location, on_date=on_date)
    if proof.state != "verified":
        return result("unavailable", proof.reason, "location")
    if (len(areas) > 64 or sum(len(p) for a in areas for p in a.polygons) > 2000
            or sum(len(a.circles) + len(a.geocodes) for a in areas) > 2000):
        return result("unavailable", "geometry_limit")
    unknown, candidate = not bool(areas), False
    projector, private_geometry = None, None
    code_results = {}

    def projected():
        nonlocal projector
        if projector is None:
            projector = Projector()
        return projector

    target = catalogue.municipalities[location.municipality_code].geometry if isinstance(location, MunicipalityLocation) else None

    def region_filter(region):
        nonlocal private_geometry
        if target is not None:
            return _intersection(target, region, 0.5)
        projection = projected()
        if private_geometry is None:
            private_geometry = projection.circle(location.latitude, location.longitude, location.radius_km)
        return _intersection(region, private_geometry, projection.margin)

    def code_filter(name, value):
        if geocode_version != catalogue.version:
            return "unavailable", False
        if name == COMMUNE:
            if re.fullmatch(r"[1-9][0-9]{0,3}", value) is None or value not in catalogue.municipalities:
                return "unavailable", False
            entry = catalogue.municipalities[value]
            if isinstance(location, MunicipalityLocation):
                return ("match", True) if value == location.municipality_code else ("no_match", False)
            return region_filter(entry.geometry), False
        if name == CANTON:
            if value in {"CH", "FL"}:
                return ("match" if value == "CH" else "no_match"), False
            region = catalogue.cantons.get(value)
            return (region_filter(region), False) if region is not None else ("unavailable", False)
        if name == COUNTRY:
            return ("match" if value == "CH" else "no_match" if value in {"LI", "DE", "FR", "IT", "AT"}
                    else "unavailable"), False
        return "unavailable", False

    for area in areas:
        if area.altitude is not None or area.ceiling is not None:
            unknown = True
            continue
        explicit = bool(area.polygons or area.circles)
        if explicit and isinstance(location, PointLocation):
            # CAP Suisse admin filters must not turn a point outside an explicit
            # hazard outline into a hit for every address in the named canton.
            exact = match_radius((replace(area, geocodes=()),), latitude=location.latitude,
                                 longitude=location.longitude, radius_km=location.radius_km)
            if exact.state == "match":
                return result("match", exact.reason, "explicit_geometry")
            unknown |= exact.state == "unavailable"
        elif explicit:
            try:
                projection = projected()
                for ring in area.polygons:
                    if not valid_polygon(ring):
                        unknown = True
                        continue
                    relation = _intersection(target, projection.polygon(ring), projection.margin)
                    if relation == "match":
                        return result("match", "municipality_polygon_intersection", "explicit_geometry")
                    unknown |= relation == "unavailable"
                for circle in area.circles:
                    relation = _intersection(target, projection.circle(*circle), projection.margin)
                    if relation == "match":
                        return result("match", "municipality_circle_intersection", "explicit_geometry")
                    unknown |= relation == "unavailable"
            except (ValueError, ProjError, shapely.errors.GEOSException):
                unknown = True
        if not explicit and not area.geocodes:
            unknown = True
        for name, value in area.geocodes:
            if explicit and name in ADMIN_CODES:
                continue  # Descriptive filter; geometry already supplies extent.
            if explicit:
                unknown = True  # Unresolved warning-region coding is not an administrative label.
                continue
            try:
                if (name, value) not in code_results:
                    code_results[name, value] = code_filter(name, value)
                relation, whole_municipality = code_results[name, value]
            except (ValueError, ProjError, shapely.errors.GEOSException):
                relation, whole_municipality = "unavailable", False
            if relation == "match" and whole_municipality:
                return result("match", "municipality_named_by_source", "administrative_filter")
            candidate |= relation == "match"
            unknown |= relation == "unavailable"
    if candidate:
        return result("unavailable", "administrative_filter_without_precise_extent", "administrative_filter")
    return (result("unavailable", "geography_unresolved") if unknown else
            result("no_match", "outside_declared_scope"))
