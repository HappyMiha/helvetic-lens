"""Local point matching for the supported Swiss CAP geometry subset.

Input pairs are WGS84 latitude/longitude, not GeoJSON coordinate order.
No address geocoding, remote lookup or implied municipal coverage occurs here.
The regional bound limits planar polygon semantics; it does not prove that a
saved point is in Switzerland. Administrative selection needs reviewed geometry.
"""

import math
from dataclasses import dataclass

REGION = (44.0, 49.0, 4.0, 12.0)
EARTH_KM = 6371.0088
EPS = 1e-10


def _inside_region(point):
    lat, lon = point
    return all(math.isfinite(v) for v in point) and REGION[0] <= lat <= REGION[1] and REGION[2] <= lon <= REGION[3]


def _cross(a, b, p):
    return (b[1] - a[1]) * (p[0] - a[0]) - (b[0] - a[0]) * (p[1] - a[1])


def _on_segment(a, b, p):
    return (abs(_cross(a, b, p)) <= EPS
            and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS
            and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS)


def _intersects(a, b, c, d):
    if (max(a[0], b[0]) + EPS < min(c[0], d[0]) or max(c[0], d[0]) + EPS < min(a[0], b[0])
            or max(a[1], b[1]) + EPS < min(c[1], d[1]) or max(c[1], d[1]) + EPS < min(a[1], b[1])):
        return False
    aa, bb, cc, dd = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if (aa > EPS and bb < -EPS or aa < -EPS and bb > EPS) and (cc > EPS and dd < -EPS or cc < -EPS and dd > EPS):
        return True
    return any((_on_segment(a, b, c), _on_segment(a, b, d), _on_segment(c, d, a), _on_segment(c, d, b)))


def valid_polygon(points):
    """Closed, simple nondegenerate regional ring; max 2000 vertices.

    This bounded check supports either winding for point containment. Canonical
    orientation and start vertex below remove representation-only changes.
    """
    if not 4 <= len(points) <= 2000 or points[0] != points[-1] or not all(_inside_region(p) for p in points):
        return False
    if len(set(points[:-1])) != len(points) - 1:
        return False
    area2 = sum(a[1] * b[0] - b[1] * a[0] for a, b in zip(points, points[1:]))
    if abs(area2) <= EPS:
        return False
    edges = tuple(zip(points, points[1:]))
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j in {i + 1, len(edges) - 1 if i == 0 else -1}:
                # Adjacent edges may meet at their shared endpoint, but cannot
                # backtrack and overlap.
                c, d = edges[j]
                if (j == i + 1 and _on_segment(a, b, d)) or (i == 0 and j == len(edges) - 1 and _on_segment(a, b, c)):
                    return False
                continue
            if _intersects(a, b, *edges[j]):
                return False
    return True


def canonical_polygon(points):
    vertices = tuple(points[:-1])
    # Coordinates themselves are evidence; do not round away changed boundaries.
    start = min(range(len(vertices)), key=vertices.__getitem__)
    forward = vertices[start:] + vertices[:start]
    reverse = (forward[0], *reversed(forward[1:]))
    chosen = min(forward, reverse)
    return (*chosen, chosen[0])


def _polygon_contains(points, point):
    inside = False
    lat, lon = point
    for a, b in zip(points, points[1:]):
        if _on_segment(a, b, point):
            return True
        if (a[0] > lat) != (b[0] > lat):
            crossing_lon = a[1] + (lat - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
            if lon < crossing_lon:
                inside = not inside
    return inside


def _distance(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(min(1, max(0, h))))


@dataclass(frozen=True)
class HazardIntersection:
    state: str
    reason: str


def _edge_within_radius(a, b, point, radius, budget):
    """Bound distance to the existing linear latitude/longitude edge.

    Distance on the sphere is 1-Lipschitz in arc length. The angular Euclidean
    length of a lat/lon segment bounds its spherical length because cos(lat)
    cannot exceed one. Midpoint distance minus half that bound therefore proves
    a miss for the entire segment. A sampled point within the radius proves a
    hit. Subdivision cannot finish a tangency numerically in every case, so a
    shared work limit returns unknown, never a guessed miss. No projected buffer
    or chord replaces the source boundary.
    """
    pending = [(a, b)]
    while pending:
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        left, right = pending.pop()
        middle = tuple((x + y) / 2 for x, y in zip(left, right))
        distance = _distance(point, middle)
        if distance <= radius + 1e-8:
            return True
        reach = EARTH_KM * math.radians(math.hypot(right[0] - left[0], right[1] - left[1])) / 2
        if distance - reach > radius + 1e-8:
            continue
        if middle in (left, right):
            return None
        pending.extend(((left, middle), (middle, right)))
    return False


def match_point(areas, *, latitude, longitude):
    return match_radius(areas, latitude=latitude, longitude=longitude, radius_km=0)


def match_radius(areas, *, latitude, longitude, radius_km):
    """Tri-state union; unknown geometry cannot become a definitive miss.

    Geocodes must be expanded through a reviewed, versioned source catalogue
    before entering this function. Names and canton abbreviations are not a
    fallback for unverified geography. Vertical restrictions need another matcher.
    Radius is a spherical distance in kilometres, bounded to the saved-place
    contract's 50 km. Zero preserves point semantics. Swiss membership/coverage
    must still be checked separately, including for circles crossing the border.
    """
    if (isinstance(latitude, bool) or isinstance(longitude, bool)
            or not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float))
            or not _inside_region((latitude, longitude))):
        return HazardIntersection("unavailable", "location_not_supported")
    if (isinstance(radius_km, bool) or not isinstance(radius_km, (int, float))
            or not math.isfinite(radius_km) or not 0 <= radius_km <= 50):
        return HazardIntersection("unavailable", "radius_not_supported")
    if (len(areas) > 64 or sum(len(p) for a in areas for p in a.polygons) > 2000
            or sum(len(a.circles) for a in areas) > 2000):
        return HazardIntersection("unavailable", "geometry_limit")
    point, unknown = (latitude, longitude), not bool(areas)
    budget = [32768]
    for area in areas:
        if area.altitude is not None or area.ceiling is not None:
            unknown = True
            continue
        unknown |= bool(area.geocodes) or not bool(area.polygons or area.circles)
        for polygon in area.polygons:
            if not valid_polygon(polygon):
                unknown = True
            elif _polygon_contains(polygon, point):
                return HazardIntersection("match", "polygon_intersection")
            elif radius_km:
                # Vertices include both ends of every edge and also establish
                # intersection when a small warning lies wholly in the radius.
                if any(_distance(point, vertex) <= radius_km + 1e-8 for vertex in polygon[:-1]):
                    return HazardIntersection("match", "polygon_radius_intersection")
                for a, b in zip(polygon, polygon[1:]):
                    intersection = _edge_within_radius(a, b, point, radius_km, budget)
                    if intersection is True:
                        return HazardIntersection("match", "polygon_radius_intersection")
                    unknown |= intersection is None
        for lat, lon, radius in area.circles:
            if not _inside_region((lat, lon)) or not math.isfinite(radius) or not 0 <= radius <= 1000:
                unknown = True
            elif _distance(point, (lat, lon)) <= radius + radius_km + 1e-8:
                return HazardIntersection("match", "circle_intersection")
    return HazardIntersection("unavailable", "geography_unresolved") if unknown else HazardIntersection("no_match", "outside_area")
