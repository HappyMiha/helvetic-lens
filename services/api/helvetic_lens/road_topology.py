"""Exact matching against a reviewed, versioned normalized TMC projection.

This is not a parser for an unseen licensed ASTRA delivery, a source permission
or a route planner. An operator must verify the native table, links, distances
and corridor labels before publishing this internal projection. Missing geometry
never falls back to road names, location-code order, compass guesses or GPS lines.
"""

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .road_feed import RoadLocation

MAX_POINTS = 100_000
MAX_PATH_POINTS = 10_000


class TopologyError(ValueError):
    pass


class TmcPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: int = Field(ge=0, le=1_000_000_000)
    positive: int | None = Field(default=None, ge=0, le=1_000_000_000)
    negative: int | None = Field(default=None, ge=0, le=1_000_000_000)
    # Reviewed distance along this link, not straight-line distance between points.
    distance_to_positive_m: int | None = Field(default=None, gt=0, le=1_000_000_000)


class TopologyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    country: str = Field(min_length=1, max_length=16)
    table: str = Field(min_length=1, max_length=16)
    version: str = Field(min_length=1, max_length=64)
    points: tuple[TmcPoint, ...] = Field(min_length=1, max_length=MAX_POINTS)


class CorridorFlow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    # This label is operator-reviewed. "northbound" need not follow positive links.
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    points: tuple[int, ...] = Field(min_length=2, max_length=MAX_PATH_POINTS)
    start_offset_m: int = Field(default=0, ge=0, le=1_000_000_000)
    end_offset_m: int = Field(default=0, ge=0, le=1_000_000_000)


@dataclass(frozen=True)
class RoadSlice:
    # Canonical positive-link endpoints. Their numeric order is irrelevant.
    edge: tuple[int, int]
    positive: bool
    start_m: int
    end_m: int | None
    point: bool = False


@dataclass(frozen=True)
class ResolvedCorridor:
    topology_hash: str
    key: str
    points: tuple[int, ...]
    slices: tuple[RoadSlice, ...]


@dataclass(frozen=True)
class RoadIntersection:
    state: Literal["match", "no_match", "unknown"]
    reason: str
    edges: tuple[tuple[int, int], ...] = ()


def _fail(code):
    raise TopologyError(code)


class TmcTopology:
    def __init__(self, definition: TopologyDefinition):
        # Revalidate model_copy/construct output at this internal trust boundary.
        definition = TopologyDefinition.model_validate(definition.model_dump(mode="python"), strict=True)
        if any(value != value.strip() for value in (definition.country, definition.table, definition.version)):
            _fail("topology_identity_invalid")
        self.key = (definition.country, definition.table, definition.version)
        points = {point.code: point for point in definition.points}
        if len(points) != len(definition.points):
            _fail("topology_duplicate_point")
        for point in points.values():
            if point.code in (point.positive, point.negative):
                _fail("topology_self_link")
            if point.positive is not None and point.positive == point.negative:
                _fail("topology_ambiguous_link")
            for target, inverse in ((point.positive, "negative"), (point.negative, "positive")):
                if target is not None and (target not in points or getattr(points[target], inverse) != point.code):
                    _fail("topology_nonreciprocal_link")
            if point.positive is None and point.distance_to_positive_m is not None:
                _fail("topology_distance_without_link")
        # Keep graph implementation private so a resolved flow cannot be silently
        # retargeted by mutating the original Pydantic definition or input sequence.
        self._points = MappingProxyType(points)
        components, positions, circular = {}, {}, set()
        for code in points:
            if code in components:
                continue
            pending, members = [code], []
            while pending:
                current = pending.pop()
                if current in components:
                    continue
                components[current] = code
                members.append(current)
                pending.extend(target for target in (points[current].positive, points[current].negative)
                               if target is not None and target not in components)
            starts = [item for item in members if points[item].negative is None]
            if not starts:
                circular.add(code)
            else:
                current, position = starts[0], 0
                while current is not None:
                    positions[current] = position
                    current, position = points[current].positive, position + 1
        self._components = MappingProxyType(components)
        self._positions = MappingProxyType(positions)
        self._circular = frozenset(circular)
        canonical = {"country": definition.country, "table": definition.table, "version": definition.version,
                     "points": [points[key].model_dump(mode="json") for key in sorted(points)]}
        self.sha256 = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _walk(self, start, end, positive):
        path, visited = [], set()
        current = start
        while current is not None and current not in visited:
            if len(path) >= MAX_PATH_POINTS:
                _fail("topology_path_limit")
            visited.add(current)
            path.append(current)
            if current == end:
                return tuple(path)
            current = self._points[current].positive if positive else self._points[current].negative
        return None

    def _edge(self, first, second):
        point = self._points[first]
        if point.positive == second:
            return (first, second), True, point.distance_to_positive_m
        if point.negative == second:
            return (second, first), False, self._points[second].distance_to_positive_m
        _fail("topology_nonadjacent_path")

    def _slices(self, path, start_offset, end_offset):
        edges = [self._edge(first, second) for first, second in zip(path, path[1:])]
        if start_offset == end_offset == 0:
            return tuple(RoadSlice(key, positive, 0, length) for key, positive, length in edges)
        if any(length is None for _, _, length in edges):
            _fail("topology_offset_distance_unknown")
        total = sum(length for _, _, length in edges)
        if start_offset + end_offset > total:
            _fail("topology_offsets_outside_extent")
        end, position = total - end_offset, 0
        result = []
        for key, positive, length in edges:
            low, high = max(start_offset, position), min(end, position + length)
            is_point = start_offset == end
            if high > low or (is_point and high == low):
                a, b = low - position, high - position
                result.append(RoadSlice(key, positive, a if positive else length - b,
                                        b if positive else length - a, is_point))
            position += length
        return tuple(result)

    def resolve_corridor(self, flow: CorridorFlow) -> ResolvedCorridor:
        flow = CorridorFlow.model_validate(flow.model_dump(mode="python"), strict=True)
        if len(set(flow.points)) != len(flow.points):
            _fail("corridor_repeated_point")
        if any(point not in self._points for point in flow.points):
            _fail("corridor_point_unknown")
        slices = self._slices(flow.points, flow.start_offset_m, flow.end_offset_m)
        if not slices or all(item.point or item.end_m == item.start_m for item in slices):
            _fail("corridor_empty_extent")
        return ResolvedCorridor(self.sha256, flow.key, flow.points, slices)

    def intersection(self, location: RoadLocation | None, corridor: ResolvedCorridor) -> RoadIntersection:
        if corridor.topology_hash != self.sha256:
            return RoadIntersection("unknown", "corridor_topology_mismatch")
        if location is None:
            return RoadIntersection("unknown", "location_unavailable")
        if (location.country, location.table, location.version) != self.key:
            return RoadIntersection("unknown", "location_topology_mismatch")
        if location.direction not in {"positive", "negative", "both"}:
            return RoadIntersection("unknown", "location_direction_unknown")
        if location.primary not in self._points or location.secondary not in self._points:
            return RoadIntersection("unknown", "location_point_unknown")
        if any(type(offset) is not int or offset < 0 for offset in (location.primary_offset_m, location.secondary_offset_m)):
            return RoadIntersection("unknown", "location_offset_invalid")
        if location.primary == location.secondary:
            if location.primary_offset_m or location.secondary_offset_m:
                return RoadIntersection("unknown", "location_offset_invalid")
            candidates = []
            for item in corridor.slices:
                key = item.edge
                length = self._points[key[0]].distance_to_positive_m
                touches = (key[0] == location.primary and item.start_m == 0) or (
                    key[1] == location.primary and (item.end_m is None or item.end_m == length))
                if touches and _same_direction(location.direction, item.positive):
                    candidates.append(key)
            return RoadIntersection("match" if candidates else "no_match", "point_intersection" if candidates
                                    else "outside_corridor_direction", tuple(sorted(set(candidates))))
        try:
            # A ring needs the explicitly supported direction-sense capability;
            # the decoder currently flags that field as unsupported. Do not select
            # one of two possible arcs merely from an affected-flow label.
            component = self._components[location.primary]
            if component != self._components[location.secondary]:
                return RoadIntersection("unknown", "location_path_unresolved")
            if component in self._circular:
                return RoadIntersection("unknown", "location_circular_extent")
            positive = self._positions[location.secondary] < self._positions[location.primary]
            if location.direction != "both" and positive != (location.direction == "positive"):
                return RoadIntersection("unknown", "location_path_unresolved")
            path = self._walk(location.secondary, location.primary, positive)
            slices = self._slices(path, location.secondary_offset_m, location.primary_offset_m)
        except TopologyError as error:
            return RoadIntersection("unknown", str(error))
        selected = {item.edge: item for item in corridor.slices if _same_direction(location.direction, item.positive)}
        intersections = []
        for item in slices:
            other = selected.get(item.edge)
            if other is None:
                continue
            low = max(item.start_m, other.start_m)
            ends = [end for end in (item.end_m, other.end_m) if end is not None]
            high = min(ends) if ends else None
            if high is None or high > low or (item.point and high == low):
                intersections.append(item.edge)
        return RoadIntersection("match" if intersections else "no_match", "segment_intersection" if intersections
                                else "outside_corridor_direction", tuple(sorted(set(intersections))))


def _same_direction(source_direction, positive):
    return source_direction == "both" or (source_direction == "positive") == positive
