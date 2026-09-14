"""Owner/tenant-scoped B8 portfolios. Callers own commits and authenticated identity."""

from copy import deepcopy

from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from .auction_contracts import AuctionProfile
from .auction_models import AuctionConfigurationRevision, AuctionMonitor
from .auction_workflow_models import AuctionRuntime
from .business_monitor_access import scope_view, visible_to
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor, _savepoint

MAX_MONITORS = 100
MAX_REVISIONS = 1000


def _fail(code, status=409):
    raise DomainError("Saved auction interest profiles are unavailable or changed. Reload to continue.", status, code) from None


def configuration(payload):
    try:
        return AuctionProfile.model_validate(payload)
    except (ValidationError, ValueError, TypeError):
        _fail("auction_configuration_invalid", 422)


def _version(value):
    if type(value) is not int or value < 1:
        _fail("auction_version_invalid", 422)


def owned(session, user_id, monitor_id, *, write=False, personal_only=False):
    from .business_monitor_sharing import monitor_for
    try:
        return monitor_for(session, user_id, "auctions", monitor_id, write=write, personal_only=personal_only)
    except DomainError as error:
        if error.code == "business_monitor_not_found":
            raise DomainError("Business monitor not found.", 404, "auction_monitor_not_found") from None
        raise


def _view(row):
    return {**scope_view(row),"id": row.id, "configuration": deepcopy(row.configuration), "status": row.status,
            "revision": row.revision, "version": row.version}


def get_monitor(session, user_id, monitor_id):
    row = owned(session, user_id, monitor_id)
    result = _view(row)
    runtime = session.get(AuctionRuntime, row.id)
    if runtime:
        from .auction_sources import _utc
        result["runtime"] = {"health": runtime.health,
            "last_check_at": _utc(runtime.last_check_at).isoformat() if runtime.last_check_at else None,
            "next_check_at": _utc(runtime.next_check_at).isoformat() if runtime.next_check_at and row.status == "active" else None}
    return result


def list_monitors(session, user_id, *, limit=20, after_id=None):
    org = _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("auction_page_invalid", 422)
    query = select(AuctionMonitor).where(AuctionMonitor.organization_id == org, visible_to(AuctionMonitor, user_id))
    if after_id is not None:
        owned(session, user_id, after_id)
        query = query.where(AuctionMonitor.id > after_id)
    rows = list(session.scalars(query.order_by(AuctionMonitor.id).limit(limit + 1)))
    return {"items": [_view(row) for row in rows[:limit]],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def create_monitor(session, user_id, payload, request_key):
    org = _actor(session, user_id, write=True)
    if (not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 100
            or any(ord(c) < 32 for c in request_key)):
        _fail("auction_request_key_invalid", 422)
    config = configuration(payload)
    fingerprint = config.fingerprint()

    def existing():
        return session.scalar(select(AuctionMonitor).where(AuctionMonitor.organization_id == org,
            AuctionMonitor.owner_user_id == user_id, AuctionMonitor.request_key == request_key)
            .execution_options(populate_existing=True))

    def replay(row):
        if row.request_hash != fingerprint:
            _fail("auction_request_conflict")
        return _view(row)

    if row := existing():
        return replay(row)
    session.scalar(select(User).where(User.id == user_id).with_for_update())
    if row := existing():
        return replay(row)
    if session.scalar(select(func.count()).select_from(AuctionMonitor).where(
            AuctionMonitor.organization_id == org, AuctionMonitor.owner_user_id == user_id)) >= MAX_MONITORS:
        _fail("auction_monitor_limit")
    try:
        with _savepoint(session):
            row = AuctionMonitor(organization_id=org, owner_user_id=user_id, request_key=request_key,
                request_hash=fingerprint, configuration=config.model_dump(mode="json"))
            session.add(row)
            session.flush()
            session.add(AuctionConfigurationRevision(organization_id=org, monitor_id=row.id, revision=1,
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
        _fail("auction_version_conflict")
    config = configuration(payload)
    values = config.model_dump(mode="json")
    if values == row.configuration:
        return _view(row)
    if row.revision >= MAX_REVISIONS:
        _fail("auction_revision_limit")
    with _savepoint(session):
        changed = session.execute(update(AuctionMonitor).where(AuctionMonitor.id == row.id,
            AuctionMonitor.organization_id == row.organization_id, visible_to(AuctionMonitor, user_id),
            AuctionMonitor.version == version, AuctionMonitor.status.in_(("draft", "paused")))
            .values(configuration=values, version=version + 1, revision=row.revision + 1, status="draft")
            .execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            _fail("auction_version_conflict")
        session.add(AuctionConfigurationRevision(organization_id=row.organization_id, monitor_id=row.id,
            revision=row.revision + 1, configuration=values, configuration_hash=config.fingerprint()))
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def revisions(session, user_id, monitor_id, *, before=None, limit=20):
    row = owned(session, user_id, monitor_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("auction_page_invalid", 422)
    query = select(AuctionConfigurationRevision).where(AuctionConfigurationRevision.monitor_id == row.id,
        AuctionConfigurationRevision.organization_id == row.organization_id)
    if before is not None:
        _version(before)
        if before > row.revision:
            _fail("auction_revision_cursor_invalid", 422)
        query = query.where(AuctionConfigurationRevision.revision < before)
    rows = list(session.scalars(query.order_by(AuctionConfigurationRevision.revision.desc()).limit(limit + 1)))
    return {"items": [{"revision": r.revision, "configuration": deepcopy(r.configuration),
                       "configuration_hash": r.configuration_hash} for r in rows[:limit]],
            "next_cursor": rows[limit - 1].revision if len(rows) > limit else None}


def archive_monitor(session, user_id, monitor_id, version):
    from .auction_email_preferences import cancel_email_work
    row = owned(session, user_id, monitor_id, write=True)
    _version(version)
    if row.version != version:
        _fail("auction_version_conflict")
    if row.status == "archived":
        return _view(row)
    if row.status not in {"draft", "paused"}:
        _fail("auction_stop_before_archive")
    changed = session.execute(update(AuctionMonitor).where(AuctionMonitor.id == row.id,
        AuctionMonitor.organization_id == row.organization_id, visible_to(AuctionMonitor, user_id),
        AuctionMonitor.version == version, AuctionMonitor.status.in_(("draft", "paused"))).values(status="archived", version=version + 1)
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        _fail("auction_version_conflict")
    cancel_email_work(session, row)
    return get_monitor(session, user_id, monitor_id)


def delete_monitor(session, user_id, monitor_id, version):
    row = owned(session, user_id, monitor_id, write=True)
    _version(version)
    if row.version != version or row.status != "archived":
        _fail("auction_archive_before_delete")
    changed = session.execute(delete(AuctionMonitor).where(AuctionMonitor.id == row.id,
        AuctionMonitor.organization_id == row.organization_id, visible_to(AuctionMonitor, user_id),
        AuctionMonitor.version == version, AuctionMonitor.status == "archived")
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        _fail("auction_version_conflict")


def preview(session, user_id, payload):
    _actor(session, user_id)
    config = configuration(payload)
    return {"configuration": config.model_dump(mode="json"), "draft_available": True,
            "start_available": False, "live_results_checked": False,
            "blocking_reasons": ["auction_source_not_configured"]}
