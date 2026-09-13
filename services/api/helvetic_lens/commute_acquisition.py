"""One shared, permission-bound binary request chain per feed and minute.

No personal routes, queries, cookies or tenant identity go to the provider.
Disabled until real credentials AND an independently reviewed grant are installed.
"""

import time
import zlib
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from .commute_models import CommuteSourcePoll
from .commute_sources import accept_feed, clock, require_permission, utc
from .config import DomainError
from .monitoring_subjects import _savepoint
from .transport_feed import ALERTS, MAX_BYTES, TRIPS

API_ORIGIN = "https://api.opentransportdata.swiss"
ENDPOINTS = {TRIPS: API_ORIGIN + "/la/gtfs-rt", ALERTS: API_ORIGIN + "/la/gtfs-sa"}
INTERVAL, LEASE_SECONDS, TOTAL_SECONDS = 60, 120, 45


class AcquisitionError(Exception):
    def __init__(self, code, *, retry_after=0, blocked=False):
        # Never embed response bodies, credentials, signed URLs or HTTP exceptions.
        super().__init__(code)
        self.code, self.retry_after, self.blocked = code, retry_after, blocked


def origin(url):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)
                or parsed.fragment or any(ord(c) < 33 or ord(c) > 126 for c in url)
                or "\\" in url):
            raise ValueError
        return "https://" + parsed.hostname.lower()
    except ValueError:
        raise AcquisitionError("invalid_source_destination", blocked=True) from None


def retry_delay(value, now):
    if not value or len(value) > 100:
        return 0
    try:
        if value.isascii() and value.isdigit():
            seconds = int(value)
        else:
            timestamp = parsedate_to_datetime(value)
            if timestamp.tzinfo is None:
                return 0
            seconds = max(0, int((timestamp - now).total_seconds()) + 1)
        # Longer requests suspend polling for operator review instead of silently
        # retrying sooner than a provider requested.
        if seconds > 86400:
            raise AcquisitionError("source_long_retry_after", retry_after=min(seconds, 315_360_000), blocked=True)
        return seconds
    except (ValueError, OverflowError, TypeError):
        return 0


def download(source, key, *, redirect_origins=(), guard=lambda: None,
             client=None, now=clock, monotonic=time.monotonic):
    if source not in ENDPOINTS or not key or len(key) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise AcquisitionError("source_credentials_invalid", blocked=True)
    allowed = {API_ORIGIN}
    for value in redirect_origins:
        if origin(value) != value or urlsplit(value).path:
            raise AcquisitionError("invalid_source_destination", blocked=True)
        allowed.add(value)
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)
    started, url, visited = monotonic(), ENDPOINTS[source], set()
    try:
        for hop in range(4):
            target = origin(url)
            if target not in allowed or url in visited:
                raise AcquisitionError("source_redirect_unreviewed", blocked=True)
            if monotonic() - started >= TOTAL_SECONDS:
                raise AcquisitionError("source_timeout")
            guard()
            visited.add(url)
            headers = {"Accept": "application/octet-stream", "Accept-Encoding": "gzip, deflate",
                       "User-Agent": "HelveticLens-Monitoring/2"}
            if target == API_ORIGIN:
                headers["Authorization"] = "Bearer " + key
            # Isolated client is never supplied a browser cookie jar. Clear any
            # provider Set-Cookie between redirects rather than tracking a session.
            client.cookies.clear()
            with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
                if response.status_code in (401, 403):
                    raise AcquisitionError("source_credentials_rejected", blocked=True)
                if response.status_code in (429, 503):
                    raise AcquisitionError("source_throttled", retry_after=retry_delay(response.headers.get("Retry-After"), now()))
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location or len(location) > 8192 or hop == 3:
                        raise AcquisitionError("source_redirect_invalid", blocked=True)
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise AcquisitionError("source_http_error")
                encoding = response.headers.get("Content-Encoding", "identity").lower()
                if encoding not in ("", "identity", "gzip", "deflate"):
                    raise AcquisitionError("source_encoding_unsupported")
                decoder = (zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS)
                           if encoding in ("gzip", "deflate") else None)
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isascii() or not length.isdigit() or len(length) > 12 or int(length) > MAX_BYTES):
                    raise AcquisitionError("source_size_limit")
                chunks, size, wire_size = [], 0, 0
                for chunk in response.iter_raw(chunk_size=64 * 1024):
                    wire_size += len(chunk)
                    if wire_size > MAX_BYTES:
                        raise AcquisitionError("source_size_limit")
                    if decoder is not None:
                        chunk = decoder.decompress(chunk, MAX_BYTES - size + 1)
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise AcquisitionError("source_size_limit")
                    if monotonic() - started >= TOTAL_SECONDS:
                        raise AcquisitionError("source_timeout")
                    chunks.append(chunk)
                if decoder is not None and (not decoder.eof or decoder.unused_data):
                    raise AcquisitionError("source_encoding_invalid")
                if length is not None and int(length) != wire_size:
                    raise AcquisitionError("source_body_incomplete")
                guard()
                return b"".join(chunks)
        raise AcquisitionError("source_redirect_invalid", blocked=True)
    except httpx.HTTPError:
        raise AcquisitionError("source_network_error") from None
    except zlib.error:
        raise AcquisitionError("source_encoding_invalid") from None
    finally:
        if owned:
            client.close()


def claim(database, source, permission_id, *, now):
    token = str(uuid4())
    with database.session() as session:
        require_permission(session, permission_id, source, now=now)
        if session.get(CommuteSourcePoll, source) is None:
            try:
                with _savepoint(session):
                    session.add(CommuteSourcePoll(source=source, permission_id=permission_id, next_request_at=now))
                    session.flush()
            except IntegrityError:
                pass
        # A new reviewed permission can recover a rejected/expired credential.
        # It still respects the previous provider cooldown and in-flight lease.
        changed = session.execute(update(CommuteSourcePoll).where(
            CommuteSourcePoll.source == source, CommuteSourcePoll.next_request_at <= now,
            or_(CommuteSourcePoll.lease_until.is_(None), CommuteSourcePoll.lease_until <= now),
            or_(CommuteSourcePoll.blocked.is_(False), and_(
                CommuteSourcePoll.permission_id != permission_id,
                CommuteSourcePoll.last_code == "source_credentials_rejected")))
            .values(permission_id=permission_id, lease_token=token,
                    lease_until=now + timedelta(seconds=LEASE_SECONDS),
                    next_request_at=now + timedelta(seconds=INTERVAL), last_attempt_at=now)
            .execution_options(synchronize_session=False))
        session.commit()
        return token if changed.rowcount == 1 else None


def owned_poll(session, source, permission_id, token, now):
    # Permission-before-poll lock order matches claim and feed acceptance.
    require_permission(session, permission_id, source, now=now)
    row = session.scalar(select(CommuteSourcePoll).where(CommuteSourcePoll.source == source)
                         .with_for_update().execution_options(populate_existing=True))
    if (row is None or row.permission_id != permission_id or row.lease_token != token
            or row.lease_until is None or utc(row.lease_until) <= now):
        raise AcquisitionError("source_lease_lost")
    return row


def collect(database, settings, source, *, downloader=download, now=clock):
    if not settings.commute_watch_enabled or not settings.commute_source_enabled:
        return {"state": "disabled"}
    if source not in ENDPOINTS:
        return {"state": "unavailable"}
    suffix = "rt" if source == TRIPS else "sa"
    key = getattr(settings, f"commute_gtfs_{suffix}_key").get_secret_value()
    permission_id = getattr(settings, f"commute_gtfs_{suffix}_permission_id")
    if not key or not permission_id:
        return {"state": "unconfigured"}
    try:
        token = claim(database, source, permission_id, now=now())
    except DomainError:
        return {"state": "source_permission_unavailable"}
    if token is None:
        return {"state": "deferred"}

    def guard():
        with database.session() as session:
            owned_poll(session, source, permission_id, token, now())

    try:
        content = downloader(source, key, redirect_origins=settings.commute_feed_redirect_origins, guard=guard, now=now)
        finished = now()
        with database.session() as session:
            row = owned_poll(session, source, permission_id, token, finished)
            result = accept_feed(session, permission_id, content, now=finished)
            row.failures, row.blocked, row.last_code = 0, False, result
            row.lease_token, row.lease_until = None, None
            row.next_request_at = max(utc(row.next_request_at), finished + timedelta(seconds=INTERVAL))
            session.commit()
        return {"state": result}
    except (AcquisitionError, DomainError, ValueError) as error:
        code = error.code if isinstance(error, (AcquisitionError, DomainError)) else "source_binary_invalid"
        with database.session() as session:
            row = session.scalar(select(CommuteSourcePoll).where(CommuteSourcePoll.source == source,
                CommuteSourcePoll.lease_token == token).with_for_update())
            if row is not None:
                row.failures = min(row.failures + 1, 10)
                row.blocked = bool(getattr(error, "blocked", False))
                row.last_code = code
                row.next_request_at = max(utc(row.next_request_at), now() + timedelta(
                    seconds=max(min(3600, INTERVAL * 2 ** row.failures), getattr(error, "retry_after", 0))))
                row.lease_token, row.lease_until = None, None
                session.commit()
        return {"state": "unavailable", "code": code}


def collect_due(database, settings):
    return {source: collect(database, settings, source) for source in ENDPOINTS}
