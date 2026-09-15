"""Bounded internal projection of FEDRO SOAP / DATEX II 2.2 situations.

This is not a raw-data export, a source grant, a topology resolver or an all-clear
detector. Unknown capabilities remain explicit. A collector must recheck rights,
freshness and full/delta continuity before using these internal facts.
"""

import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .road_recurrence import RoadCalendar, RoadDaily, canonical_periods

D2 = "http://datex2.eu/schema/2/2_0"
SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
MAX_BYTES = 32 * 1024 * 1024
MAX_NODES = 300_000
MAX_DEPTH = 64
MAX_SITUATIONS = 10_000
MAX_RECORDS = 50_000
PUBLIC_COMMENTS = frozenset({"description", "warning", "locationDescriptor"})


class RoadFeedError(ValueError):
    """Stable, source-text-free rejection; never log raw XML on failure."""


def _reject(code):
    raise RoadFeedError(code) from None


def _tag(name):
    return f"{{{D2}}}{name}"


def _one(parent, name, *, required=True):
    values = [] if parent is None else parent.findall(_tag(name))
    if len(values) > 1 or (required and not values):
        _reject("road_field_cardinality")
    return values[0] if values else None


def _text(parent, name, *, required=True, limit=256):
    item = _one(parent, name, required=required)
    if item is None:
        return None
    if len(item):
        _reject("road_scalar_structure")
    return _token(item.text or "", limit=limit)


def _token(value, *, limit=256):
    value = value.strip()
    if not value or len(value) > limit or any(ord(c) < 32 for c in value):
        _reject("road_invalid_scalar")
    return value


def _time(value):
    # ISO-8601 date-times with an explicit offset; date-only/naive input is unsafe.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value):
        _reject("road_invalid_time")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        _reject("road_invalid_time")


def _optional_time(parent, name):
    value = _text(parent, name, required=False)
    return None if value is None else _time(value)


def _boolean(parent, name):
    value = _text(parent, name, required=False)
    if value not in (None, "true", "false", "1", "0"):
        _reject("road_invalid_boolean")
    return None if value is None else value in ("true", "1")


def _number(parent, name, *, integer=False, required=False):
    value = _text(parent, name, required=required)
    if value is None:
        return None
    if not re.fullmatch(r"\+?\d+" if integer else r"[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?", value):
        _reject("road_invalid_number")
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or number > 1_000_000_000:
            _reject("road_invalid_number")
        return int(number) if integer else float(number)
    except (InvalidOperation, OverflowError):
        _reject("road_invalid_number")


def _shape(parent, names, unsupported, path):
    if parent is None:
        return
    if any(child.tag not in {_tag(name) for name in names} for child in parent):
        unsupported.add(path)
    # An extension may replace behavior even without adding a visible child.
    # Namespace resolution was validated during parsing; shape support is separate.
    declared = parent.get(f"{{{XSI}}}type")
    if declared:
        local = parent.tag.rsplit("}", 1)[-1]
        supported = {
            "validityTimeSpecification": {"OverallPeriod"}, "validPeriod": {"Period"}, "exceptionPeriod": {"Period"},
            "recurringTimePeriodOfDay": {"TimePeriodByHour"}, "recurringDayWeekMonthPeriod": {"DayWeekMonth"},
            "groupOfLocations": {"Linear"}, "alertCLinear": {"AlertCMethod4Linear"},
            "payloadPublication": {"SituationPublication"},
            "situationRecord": {"RoadOrCarriagewayOrLaneManagement", "AbnormalTraffic", "Accident",
                                "ConstructionWorks", "MaintenanceWorks", "WinterDrivingManagement"},
        }.get(local, {local[:1].upper() + local[1:]})
        if declared.rsplit(":", 1)[-1] not in supported:
            unsupported.add(path)


def _parse(payload):
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
        _reject("road_response_size")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        _reject("road_xml_encoding")
    declaration = re.match(r"<\?xml\s[^?]*\?>", text)
    if declaration:
        encoding = re.search(r"encoding\s*=\s*['\"]([^'\"]+)['\"]", declaration[0])
        if encoding and encoding[1].lower() not in ("utf-8", "utf8"):
            _reject("road_xml_encoding")
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        _reject("road_unsafe_xml")
    scopes, stack, pending, count = {}, [], [], 0
    try:
        parser = ET.iterparse(io.StringIO(text), events=("start-ns", "start", "end"))
        for event, value in parser:
            if event == "start-ns":
                pending.append(value)
                if len(pending) > 64:
                    _reject("road_xml_namespaces")
            elif event == "start":
                count += 1
                if count > MAX_NODES or len(stack) >= MAX_DEPTH or len(value.attrib) > 32:
                    _reject("road_xml_complexity")
                inherited = stack[-1] if stack else {}
                scope = {**inherited, **dict(pending)} if pending else inherited
                if len(scope) > 64:
                    _reject("road_xml_namespaces")
                pending.clear()
                stack.append(scope)
                scopes[value] = scope
                if f"{{{XSI}}}type" in value.attrib:
                    _type(value, scopes)
            else:
                stack.pop()
        return parser.root, scopes
    except ET.ParseError:
        _reject("road_invalid_xml")


def _type(element, scopes):
    value = _token(element.get(f"{{{XSI}}}type", ""))
    parts = value.split(":")
    if len(parts) > 2 or any(not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.-]*", part) for part in parts):
        _reject("road_invalid_type")
    prefix, name = parts if len(parts) == 2 else ("", parts[0])
    if scopes[element].get(prefix) != D2:
        _reject("road_type_namespace")
    return name


@dataclass(frozen=True)
class RoadPeriod:
    start: datetime | None
    end: datetime | None
    daily: tuple[RoadDaily, ...] = ()
    calendar: tuple[RoadCalendar, ...] = ()


@dataclass(frozen=True)
class RoadValidity:
    status: str
    overall: RoadPeriod
    periods: tuple[RoadPeriod, ...]
    exceptions: tuple[RoadPeriod, ...]
    overrunning: bool | None


@dataclass(frozen=True)
class RoadLocation:
    country: str
    table: str
    version: str
    direction: str
    primary: int
    secondary: int
    primary_offset_m: int
    secondary_offset_m: int


@dataclass(frozen=True)
class RoadComment:
    kind: str
    language: str
    text: str


@dataclass(frozen=True)
class RoadRecord:
    source_id: str
    source_version: int
    created_at: datetime
    version_at: datetime
    source_type: str
    kind: str
    source_codes: tuple[tuple[str, str], ...]
    probability: str
    severity: str | None
    confidentiality: str
    validity: RoadValidity
    cancelled: bool | None
    ended: bool | None
    location: RoadLocation | None
    delay_seconds: float | None
    lanes_restricted: int | None
    lanes_operational: int | None
    lanes_original: int | None
    comments: tuple[RoadComment, ...]
    unsupported: tuple[str, ...]

    @property
    def semantic_hash(self):
        facts = asdict(self)
        for key in ("source_id", "source_version", "created_at", "version_at"):
            facts.pop(key)
        # Keep source text verbatim in evidence, normalize only the fingerprint.
        facts["comments"] = sorted({(c.kind, c.language.lower(), " ".join(c.text.split())) for c in self.comments})
        return _digest(facts)


@dataclass(frozen=True)
class RoadSituation:
    source_id: str
    source_version: int
    development_id: str
    confidentiality: str
    information_status: str
    version_at: datetime
    records: tuple[RoadRecord, ...]
    unsupported: tuple[str, ...]

    @property
    def semantic_hash(self):
        return _digest((self.confidentiality, self.information_status, self.unsupported,
                        sorted({record.semantic_hash for record in self.records})))

    @property
    def cancelled(self):
        # Revoking one clause does not revoke the whole multi-clause situation.
        return all(record.cancelled is True for record in self.records)


@dataclass(frozen=True)
class RoadSnapshot:
    supplier: tuple[str, str]
    published_at: datetime
    received_at: datetime
    sha256: str
    situations: tuple[RoadSituation, ...]
    unsupported: tuple[str, ...]


def _digest(value):
    def encode(item):
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError("Unsupported internal road fingerprint value")

    return hashlib.sha256(json.dumps(canonical_periods(value), sort_keys=True, separators=(",", ":"), default=encode).encode()).hexdigest()


def _period(node, start, end, unsupported, path):
    _shape(node, {start, end, "periodName", "recurringTimePeriodOfDay", "recurringDayWeekMonthPeriod"}, unsupported, path)
    daily_nodes = node.findall(_tag("recurringTimePeriodOfDay"))
    calendar_nodes = node.findall(_tag("recurringDayWeekMonthPeriod"))
    if len(daily_nodes) > 16 or len(calendar_nodes) > 16:
        _reject("road_recurrence_limit")
    daily = set()
    for item in daily_nodes:
        _shape(item, {"startTimeOfPeriod", "endTimeOfPeriod"}, unsupported, path)
        if item.get(f"{{{XSI}}}type", "").rsplit(":", 1)[-1] != "TimePeriodByHour":
            unsupported.add("recurring_period")
            continue
        values = [_daily_time(_text(item, field), unsupported)
                  for field in ("startTimeOfPeriod", "endTimeOfPeriod")]
        if None in values:
            continue
        (a, offset), (b, end_offset) = values
        if offset != end_offset or a == b or a == 86400 * 1000000:
            unsupported.add("recurring_period")
            continue
        daily.add(RoadDaily(a, b, offset))
    calendars = set()
    for item in calendar_nodes:
        _shape(item, {"applicableDay", "applicableWeek", "applicableMonth"}, unsupported, path)
        values = []
        for field, vocabulary, first_index in (
            ("applicableDay", "monday tuesday wednesday thursday friday saturday sunday".split(), 0),
            ("applicableWeek", "firstWeekOfMonth secondWeekOfMonth thirdWeekOfMonth fourthWeekOfMonth fifthWeekOfMonth".split(), 1),
            ("applicableMonth", "january february march april may june july august september october november december".split(), 1),
        ):
            nodes = item.findall(_tag(field))
            if len(nodes) > len(vocabulary):
                _reject("road_recurrence_limit")
            selected = set()
            for value in nodes:
                if len(value) or (value.text or "").strip() not in vocabulary:
                    _reject("road_invalid_calendar")
                selected.add(vocabulary.index(value.text.strip()) + first_index)
            values.append(tuple(sorted(selected)))
        calendars.add(RoadCalendar(*values))
    if calendars and not daily:
        unsupported.add("recurring_period")  # No source calendar timezone.
    result = RoadPeriod(_optional_time(node, start), _optional_time(node, end),
                        tuple(sorted(daily, key=lambda p: (p.start_us, p.end_us, p.offset_minutes))),
                        tuple(sorted(calendars, key=lambda p: (p.days, p.weeks, p.months))))
    if result.start and result.end and result.end < result.start:
        _reject("road_reversed_period")
    return result


def _daily_time(value, unsupported):
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})?", value)
    if not match:
        _reject("road_invalid_recurring_time")
    h, m, s, fraction, zone = match.groups()
    h, m, s = int(h), int(m), int(s)
    micros = int((fraction or "").ljust(6, "0"))
    if h > 24 or m > 59 or s > 59 or (h == 24 and (m or s or micros)):
        _reject("road_invalid_recurring_time")
    if zone is None:
        unsupported.add("recurring_period")
        return None
    offset = 0
    if zone != "Z":
        hours, minutes = int(zone[1:3]), int(zone[4:6])
        if hours > 14 or minutes > 59 or (hours == 14 and minutes):
            _reject("road_invalid_recurring_time")
        offset = (hours * 60 + minutes) * (-1 if zone[0] == "-" else 1)
    return (h * 3600 + m * 60 + s) * 1000000 + micros, offset


def _validity(record, unsupported):
    node = _one(record, "validity")
    _shape(node, {"validityStatus", "overrunning", "validityTimeSpecification"}, unsupported, "validity")
    status = _text(node, "validityStatus")
    if status not in {"active", "suspended", "definedByValidityTimeSpec"}:
        unsupported.add("validity_status")
    spec = _one(node, "validityTimeSpecification")
    _shape(spec, {"overallStartTime", "overallEndTime", "validPeriod", "exceptionPeriod"}, unsupported, "validity_period")
    start, end = _time(_text(spec, "overallStartTime")), _optional_time(spec, "overallEndTime")
    if end and end < start:
        _reject("road_reversed_period")
    groups = []
    for name in ("validPeriod", "exceptionPeriod"):
        nodes = spec.findall(_tag(name))
        if len(nodes) > 128:
            _reject("road_period_limit")
        periods = {_period(item, "startOfPeriod", "endOfPeriod", unsupported, "recurring_period") for item in nodes}
        groups.append(tuple(sorted(periods, key=lambda p: (str(p.start), str(p.end), str(p.daily), str(p.calendar)))))
    return RoadValidity(status, RoadPeriod(start, end), *groups, _boolean(node, "overrunning"))


def _location(record, scopes, unsupported):
    group = _one(record, "groupOfLocations")
    if _type(group, scopes) != "Linear":
        unsupported.add("location_type")
        return None
    _shape(group, {"alertCLinear"}, unsupported, "location")
    alert = _one(group, "alertCLinear", required=False)
    if alert is None or _type(alert, scopes) != "AlertCMethod4Linear":
        unsupported.add("location_method")
        return None
    names = {"alertCLocationCountryCode", "alertCLocationTableNumber", "alertCLocationTableVersion",
             "alertCDirection", "alertCMethod4PrimaryPointLocation", "alertCMethod4SecondaryPointLocation"}
    _shape(alert, names, unsupported, "alert_c_location")
    direction_node = _one(alert, "alertCDirection")
    _shape(direction_node, {"alertCDirectionCoded"}, unsupported, "location_direction")
    direction = _text(direction_node, "alertCDirectionCoded")
    if direction not in {"positive", "negative", "both", "unknown"}:
        unsupported.add("location_direction")
    points = []
    for name in ("alertCMethod4PrimaryPointLocation", "alertCMethod4SecondaryPointLocation"):
        point = _one(alert, name)
        _shape(point, {"alertCLocation", "offsetDistance"}, unsupported, "location_point")
        location = _one(point, "alertCLocation")
        _shape(location, {"specificLocation"}, unsupported, "location_point")
        offset = _one(point, "offsetDistance")
        _shape(offset, {"offsetDistance"}, unsupported, "location_offset")
        points.append((_number(location, "specificLocation", integer=True, required=True),
                       _number(offset, "offsetDistance", integer=True, required=True)))
    return RoadLocation(*(_text(alert, name) for name in (
        "alertCLocationCountryCode", "alertCLocationTableNumber", "alertCLocationTableVersion")),
        direction, points[0][0], points[1][0], points[0][1], points[1][1])


def _comments(record, allowed):
    if not allowed:
        return ()
    nodes = record.findall(_tag("generalPublicComment"))
    if len(nodes) > 64:
        _reject("road_comment_limit")
    result = set()
    for node in nodes:
        kind = _text(node, "commentType", required=False)
        # Unknown/missing types, internalNote, dataProcessingNote and ambiguous
        # "other" never become public text. Never read nonGeneralPublicComment.
        if kind not in PUBLIC_COMMENTS:
            continue
        editions = _one(_one(node, "comment"), "values")
        if len(editions) > 20:
            _reject("road_language_limit")
        languages = {}
        for edition in editions:
            if edition.tag != _tag("value") or len(edition):
                _reject("road_comment_structure")
            language = _token(edition.get("lang", ""), limit=35).lower()
            if not re.fullmatch(r"[a-z]{2,8}(?:-[a-z0-9]{1,8})*", language):
                _reject("road_comment_language")
            text = edition.text or ""
            if not text.strip() or len(text.encode()) > 32768:
                _reject("road_comment_size")
            if language in languages and languages[language] != text:
                _reject("road_conflicting_language")
            languages[language] = text
            result.add(RoadComment(kind, language, text))
    return tuple(sorted(result, key=lambda c: (c.kind, c.language, c.text)))


def _classification(record, source_type, unsupported):
    fields = {
        "RoadOrCarriagewayOrLaneManagement": ("roadOrCarriagewayOrLaneManagementType",),
        "AbnormalTraffic": ("abnormalTrafficType",),
        "Accident": ("accidentType",),
        "ConstructionWorks": ("constructionWorkType",),
        "MaintenanceWorks": ("roadMaintenanceType",),
        "WinterDrivingManagement": ("winterEquipmentManagementType",),
    }
    codes = []
    for name in fields.get(source_type, ()):
        for item in record.findall(_tag(name)):
            if len(item):
                _reject("road_scalar_structure")
            codes.append((name, _token(item.text or "")))
    values = {value for _, value in codes}
    kind = "unknown"
    if source_type == "RoadOrCarriagewayOrLaneManagement":
        if len(values) != 1 or len(codes) != 1:
            _reject("road_management_type_cardinality")
        kind = {
            "roadClosed": "road_closure", "carriagewayClosures": "carriageway_closure",
            "laneClosures": "lane_restriction", "narrowLanes": "lane_restriction",
            "lanesDeviated": "lane_restriction", "roadCleared": "source_clearance",
        }.get(next(iter(values)), "unknown")
    elif source_type == "AbnormalTraffic":
        if len(codes) != 1:
            _reject("road_traffic_type_cardinality")
        if values <= {"stationaryTraffic", "queuingTraffic", "slowTraffic", "heavyTraffic"}:
            kind = "congestion"
    elif source_type == "Accident":
        kind = "accident"
    elif source_type in {"ConstructionWorks", "MaintenanceWorks"}:
        kind = "roadworks"
    if kind == "unknown":
        unsupported.add("event_type")
    return kind, tuple(sorted(set(codes))), set(fields.get(source_type, ()))


def _record(node, scopes, publication_time, confidentiality, is_real):
    unsupported = set()
    source_type = _type(node, scopes)
    kind, codes, type_fields = _classification(node, source_type, unsupported)
    _shape(node, type_fields | {"situationRecordCreationTime", "situationRecordVersionTime",
        "probabilityOfOccurrence", "severity", "confidentialityOverride", "validity", "impact",
        "generalPublicComment", "nonGeneralPublicComment", "groupOfLocations", "management"}, unsupported, "record_fields")
    created, version = (_time(_text(node, name)) for name in (
        "situationRecordCreationTime", "situationRecordVersionTime"))
    if created > version or version > publication_time + timedelta(minutes=5):
        _reject("road_record_clock")
    effective_confidentiality = _text(node, "confidentialityOverride", required=False) or confidentiality
    management = _one(node, "management", required=False)
    _shape(management, {"lifeCycleManagement"}, unsupported, "management")
    lifecycle = _one(management, "lifeCycleManagement", required=False)
    _shape(lifecycle, {"cancel", "end"}, unsupported, "lifecycle")
    impact = _one(node, "impact", required=False)
    _shape(impact, {"numberOfLanesRestricted", "numberOfOperationalLanes", "originalNumberOfLanes", "delays"},
           unsupported, "impact")
    delays = _one(impact, "delays", required=False)
    _shape(delays, {"delayTimeValue", "delayBand", "delaysType"}, unsupported, "delay")
    for name in ("delayBand", "delaysType"):
        value = _text(delays, name, required=False)
        if value is not None:
            codes += ((name, value),)
    lanes = tuple(_number(impact, name, integer=True) for name in (
        "numberOfLanesRestricted", "numberOfOperationalLanes", "originalNumberOfLanes"))
    if lanes[2] is not None and any(n is not None and n > lanes[2] for n in lanes[:2]):
        _reject("road_inconsistent_lanes")
    probability = _text(node, "probabilityOfOccurrence")
    if probability not in {"certain", "probable", "riskOf"}:
        unsupported.add("probability")
    return RoadRecord(_token(node.get("id", "")), _version(node), created, version, source_type,
        kind, tuple(sorted(codes)), probability, _text(node, "severity", required=False), effective_confidentiality,
        _validity(node, unsupported), _boolean(lifecycle, "cancel"), _boolean(lifecycle, "end"),
        _location(node, scopes, unsupported), _number(delays, "delayTimeValue"), *lanes,
        _comments(node, is_real and confidentiality == effective_confidentiality == "noRestriction"),
        tuple(sorted(unsupported)))


def _version(node):
    value = node.get("version", "")
    if not re.fullmatch(r"\d{1,18}", value):
        _reject("road_invalid_version")
    return int(value)


def decode_road_feed(payload: bytes, *, received_at: datetime) -> RoadSnapshot:
    """Decode an entire response atomically, with no implicit full/delta status.

    The caller supplies receipt time and owns the retrieval mode. Missing
    situations (including an empty valid publication) never imply cancellation.
    """
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        _reject("road_receipt_clock")
    root, scopes = _parse(payload)
    if root.tag != f"{{{SOAP}}}Envelope":
        _reject("road_soap_envelope")
    bodies = root.findall(f"{{{SOAP}}}Body")
    if len(bodies) != 1 or len(bodies[0]) != 1 or bodies[0][0].tag != _tag("d2LogicalModel"):
        _reject("road_soap_body")
    if any(n.tag not in {f"{{{SOAP}}}Header", f"{{{SOAP}}}Body"} for n in root):
        _reject("road_soap_envelope")
    headers = root.findall(f"{{{SOAP}}}Header")
    if len(headers) > 1 or any(len(header) for header in headers):
        _reject("road_soap_header")
    model = bodies[0][0]
    if model.get("modelBaseVersion") != "2":
        _reject("road_model_version")
    unsupported = set()
    _shape(model, {"exchange", "payloadPublication"}, unsupported, "model")
    exchange = _one(model, "exchange")
    supplier_node = _one(exchange, "supplierIdentification")
    supplier = tuple(_text(supplier_node, name) for name in ("country", "nationalIdentifier"))
    publication = _one(model, "payloadPublication")
    if _type(publication, scopes) != "SituationPublication":
        _reject("road_publication_type")
    _shape(publication, {"publicationTime", "publicationCreator", "situation"}, unsupported, "publication")
    creator = _one(publication, "publicationCreator")
    if tuple(_text(creator, name) for name in ("country", "nationalIdentifier")) != supplier:
        _reject("road_supplier_mismatch")
    published = _time(_text(publication, "publicationTime"))
    if published > received_at + timedelta(minutes=5):
        _reject("road_publication_clock")
    situations, ids, record_count = [], set(), 0
    for node in publication.findall(_tag("situation")):
        source_id = _token(node.get("id", ""))
        if source_id in ids or len(ids) >= MAX_SITUATIONS:
            _reject("road_situation_identity_or_limit")
        ids.add(source_id)
        issues = set()
        _shape(node, {"headerInformation", "situationRecord", "situationVersionTime"}, issues, "situation")
        situation_time = _optional_time(node, "situationVersionTime")
        if situation_time and situation_time > published + timedelta(minutes=5):
            _reject("road_situation_clock")
        header = _one(node, "headerInformation")
        _shape(header, {"confidentiality", "informationStatus", "urgency"}, issues, "header")
        confidentiality, status = (_text(header, name) for name in ("confidentiality", "informationStatus"))
        if status != "real":
            issues.add("non_real_information")
        if confidentiality != "noRestriction":
            issues.add("restricted_information")
        records, record_ids = [], set()
        for record in node.findall(_tag("situationRecord")):
            record_count += 1
            if record_count > MAX_RECORDS:
                _reject("road_record_limit")
            decoded = _record(record, scopes, published, confidentiality, status == "real")
            if decoded.source_id in record_ids:
                _reject("road_duplicate_record")
            record_ids.add(decoded.source_id)
            records.append(decoded)
        if not records:
            _reject("road_empty_situation")
        situations.append(RoadSituation(source_id, _version(node), _digest((*supplier, source_id)),
            confidentiality, status, max([r.version_at for r in records] + ([situation_time] if situation_time else [])),
            tuple(sorted(records, key=lambda r: r.source_id)), tuple(sorted(issues))))
    return RoadSnapshot(supplier, published, received_at.astimezone(UTC), hashlib.sha256(payload).hexdigest(),
        tuple(sorted(situations, key=lambda s: s.source_id)), tuple(sorted(unsupported)))
