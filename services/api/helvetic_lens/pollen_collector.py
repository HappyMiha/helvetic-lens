"""Bounded shared official observation collection; no user data in source requests."""

import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .monitoring_live_models import MonitoringSourceArtifact, MonitoringSourceChannel, MonitoringSourceSample
from .monitoring_subjects import _savepoint
from .pollen_sources import (
    ATTRIBUTION,
    HOURLY_METHOD,
    OBSERVATION_SOURCE,
    ChannelApproval,
    decode_daily,
    decode_hourly,
    sample_channel_hash,
)
from .pollen_thresholds import _hash

STAC = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-pollen"


class FetchBudget:
    """Wall-clock bound below the public lease, with durable job checkpoints."""
    def __init__(self, checkpoint=lambda: None, seconds=210):
        self.deadline = time.monotonic() + seconds
        self.checkpoint = checkpoint
        self.last_checkpoint = 0.0

    def check(self):
        current = time.monotonic()
        if current >= self.deadline:
            raise ValueError("Official fetch time budget exhausted")
        if current - self.last_checkpoint >= 10:
            self.checkpoint()
            self.last_checkpoint = current
        return min(30, self.deadline - current)


def record_artifact(session, *, digest, source_id, identity, body, fetched, retention_days, storage_root):
    """Concurrent model points can share byte-identical grids and density files."""
    deadline = fetched + timedelta(days=retention_days)
    if session.scalar(select(MonitoringSourceArtifact).where(MonitoringSourceArtifact.sha256 == digest).with_for_update()) is None:
        try:
            with _savepoint(session):
                session.add(MonitoringSourceArtifact(sha256=digest, source_id=source_id, identity=identity,
                    byte_count=len(body), fetched_at=fetched, retention_until=deadline, attribution=ATTRIBUTION))
                session.flush()
        except IntegrityError:
            if session.get(MonitoringSourceArtifact, digest) is None:
                raise
    session.execute(update(MonitoringSourceArtifact).where(MonitoringSourceArtifact.sha256 == digest,
        MonitoringSourceArtifact.retention_until < deadline).values(retention_until=deadline))
    session.scalar(select(MonitoringSourceArtifact).where(MonitoringSourceArtifact.sha256 == digest).with_for_update())
    _retain(storage_root, digest, body)


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _provider_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.fragment or not (host == "data.geo.admin.ch" or host.endswith(".cscs.ch"))):
        raise ValueError("Unexpected official-data endpoint")
    return url


def download(client: httpx.Client, url: str, *, max_bytes: int, payload: dict | None = None, budget=None) -> tuple[bytes, str | None]:
    budget = budget or FetchBudget()
    # Validate every redirect rather than trusting an upstream Location header.
    for _ in range(4):
        with client.stream("POST" if payload is not None else "GET", _provider_url(url), json=payload, follow_redirects=False,
                           timeout=budget.check(), headers={"User-Agent": "HelveticLens-PollenWatch/1"}) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get("location", ""))
                continue
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                budget.check()
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("Official artifact exceeds download bound")
                chunks.append(chunk)
            body = b"".join(chunks)
            expected = response.headers.get("x-amz-meta-sha256")
            if expected and hashlib.sha256(body).hexdigest() != expected:
                raise ValueError("Official artifact checksum mismatch")
            return body, response.headers.get("etag")
    raise ValueError("Too many official-data redirects")


def _retain(root: Path, digest: str, body: bytes):
    directory = root / "monitoring-public-artifacts" / digest[:2]
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / digest
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("Retained official evidence has changed")
        return
    temporary = directory / f"{digest}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as file:
            file.write(body)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _lease(database, key, now):
    token = str(uuid4())
    with database.session() as session:
        if session.get(MonitoringSourceChannel, key) is None:
            try:
                with _savepoint(session):
                    session.add(MonitoringSourceChannel(id=key, next_fetch_at=now, failures=0))
                    session.flush()
            except IntegrityError:
                pass  # Another collector established the same public channel.
        claimed = session.execute(update(MonitoringSourceChannel).where(
            MonitoringSourceChannel.id == key, MonitoringSourceChannel.next_fetch_at <= now,
            or_(MonitoringSourceChannel.lease_until.is_(None), MonitoringSourceChannel.lease_until <= now),
        ).values(lease_token=token, lease_until=now + timedelta(minutes=5)))
        session.commit()
        return token if claimed.rowcount == 1 else None


def collect_hourly(database, settings, *, station_id: str, approval: ChannelApproval,
                   now: datetime, client: httpx.Client | None = None, checkpoint=lambda: None) -> dict:
    """One shared refresh across all owners; call only with deployment-owned approval.

    A failed/expired lease never publishes partial source rows. HTTP failures are
    recorded as bounded codes rather than signed URLs or response bodies. Tests
    can inject a transport against isolated storage; the running worker cannot
    accept artifacts or source-ready flags from API clients.
    """
    hourly = approval.period == "observation_hourly"
    method = HOURLY_METHOD if hourly else "meteoswiss-automatic-daily-v1"
    if (approval.status != "approved" or not approval.valid_from <= now < approval.valid_until
            or approval.source_id != OBSERVATION_SOURCE or approval.method_version != method
            or approval.period == "forecast_instant" or station_id not in approval.stations):
        return {"status": "source_not_approved"}
    key = _hash({"source": approval.source_id, "station": station_id, "period": approval.period})
    token = _lease(database, key, now)
    if token is None:
        with database.session() as session:
            channel = session.get(MonitoringSourceChannel, key)
            return {"status": "cached_or_collecting", "source_error": channel.error_code if channel else None}
    owned_client = client is None
    budget = FetchBudget(checkpoint)
    client = client or httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), trust_env=False)
    try:
        import json

        item = json.loads(download(client, f"{STAC}/items/{station_id.lower()}", max_bytes=1024 * 1024, budget=budget)[0])
        if item.get("id") != station_id.lower():
            raise ValueError("Unexpected STAC station identity")
        name = f"ogd-pollen_{station_id.lower()}_{'h_now' if hourly else 'd_recent'}.csv"
        asset = item["assets"][name]
        body, _etag = download(client, asset["href"], max_bytes=4 * 1024 * 1024, budget=budget)
        fetched = datetime.now(UTC)
        if not approval.valid_from <= fetched < approval.valid_until:
            raise ValueError("Source approval expired during collection")
        digest = hashlib.sha256(body).hexdigest()
        checksum = asset.get("file:checksum")
        if checksum and (not checksum.startswith("1220") or checksum[4:] != digest):
            raise ValueError("STAC artifact checksum mismatch")
        observations = decode_hourly(body, station_id=station_id, fetched_at=fetched) if hourly else decode_daily(
            body, station_id=station_id, fetched_at=fetched, period=approval.period)
        _retain(settings.data_dir, digest, body)
        with database.session() as session:
            channel = session.scalar(select(MonitoringSourceChannel).where(
                MonitoringSourceChannel.id == key).with_for_update())
            if channel.lease_token != token or _utc(channel.lease_until) <= fetched:
                return {"status": "lease_expired"}
            record_artifact(session, digest=digest, source_id=approval.source_id,
                identity=f"{STAC}/items/{station_id.lower()}#asset={name}", body=body,
                fetched=fetched, retention_days=approval.retention_days, storage_root=settings.data_dir)
            written = 0
            hashes = {_hash(observation.series.model_dump()) for observation in observations}
            ranked = select(MonitoringSourceSample.id, func.row_number().over(
                partition_by=(MonitoringSourceSample.series_hash, MonitoringSourceSample.valid_at),
                order_by=MonitoringSourceSample.revision.desc()).label("rank")).where(
                MonitoringSourceSample.series_hash.in_(hashes), MonitoringSourceSample.valid_at >= min(o.valid_at for o in observations),
                MonitoringSourceSample.valid_at <= max(o.valid_at for o in observations)).subquery()
            existing = {(row.series_hash, _utc(row.valid_at)): row for row in session.scalars(
                select(MonitoringSourceSample).join(ranked, ranked.c.id == MonitoringSourceSample.id).where(ranked.c.rank == 1))}
            for observation in observations:
                if observation.series.allergen not in approval.allergens:
                    continue
                series_hash = _hash(observation.series.model_dump())
                previous = existing.get((series_hash, observation.valid_at))
                if previous and previous.content_hash == observation.row_hash:
                    continue
                revision = previous.revision + 1 if previous else 1
                sample = observation.sample(revision=revision, fetched_at=fetched, approval=approval)
                session.add(MonitoringSourceSample(channel_hash=sample_channel_hash(sample.series), series_hash=series_hash, valid_at=sample.valid_at,
                    revision=revision, retention_until=fetched + timedelta(days=approval.retention_days),
                    content_hash=observation.row_hash, sample_json=sample.model_dump(mode="json"),
                    provenance_json={"source_review_sha256": approval.review_sha256, "row_sha256": observation.row_hash}))
                written += 1
            channel.last_success_at, channel.error_code, channel.failures = fetched, None, 0
            channel.lease_token = channel.lease_until = None
            channel.next_fetch_at = fetched + timedelta(seconds=approval.poll_seconds)
            session.commit()
        return {"status": "collected", "new_revisions": written}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError):
        with database.session() as session:
            channel = session.scalar(select(MonitoringSourceChannel).where(
                MonitoringSourceChannel.id == key).with_for_update())
            if channel and channel.lease_token == token:
                channel.failures = min(channel.failures + 1, 16)
                channel.error_code = "official_source_unavailable"
                channel.lease_token = channel.lease_until = None
                channel.next_fetch_at = now + timedelta(seconds=min(86400, approval.poll_seconds * 2 ** channel.failures))
                session.commit()
        return {"status": "official_source_unavailable"}
    finally:
        if owned_client:
            client.close()
