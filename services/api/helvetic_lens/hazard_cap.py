"""Bounded, offline CAP decoding; protocol validity is not source authorization.

Supported contract: OASIS CAP 1.2 and the fields used by CAP Suisse 1.1.
No current Alertswiss endpoint or operational CAP coverage is implied. Links,
attachments and signatures are never fetched or treated as verified here.
"""

import hashlib
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from .hazard_geometry import canonical_polygon, valid_polygon

CAP = "urn:oasis:names:tc:emergency:cap:1.2"
MAX_BYTES = 2 * 1024 * 1024
MAX_NODES = 20_000
MAX_POINTS = 2000
SEVERITY = {"Unknown": None, "Minor": 1, "Moderate": 2, "Severe": 3, "Extreme": 4}
CATEGORIES = {"Geo", "Met", "Safety", "Security", "Rescue", "Fire", "Health", "Env",
              "Transport", "Infra", "CBRNE", "Other"}
RESPONSES = {"Shelter", "Evacuate", "Prepare", "Execute", "Avoid", "Monitor", "Assess", "AllClear", "None"}


class HazardCAPError(ValueError):
    """Stable diagnostics that contain no source text or private coordinates."""


def reject(code):
    raise HazardCAPError(code) from None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def _tag(name):
    return f"{{{CAP}}}{name}"


def _nodes(parent, name, limit=64):
    nodes = parent.findall(_tag(name))
    if len(nodes) > limit:
        reject("hazard_field_limit")
    return nodes


def _scalar(node, *, limit=256, verbatim=False):
    value = node.text or ""
    if node.attrib or len(node) or not value.strip() or len(value) > limit or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        reject("hazard_invalid_scalar")
    return value if verbatim else value.strip()


def _text(parent, name, *, required=True, limit=256, verbatim=False):
    nodes = _nodes(parent, name, 1)
    if not nodes:
        if required:
            reject("hazard_missing_field")
        return None
    return _scalar(nodes[0], limit=limit, verbatim=verbatim)


def _tokens(parent, name, allowed=None):
    values = tuple(sorted({_scalar(n) for n in _nodes(parent, name)}))
    if allowed is not None and any(v not in allowed for v in values):
        reject("hazard_unknown_enum")
    return values


def _enum(parent, name, allowed):
    value = _text(parent, name)
    if value not in allowed:
        reject("hazard_unknown_enum")
    return value


def _time(value):
    # CAP requires a numeric offset (UTC is -00:00), not Z or naive local time.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?[+-]\d{2}:\d{2}", value):
        reject("hazard_invalid_time")
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except ValueError:
        reject("hazard_invalid_time")


def _optional_time(parent, name):
    value = _text(parent, name, required=False)
    return _time(value) if value is not None else None


def _shape(node, allowed, issues, code):
    if node.attrib or any(n.tag not in {_tag(name) for name in allowed} for n in node):
        issues.add(code)


def _pairs(parent, name, issues):
    pairs = []
    for node in _nodes(parent, name):
        _shape(node, {"valueName", "value"}, issues, "extended_pair")
        pairs.append((_text(node, "valueName"), _text(node, "value", limit=8192)))
    return tuple(sorted(set(pairs)))


def _number(value):
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value):
        reject("hazard_invalid_coordinate")
    result = float(value)
    if not math.isfinite(result):
        reject("hazard_invalid_coordinate")
    return result


def _point(value):
    parts = value.split(",")
    if len(parts) != 2:
        reject("hazard_invalid_coordinate")
    lat, lon = map(_number, parts)
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        reject("hazard_invalid_coordinate")
    return lat, lon


@dataclass(frozen=True, order=True)
class CAPReference:
    sender: str
    identifier: str
    sent: datetime

    @property
    def key(self):
        return digest((self.sender, self.identifier, self.sent))


@dataclass(frozen=True)
class CAPArea:
    description: str
    polygons: tuple[tuple[tuple[float, float], ...], ...]
    circles: tuple[tuple[float, float, float], ...]
    geocodes: tuple[tuple[str, str], ...]
    altitude: float | None
    ceiling: float | None

    @property
    def semantic(self):
        # areaDesc is a translated label; geometry/code changes carry scope.
        return (tuple(sorted({canonical_polygon(p) for p in self.polygons})),
                tuple(sorted(set(self.circles))), self.geocodes, self.altitude, self.ceiling)


def _area(node, issues):
    _shape(node, {"areaDesc", "polygon", "circle", "geocode", "altitude", "ceiling"}, issues, "extended_area")
    polygons = []
    for polygon in _nodes(node, "polygon", 32):
        points = tuple(_point(v) for v in _scalar(polygon, limit=100_000).split())
        if not 4 <= len(points) <= MAX_POINTS or points[0] != points[-1] or len(set(points)) < 3:
            reject("hazard_invalid_polygon")
        polygons.append(points)
    circles = []
    for circle in _nodes(node, "circle", 32):
        parts = _scalar(circle).split()
        if len(parts) != 2:
            reject("hazard_invalid_circle")
        radius = _number(parts[1])
        if not 0 <= radius <= 20_000:
            reject("hazard_invalid_circle")
        circles.append((*_point(parts[0]), radius))
    vertical = [_text(node, name, required=False) for name in ("altitude", "ceiling")]
    altitude, ceiling = (None if v is None else _number(v) for v in vertical)
    if ceiling is not None and (altitude is None or ceiling < altitude):
        reject("hazard_invalid_altitude")
    return CAPArea(_text(node, "areaDesc", limit=8192, verbatim=True), tuple(polygons), tuple(circles),
                   _pairs(node, "geocode", issues), altitude, ceiling)


@dataclass(frozen=True)
class CAPInfo:
    language: str
    categories: tuple[str, ...]
    event: str
    event_codes: tuple[tuple[str, str], ...]
    responses: tuple[str, ...]
    urgency: str
    severity: str
    certainty: str
    effective: datetime | None
    onset: datetime | None
    expires: datetime | None
    sender_name: str | None
    headline: str | None
    description: str | None
    instruction: str | None
    web: str | None
    parameters: tuple[tuple[str, str], ...]
    areas: tuple[CAPArea, ...]

    @property
    def core(self):
        # Only fields independent of translation. Text is compared separately.
        return (self.categories, self.event_codes, self.responses, self.urgency, self.severity,
                self.certainty, self.effective, self.onset, self.expires,
                tuple(sorted({digest(a.semantic) for a in self.areas})),
                tuple(p for p in self.parameters if p[0] not in
                      {"GENUpdateType", "GENWebURL", "GENWEBLINKTEXT", "GENDISSEMINATIONMANDATORY-Language", "impacts"}))

    @property
    def texts(self):
        return tuple(" ".join((text or "").split()) for text in
                     (self.event, self.headline, self.description, self.instruction,
                      *(value for name, value in self.parameters if name == "impacts")))


def _info(node, issues, *, profile="cap-suisse"):
    names = {"language", "category", "event", "eventCode", "responseType", "urgency", "severity", "certainty",
             "effective", "onset", "expires", "senderName", "headline", "description", "instruction", "web",
             "parameter", "area", "resource", "contact", "audience"}
    _shape(node, names, issues, "extended_info")
    language = _text(node, "language")
    if not re.fullmatch(r"[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*", language):
        reject("hazard_invalid_language")
    categories = _tokens(node, "category", CATEGORIES)
    if not categories:
        reject("hazard_missing_category")
    effective, onset, expires = (_optional_time(node, n) for n in ("effective", "onset", "expires"))
    if expires and any(t is not None and t > expires for t in (effective, onset)):
        reject("hazard_invalid_period")
    web = _text(node, "web", required=False, limit=2048)
    if web:
        try:
            parsed = urlsplit(web)
            schemes = {"http", "https"} if profile == "meteoalarm-v2" else {"https"}
            if (parsed.scheme not in schemes or not parsed.hostname or parsed.username or parsed.password
                    or parsed.port not in (None, 443 if parsed.scheme == "https" else 80)
                    or any(c.isspace() for c in web)):
                reject("hazard_invalid_link")
        except ValueError:
            reject("hazard_invalid_link")
    # Resource text, derefUri and attachments can contain essential information;
    # ignoring them must not silently promote this subset to full coverage.
    if _nodes(node, "resource"):
        issues.add("resources_not_processed")
    if _text(node, "audience", required=False):
        issues.add("audience_not_processed")
    parameters = _pairs(node, "parameter", issues)
    hints = [v for k, v in parameters if k == "GENUpdateType"]
    if len(hints) > 1:
        reject("hazard_conflicting_update_hint")
    return CAPInfo(language.lower(), categories, _text(node, "event", limit=1024, verbatim=True),
        _pairs(node, "eventCode", issues), _tokens(node, "responseType", RESPONSES),
        _enum(node, "urgency", {"Immediate", "Expected", "Future", "Past", "Unknown"}),
        _enum(node, "severity", SEVERITY),
        _enum(node, "certainty", {"Observed", "Likely", "Possible", "Unlikely", "Unknown"}),
        effective, onset, expires, _text(node, "senderName", required=False, limit=1024, verbatim=True),
        *(_text(node, n, required=False, limit=32_768, verbatim=True) for n in
          ("headline", "description", "instruction")), web, parameters,
        tuple(_area(a, issues) for a in _nodes(node, "area", 64)))


@dataclass(frozen=True)
class CAPMessage:
    identity: CAPReference
    message_type: str
    references: tuple[CAPReference, ...]
    codes: tuple[str, ...]
    infos: tuple[CAPInfo, ...]
    received_at: datetime
    evidence_hash: str
    unsupported: tuple[str, ...]
    profile: Literal["cap-suisse", "meteoalarm-v2"] = "cap-suisse"

    @property
    def state(self):
        if self.message_type == "Cancel":
            return "cancelled"
        if self.infos and all("AllClear" in i.responses and i.severity == "Minor" for i in self.infos):
            return "resolved"
        return "active"


def _parse(payload):
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_BYTES:
        reject("hazard_payload_limit")
    # CAP Suisse encodings are UTF-8/ISO-8859-1; UTF-16/NUL encodings would
    # defeat a byte-level declaration check and are not supported.
    if b"\x00" in payload or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", payload, re.I):
        reject("hazard_forbidden_xml")
    encoding = re.search(br"^\s*<\?xml\b[^?]*\bencoding\s*=\s*['\"]([^'\"]+)['\"]", payload, re.I)
    if encoding and encoding[1].lower() not in {b"utf-8", b"iso-8859-1"}:
        reject("hazard_unsupported_encoding")
    depth, count, root = 0, 0, None
    try:
        for event, node in ET.iterparse(io.BytesIO(payload), events=("start", "end")):
            if event == "start":
                depth += 1
                count += 1
                if root is None:
                    root = node
                if depth > 16 or count > MAX_NODES:
                    reject("hazard_xml_limit")
            else:
                depth -= 1
        return root
    except (ET.ParseError, LookupError, UnicodeError):
        reject("hazard_invalid_xml")


def decode_cap(payload: bytes, *, received_at: datetime, profile="cap-suisse") -> CAPMessage:
    """Decode one atomic message. The caller must verify issuer and use rights.

    Unknown extensions are explicit. This function neither creates user events
    nor makes a feed, signature, source licence or URL authoritative.
    """
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        reject("hazard_receipt_clock")
    if profile not in {"cap-suisse", "meteoalarm-v2"}:
        reject("hazard_unknown_profile")
    root = _parse(payload)
    if root.tag != _tag("alert"):
        reject("hazard_cap_namespace")
    issues = set()
    _shape(root, {"identifier", "sender", "sent", "status", "msgType", "scope", "source", "code",
                  "references", "info", "note", "incidents", "restriction", "addresses"}, issues, "extended_alert")
    if _text(root, "status") != "Actual" or _text(root, "scope") != "Public":
        reject("hazard_not_public_actual")
    if _nodes(root, "restriction") or _nodes(root, "addresses"):
        reject("hazard_restricted_recipients")
    sender, identifier = (_text(root, name) for name in ("sender", "identifier"))
    if any(re.search(r"[\s,<>&]", v) for v in (sender, identifier)):
        reject("hazard_invalid_identity")
    sent = _time(_text(root, "sent"))
    if sent > received_at:
        reject("hazard_future_publication")
    identity = CAPReference(sender, identifier, sent)
    message_type = _enum(root, "msgType", {"Alert", "Update", "Cancel"})
    references = []
    for value in (_text(root, "references", required=False, limit=32_768) or "").split():
        parts = value.split(",")
        if len(parts) != 3 or parts[0] != sender or re.search(r"[\s,<>&]", parts[1]) or not parts[1]:
            reject("hazard_unverified_reference")
        ref = CAPReference(parts[0], parts[1], _time(parts[2]))
        if ref == identity or ref.sent > sent or ref in references or len(references) >= 64:
            reject("hazard_invalid_reference")
        references.append(ref)
    if (message_type in {"Update", "Cancel"}) != bool(references):
        reject("hazard_reference_required")
    infos = tuple(_info(n, issues, profile=profile) for n in _nodes(root, "info", 16))
    # Repeated language editions often carry exactly the same geometry. Bound
    # unique geometry before the quadratic simplicity check, then validate once.
    polygons = {canonical_polygon(p) for i in infos for a in i.areas for p in a.polygons}
    if sum(len(p) for p in polygons) > MAX_POINTS:
        reject("hazard_geometry_limit")
    if any(not valid_polygon(p) for p in polygons):
        issues.add("polygon_not_supported")
    if not infos and message_type != "Cancel":
        reject("hazard_missing_info")
    if len({i.language for i in infos}) != len(infos):
        issues.add("multiple_blocks_per_language")
    if any("AllClear" in i.responses and (i.severity != "Minor" or message_type != "Update") for i in infos):
        reject("hazard_invalid_all_clear")
    if any("AllClear" in i.responses for i in infos) and not all("AllClear" in i.responses for i in infos):
        issues.add("inconsistent_all_clear")
    if any(i.effective is None for i in infos):
        issues.add("implicit_effective_time")
    # A differing core cannot be collapsed as translations of one geographic
    # event; the later source adapter must support its distinct info segments.
    if len({digest(i.core) for i in infos}) > 1:
        issues.add("distinct_info_segments")
    codes = _tokens(root, "code")
    if "NAT=Teaser" in codes:
        issues.add("teaser_not_full_warning")
    return CAPMessage(identity, message_type, tuple(sorted(references)), codes, infos,
                      received_at.astimezone(UTC), hashlib.sha256(payload).hexdigest(), tuple(sorted(issues)), profile)


def material_change(previous: CAPMessage, current: CAPMessage) -> str:
    """Classify a referenced revision without mutating review or delivery state.

    A provider 'minor update' hint cannot hide changed instructions or severity.
    Language-only additions are silent only when an unchanged original edition
    remains and every language-independent field agrees.
    """
    if previous.identity not in current.references:
        reject("hazard_predecessor_missing")
    if previous.unsupported or current.unsupported:
        return "unavailable"
    if current.state != previous.state:
        return current.state if current.state != "active" else "updated"
    if current.codes != previous.codes:
        return "updated"
    old, new = ({i.language: i for i in m.infos} for m in (previous, current))
    shared = old.keys() & new.keys()
    if not shared:
        return "updated"
    cores_equal = {digest(i.core) for i in previous.infos} == {digest(i.core) for i in current.infos}
    old_levels = [SEVERITY[i.severity] for i in previous.infos]
    new_levels = [SEVERITY[i.severity] for i in current.infos]
    if None not in old_levels + new_levels:
        if max(new_levels) > max(old_levels):
            return "escalated"
        if max(new_levels) < max(old_levels):
            return "downgraded"
    if cores_equal and all(old[k].texts == new[k].texts for k in shared) and old.keys() <= new.keys():
        return "refreshed"
    return "updated"
