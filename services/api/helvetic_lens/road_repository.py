"""Owner-scoped Road Watch drafts. Callers supply authenticated identity and own transactions."""

from copy import deepcopy

from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from .config import DomainError
from .models import User
from .monitoring_subjects import _actor, _savepoint
from .road_catalog import CatalogReadBudget, _reference, describe_reference
from .road_contracts import RoadConfiguration
from .road_models import (
    RoadConfigurationRevision,
    RoadCorridorMap,
    RoadCorridorReference,
    RoadMonitor,
    RoadTopologyRevision,
)
from .road_sources import _clock, _utc


def _fail(code, status=409):
    raise DomainError("Road Watch settings are unavailable or changed. Reload to continue.", status, code) from None


def configuration(payload):
    try:
        # JSON validation permits JSON arrays for the strict nested materiality
        # tuple, while still rejecting strings/bools masquerading as numbers.
        from .road_sources import _encoded
        return RoadConfiguration.model_validate_json(_encoded(payload))
    except (ValidationError, ValueError, TypeError):
        _fail("road_configuration_invalid", 422)


def _positive(version):
    if type(version) is not int or version < 1:
        _fail("road_monitor_version_invalid", 422)


def owned(session, user_id, monitor_id, *, write=False):
    org = _actor(session, user_id, write=write)
    row = session.scalar(select(RoadMonitor).where(RoadMonitor.id == monitor_id,
        RoadMonitor.organization_id == org, RoadMonitor.owner_user_id == user_id)
        .execution_options(populate_existing=True))
    if row is None:
        _fail("road_monitor_not_found", 404)
    return row


def _view(row):
    # Do not attach licensed catalogue labels to private history without current
    # display rights. The owner's own settings remain available for editing.
    return {"id": row.id, "configuration": deepcopy(row.configuration), "revision": row.revision,
            "version": row.version, "status": row.status, "health": row.health,
            "last_check_at": _utc(row.last_poll_at).isoformat() if row.last_poll_at else None}


def get_monitor(session, user_id, monitor_id):
    return _view(owned(session, user_id, monitor_id))


def _require_references(session, config):
    # Drafts can survive expired grants, but new selections must be real enabled
    # reviewed reference identities. Saving does not assert current source access.
    for reference_id in sorted(str(value) for value in config.corridor_reference_ids):
        ref = _reference(session, reference_id)
        if not ref.enabled or session.scalar(select(RoadCorridorMap.id).where(
                RoadCorridorMap.reference_id == ref.id).limit(1)) is None:
            _fail("road_corridor_not_selectable")


def _limit(value):
    if type(value) is not int or not 1 <= value <= 100:
        _fail("road_monitor_page_invalid", 422)


def list_monitors(session, user_id, *, limit=20, after_id=None):
    org = _actor(session, user_id)
    _limit(limit)
    query = select(RoadMonitor).where(RoadMonitor.organization_id == org, RoadMonitor.owner_user_id == user_id)
    if after_id is not None:
        owned(session, user_id, after_id)
        query = query.where(RoadMonitor.id > after_id)
    rows = list(session.scalars(query.order_by(RoadMonitor.id).limit(limit + 1)))
    return {"items": [_view(row) for row in rows[:limit]],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


def create_monitor(session, user_id, payload, key):
    org = _actor(session, user_id, write=True)
    if not isinstance(key, str) or not key.strip() or len(key) > 100 or any(ord(c) < 32 for c in key):
        _fail("road_monitor_request_invalid", 422)
    config = configuration(payload)
    hashed = config.fingerprint()

    def existing():
        return session.scalar(select(RoadMonitor).where(RoadMonitor.organization_id == org,
            RoadMonitor.owner_user_id == user_id, RoadMonitor.request_key == key)
            .execution_options(populate_existing=True))

    def replay(row):
        if row.request_hash != hashed:
            _fail("road_monitor_request_conflict")
        return _view(row)

    if row := existing():
        return replay(row)
    _require_references(session, config)
    session.scalar(select(User).where(User.id == user_id).with_for_update())
    if session.scalar(select(func.count()).select_from(RoadMonitor).where(
            RoadMonitor.organization_id == org, RoadMonitor.owner_user_id == user_id)) >= 100:
        _fail("road_monitor_limit_reached")
    try:
        with _savepoint(session):
            row = RoadMonitor(organization_id=org, owner_user_id=user_id, request_key=key, request_hash=hashed,
                              configuration=config.model_dump(mode="json"))
            session.add(row)
            session.flush()
            session.add(RoadConfigurationRevision(monitor_id=row.id, organization_id=org, revision=1,
                configuration=row.configuration, configuration_hash=hashed))
            session.flush()
    except IntegrityError:
        if row := existing():
            return replay(row)
        raise
    return _view(row)


def edit_monitor(session, user_id, monitor_id, version, payload):
    row = owned(session, user_id, monitor_id, write=True)
    _positive(version)
    if row.version != version or row.status not in ("draft", "paused"):
        _fail("road_monitor_version_conflict")
    config = configuration(payload)
    _require_references(session, config)
    values = config.model_dump(mode="json")
    if values == row.configuration:
        return _view(row)
    if row.revision >= 1000:
        _fail("road_monitor_revision_limit")
    with _savepoint(session):
        updated = session.execute(update(RoadMonitor).where(RoadMonitor.id == row.id,
            RoadMonitor.organization_id == row.organization_id, RoadMonitor.owner_user_id == user_id,
            RoadMonitor.version == version, RoadMonitor.status.in_(("draft", "paused")))
            .values(configuration=values, revision=row.revision + 1, version=version + 1, status="draft", health="not_started")
            .execution_options(synchronize_session=False))
        if updated.rowcount != 1:
            _fail("road_monitor_version_conflict")
        session.add(RoadConfigurationRevision(monitor_id=row.id, organization_id=row.organization_id,
            revision=row.revision + 1, configuration=values, configuration_hash=config.fingerprint()))
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def command(session, user_id, monitor_id, version, action, *, settings=None, now=None):
    from .road_jobs import cancel_work, clock, enqueue, ready
    row = owned(session, user_id, monitor_id, write=True)
    row = session.scalar(select(RoadMonitor).where(RoadMonitor.id == row.id).with_for_update()
                         .execution_options(populate_existing=True))
    _positive(version)
    now = _clock(now or clock())
    if row.version != version:
        _fail("road_monitor_version_conflict")
    if action in ("start", "resume"):
        if row.status != ("draft" if action == "start" else "paused"):
            _fail("road_monitor_action_invalid")
        ready(session, settings, configuration(row.configuration), now=now)
        target = "active"
    else:
        target = "archived" if action == "archive" else "paused" if action == "pause" else None
    if target is None or row.status == "archived" or (action == "pause" and row.status != "active"):
        _fail("road_monitor_action_invalid")
    updated = session.execute(update(RoadMonitor).where(RoadMonitor.id == row.id,
        RoadMonitor.organization_id == row.organization_id, RoadMonitor.owner_user_id == user_id,
        RoadMonitor.version == version, RoadMonitor.status == row.status).values(status=target, version=version + 1)
        .execution_options(synchronize_session=False))
    if updated.rowcount != 1:
        _fail("road_monitor_version_conflict")
    cancel_work(session, row)
    session.refresh(row)
    if row.status == "active":
        row.health, row.next_poll_at = "waiting", now
        enqueue(session, row, now)
    return get_monitor(session, user_id, monitor_id)


def remove_monitor(session, user_id, monitor_id, version):
    from .road_jobs import cancel_work
    row = owned(session, user_id, monitor_id, write=True)
    _positive(version)
    if row.version != version:
        _fail("road_monitor_version_conflict")
    cancel_work(session, row)
    deleted = session.execute(delete(RoadMonitor).where(RoadMonitor.id == row.id,
        RoadMonitor.organization_id == row.organization_id, RoadMonitor.owner_user_id == user_id,
        RoadMonitor.version == version).execution_options(synchronize_session=False))
    if deleted.rowcount != 1:
        _fail("road_monitor_version_conflict")


def revisions(session, user_id, monitor_id, *, after_revision=0, limit=20):
    row = owned(session, user_id, monitor_id)
    _limit(limit)
    if type(after_revision) is not int or after_revision < 0:
        _fail("road_monitor_page_invalid", 422)
    rows = list(session.scalars(select(RoadConfigurationRevision).where(
        RoadConfigurationRevision.monitor_id == row.id, RoadConfigurationRevision.organization_id == row.organization_id,
        RoadConfigurationRevision.revision > after_revision).order_by(RoadConfigurationRevision.revision).limit(limit + 1)))
    return {"items": [{"revision": r.revision, "configuration": deepcopy(r.configuration),
                       "configuration_hash": r.configuration_hash} for r in rows[:limit]],
            "next_cursor": rows[limit - 1].revision if len(rows) > limit else None}


def describe_current_reference(session, reference_id, *, now, budget=None):
    # Stable labels are read from the latest explicitly reviewed map. This does
    # not choose the topology for event matching: that remains source-version exact.
    latest = session.execute(select(RoadTopologyRevision.country, RoadTopologyRevision.table, RoadTopologyRevision.version)
        .join(RoadCorridorMap, RoadCorridorMap.topology_id == RoadTopologyRevision.id)
        .where(RoadCorridorMap.reference_id == reference_id).order_by(RoadCorridorMap.generation.desc()).limit(1)).first()
    if latest is None:
        _fail("road_corridor_mapping_unavailable")
    return describe_reference(session, reference_id, table_key=tuple(latest), now=now, read_budget=budget)


def catalog_page(session, user_id, *, table_key=None, now, query="", limit=20, after_id=None):
    _actor(session, user_id)
    _limit(limit)
    now = _clock(now)
    if not isinstance(query, str) or len(query) > 100:
        _fail("road_catalog_query_invalid", 422)
    statement = select(RoadCorridorReference.id).where(RoadCorridorReference.enabled.is_(True))
    if after_id is not None:
        statement = statement.where(RoadCorridorReference.id > after_id)
    # Search only after permission projection, never through withheld labels.
    ids = list(session.scalars(statement.order_by(RoadCorridorReference.id).limit(21)))
    items, last, budget = [], None, CatalogReadBudget()
    for reference_id in ids[:20]:
        try:
            item = (describe_reference(session, reference_id, table_key=table_key, now=now, read_budget=budget)
                    if table_key is not None else describe_current_reference(session, reference_id, now=now, budget=budget))
        except DomainError as error:
            if error.code == "road_catalog_read_limit":
                if last is None:
                    raise
                break
            last = reference_id
            continue
        last = reference_id
        if query.casefold() in item["name"].casefold():
            items.append(item)
        if len(items) == limit:
            break
    has_more = last is not None and (len(ids) == 21 or last != ids[-1])
    return {"items": items, "next_cursor": last if has_more else None, "complete_network": False}


def preview(session, user_id, payload, *, table_key=None, now, settings=None):
    from .road_jobs import ready
    _actor(session, user_id, write=True)
    config = configuration(payload)
    now = _clock(now)
    items, reasons, budget = [], [], CatalogReadBudget()
    try:
        ready(session, settings, config, now=now)
    except DomainError as error:
        reasons.append(error.code)
    for reference_id in config.corridor_reference_ids:
        try:
            items.append(describe_reference(session, str(reference_id), table_key=table_key, now=now, read_budget=budget)
                         if table_key is not None else describe_current_reference(session, str(reference_id), now=now, budget=budget))
        except DomainError as error:
            items.append({"id": str(reference_id), "state": "unavailable"})
            reasons.append(error.code)
    return {"configuration": config.model_dump(mode="json"), "configuration_hash": config.fingerprint(),
            "corridors": items, "start_available": not reasons, "live_results_checked": False,
            "blocking_reasons": list(dict.fromkeys(reasons))}
