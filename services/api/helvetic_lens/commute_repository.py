"""Private commute lifecycle. Callers own transactions and authenticated identity."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from .commute_catalog import preview_version, require_references, resolve_configuration
from .commute_contracts import CommuteConfiguration
from .commute_models import CommuteConfigurationRevision, CommuteLegReference, CommuteMonitor
from .commute_pause import notification_pause_until
from .commute_sources import utc
from .config import DomainError
from .models import User
from .monitoring_subjects import _actor, _savepoint
from .transport_reference import ZURICH, commute_window


def configuration(value):
    try:
        return CommuteConfiguration.model_validate(value)
    except ValidationError:
        raise DomainError("Invalid commute settings.", 422, "commute_configuration_invalid") from None


def positive(value):
    if type(value) is not int or value < 1:
        raise DomainError("A positive version is required.", 422, "commute_version_invalid")


def owned(session, user_id, monitor_id, *, write=False):
    organization = _actor(session, user_id, write=write)
    row = session.scalar(select(CommuteMonitor).where(CommuteMonitor.id == monitor_id,
        CommuteMonitor.organization_id == organization, CommuteMonitor.owner_user_id == user_id)
        .execution_options(populate_existing=True))
    if row is None:
        raise DomainError("Commute monitor not found.", 404, "commute_not_found")
    return row


def view(row, session, *, now=None):
    return {"id": row.id, "configuration": deepcopy(row.configuration), "revision": row.revision,
            "version": row.version, "status": row.status, "health": row.health,
            "paused_on": row.paused_on.isoformat() if row.paused_on else None,
            "notification_pause_until": notification_pause_until(row, now=now),
            "last_check_at": utc(row.last_poll_at).isoformat() if row.last_poll_at else None,
            "next_check_at": utc(row.next_poll_at).isoformat() if row.status == "active" else None,
            "reference_labels": reference_labels(session, row.configuration)}


def get_monitor(session, user_id, monitor_id, *, now=None):
    row = owned(session, user_id, monitor_id)
    return view(row, session, now=now)


def reference_labels(session, config):
    return [{"id": row.id, "label": row.label, "enabled": row.enabled}
            for row in session.scalars(select(CommuteLegReference).where(
                CommuteLegReference.id.in_(config["leg_reference_ids"])))]


def list_monitors(session, user_id, *, limit=20, after_id=None):
    organization = _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("Choose a page size from one to 100.", 422, "commute_limit_invalid")
    statement = select(CommuteMonitor).where(CommuteMonitor.organization_id == organization,
                                            CommuteMonitor.owner_user_id == user_id)
    if after_id:
        owned(session, user_id, after_id)
        statement = statement.where(CommuteMonitor.id > after_id)
    rows = list(session.scalars(statement.order_by(CommuteMonitor.id).limit(limit + 1)))
    return {"items": [view(row, session) for row in rows[:limit]],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def create_monitor(session, user_id, payload, key):
    organization = _actor(session, user_id, write=True)
    if not isinstance(key, str) or not key.strip() or len(key) > 100 or any(ord(c) < 32 for c in key):
        raise DomainError("A bounded save request key is required.", 422, "commute_request_invalid")
    config = configuration(payload)
    hashed = config.fingerprint()

    def existing():
        return session.scalar(select(CommuteMonitor).where(CommuteMonitor.organization_id == organization,
            CommuteMonitor.owner_user_id == user_id, CommuteMonitor.request_key == key)
            .execution_options(populate_existing=True))

    def replay(row):
        if row.request_hash != hashed:
            raise DomainError("This save request has different settings.", 409, "commute_request_conflict")
        return view(row, session)

    if row := existing():
        return replay(row)
    require_references(session, config)
    # The owner row serializes quota checks on PostgreSQL.
    session.scalar(select(User).where(User.id == user_id).with_for_update())
    if session.scalar(select(func.count()).select_from(CommuteMonitor).where(
            CommuteMonitor.organization_id == organization, CommuteMonitor.owner_user_id == user_id)) >= 100:
        raise DomainError("Remove an old commute before creating another.", 409, "commute_limit_reached")
    try:
        with _savepoint(session):
            row = CommuteMonitor(organization_id=organization, owner_user_id=user_id, request_key=key,
                                 request_hash=hashed, configuration=config.model_dump(mode="json"))
            session.add(row)
            session.flush()
            session.add(CommuteConfigurationRevision(monitor_id=row.id, organization_id=organization, revision=1,
                                                     configuration=row.configuration, configuration_hash=hashed))
            session.flush()
    except IntegrityError:
        if row := existing():
            return replay(row)
        raise
    return view(row, session)


def edit_monitor(session, user_id, monitor_id, version, payload):
    row = owned(session, user_id, monitor_id, write=True)
    positive(version)
    config = configuration(payload)
    if row.version != version or row.status not in ("draft", "paused"):
        raise DomainError("Pause the commute and reload before editing.", 409, "commute_version_conflict")
    require_references(session, config)
    if row.revision >= 1000:
        raise DomainError("The saved revision limit has been reached.", 409, "commute_revision_limit")
    values = config.model_dump(mode="json")
    if values == row.configuration:
        return view(row, session)
    with _savepoint(session):
        changed = session.execute(update(CommuteMonitor).where(CommuteMonitor.id == monitor_id,
            CommuteMonitor.organization_id == row.organization_id, CommuteMonitor.owner_user_id == user_id,
            CommuteMonitor.version == version, CommuteMonitor.status.in_(("draft", "paused")))
            .values(configuration=values, revision=row.revision + 1, version=version + 1,
                    status="draft", health="not_started", paused_on=None).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise DomainError("The commute changed. Reload it.", 409, "commute_version_conflict")
        session.add(CommuteConfigurationRevision(monitor_id=row.id, organization_id=row.organization_id,
            revision=row.revision + 1, configuration=values, configuration_hash=config.fingerprint()))
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def preview(session, user_id, payload, *, service_day, static_version=None, settings=None, now=None):
    from .commute_jobs import ready
    from .commute_sources import clock
    _actor(session, user_id, write=True)
    config = configuration(payload)
    static_version = static_version or preview_version(session, config, service_day=service_day, now=clock(now))
    # Exact dates/versions only. Do not silently use the latest unrelated archive.
    resolved = resolve_configuration(session, config, service_day=service_day, static_version=static_version)
    from .commute_interchanges import ALLOWED, journey_interchanges
    interchanges = journey_interchanges(session, config, resolved)
    plans, reasons = [], []
    if any(proof["state"] not in ALLOWED for proof in interchanges):
        reasons.append("transfer_not_verified")
    try:
        ready(session, settings, config, now=clock(now), service_day=service_day, static_version=static_version)
    except DomainError as error:
        reasons.append(error.code)
    for reference_id in config.leg_reference_ids:
        leg = resolved[str(reference_id)]
        local_departure = leg.departure.astimezone(ZURICH)
        day = local_departure.date()
        if config.window_end < config.window_start and local_departure.strftime("%H:%M") < config.window_end:
            day -= timedelta(days=1)
        try:
            window = commute_window(day, config.window_start, config.window_end, config.weekdays)
        except ValueError:
            window = None
            reasons.append("nonexistent_wall_time")
        if not window or not window[0] <= leg.departure < window[1]:
            reasons.append("departure_outside_saved_window")
        plans.append({"reference_id": str(reference_id), "boarding_name": leg.boarding_name,
                      "alighting_name": leg.alighting_name, "route_name": leg.route_name,
                      "departure": leg.departure.isoformat(), "arrival": leg.arrival.isoformat(),
                      "static_version": leg.reference.static_version, "archive_sha256": leg.archive_sha256})
    return {"configuration": config.model_dump(mode="json"), "configuration_hash": config.fingerprint(),
            "service_day": service_day.isoformat(), "legs": plans, "interchanges": interchanges, "start_available": not reasons,
            "blocking_reasons": list(dict.fromkeys(reasons)), "live_results_checked": False}


def command(session, user_id, monitor_id, version, action, *, now=None, settings=None):
    from .commute_jobs import cancel_work, enqueue, ready
    row = owned(session, user_id, monitor_id, write=True)
    positive(version)
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use an aware lifecycle clock")
    if row.version != version:
        raise DomainError("The commute changed. Reload it.", 409, "commute_version_conflict")
    if action in ("start", "resume"):
        allowed = "draft" if action == "start" else "paused"
        if row.status != allowed:
            raise DomainError("This action is unavailable for the commute.", 409, "commute_action_invalid")
        try:
            ready(session, settings, configuration(row.configuration), now=now)
        except DomainError:
            raise DomainError("Live transport processing is not ready.", 409, "commute_source_not_ready") from None
        values = {"status": "active", "health": "waiting", "next_poll_at": now, "paused_on": None}
    elif action == "archive" and row.status in ("draft", "active", "paused"):
        values = {"status": "archived", "paused_on": None}
    elif action == "pause" and row.status == "active":
        values = {"status": "paused", "paused_on": None}
    elif action == "pause_today" and row.status == "active":
        values = {"paused_on": now.astimezone(ZURICH).date()}
    elif action == "unpause_today" and row.status == "active":
        values = {"paused_on": None}
    else:
        raise DomainError("This action is unavailable for the commute.", 409, "commute_action_invalid")
    with _savepoint(session):
        changed = session.execute(update(CommuteMonitor).where(CommuteMonitor.id == monitor_id,
            CommuteMonitor.organization_id == row.organization_id, CommuteMonitor.owner_user_id == user_id,
            CommuteMonitor.version == version, CommuteMonitor.status == row.status).values(**values, version=version + 1)
            .execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise DomainError("The commute changed. Reload it.", 409, "commute_version_conflict")
        cancel_work(session, row)
        session.refresh(row)
        if row.status == "active":
            enqueue(session, row, now)
    return get_monitor(session, user_id, monitor_id, now=now)


def remove_monitor(session, user_id, monitor_id, version):
    from .commute_jobs import cancel_work
    row = owned(session, user_id, monitor_id, write=True)
    positive(version)
    if row.version != version:
        raise DomainError("The commute changed. Reload before deleting.", 409, "commute_version_conflict")
    cancel_work(session, row)
    changed = session.execute(delete(CommuteMonitor).where(CommuteMonitor.id == row.id,
        CommuteMonitor.organization_id == row.organization_id, CommuteMonitor.owner_user_id == user_id,
        CommuteMonitor.version == version).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise DomainError("The commute changed. Reload before deleting.", 409, "commute_version_conflict")


def revisions(session, user_id, monitor_id, *, after_revision=0, limit=20):
    row = owned(session, user_id, monitor_id)
    if type(after_revision) is not int or after_revision < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise DomainError("Invalid history page.", 422, "commute_history_query_invalid")
    records = list(session.scalars(select(CommuteConfigurationRevision).where(
        CommuteConfigurationRevision.monitor_id == row.id, CommuteConfigurationRevision.organization_id == row.organization_id,
        CommuteConfigurationRevision.revision > after_revision).order_by(CommuteConfigurationRevision.revision).limit(limit + 1)))
    return {"items": [{"revision": r.revision, "configuration": deepcopy(r.configuration),
                       "configuration_hash": r.configuration_hash,
                       "reference_labels": reference_labels(session, r.configuration)} for r in records[:limit]],
            "next_cursor": records[limit - 1].revision if len(records) > limit else None}
