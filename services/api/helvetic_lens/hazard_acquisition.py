"""Shared leased native warning collection. No private locations are sent."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .hazard_boundaries import BoundaryError
from .hazard_meteoalarm import POLL_SECONDS, MeteoAlarmError, download
from .hazard_meteoalarm_store import publish
from .hazard_native_source import permission_id as selected_permission_id
from .hazard_source_models import HazardSourcePoll
from .hazard_sources import _clock, _error, _selection, _utc, require_permission
from .monitoring_subjects import _savepoint

LEASE_SECONDS = 180


def clock():
    return datetime.now(UTC)


@dataclass(frozen=True)
class Claim:
    source_key: str
    permission_id: str
    generation: int
    cursor: int
    token: str


def claim(database, permission_id, *, now):
    now = _clock(now)
    with database.session() as session:
        _, policy = require_permission(session, permission_id, now=now)
        if policy.protocol != "meteoalarm-v2":
            return None
        selected = _selection(session, policy.source_key)
        if selected is None or selected.permission_id != permission_id:
            _error("hazard_source_selection_changed")
        try:
            with _savepoint(session):
                row = session.get(HazardSourcePoll, policy.source_key, with_for_update=True)
                if row is None:
                    row = HazardSourcePoll(source_key=policy.source_key, permission_id=permission_id, next_request_at=now)
                    session.add(row)
                    session.flush()
                if (_utc(row.next_request_at) > now or row.lease_until is not None and _utc(row.lease_until) > now):
                    return None
                token = str(uuid4())
                changed = session.execute(update(HazardSourcePoll).where(
                    HazardSourcePoll.source_key == policy.source_key, HazardSourcePoll.next_request_at <= now,
                    or_(HazardSourcePoll.lease_until.is_(None), HazardSourcePoll.lease_until <= now))
                    .values(permission_id=permission_id, lease_token=token, lease_until=now + timedelta(seconds=LEASE_SECONDS),
                            next_request_at=now + timedelta(seconds=max(POLL_SECONDS, policy.min_poll_seconds)))
                    .execution_options(synchronize_session=False))
                if changed.rowcount != 1:
                    return None
                result = Claim(policy.source_key, permission_id, selected.generation, selected.cursor_version, token)
            session.commit()
            return result
        except IntegrityError:
            return None


def owned(session, selected, *, now):
    now = _clock(now)
    require_permission(session, selected.permission_id, now=now)
    source = _selection(session, selected.source_key)
    if (source is None or source.permission_id != selected.permission_id or source.generation != selected.generation
            or source.cursor_version != selected.cursor):
        _error("hazard_source_selection_changed")
    row = session.get(HazardSourcePoll, selected.source_key, with_for_update=True, populate_existing=True)
    if (row is None or row.permission_id != selected.permission_id or row.lease_token != selected.token
            or row.lease_until is None or _utc(row.lease_until) <= now):
        _error("hazard_source_lease_lost")
    return row


def collect(database, settings, *, downloader=download, now=clock, prepare=None):
    def enabled():
        return settings.hazard_watch_enabled and settings.hazard_source_enabled

    if not enabled():
        return {"state": "disabled"}
    with database.session() as session:
        permission_id = selected_permission_id(session, settings)
    if not permission_id:
        return {"state": "unconfigured"}
    try:
        selected = claim(database, permission_id, now=now())
    except DomainError:
        return {"state": "permission_unavailable"}
    if selected is None:
        return {"state": "deferred"}

    def guard():
        if not enabled():
            _error("hazard_source_configuration_changed")
        with database.session() as session:
            if selected_permission_id(session, settings) != permission_id:
                _error("hazard_source_configuration_changed")
            owned(session, selected, now=now())

    try:
        if prepare is not None:
            prepare(guard)
        batch = downloader(now=now, checkpoint=guard)
        guard()
        with database.session() as session:
            row = owned(session, selected, now=now())
            result = publish(session, permission_id, batch, expected_generation=selected.generation,
                             expected_cursor=selected.cursor, now=now())
            finished = _clock(now())
            require_permission(session, permission_id, now=finished)
            if (not enabled() or selected_permission_id(session, settings) != permission_id
                    or row.lease_until is None or _utc(row.lease_until) <= finished):
                _error("hazard_source_lease_lost")
            row.last_success_at, row.last_code, row.failures = batch.completed_at, "published", 0
            row.lease_token = row.lease_until = None
            # Keep the start-to-start source budget; a slow valid request does
            # not add another complete polling interval to dissemination delay.
            session.commit()
        return result
    except (DomainError, ValueError, OSError) as error:
        code = error.code if isinstance(error, (DomainError, MeteoAlarmError)) else "hazard_source_contract_unavailable"
        if isinstance(error, (BoundaryError, OSError)):
            code = "hazard_boundary_installation_unavailable"
        with database.session() as session:
            row = session.scalar(select(HazardSourcePoll).where(HazardSourcePoll.source_key == selected.source_key,
                HazardSourcePoll.lease_token == selected.token).with_for_update())
            if row is not None:
                row.failures = min(row.failures + 1, 10)
                row.last_code = code
                row.next_request_at = max(_utc(row.next_request_at), _clock(now()) + timedelta(seconds=max(
                    min(3600, POLL_SECONDS * 2 ** row.failures), getattr(error, "retry_after_seconds", 0))))
                row.lease_token = row.lease_until = None
                session.commit()
        return {"state": "unavailable", "code": code}
