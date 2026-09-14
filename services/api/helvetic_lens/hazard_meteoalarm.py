"""MeteoAlarm Switzerland Atom transport for the native Hazard feature.

An Atom entry is a summary, not a complete warning. Download its linked CAP
original once even when several language/area entries refer to it. This module
does not install permissions, mark a complete poll, infer all-clear or send mail.
The caller must atomically publish the whole validated snapshot and its presence
set. A partial download is never an empty successful snapshot.
"""

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from .hazard_cap import CAP, _parse
from .hazard_cap import MAX_BYTES as MAX_CAP_BYTES

ATOM = "http://www.w3.org/2005/Atom"
FEED_URL = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-switzerland"
CAP_BASE = "https://feeds.meteoalarm.org/api/v1/warnings/feeds-switzerland/"
FEED_ID = "tag:meteoalarm.org,2021-02-19:CH"
ISSUER_PREFIX = "2.49.0.0.756.0."
TERMS_URL = "https://meteoalarm.org/en/live/page/terms-and-conditions"
SOURCE_URL = "https://meteoalarm.org/en/live/"
ATTRIBUTION = "Federal Office of Meteorology and Climatology MeteoSwiss · EUMETNET – MeteoAlarm"
DELAY_DISCLAIMER = (
    "Time delays between this website and the www.meteoalarm.org website are possible. "
    "For the most up-to-date awareness information as published by the participating "
    "National Meteorological and Hydrological Services, please refer to www.meteoalarm.org."
)
MAX_ENTRIES = 1500
MAX_DOCUMENTS = 200
MAX_BATCH_BYTES = 16 * 1024 * 1024
TOTAL_SECONDS = 90
POLL_SECONDS = 120
MAX_CURRENT_SECONDS = 300


class MeteoAlarmError(ValueError):
    """Stable diagnostics: never include source text or private data."""

    def __init__(self, code, *, retry_after_seconds=0):
        super().__init__(code)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


def fail(code):
    raise MeteoAlarmError(code) from None


def retry_after(value, now):
    if not isinstance(value, str) or not value or len(value) > 100:
        return POLL_SECONDS
    try:
        if value.isascii() and value.isdigit():
            # Preserve a long source-requested pause. Do not cap it to the
            # routine poll interval and accidentally hammer a throttled feed.
            return max(POLL_SECONDS, min(int(value), 315_360_000))
        delay = (clock(parsedate_to_datetime(value)) - clock(now)).total_seconds()
        return max(POLL_SECONDS, min(int(delay) + 1, 315_360_000))
    except (ValueError, OverflowError, TypeError):
        return POLL_SECONDS


def clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        fail("meteoalarm_invalid_clock")
    return value.astimezone(UTC)


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        fail("meteoalarm_invalid_time")
    try:
        return clock(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        fail("meteoalarm_invalid_time")


def scalar(parent, namespace, name):
    nodes = parent.findall(f"{{{namespace}}}{name}")
    if len(nodes) != 1 or len(nodes[0]) or nodes[0].attrib:
        fail("meteoalarm_invalid_field")
    value = nodes[0].text or ""
    if not value or value != value.strip() or len(value) > 2048:
        fail("meteoalarm_invalid_field")
    return value


def cap_url(value):
    # The download URL must be the direct CAP resource, never the entry's id
    # containing index_info/index_area, an external web link or a redirect.
    if not isinstance(value, str) or not value.startswith(CAP_BASE):
        fail("meteoalarm_untrusted_cap_url")
    suffix = value[len(CAP_BASE):]
    try:
        if str(UUID(suffix)) != suffix:
            fail("meteoalarm_untrusted_cap_url")
    except ValueError:
        fail("meteoalarm_untrusted_cap_url")
    parsed = urlsplit(value)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        fail("meteoalarm_untrusted_cap_url")
    return value


@dataclass(frozen=True)
class LinkedWarning:
    url: str
    identifier: str
    sent: datetime
    message_type: str


@dataclass(frozen=True)
class Feed:
    updated: datetime
    evidence_sha256: str
    warnings: tuple[LinkedWarning, ...]


@dataclass(frozen=True)
class Original:
    warning: LinkedWarning
    payload: bytes
    evidence_sha256: str


@dataclass(frozen=True)
class Snapshot:
    feed: Feed
    originals: tuple[Original, ...]
    started_at: datetime
    completed_at: datetime


def parse_feed(payload, *, now):
    now = clock(now)
    root = _parse(payload)  # Shared XML byte/depth/node/entity bounds.
    if root.tag != f"{{{ATOM}}}feed" or root.attrib or scalar(root, ATOM, "id") != FEED_ID:
        fail("meteoalarm_wrong_feed")
    allowed = {f"{{{ATOM}}}{name}" for name in
               ("id", "title", "updated", "link", "rights", "generator", "logo", "author", "entry", "subtitle", "icon")}
    if any(node.tag not in allowed for node in root):
        # A changed entry namespace/unknown wrapper must not become a fabricated
        # empty successful poll which would withdraw every previous warning.
        fail("meteoalarm_feed_structure_changed")
    selves = [node for node in root.findall(f"{{{ATOM}}}link") if node.get("rel") == "self"]
    if len(selves) != 1 or selves[0].get("href") != FEED_URL:
        fail("meteoalarm_wrong_feed")
    updated = instant(scalar(root, ATOM, "updated"))
    if updated > now:
        fail("meteoalarm_future_feed")
    # updated may remain old when an empty feed has not changed. It is evidence
    # of the publisher's version, not a locally invented completed-poll clock.
    entries = root.findall(f"{{{ATOM}}}entry")
    if len(entries) > MAX_ENTRIES:
        fail("meteoalarm_entry_limit")
    warnings, identifiers, entry_ids = {}, {}, set()
    for entry in entries:
        entry_id = scalar(entry, ATOM, "id")
        if entry_id in entry_ids:
            fail("meteoalarm_duplicate_entry")
        entry_ids.add(entry_id)
        if (scalar(entry, CAP, "status") != "Actual" or scalar(entry, CAP, "scope") != "Public"):
            fail("meteoalarm_nonpublic_warning")
        identifier = scalar(entry, CAP, "identifier")
        if (not identifier.startswith(ISSUER_PREFIX) or len(identifier) > 256
                or re.search(r"[\s,<>&]", identifier)):
            fail("meteoalarm_wrong_issuer")
        sent = instant(scalar(entry, CAP, "sent"))
        published, changed = (instant(scalar(entry, ATOM, name)) for name in ("published", "updated"))
        if sent > now or published != sent or changed > now or changed < published:
            fail("meteoalarm_entry_time_conflict")
        message_type = scalar(entry, CAP, "message_type")
        if message_type not in {"Alert", "Update"}:
            fail("meteoalarm_unexpected_message_type")
        links = [node for node in entry.findall(f"{{{ATOM}}}link")
                 if node.get("type") == "application/cap+xml"]
        if len(links) != 1:
            fail("meteoalarm_missing_cap_original")
        url = cap_url(links[0].get("href"))
        warning = LinkedWarning(url, identifier, sent, message_type)
        if url in warnings and warnings[url] != warning:
            fail("meteoalarm_conflicting_cap_summary")
        if identifier in identifiers and identifiers[identifier] != url:
            fail("meteoalarm_conflicting_cap_identity")
        warnings[url], identifiers[identifier] = warning, url
    if len(warnings) > MAX_DOCUMENTS:
        fail("meteoalarm_document_limit")
    return Feed(updated, hashlib.sha256(payload).hexdigest(), tuple(sorted(warnings.values(), key=lambda w: w.url)))


def verify_original(warning, payload):
    root = _parse(payload)
    if root.tag != f"{{{CAP}}}alert":
        fail("meteoalarm_wrong_cap_original")
    if (scalar(root, CAP, "identifier") != warning.identifier
            or instant(scalar(root, CAP, "sent")) != warning.sent
            or scalar(root, CAP, "msgType") != warning.message_type
            or scalar(root, CAP, "status") != "Actual" or scalar(root, CAP, "scope") != "Public"):
        fail("meteoalarm_cap_summary_mismatch")
    # Full CAP/profile, geometry and history checks are a separate atomic
    # publication step. Do not change raw source bytes to make a parser accept.
    return Original(warning, payload, hashlib.sha256(payload).hexdigest())


def classify_weather(message, *, importance):
    """Use the publisher's coded hazard, never translate/guess from prose.

    Snow-or-ice is broader than the product's heavy-snow selection. It needs an
    explicit snow OET code; an ice warning must not be re-labelled as snowfall.
    Unknown or conflicting source coding remains unclassified.
    """
    unknown = {"hazards": [], "importance": None, "complete": False}
    if message.profile != "meteoalarm-v2" or not message.infos:
        return unknown
    info = message.infos[0]
    values = [value for name, value in info.parameters if name == "awareness_type"]
    if len(values) != 1:
        return unknown
    match = re.fullmatch(r"(\d{1,2});\s*([A-Za-z -]+)", values[0])
    if match is None:
        return unknown
    code, label = int(match[1]), match[2].strip().lower()
    mapping = {1: ("wind", "storm"), 3: ("thunderstorm", "storm"),
               8: ("forest-fire", "forest_fire"), 12: ("flooding", "flood"), 13: ("rain-flood", "flood")}
    if code == 2 and label == "snow-ice":
        events = {value for name, value in info.event_codes if name == "OET:v1.0"}
        # Blizzard/blowing-snow codes can describe wind lifting existing snow,
        # not the snowfall selected by the user. Require the explicit Snow code.
        if events != {"OET-184"}:
            return unknown
        hazard = "heavy_snow"
    else:
        expected, hazard = mapping.get(code, (None, None))
        if label != expected:
            return unknown
    level = importance.get(info.severity)
    return {"hazards": [hazard], "importance": level, "complete": level is not None}


def download(*, now=lambda: datetime.now(UTC), client=None, checkpoint=lambda: None, monotonic=time.monotonic):
    started, timer = clock(now()), monotonic()
    size = 0
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)

    def guard():
        checkpoint()
        if monotonic() - timer > TOTAL_SECONDS or clock(now()) - started > timedelta(seconds=TOTAL_SECONDS):
            fail("meteoalarm_batch_timeout")

    def read(url, content_types):
        nonlocal size
        guard()
        # A standalone request excludes client default cookies, query parameters
        # and authorization. No source URL accepts user-provided addresses.
        if url != FEED_URL:
            cap_url(url)
        request = httpx.Request("GET", url, headers={
            # The live Atom route returns 406 for Atom-only negotiation even
            # though its successful response is application/atom+xml. Permit
            # negotiation fallback, then enforce the actual response MIME/XML.
            "Accept": ", ".join(content_types) + ", */*;q=0.1", "Accept-Encoding": "identity",
            "User-Agent": "HelveticLens-Monitoring/2 (helveticlens.ch)",
        })
        response = client.send(request, stream=True, follow_redirects=False, auth=None)
        try:
            if response.status_code in (429, 503):
                raise MeteoAlarmError("meteoalarm_rate_limited", retry_after_seconds=retry_after(
                    response.headers.get("Retry-After"), clock(now())))
            if response.status_code != 200:
                fail("meteoalarm_response_unavailable")
            if response.headers.get("content-type", "").split(";")[0].strip().lower() not in content_types:
                fail("meteoalarm_response_type_changed")
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                fail("meteoalarm_encoded_response")
            body = bytearray()
            for chunk in response.iter_raw():
                guard()
                size += len(chunk)
                body.extend(chunk)
                if len(body) > MAX_CAP_BYTES or size > MAX_BATCH_BYTES:
                    fail("meteoalarm_response_limit")
            return bytes(body)
        finally:
            response.close()

    try:
        feed = parse_feed(read(FEED_URL, ("application/atom+xml",)), now=clock(now()))
        originals = tuple(verify_original(warning, read(warning.url, ("application/cap+xml", "application/xml", "text/xml")))
                          for warning in feed.warnings)
        guard()
        return Snapshot(feed, originals, started, clock(now()))
    except httpx.HTTPError:
        fail("meteoalarm_transport_unavailable")
    finally:
        if owned:
            client.close()
