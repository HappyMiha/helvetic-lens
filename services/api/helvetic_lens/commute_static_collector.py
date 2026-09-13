"""One durable, default-off shared static collector; no private routes on wire."""

import csv
import re
from datetime import timedelta
from uuid import UUID, uuid4
from zipfile import BadZipFile

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .commute_acquisition import AcquisitionError
from .commute_models import CommuteStaticArchive, CommuteStaticPoll
from .commute_sources import SOURCES, clock, read_feed, require_permission, utc
from .commute_static_acquisition import acquire_archive, fetch_catalog, select_resource
from .config import DomainError
from .monitoring_subjects import _savepoint
from .transport_static import MAX_ARCHIVE, StaticArchive

POLL_ID = "static"
INTERVAL = 900
LEASE_SECONDS = 1800
MAX_VERSIONS = 512


def enabled(settings):
    return settings.commute_watch_enabled and settings.commute_source_enabled and settings.commute_static_enabled


def current_version(database, now):
    with database.session() as session:
        readings = [read_feed(session, source, now=now, require_fresh=True) for source in SOURCES]
        versions = {snapshot.feed_version for _, _, snapshot in readings}
        if len(versions) != 1 or None in versions or "" in versions:
            raise AcquisitionError("static_feed_version_ambiguous")
        permissions = {source: permission.id for source, (_, permission, _) in zip(SOURCES, readings, strict=True)}
        return versions.pop(), permissions


def claim(database, permissions, now):
    token = str(uuid4())
    with database.session() as session:
        for source, permission in permissions.items():
            require_permission(session, permission, source, now=now)
        if session.get(CommuteStaticPoll, POLL_ID) is None:
            try:
                with _savepoint(session):
                    session.add(CommuteStaticPoll(id=POLL_ID, next_attempt_at=now))
                    session.flush()
            except IntegrityError:
                pass
        result = session.execute(update(CommuteStaticPoll).where(CommuteStaticPoll.id == POLL_ID,
            CommuteStaticPoll.blocked.is_(False), CommuteStaticPoll.next_attempt_at <= now,
            or_(CommuteStaticPoll.lease_until.is_(None), CommuteStaticPoll.lease_until <= now))
            .values(lease_token=token, lease_until=now + timedelta(seconds=LEASE_SECONDS),
                    next_attempt_at=now + timedelta(seconds=INTERVAL)).execution_options(synchronize_session=False))
        session.commit()
        return token if result.rowcount == 1 else None


def owned(session, settings, token, permissions, now):
    if not enabled(settings):
        raise AcquisitionError("static_disabled")
    for source, permission in permissions.items():
        require_permission(session, permission, source, now=now)
    row = session.scalar(select(CommuteStaticPoll).where(CommuteStaticPoll.id == POLL_ID).with_for_update()
                         .execution_options(populate_existing=True))
    if row is None or row.lease_token != token or row.lease_until is None or utc(row.lease_until) <= now:
        raise AcquisitionError("static_lease_lost")
    return row


def _path(directory, sha256):
    if not re.fullmatch(r"[a-f0-9]{64}", sha256):
        raise AcquisitionError("static_cache_invalid", blocked=True)
    path = directory / (sha256 + ".zip")
    if path.is_symlink():
        raise AcquisitionError("static_cache_invalid", blocked=True)
    return path


def _usage(directory):
    total = 0
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file():
            raise AcquisitionError("static_cache_invalid", blocked=True)
        total += path.stat().st_size
    return total


def _reserve(database, settings, directory, version, token, permissions, now):
    """Reserve one maximum-sized staging file; only expire owned old ZIP cache."""
    directory.mkdir(parents=True, exist_ok=True)
    with database.session() as session:
        owned(session, settings, token, permissions, now)
        used = _usage(directory)
        rows = list(session.scalars(select(CommuteStaticArchive).where(CommuteStaticArchive.present.is_(True),
            CommuteStaticArchive.version != version, CommuteStaticArchive.last_used_at < now - timedelta(days=7))
            .order_by(CommuteStaticArchive.last_used_at)))
        for row in rows:
            if used + MAX_ARCHIVE <= settings.commute_static_cache_max_bytes:
                break
            path = _path(directory, row.sha256)
            if path.exists():
                size = path.stat().st_size
                path.unlink()  # Exact hash-named disposable cache file; history rows are retained.
                used -= size
            row.present = False
        session.commit()
    if used + MAX_ARCHIVE > settings.commute_static_cache_max_bytes:
        raise AcquisitionError("static_cache_full")


def collect(database, settings, *, catalog=fetch_catalog, downloader=acquire_archive, now=clock):
    from .commute_catalog_worker import renew_cached
    if not enabled(settings):
        return {"state": "disabled"}
    try:
        if str(UUID(settings.commute_static_dataset_id)) != settings.commute_static_dataset_id:
            raise ValueError
    except (ValueError, AttributeError):
        return {"state": "unconfigured"}
    try:
        version, permissions = current_version(database, now())
        token = claim(database, permissions, now())
    except (AcquisitionError, DomainError, ValueError):
        return {"state": "source_unavailable"}
    if token is None:
        return {"state": "deferred"}
    directory = (settings.storage_path / "commute-static").absolute()

    def guard():
        with database.session() as session:
            owned(session, settings, token, permissions, now())

    try:
        with database.session() as session:
            owned(session, settings, token, permissions, now())
            binding = session.get(CommuteStaticArchive, version)
            values = None if binding is None else {"sha256": binding.sha256, "size": binding.size,
                "dataset_id": binding.dataset_id, "resource_id": binding.resource_id, "resource_url": binding.resource_url,
                "valid_from": binding.valid_from, "valid_to": binding.valid_to}
            if values is None and session.scalar(select(func.count()).select_from(CommuteStaticArchive)) >= MAX_VERSIONS:
                raise AcquisitionError("static_version_limit", blocked=True)
        if values and values["dataset_id"] != settings.commute_static_dataset_id:
            raise AcquisitionError("static_dataset_conflict", blocked=True)
        path = _path(directory, values["sha256"]) if values else None
        if path and path.is_file():
            if path.stat().st_size != values["size"]:
                raise AcquisitionError("static_cache_conflict", blocked=True)
            try:
                with StaticArchive(path, expected_version=version) as archive:
                    if archive.sha256 != values["sha256"]:
                        raise AcquisitionError("static_cache_conflict", blocked=True)
            except (BadZipFile, csv.Error, ValueError):
                raise AcquisitionError("static_cache_conflict", blocked=True) from None
            state, artifact = "cached", None
        else:
            _reserve(database, settings, directory, version, token, permissions, now())
            payload = catalog(settings.commute_static_dataset_id, guard=guard, now=now)
            resource = select_resource(payload, dataset_id=settings.commute_static_dataset_id, version=version)
            if values and (resource.resource_id != values["resource_id"] or resource.url != values["resource_url"]):
                raise AcquisitionError("static_resource_conflict", blocked=True)
            artifact = downloader(resource, directory, redirect_origins=settings.commute_static_redirect_origins,
                expected_sha256=values["sha256"] if values else None, guard=guard, now=now)
            if (artifact.resource != resource or artifact.path != _path(directory, artifact.sha256)
                    or artifact.size <= 0 or artifact.size > MAX_ARCHIVE):
                raise AcquisitionError("static_artifact_invalid", blocked=True)
            state, path = "acquired", artifact.path
        with database.session() as session:
            poll = owned(session, settings, token, permissions, now())
            binding = session.get(CommuteStaticArchive, version)
            if binding is None:
                session.add(CommuteStaticArchive(version=version, dataset_id=artifact.resource.dataset_id,
                    resource_id=artifact.resource.resource_id, resource_url=artifact.resource.url,
                    sha256=artifact.sha256, size=artifact.size, valid_from=artifact.valid_from, valid_to=artifact.valid_to,
                    acquired_at=now(), last_used_at=now(), present=True))
            else:
                if artifact and artifact.sha256 != binding.sha256:
                    raise AcquisitionError("static_checksum_conflict", blocked=True)
                binding.last_used_at, binding.present = now(), True
            # Commit the durable cache binding, retaining the same shared lease
            # through renewal so GC cannot remove an archive being scanned.
            session.commit()
        renew_cached(database, settings, path, version, artifact.sha256 if artifact else values["sha256"],
                     token, permissions, now=now)
        with database.session() as session:
            poll = owned(session, settings, token, permissions, now())
            poll.last_code, poll.failures = state, 0
            poll.lease_token, poll.lease_until = None, None
            poll.next_attempt_at = now() + timedelta(seconds=INTERVAL)
            session.commit()
        return {"state": state, "version": version}
    except (AcquisitionError, DomainError, ValueError, OSError, BadZipFile, csv.Error) as error:
        code = error.code if isinstance(error, (AcquisitionError, DomainError)) else "static_cache_error"
        with database.session() as session:
            poll = session.scalar(select(CommuteStaticPoll).where(CommuteStaticPoll.id == POLL_ID,
                CommuteStaticPoll.lease_token == token).with_for_update())
            if poll:
                poll.failures = min(poll.failures + 1, 10)
                poll.last_code, poll.blocked = code, bool(getattr(error, "blocked", False))
                poll.lease_token, poll.lease_until = None, None
                poll.next_attempt_at = max(utc(poll.next_attempt_at), now() + timedelta(seconds=max(
                    min(86400, INTERVAL * 2 ** poll.failures), getattr(error, "retry_after", 0))))
                session.commit()
        return {"state": "unavailable", "code": code}
