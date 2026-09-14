"""Explicit bounded native decisions over the evidence the user previewed."""

from urllib.parse import urlencode

from sqlalchemy import select

from . import monitoring_evidence_ask as evidence
from .business_item_work import DECISIONS
from .config import DomainError
from .monitoring_subjects import _actor, _savepoint

MAX_ITEMS = 20


def fail(code="monitoring_batch_changed", status=409):
    raise DomainError("Nothing was applied. Preview the selected records again.", status, code)


def validate(records):
    keys = [(item.domain, item.monitor_id, item.item_id) for item in records]
    if not 1 <= len(keys) <= MAX_ITEMS or len(set(keys)) != len(keys):
        fail("monitoring_batch_selection_invalid", 422)


def _lock(session, user, record):
    """Serialize the native monitor and item, in the same order as its commands."""
    if record.domain in DECISIONS:
        from .business_item_work import _target
        return _target(session, user, record.domain, record.monitor_id, record.item_id, write=True)
    from .air_models import AirChange, AirMonitor
    from .commute_models import CommuteDevelopment, CommuteMonitor
    from .hazard_models import HazardDevelopment, HazardMonitor
    from .models import MonitoringSubject
    from .river_models import RiverChange, RiverMonitor
    from .road_models import RoadDevelopment, RoadMonitor
    models = {"pollen": (MonitoringSubject, None), "river": (RiverMonitor, RiverChange),
        "air": (AirMonitor, AirChange), "warnings": (HazardMonitor, HazardDevelopment),
        "commute": (CommuteMonitor, CommuteDevelopment), "traffic": (RoadMonitor, RoadDevelopment)}
    if record.domain not in models:
        fail("monitoring_batch_selection_invalid", 422)
    organization = _actor(session, user, write=True)
    monitor_model, item_model = models[record.domain]
    monitor = session.scalar(select(monitor_model).where(monitor_model.id == record.monitor_id,
        monitor_model.organization_id == organization, monitor_model.owner_user_id == user)
        .with_for_update().execution_options(populate_existing=True))
    if monitor is None:
        fail("monitoring_batch_not_found", 404)
    if monitor.status == "archived":
        fail()
    row = None
    if item_model is not None:
        row = session.scalar(select(item_model).where(item_model.id == record.item_id,
            item_model.monitor_id == monitor.id, item_model.organization_id == organization)
            .with_for_update().execution_options(populate_existing=True))
        if row is None:
            fail("monitoring_batch_not_found", 404)
    return monitor, row


def _read(session, settings, user, record, now, locale):
    view, source = evidence.native(session, settings, user, record, now=now)
    if record.domain == "warnings" and record.sequence is not None:
        current, _ = evidence.native(session, settings, user,
            evidence.Record(record.domain, record.monitor_id, record.item_id), now=now)
        if current["revision"] != record.sequence:
            fail()
    if view.get("newer_available") or view.get("current_configuration") is False:
        fail()
    if record.domain in DECISIONS and not view.get("can_review"):
        fail()
    # Same source-size boundary as the native evidence panel; no silently truncated
    # document is substituted for the original, which remains linked from the UI.
    extracts = evidence.extracts(source)
    binding = evidence._binding(record, view, locale)
    reference = "/api/monitoring-centre/evidence/reference?" + urlencode({
        **{key: value for key, value in record.__dict__.items() if value is not None},
        "locale": locale, "expected_binding": binding})
    return view, {"record": record.__dict__, "binding": binding, "reference_url": reference,
        "extracts": extracts[:12], "more_extracts": len(extracts) > 12,
        "actions": DECISIONS.get(record.domain, ["reviewed"])}


def preview(session, settings, user, records, *, now, locale):
    validate(records)
    _actor(session, user, write=True)
    if locale not in evidence.LOCALES:
        fail("monitoring_batch_selection_invalid", 422)
    # Preview never writes native decisions. Native readers retain their existing
    # locking and source permission behavior.
    return {"items": [_read(session, settings, user, record, now, locale)[1] for record in records],
        "locale": locale, "checked_at": now.isoformat(), "applied": False}


def apply(session, settings, user, selections, *, now, locale):
    records = [item[0] for item in selections]
    validate(records)
    if locale not in evidence.LOCALES:
        fail("monitoring_batch_selection_invalid", 422)
    ordered = sorted(selections, key=lambda item: (item[0].domain, item[0].monitor_id, item[0].item_id))
    with _savepoint(session):
        _actor(session, user, write=True)
        locked = {record: _lock(session, user, record) for record, _, _ in ordered}
        prepared = []
        for record, expected, action in ordered:
            view, current = _read(session, settings, user, record, now, locale)
            if current["binding"] != expected or action not in current["actions"]:
                fail()
            prepared.append((record, view, action))
        for record, view, action in prepared:
            _act(session, user, record, view, action, locked[record], settings, now)
        session.flush()
        _actor(session, user, write=True)
    return {"applied": True, "count": len(records), "records": [record.__dict__ for record in records]}


def _act(session, user, record, view, action, locked, settings, now):
    domain, monitor, identifier = record.domain, record.monitor_id, record.item_id
    if domain == "pollen":
        from .monitoring_runtime import review
        review(session, user_id=user, subject_id=monitor, entry_id=identifier,
            decision=action, expected_version=(view["entry"].get("review") or {}).get("version", 0))
    elif domain in {"river", "air"}:
        if domain == "river":
            from .river_runtime import review
        else:
            from .air_runtime import review
        review(session, user, monitor, identifier, view["event"]["review_version"], action)
    elif domain == "warnings":
        from .hazard_boundary_store import BoundaryStore
        from .hazard_events import set_review
        set_review(session, user, monitor, identifier, version=view["version"],
            expected_revision=view["revision"], action=action, store=BoundaryStore(settings.storage_path), now=now)
    elif domain == "commute":
        from .commute_events import review_event
        review_event(session, user, identifier, view["event"]["version"], view["snapshot"]["sequence"], now=now)
    elif domain == "traffic":
        from .road_events import review_event
        review_event(session, user, identifier, expected_version=view["event"]["version"], sequence=view["snapshot"]["sequence"])
    else:
        from .business_item_work import act, binding
        _, row = locked
        act(session, user, domain, monitor, identifier, expected_version=row.version,
            expected_binding=binding(session, domain, row), assigned_user_id=row.assigned_user_id,
            comment="", decision=action, now=now)
