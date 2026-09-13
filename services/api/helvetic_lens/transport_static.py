"""Read exact legs from a pinned Swiss GTFS archive in a background import.

Never extract archive paths or load the multi-gigabyte stop-times file in memory.
This is an import boundary, not a request-time journey planner. Callers persist
resolved legs with their archive hash and must not relabel them to a new feed.
"""

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from io import TextIOWrapper
from zipfile import ZipFile

from .transport_reference import VerifiedLeg, service_instant, service_seconds

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MAX_ARCHIVE = 512_000_000
MAX_EXPANDED = 6_000_000_000


def gtfs_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError("Invalid GTFS date")
    return datetime.strptime(value, "%Y%m%d").date()


def identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("Invalid GTFS identifier")
    return value


@dataclass(frozen=True)
class LegRequest:
    trip_id: str
    service_day: date
    boarding_sequence: int
    alighting_sequence: int

    def __post_init__(self):
        identifier(self.trip_id)
        if type(self.service_day) is not date:
            raise ValueError("An explicit service date is required")
        if any(type(s) is not int or s < 0 for s in (self.boarding_sequence, self.alighting_sequence)):
            raise ValueError("Invalid stop sequence")
        if self.boarding_sequence >= self.alighting_sequence:
            raise ValueError("Boarding must precede alighting")


@dataclass(frozen=True)
class ResolvedLeg:
    reference: VerifiedLeg
    archive_sha256: str
    departure: datetime
    arrival: datetime
    boarding_name: str
    alighting_name: str
    route_name: str
    stop_sequences: tuple[int, ...] = ()


class StaticArchive:
    """Strict UTF-8 CSV import; bounds include actual decompressed member sizes."""

    def __init__(self, path, *, expected_version, checkpoint=lambda: None):
        self.version = identifier(expected_version)
        self.path = path
        self.sha256 = None
        self.archive = None
        self.checkpoint = checkpoint

    def __enter__(self):
        digest, size = hashlib.sha256(), 0
        with open(self.path, "rb") as stream:
            while chunk := stream.read(1024 * 1024):
                self.checkpoint()
                size += len(chunk)
                if size > MAX_ARCHIVE:
                    raise ValueError("GTFS archive exceeded size bound")
                digest.update(chunk)
        self.sha256 = digest.hexdigest()
        self.archive = ZipFile(self.path)
        try:
            members = self.archive.infolist()
            names = [member.filename for member in members]
            if (
                len(names) > 40
                or len(set(names)) != len(names)
                or any(not re.fullmatch(r"[a-z_]+\.txt", name) for name in names)
                or sum(member.file_size for member in members) > MAX_EXPANDED
                or any(member.flag_bits & 1 for member in members)
            ):
                raise ValueError("Unsupported GTFS archive structure")
            info = list(self.rows("feed_info.txt", {"feed_version", "feed_start_date", "feed_end_date"}, limit=1))
            if len(info) != 1 or info[0]["feed_version"] != self.version:
                raise ValueError("Static archive does not match realtime feed version")
            self.start = gtfs_date(info[0]["feed_start_date"])
            self.end = gtfs_date(info[0]["feed_end_date"])
            if self.start > self.end:
                raise ValueError("Invalid feed date range")
            return self
        except Exception:
            self.archive.close()
            raise

    def __exit__(self, *args):
        self.archive.close()

    def rows(self, name, columns, *, limit=50_000_000):
        self.checkpoint()
        if name not in self.archive.namelist():
            raise ValueError(f"Missing GTFS table: {name}")
        with self.archive.open(name) as member, TextIOWrapper(member, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            fields = reader.fieldnames or []
            if len(set(fields)) != len(fields) or not columns.issubset(fields):
                raise ValueError(f"Invalid GTFS columns: {name}")
            for index, row in enumerate(reader):
                if index % 16384 == 0:
                    self.checkpoint()
                if index >= limit or None in row or any(v is None for v in row.values()):
                    raise ValueError(f"Invalid or oversized GTFS table: {name}")
                yield row

    def active_services(self, services, days):
        """Resolve exact service dates for import and catalogue renewal alike."""
        if len(services) * len(days) > 200_000:
            raise ValueError("Service-date expansion exceeds import bound")
        calendar, exceptions = {}, {}
        for row in self.rows("calendar.txt", {"service_id", "start_date", "end_date", *WEEKDAYS}):
            if row["service_id"] in services:
                if row["service_id"] in calendar or any(row[day] not in {"0", "1"} for day in WEEKDAYS):
                    raise ValueError("Ambiguous service calendar")
                if gtfs_date(row["start_date"]) > gtfs_date(row["end_date"]):
                    raise ValueError("Invalid service calendar range")
                calendar[row["service_id"]] = row
        for row in self.rows("calendar_dates.txt", {"service_id", "date", "exception_type"}):
            if row["service_id"] in services:
                day = gtfs_date(row["date"])
                if day in days:
                    key = (row["service_id"], day)
                    if key in exceptions or row["exception_type"] not in {"1", "2"}:
                        raise ValueError("Ambiguous service exception")
                    exceptions[key] = row["exception_type"]
        active_pairs = set()
        for service in services:
            regular = calendar.get(service)
            for day in days:
                active = regular is not None and (
                    gtfs_date(regular["start_date"]) <= day <= gtfs_date(regular["end_date"])
                    and regular[WEEKDAYS[day.weekday()]] == "1"
                )
                exception = exceptions.get((service, day))
                if exception == "1" or active and exception != "2":
                    active_pairs.add((service, day))
        return active_pairs

    def resolve(self, requests: tuple[LegRequest, ...]) -> tuple[ResolvedLeg, ...]:
        if not requests or len(requests) > 32 or len(set(requests)) != len(requests):
            raise ValueError("Import one to 32 distinct legs")
        if any(not self.start <= request.service_day <= self.end for request in requests):
            raise ValueError("Requested service date is outside this feed")
        wanted = {request.trip_id for request in requests}
        trips = {}
        for row in self.rows("trips.txt", {"trip_id", "route_id", "service_id", "direction_id"}):
            if row["trip_id"] in wanted:
                if row["trip_id"] in trips or row["direction_id"] not in {"", "0", "1"}:
                    raise ValueError("Ambiguous trip identity")
                trips[row["trip_id"]] = row
        if trips.keys() != wanted:
            raise ValueError("Unknown trip in this static version")
        if "frequencies.txt" in self.archive.namelist():
            for row in self.rows("frequencies.txt", {"trip_id"}):
                if row["trip_id"] in wanted:
                    raise ValueError("Frequency trips require a separate departure-instance contract")
        services = {identifier(row["service_id"]) for row in trips.values()}
        active = self.active_services(services, {request.service_day for request in requests})
        for request in requests:
            if (trips[request.trip_id]["service_id"], request.service_day) not in active:
                raise ValueError("Trip does not operate on the selected service day")
        routes = {}
        route_ids = {identifier(row["route_id"]) for row in trips.values()}
        for row in self.rows("routes.txt", {"route_id", "agency_id", "route_short_name", "route_long_name"}):
            if row["route_id"] in route_ids:
                if row["route_id"] in routes:
                    raise ValueError("Duplicate route")
                routes[row["route_id"]] = row
        if routes.keys() != route_ids:
            raise ValueError("Unknown route")
        agency_ids = {identifier(row["agency_id"]) for row in routes.values()}
        agencies = {}
        for row in self.rows("agency.txt", {"agency_id", "agency_timezone"}):
            if row["agency_id"] in agency_ids:
                if row["agency_id"] in agencies or row["agency_timezone"] not in {"Europe/Zurich", "Europe/Berlin"}:
                    raise ValueError("Unsupported or ambiguous agency timezone")
                agencies[row["agency_id"]] = row
        if agencies.keys() != agency_ids:
            raise ValueError("Unknown agency")
        stop_times = {trip: {} for trip in wanted}
        for row in self.rows("stop_times.txt", {"trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time", "pickup_type", "drop_off_type"}):
            if row["trip_id"] in wanted:
                if not re.fullmatch(r"[0-9]{1,8}", row["stop_sequence"]):
                    raise ValueError("Invalid stop sequence")
                seq = int(row["stop_sequence"])
                times = stop_times[row["trip_id"]]
                if seq in times or len(times) >= 2000:
                    raise ValueError("Ambiguous or oversized trip stop list")
                times[seq] = row
        selected = []
        for request in requests:
            times = stop_times[request.trip_id]
            if request.boarding_sequence not in times or request.alighting_sequence not in times:
                raise ValueError("Selected stop sequence is absent")
            segment = [times[seq] for seq in sorted(times) if request.boarding_sequence <= seq <= request.alighting_sequence]
            if segment[0]["pickup_type"] not in {"", "0"} or segment[-1]["drop_off_type"] not in {"", "0"}:
                raise ValueError("Selected leg requires unavailable or conditional boarding/alighting")
            previous = None
            for row in segment:
                arrive, depart = service_seconds(row["arrival_time"]), service_seconds(row["departure_time"])
                if arrive > depart or previous is not None and arrive < previous:
                    raise ValueError("Non-monotonic scheduled stop times")
                previous = depart
            selected.append(segment)
        stop_ids = {row["stop_id"] for segment in selected for row in segment}
        stops = {}
        # Keep the bounded stop catalogue to validate explicit parents as well.
        for row in self.rows("stops.txt", {"stop_id", "stop_name", "parent_station", "location_type"}, limit=300_000):
            key = identifier(row["stop_id"])
            if key in stops:
                raise ValueError("Duplicate stop identity")
            stops[key] = row
        if not stop_ids.issubset(stops):
            raise ValueError("Unknown stop")
        resolved = []
        for request, segment in zip(requests, selected, strict=True):
            trip = trips[request.trip_id]
            route = routes[trip["route_id"]]
            parents = set()
            for row in segment:
                stop = stops[row["stop_id"]]
                if stop["location_type"] not in {"", "0"}:
                    raise ValueError("Selected stop is not a boarding location")
                parent = stop["parent_station"]
                if parent:
                    if parent not in stops or stops[parent]["location_type"] != "1":
                        raise ValueError("Unverified parent station")
                    parents.add(parent)
            first, last = segment[0], segment[-1]
            departure = service_instant(request.service_day, first["departure_time"])
            arrival = service_instant(request.service_day, last["arrival_time"])
            if departure >= arrival:
                raise ValueError("Selected leg has no positive journey duration")
            resolved.append(ResolvedLeg(
                reference=VerifiedLeg(
                    static_version=self.version, agency_id=route["agency_id"], route_id=trip["route_id"],
                    trip_id=request.trip_id, service_day=request.service_day,
                    direction_id=int(trip["direction_id"]) if trip["direction_id"] else None,
                    stop_ids=tuple(row["stop_id"] for row in segment), parent_stop_ids=tuple(sorted(parents)),
                ),
                archive_sha256=self.sha256, departure=departure, arrival=arrival,
                boarding_name=stops[first["stop_id"]]["stop_name"], alighting_name=stops[last["stop_id"]]["stop_name"],
                route_name=route["route_short_name"] or route["route_long_name"],
                stop_sequences=tuple(int(row["stop_sequence"]) for row in segment),
            ))
        return tuple(resolved)
