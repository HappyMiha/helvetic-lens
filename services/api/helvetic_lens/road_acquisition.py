"""Default-off shared FEDRO SOAP collection. No private routes go on the wire."""

import time
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from uuid import uuid4

import httpx
from sqlalchemy import or_, select, update

from .config import DomainError
from .monitoring_subjects import _savepoint
from .road_feed import MAX_BYTES
from .road_models import RoadSourcePoll
from .road_sources import SOURCE, _head, _utc, accept_snapshot, purge_expired, require_permission

ENDPOINT = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"
SOAP_ACTION = "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullTrafficMessages"
# The official cookbook says the body is fixed, including this subscription date.
# It contains no route, user, company, callback URL or runtime-generated identity.
REQUEST_BODY = b'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>
<d2LogicalModel xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" modelBaseVersion="2"
 xmlns="http://datex2.eu/schema/2/2_0"><exchange><supplierIdentification>
<country>ch</country><nationalIdentifier>FEDRO</nationalIdentifier></supplierIdentification>
<subscription><operatingMode>operatingMode1</operatingMode>
<subscriptionStartTime>2025-05-01T08:00:00.00+01:00</subscriptionStartTime>
<subscriptionState>active</subscriptionState><updateMethod>singleElementUpdate</updateMethod>
<target><address></address><protocol>http</protocol></target></subscription></exchange>
</d2LogicalModel></soap:Body></soap:Envelope>'''
INTERVAL, LEASE_SECONDS, TOTAL_SECONDS = 60, 180, 45


def clock():
    return datetime.now(UTC)


class RoadAcquisitionError(Exception):
    def __init__(self, code, *, blocked=False, retry_after=0):
        super().__init__(code)
        self.code, self.blocked, self.retry_after = code, blocked, retry_after


def _retry_after(value, now):
    if not value or len(value) > 100:
        return 0
    try:
        if value.isascii() and value.isdigit():
            seconds = int(value)
        else:
            instant = parsedate_to_datetime(value)
            if instant.tzinfo is None:
                return 0
            seconds = max(0, int((instant - now).total_seconds()) + 1)
        if seconds > 86400:
            raise RoadAcquisitionError("road_long_retry_after", blocked=True, retry_after=min(seconds, 315_360_000))
        return seconds
    except (ValueError, TypeError, OverflowError):
        return 0


def download(key, *, since=None, guard=lambda: None, client=None, now=clock, monotonic=time.monotonic):
    if not key or len(key) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise RoadAcquisitionError("road_credentials_invalid", blocked=True)
    headers = {"Authorization": "Bearer " + key, "SOAPAction": SOAP_ACTION,
               "Content-Type": "text/xml; charset=utf-8", "Accept": "text/xml, application/xml",
               "Accept-Encoding": "identity", "User-Agent": "HelveticLens-Monitoring/2"}
    if since is not None:
        if since.tzinfo is None or not timedelta(0) <= now() - since <= timedelta(minutes=5):
            raise RoadAcquisitionError("road_delta_window_invalid")
        headers["If-Modified-Since"] = format_datetime(since.astimezone(UTC), usegmt=True)
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False)
    started = monotonic()
    try:
        guard()
        # A standalone Request excludes injected client cookies, query parameters,
        # default headers and auth. No redirect destination receives this key.
        request = httpx.Request("POST", ENDPOINT, headers=headers, content=REQUEST_BODY)
        response = client.send(request, stream=True, follow_redirects=False, auth=None)
        try:
            if response.status_code in (401, 403):
                raise RoadAcquisitionError("road_credentials_rejected", blocked=True)
            if response.status_code in (429, 503):
                raise RoadAcquisitionError("road_source_throttled", retry_after=_retry_after(
                    response.headers.get("Retry-After"), now()))
            if 300 <= response.status_code < 400:
                # The documented response is a DATEX publication. A bare 304 has
                # no publication clock/continuity proof for this source contract.
                raise RoadAcquisitionError("road_response_contract_unreviewed", blocked=True)
            if response.status_code != 200:
                raise RoadAcquisitionError("road_http_error")
            encoding = response.headers.get("Content-Encoding", "identity").lower()
            if encoding not in ("", "identity", "gzip", "deflate"):
                raise RoadAcquisitionError("road_encoding_unsupported")
            decoder = (zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS)
                       if encoding in ("gzip", "deflate") else None)
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isascii() or not length.isdigit() or len(length) > 12 or int(length) > MAX_BYTES):
                raise RoadAcquisitionError("road_transfer_size")
            chunks, size, wire_size = [], 0, 0
            for chunk in response.iter_raw(chunk_size=64 * 1024):
                guard()
                if monotonic() - started >= TOTAL_SECONDS:
                    raise RoadAcquisitionError("road_transfer_timeout")
                wire_size += len(chunk)
                if wire_size > MAX_BYTES:
                    raise RoadAcquisitionError("road_transfer_size")
                if decoder:
                    chunk = decoder.decompress(chunk, MAX_BYTES - size + 1)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise RoadAcquisitionError("road_transfer_size")
                chunks.append(chunk)
            if decoder and (not decoder.eof or decoder.unused_data):
                raise RoadAcquisitionError("road_encoding_invalid")
            if length is not None and int(length) != wire_size:
                raise RoadAcquisitionError("road_transfer_incomplete")
            if monotonic() - started >= TOTAL_SECONDS:
                raise RoadAcquisitionError("road_transfer_timeout")
            guard()
            return b"".join(chunks)
        finally:
            response.close()
    except httpx.HTTPError:
        raise RoadAcquisitionError("road_network_error") from None
    except zlib.error:
        raise RoadAcquisitionError("road_encoding_invalid") from None
    finally:
        if owned:
            client.close()


@dataclass(frozen=True)
class RoadClaim:
    token: str
    permission_id: str
    generation: int
    started_at: datetime
    since: datetime | None


def claim(database, permission_id, *, now):
    with database.session() as session:
        require_permission(session, permission_id, now=now)
        with _savepoint(session):
            head = _head(session)
            if head is None or head.permission_id != permission_id:
                raise RoadAcquisitionError("road_permission_not_selected", blocked=True)
            row = session.scalar(select(RoadSourcePoll).where(RoadSourcePoll.source == SOURCE).with_for_update())
            if row is None:
                row = RoadSourcePoll(source=SOURCE, permission_id=permission_id, next_request_at=now)
                session.add(row)
                session.flush()
            recover = (row.permission_id != permission_id and row.last_code == "road_credentials_rejected")
            if (row.blocked and not recover) or _utc(row.next_request_at) > now or (row.lease_until and _utc(row.lease_until) > now):
                return None
            full = (row.permission_id != permission_id or row.force_full or head.published_at is None
                    or head.last_full_at is None or now - _utc(head.last_full_at) >= timedelta(days=1)
                    or row.last_success_at is None or not timedelta(0) <= now - _utc(row.last_success_at) <= timedelta(minutes=4))
            since = None if full else _utc(row.last_success_at) - timedelta(seconds=10)
            token = str(uuid4())
            updated = session.execute(update(RoadSourcePoll).where(RoadSourcePoll.source == SOURCE,
                RoadSourcePoll.next_request_at <= now, or_(RoadSourcePoll.blocked.is_(False),
                    (RoadSourcePoll.permission_id != permission_id)
                    & (RoadSourcePoll.last_code == "road_credentials_rejected")),
                or_(RoadSourcePoll.lease_until.is_(None), RoadSourcePoll.lease_until <= now))
                .values(permission_id=permission_id, blocked=False, lease_token=token, lease_until=now + timedelta(seconds=LEASE_SECONDS),
                        next_request_at=now + timedelta(seconds=INTERVAL)).execution_options(synchronize_session=False))
            if updated.rowcount != 1:
                return None
            generation = head.generation
        session.commit()
        return RoadClaim(token, permission_id, generation, now, since)


def _owned(session, selected, now):
    require_permission(session, selected.permission_id, now=now)
    head = _head(session)
    if head is None or head.permission_id != selected.permission_id or head.generation != selected.generation:
        raise RoadAcquisitionError("road_source_generation_changed")
    row = session.scalar(select(RoadSourcePoll).where(RoadSourcePoll.source == SOURCE)
                         .with_for_update().execution_options(populate_existing=True))
    if (row is None or row.permission_id != selected.permission_id or row.lease_token != selected.token
            or row.lease_until is None or _utc(row.lease_until) <= now):
        raise RoadAcquisitionError("road_source_lease_lost")
    return row


def collect(database, settings, *, downloader=download, now=clock):
    def enabled():
        return settings.road_watch_enabled and settings.road_source_enabled

    if not enabled():
        return {"state": "disabled"}
    key, permission_id = settings.road_source_key.get_secret_value(), settings.road_source_permission_id
    if not key or not permission_id:
        return {"state": "unconfigured"}
    try:
        selected = claim(database, permission_id, now=now())
    except (DomainError, RoadAcquisitionError):
        return {"state": "source_permission_unavailable"}
    if selected is None:
        return {"state": "deferred"}

    def guard():
        if not enabled():
            raise RoadAcquisitionError("road_source_disabled")
        if settings.road_source_permission_id != permission_id or settings.road_source_key.get_secret_value() != key:
            raise RoadAcquisitionError("road_source_configuration_changed")
        with database.session() as session:
            _owned(session, selected, now())

    try:
        payload = downloader(key, since=selected.since, guard=guard, now=now)
        received = now()
        if not enabled():
            raise RoadAcquisitionError("road_source_disabled")
        with database.session() as session:
            row = _owned(session, selected, now())
            result = accept_snapshot(session, permission_id, payload, request_id=selected.token,
                expected_generation=selected.generation, mode="full" if selected.since is None else "delta",
                continuous=True, received_at=received, now=now())
            # Validation/storage can outlive a grant or lease. These checks occur
            # in the outer transaction so failure rolls back the staged snapshot.
            finished = now()
            if not enabled():
                raise RoadAcquisitionError("road_source_disabled")
            if settings.road_source_permission_id != permission_id or settings.road_source_key.get_secret_value() != key:
                raise RoadAcquisitionError("road_source_configuration_changed")
            if row.lease_until is None or _utc(row.lease_until) <= finished:
                raise RoadAcquisitionError("road_source_lease_lost")
            require_permission(session, permission_id, now=finished)
            # Never let a faster client clock skip a provider update. The next
            # delta overlaps the earlier of request start and source publication.
            row.last_success_at = min(selected.started_at, _utc(_head(session).published_at))
            row.failures, row.blocked, row.force_full, row.last_code = 0, False, False, "accepted"
            row.lease_token = row.lease_until = None
            row.next_request_at = max(_utc(row.next_request_at), finished + timedelta(seconds=INTERVAL))
            session.commit()
        return {"state": "accepted", "generation": result.generation, "changes": len(result.change_ids)}
    except (RoadAcquisitionError, DomainError, ValueError) as error:
        code = error.code if isinstance(error, (RoadAcquisitionError, DomainError)) else "road_payload_invalid"
        with database.session() as session:
            row = session.scalar(select(RoadSourcePoll).where(RoadSourcePoll.source == SOURCE,
                RoadSourcePoll.lease_token == selected.token).with_for_update())
            if row is not None:
                row.failures = min(row.failures + 1, 10)
                row.force_full, row.blocked, row.last_code = True, bool(getattr(error, "blocked", False)), code
                row.next_request_at = max(_utc(row.next_request_at), now() + timedelta(seconds=max(
                    min(3600, INTERVAL * 2 ** row.failures), getattr(error, "retry_after", 0))))
                row.lease_token = row.lease_until = None
                session.commit()
        return {"state": "unavailable", "code": code}


def cleanup(database, *, now=clock):
    """Retention continues even with acquisition disabled; no network or credentials."""
    from .road_catalog import purge_catalog
    from .road_events import purge_events

    with database.session(include_all_organizations=True) as session:
        checked_at = now()
        purge_expired(session, now=checked_at)
        purge_events(session, now=checked_at)
        purge_catalog(session, now=checked_at)
        session.commit()
    return {"state": "retention_checked"}
