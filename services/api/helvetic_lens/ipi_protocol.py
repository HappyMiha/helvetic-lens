"""Bounded offline IPI datadelivery XML/ZIP envelope codec.

Based on the publisher's datadelivery core/common/trademark 1.0.0 schemas.
No HTTP, accounts, schema fetching, resource fetching or coverage claim occurs.
"""

import hashlib
import io
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from zipfile import BadZipFile, ZipFile

CORE = "urn:ige:schema:xsd:datadeliverycore-1.0.0"
COMMON = "urn:ige:schema:xsd:datadeliverycommon-1.0.0"
SEARCH = "urn:ige:schema:xsd:datadeliverytrademark-1.0.0"
TM = "http://www.wipo.int/standards/XMLSchema/ST96/Trademark"
COM = "http://www.wipo.int/standards/XMLSchema/ST96/Common"
MAX_BYTES = 32 * 1024 * 1024
MAX_NODES = 150_000
MAX_DEPTH = 64
MAX_CONTINUATION = 32_768


class IPIProtocolError(ValueError):
    def __init__(self, code, *, retry_after_seconds=None):
        super().__init__(code)
        self.code, self.retry_after_seconds = code, retry_after_seconds


def q(namespace, name):
    return f"{{{namespace}}}{name}"


def parse_xml(payload, *, maximum=MAX_BYTES):
    if not isinstance(payload, bytes) or not 0 < len(payload) <= maximum:
        raise IPIProtocolError("ipi_xml_size_invalid")
    if b"\x00" in payload or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", payload, re.I):
        raise IPIProtocolError("ipi_unsafe_xml")
    try:
        depth, nodes = 0, 0
        parser = ET.iterparse(io.BytesIO(payload), events=("start", "end"))
        for event, _ in parser:
            if event == "start":
                depth, nodes = depth + 1, nodes + 1
                if depth > MAX_DEPTH or nodes > MAX_NODES:
                    raise IPIProtocolError("ipi_xml_complexity_limit")
            else:
                depth -= 1
        return parser.root
    except ET.ParseError:
        raise IPIProtocolError("ipi_xml_invalid") from None


def initial_request(*, page_size=64, request_uuid=None):
    if type(page_size) is not int or not 1 <= page_size <= 64:
        raise IPIProtocolError("ipi_page_size_invalid")
    root = ET.Element(q(CORE, "ApiRequest"))
    if request_uuid is not None:
        if not isinstance(request_uuid, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", request_uuid):
            raise IPIProtocolError("ipi_request_id_invalid")
        root.set("uuid", request_uuid)
    search = ET.SubElement(ET.SubElement(root, q(CORE, "Action"), {"type": "TrademarkSearch"}), q(SEARCH, "TrademarkSearchRequest"))
    representation = ET.SubElement(search, q(COMMON, "Representation"), {
        "details": "Maximal", "strictness": "Strict", "images": "Link", "itemBags": "false"})
    ET.SubElement(representation, q(COMMON, "Resource"), {"role": "item", "action": "Embed"})
    ET.SubElement(search, q(COMMON, "Page"), {"size": str(page_size)})
    ET.SubElement(ET.SubElement(search, q(COMMON, "Query")), q(COMMON, "LastUpdate"))
    ET.SubElement(ET.SubElement(search, q(COMMON, "Sort")), q(COMMON, "LastUpdateSort")).text = "Ascending"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def retry_after(value, *, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise IPIProtocolError("ipi_clock_invalid")
    if not isinstance(value, str) or len(value) > 100:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]{1,10}", value):
        return int(value)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return None
        # Round up fractional seconds rather than retrying before the publisher's date.
        delay = (parsed.astimezone(UTC) - now.astimezone(UTC)).total_seconds()
        return max(0, int(delay) + int(delay > int(delay)))
    except (TypeError, ValueError, OverflowError):
        return None


def _xml_body(content_type, payload):
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES:
        raise IPIProtocolError("ipi_response_size_invalid")
    media = content_type.split(";", 1)[0].strip().lower()
    if media in {"application/xml", "text/xml"}:
        return payload
    if media != "application/zip":
        raise IPIProtocolError("ipi_response_format_unavailable")
    try:
        with ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > 256 or len({e.filename for e in entries}) != len(entries):
                raise IPIProtocolError("ipi_bundle_limit")
            if sum(e.file_size for e in entries) > MAX_BYTES:
                raise IPIProtocolError("ipi_bundle_limit")
            for entry in entries:
                if (entry.flag_bits & 1 or entry.filename.startswith(("/", "\\"))
                        or "\\" in entry.filename or ":" in entry.filename
                        or ".." in entry.filename.split("/")
                        or any(ord(c) < 32 for c in entry.filename)):
                    raise IPIProtocolError("ipi_bundle_invalid")
            if "response.xml" not in archive.namelist():
                raise IPIProtocolError("ipi_bundle_response_missing")
            with archive.open("response.xml") as stream:
                result = stream.read(MAX_BYTES + 1)
            if len(result) > MAX_BYTES:
                raise IPIProtocolError("ipi_bundle_limit")
            return result
    except (BadZipFile, KeyError, RuntimeError, NotImplementedError, EOFError):
        raise IPIProtocolError("ipi_bundle_invalid") from None


@dataclass(frozen=True)
class IPIItem:
    item_id: str | None
    role: str | None
    context: str | None
    xml: bytes


@dataclass(frozen=True)
class IPIPage:
    response_sha256: str
    xml_sha256: str
    items: tuple[IPIItem, ...]
    offset: int
    count: int
    total: int
    next_request: bytes | None
    coverage_verified: bool = False


def decode_response(status, headers, payload, *, now, max_items=64, expected_request_uuid=None):
    """One TrademarkSearch action. Unsupported/partial layouts remain unavailable."""
    if type(max_items) is not int or not 1 <= max_items <= 64:
        raise IPIProtocolError("ipi_page_size_invalid")
    values = {}
    pairs = headers.multi_items() if hasattr(headers, "multi_items") else headers.items() if hasattr(headers, "items") else headers
    for key, value in pairs:
        name = key.lower()
        if name in {"x-ipi-success", "content-type", "retry-after"}:
            if name in values:
                raise IPIProtocolError("ipi_ambiguous_headers")
            values[name] = value
    if status != 200:
        raise IPIProtocolError(f"ipi_http_{status}", retry_after_seconds=retry_after(values.get("retry-after"), now=now))
    if values.get("x-ipi-success", "").strip().lower() != "true":
        raise IPIProtocolError("ipi_actions_unsuccessful")
    xml = _xml_body(values.get("content-type", ""), payload)
    root = parse_xml(xml)
    if root.tag != q(CORE, "ApiResponse") or any(e.tag != q(CORE, "Result") for e in root):
        raise IPIProtocolError("ipi_response_root_invalid")
    if expected_request_uuid is not None and root.get("requestUuid") != expected_request_uuid:
        raise IPIProtocolError("ipi_response_request_mismatch")
    results = list(root)
    if len(results) != 1 or results[0].get("success") not in {"true", "1"}:
        raise IPIProtocolError("ipi_action_result_invalid")
    result = results[0]
    meta = result.findall(q(CORE, "Meta"))
    if len(meta) != 1:
        raise IPIProtocolError("ipi_page_metadata_missing")
    counts = []
    for name in ("ItemCountOffset", "ItemCount", "TotalItemCount"):
        elements = meta[0].findall(q(COMMON, name))
        if len(elements) != 1 or not re.fullmatch(r"[0-9]{1,10}", (elements[0].text or "").strip()):
            raise IPIProtocolError("ipi_page_metadata_invalid")
        counts.append(int(elements[0].text.strip()))
    offset, count, total = counts
    if count > max_items or offset + count > total:
        raise IPIProtocolError("ipi_page_metadata_invalid")
    items = []

    def data(element, inherited_id=None):
        if element.tag == q(CORE, "DataBag"):
            for child in element:
                data(child, element.get("id") or inherited_id)
        elif element.tag in {q(CORE, "Data"), q(CORE, "DataLax"), q(CORE, "DataAny")}:
            if len(element) == 1 and element[0].tag == q(TM, "TrademarkApplication"):
                items.append(IPIItem(element.get("id") or inherited_id, element.get("role"), element.get("context"),
                    ET.tostring(element[0], encoding="utf-8")))
            elif element.get("role") not in {"image", "thumbnail"}:
                raise IPIProtocolError("ipi_item_payload_unavailable")
        elif element.tag in {q(CORE, "DataReference"), q(CORE, "DataBinary"), q(CORE, "DataText")}:
            if element.get("role") not in {"image", "thumbnail"}:
                raise IPIProtocolError("ipi_item_payload_unavailable")
        else:
            raise IPIProtocolError("ipi_result_layout_unavailable")

    for element in result:
        if element.tag not in {q(CORE, "Meta"), q(CORE, "Continuations"), q(CORE, "Log")}:
            data(element)
    if len(items) != count:
        raise IPIProtocolError("ipi_item_count_mismatch")
    wrappers = result.findall(q(CORE, "Continuations"))
    if len(wrappers) > 1:
        raise IPIProtocolError("ipi_continuation_invalid")
    continuations = list(wrappers[0]) if wrappers else []
    if len(continuations) > 1:
        raise IPIProtocolError("ipi_continuation_invalid")
    next_request = None
    if continuations:
        continuation = continuations[0]
        if (continuation.tag != q(CORE, "Continuation") or continuation.get("name") != "NextPage"
                or len(continuation) or not (continuation.text or "").strip()
                or len(ET.tostring(continuation)) > MAX_CONTINUATION):
            raise IPIProtocolError("ipi_continuation_invalid")
        followup = ET.Element(q(CORE, "ApiRequest"))
        followup.append(deepcopy(continuation))
        next_request = ET.tostring(followup, encoding="utf-8", xml_declaration=True)
    elif offset + count < total:
        raise IPIProtocolError("ipi_page_incomplete")
    return IPIPage(hashlib.sha256(payload).hexdigest(), hashlib.sha256(xml).hexdigest(),
        tuple(items), offset, count, total, next_request)
