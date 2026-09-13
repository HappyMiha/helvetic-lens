"""Owner/tenant-scoped C1 drafts. Callers own commits and authenticated identity."""

from copy import deepcopy

from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .hazard_contracts import HazardConfiguration
from .hazard_models import HazardConfigurationRevision, HazardMonitor
from .models import User
from .monitoring_subjects import _actor, _savepoint

MAX_MONITORS = 100
MAX_REVISIONS = 1000


def _fail(code, status=409):
    raise DomainError("Saved warning locations are unavailable or changed. Reload to continue.", status, code) from None


def configuration(payload):
    try:
        return HazardConfiguration.model_validate(payload)
    except (ValidationError, ValueError, TypeError):
        _fail("hazard_configuration_invalid", 422)


def _version(value):
    if type(value) is not int or value < 1:
        _fail("hazard_version_invalid", 422)


def owned(session, user_id, monitor_id, *, write=False):
    org = _actor(session, user_id, write=write)
    row = session.scalar(select(HazardMonitor).where(HazardMonitor.id == monitor_id,
        HazardMonitor.organization_id == org, HazardMonitor.owner_user_id == user_id)
        .execution_options(populate_existing=True))
    if row is None:
        _fail("hazard_monitor_not_found", 404)
    return row


def _view(row):
    return {"id": row.id, "configuration": deepcopy(row.configuration), "status": row.status,
            "revision": row.revision, "version": row.version, "health": row.health,
            "last_poll_at": row.last_poll_at, "next_poll_at": row.next_poll_at}


def get_monitor(session, user_id, monitor_id):
    return _view(owned(session, user_id, monitor_id))


def list_monitors(session, user_id, *, limit=20, after_id=None):
    org = _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("hazard_page_invalid", 422)
    query = select(HazardMonitor).where(HazardMonitor.organization_id == org, HazardMonitor.owner_user_id == user_id)
    if after_id is not None:
        owned(session, user_id, after_id)
        query = query.where(HazardMonitor.id > after_id)
    rows = list(session.scalars(query.order_by(HazardMonitor.id).limit(limit + 1)))
    return {"items": [_view(row) for row in rows[:limit]],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def create_monitor(session, user_id, payload, request_key):
    org = _actor(session, user_id, write=True)
    if (not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 100
            or any(ord(c) < 32 for c in request_key)):
        _fail("hazard_request_key_invalid", 422)
    config = configuration(payload)
    fingerprint = config.fingerprint()

    def existing():
        return session.scalar(select(HazardMonitor).where(HazardMonitor.organization_id == org,
            HazardMonitor.owner_user_id == user_id, HazardMonitor.request_key == request_key)
            .execution_options(populate_existing=True))

    def replay(row):
        if row.request_hash != fingerprint:
            _fail("hazard_request_conflict")
        return _view(row)

    if row := existing():
        return replay(row)
    session.scalar(select(User).where(User.id == user_id).with_for_update())
    if row := existing():
        return replay(row)
    if session.scalar(select(func.count()).select_from(HazardMonitor).where(
            HazardMonitor.organization_id == org, HazardMonitor.owner_user_id == user_id)) >= MAX_MONITORS:
        _fail("hazard_monitor_limit")
    try:
        with _savepoint(session):
            row = HazardMonitor(organization_id=org, owner_user_id=user_id, request_key=request_key,
                request_hash=fingerprint, configuration=config.model_dump(mode="json"))
            session.add(row)
            session.flush()
            session.add(HazardConfigurationRevision(organization_id=org, monitor_id=row.id, revision=1,
                configuration=row.configuration, configuration_hash=fingerprint))
            session.flush()
    except IntegrityError:
        if row := existing():
            return replay(row)
        raise
    return _view(row)


def edit_monitor(session, user_id, monitor_id, version, payload):
    row = owned(session, user_id, monitor_id, write=True)
    _version(version)
    if row.version != version or row.status not in {"draft", "paused"}:
        _fail("hazard_version_conflict")
    config = configuration(payload)
    values = config.model_dump(mode="json")
    if values == row.configuration:
        return _view(row)
    if row.revision >= MAX_REVISIONS:
        _fail("hazard_revision_limit")
    with _savepoint(session):
        changed = session.execute(update(HazardMonitor).where(HazardMonitor.id == row.id,
            HazardMonitor.organization_id == row.organization_id, HazardMonitor.owner_user_id == user_id,
            HazardMonitor.version == version, HazardMonitor.status.in_(("draft", "paused")))
            .values(configuration=values, version=version + 1, revision=row.revision + 1, status="draft",
                    health="not_started", next_poll_at=None, activation_proof=None)
            .execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            _fail("hazard_version_conflict")
        session.add(HazardConfigurationRevision(organization_id=row.organization_id, monitor_id=row.id,
            revision=row.revision + 1, configuration=values, configuration_hash=config.fingerprint()))
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def revisions(session, user_id, monitor_id, *, before=None, limit=20):
    row = owned(session, user_id, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("hazard_page_invalid", 422)
    query = select(HazardConfigurationRevision).where(HazardConfigurationRevision.monitor_id == row.id,
        HazardConfigurationRevision.organization_id == row.organization_id)
    if before is not None:
        _version(before)
        if before > row.revision:
            _fail("hazard_revision_cursor_invalid", 422)
        query = query.where(HazardConfigurationRevision.revision < before)
    rows = list(session.scalars(query.order_by(HazardConfigurationRevision.revision.desc()).limit(limit + 1)))
    return {"items": [{"revision": r.revision, "configuration": deepcopy(r.configuration),
                       "configuration_hash": r.configuration_hash} for r in rows[:limit]],
            "next_cursor": rows[limit - 1].revision if len(rows) > limit else None}


def archive_monitor(session, user_id, monitor_id, version):
    from .db import utcnow
    from .hazard_lifecycle import command

    row = owned(session, user_id, monitor_id, write=True)
    _version(version)
    if row.version != version:
        _fail("hazard_version_conflict")
    if row.status == "archived":
        return _view(row)
    return command(session, user_id, monitor_id, version, "archive", settings=None, store=None, now=utcnow())


def delete_monitor(session, user_id, monitor_id, version):
    row = owned(session, user_id, monitor_id, write=True)
    _version(version)
    if row.version != version or row.status != "archived":
        _fail("hazard_archive_before_delete")
    changed = session.execute(delete(HazardMonitor).where(HazardMonitor.id == row.id,
        HazardMonitor.organization_id == row.organization_id, HazardMonitor.owner_user_id == user_id,
        HazardMonitor.version == version, HazardMonitor.status == "archived")
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        _fail("hazard_version_conflict")


def preview(session, user_id, payload, *, geography_resolver=None):
    _actor(session, user_id)
    config = configuration(payload)
    geography = (geography_resolver(config.location) if geography_resolver else
                 {"state": "unavailable", "reason": "boundary_catalogue_not_installed"})
    reasons = ["hazard_source_not_configured"]
    if geography["state"] != "verified":
        reasons.append("hazard_location_not_verified")
    if config.location.kind == "point" and config.location.radius_km > 0:
        reasons.append("hazard_radius_coverage_not_verified")
    # Administrative proof is separate from warning-channel rights/coverage.
    return {"configuration": config.model_dump(mode="json"), "draft_available": True,
            "start_available": False, "live_results_checked": False,
            "blocking_reasons": reasons, "geography": geography}
