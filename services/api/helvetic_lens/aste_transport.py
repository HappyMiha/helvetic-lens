"""Public fixed-origin GETs only. A durable source lease must guard each request."""

import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from .aste_parser import MAX_BYTES, ORIGIN, _listing_parts, listing_url
from .config import DomainError

MAX_DOCUMENT_BYTES = 16 * 1024 * 1024


class AsteTransportError(Exception):
    def __init__(self, code, *, retry_after_seconds=None):
        super().__init__(code)
        self.code, self.retry_after_seconds = code, retry_after_seconds


def validate_url(url):
    """Admit only paths observed in official public representations, never actions."""
    if not isinstance(url, str) or not url.startswith(ORIGIN + "/"):
        raise AsteTransportError("aste_endpoint_denied")
    try:
        parsed = urlsplit(url)
        if (parsed.netloc != "www.aste.ti.ch" or parsed.fragment
                or any(ord(c) < 33 or c == "\\" for c in url)):
            raise ValueError()
        if parsed.path in ("/it/", "/it/preview"):
            # Canonical reconstruction rejects encoded traversal, duplicate query
            # keys and unsupported filters while keeping our generated category URL.
            if url != listing_url(**_listing_parts(url)):
                raise ValueError()
            return "html"
        if re.fullmatch(r"/it/auction/[1-9][0-9]{0,8}", parsed.path) and not parsed.query:
            return "html"
        if re.fullmatch(r"/it/api/auction/auction-status/[1-9][0-9]{0,8}", parsed.path) and not parsed.query:
            return "json"
        if (re.fullmatch(r"/uploads/[1-9][0-9]{0,8}/[a-f0-9]{32}\.pdf", parsed.path)
                and (not parsed.query or re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", parsed.query))):
            return "pdf"
    except (ValueError, DomainError):
        pass
    raise AsteTransportError("aste_endpoint_denied")


def _retry_after(value, now):
    try:
        if value.isascii() and value.isdigit():
            return int(value)
        instant = parsedate_to_datetime(value)
        if instant.tzinfo is None:
            return None
        return max(0, int((instant - now).total_seconds()) + 1)
    except (ValueError, TypeError, OverflowError):
        return None


def fetch(client, url, *, guard, now=lambda: datetime.now(UTC), monotonic=time.monotonic):
    kind = validate_url(url)
    maximum = MAX_DOCUMENT_BYTES if kind == "pdf" else MAX_BYTES
    accepted = {"html": "text/html", "json": "application/json", "pdf": "application/pdf"}[kind]
    request = httpx.Request("GET", url, headers={"Accept": accepted, "Accept-Encoding": "identity",
        "User-Agent": "HelveticLens-Monitoring/2"},
        extensions={"timeout": {"connect": 5.0, "read": 10.0, "write": 10.0, "pool": 5.0}})
    # An explicit request and auth=None exclude injected client cookies, auth,
    # parameters and defaults. No bidder/session state is needed for public reads.
    guard()
    started = monotonic()
    try:
        response = client.send(request, stream=True, follow_redirects=False, auth=None)
        try:
            if response.status_code != 200:
                delays = [_retry_after(value, now()) for value in response.headers.get_list("retry-after")]
                raise AsteTransportError(f"aste_http_{response.status_code}",
                    retry_after_seconds=max((value for value in delays if value is not None), default=None))
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise AsteTransportError("aste_response_encoding")
            if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != accepted:
                raise AsteTransportError("aste_response_type")
            length = response.headers.get("content-length")
            if length is not None and (not length.isascii() or not length.isdigit() or len(length) > 10 or int(length) > maximum):
                raise AsteTransportError("aste_response_size")
            content = bytearray()
            for chunk in response.iter_raw():
                if monotonic() - started > 45:
                    raise AsteTransportError("aste_request_deadline")
                if len(content) + len(chunk) > maximum:
                    raise AsteTransportError("aste_response_size")
                content.extend(chunk)
            if not content or kind == "pdf" and not bytes(content).startswith(b"%PDF-"):
                raise AsteTransportError("aste_response_type")
            guard()
            return bytes(content)
        finally:
            response.close()
    except httpx.HTTPError:
        raise AsteTransportError("aste_transport_unavailable") from None
