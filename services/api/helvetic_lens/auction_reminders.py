"""Durable ending-soon epochs; evidence is rechecked, never copied into reminders."""

from datetime import timedelta

from sqlalchemy import and_, or_, select, update

from .auction_contracts import AuctionProfile, clock
from .auction_models import AuctionMonitor
from .auction_repository import _fail, _version
from .auction_rules import ending_soon
from .auction_workflow_models import AuctionItem, AuctionReminder
from .business_monitor_access import collection_actor, visible_to
from .config import DomainError
from .monitoring_subjects import _actor, _savepoint

MAX_DUE = 100
SCAN_LIMIT = 100


def _utc(value):
    from .auction_workflow import _utc as utc
    return utc(value)


def invalidate(session, monitor_id, *, item_id=None):
    query = update(AuctionReminder).where(AuctionReminder.monitor_id == monitor_id,
        AuctionReminder.state.in_({"scheduled", "ready"}))
    if item_id is not None:
        query = query.where(AuctionReminder.item_id == item_id)
    session.execute(query.values(state="invalidated", version=AuctionReminder.version + 1,
        check_after=None).execution_options(synchronize_session=False))


def plan(session, monitor, item, facts, *, now):
    """Called only after source projection/follow under the owner monitor lock."""
    now = clock(now)
    profile = AuctionProfile.model_validate(monitor.configuration)
    hours = profile.notify.ending_soon_hours
    if (monitor.status != "active" or not item.following or hours is None
            or facts.status != "open" or facts.ends_at is None or facts.ends_at <= now):
        invalidate(session, monitor.id, item_id=item.id)
        return None
    epoch = (AuctionReminder.item_id == item.id, AuctionReminder.profile_revision == monitor.revision,
             AuctionReminder.deadline_generation == item.deadline_generation)
    session.execute(update(AuctionReminder).where(AuctionReminder.item_id == item.id,
        AuctionReminder.state.in_({"scheduled", "ready"}),
        (AuctionReminder.profile_revision != monitor.revision) | (AuctionReminder.deadline_generation != item.deadline_generation))
        .values(state="invalidated", version=AuctionReminder.version + 1, check_after=None)
        .execution_options(synchronize_session=False))
    row = session.scalar(select(AuctionReminder).where(*epoch).execution_options(populate_existing=True))
    due = facts.ends_at - timedelta(hours=hours)
    if row is None:
        row = AuctionReminder(monitor_id=monitor.id, organization_id=monitor.organization_id,
            item_id=item.id, profile_revision=monitor.revision, deadline_generation=item.deadline_generation,
            deadline_hash=item.deadline_hash, hours=hours, due_at=due, ends_at=facts.ends_at,
            check_after=max(now, due), created_at=now)
        session.add(row)
    elif row.state == "invalidated":
        row.state, row.version, row.check_after = "scheduled", row.version + 1, max(now, due)
    session.flush()
    return row.id


def eligible(session, monitor, item, reminder, *, now):
    from .auction_sources import require_permission
    from .auction_workflow import _current
    now = clock(now)
    if (item is None or monitor.status != "active" or not item.following or reminder.monitor_id != monitor.id
            or reminder.organization_id != monitor.organization_id or reminder.item_id != item.id
            or item.profile_revision != monitor.revision or reminder.profile_revision != monitor.revision
            or reminder.deadline_generation != item.deadline_generation or reminder.deadline_hash != item.deadline_hash):
        return False, "superseded"
    profile = AuctionProfile.model_validate(monitor.configuration)
    if profile.notify.ending_soon_hours != reminder.hours:
        return False, "superseded"
    if now >= _utc(reminder.ends_at):
        return False, "auction_ended"
    require_permission(session, item.permission_id, now=now, purpose="matching")
    facts, _, policy = _current(session, monitor, item, now=now, purpose="display")
    if facts.ends_at is None or facts.ends_at != _utc(reminder.ends_at):
        return False, "superseded"
    decision = ending_soon(profile, facts, now=now, max_age_seconds=policy.max_age_seconds, following=item.following)
    return decision["eligible"], decision["reason"]


def activate_due(database, settings, *, now):
    from .auction_delivery import prepare_monitor
    now = clock(now)
    if not settings.auction_watch_enabled:
        return {"ready": 0, "invalidated": 0, "deferred": 0}
    with database.session(include_all_organizations=True) as session:
        rows = list(session.execute(select(AuctionReminder.id, AuctionReminder.monitor_id, AuctionReminder.organization_id)
            .where(AuctionReminder.state.in_({"scheduled", "ready"}), AuctionReminder.check_after <= now)
            .order_by(AuctionReminder.check_after, AuctionReminder.id).limit(MAX_DUE)))
    result = {"ready": 0, "invalidated": 0, "deferred": 0}
    for identifier, monitor_id, organization in rows:
        with database.organization_context(organization), database.session() as session:
            monitor = session.scalar(select(AuctionMonitor).where(AuctionMonitor.id == monitor_id)
                .with_for_update(skip_locked=True).execution_options(populate_existing=True))
            if monitor is None:
                continue
            reminder = session.get(AuctionReminder, identifier, populate_existing=True)
            if (reminder is None or reminder.state not in {"scheduled", "ready"}
                    or reminder.check_after is None or _utc(reminder.check_after) > now):
                continue
            item = session.get(AuctionItem, reminder.item_id)
            try:
                collection_actor(session, monitor)
                ready, reason = eligible(session, monitor, item, reminder, now=now)
            except DomainError as error:
                ready, reason = False, error.code
            if reason in {"superseded", "auction_ended", "auction_not_open", "deadline_unknown", "not_requested",
                          "membership_required", "subject_role_denied"}:
                reminder.state, reminder.version, reminder.check_after = "invalidated", reminder.version + 1, None
                result["invalidated"] += 1
            else:
                reminder.check_after = now + timedelta(seconds=60)
                if ready and reminder.state == "scheduled":
                    reminder.state, reminder.version = "ready", reminder.version + 1
                    reminder.activated_at = reminder.activated_at or now
                    result["ready"] += 1
                elif not ready:
                    result["deferred"] += 1
            session.flush()
            if ready:
                prepare_monitor(session, monitor, now=now)
            session.commit()
    return result


def view(session, user_id, monitor_id, reminder_id, *, now):
    from .auction_workflow import _item, item_view
    organization = _actor(session, user_id)
    reminder = session.scalar(select(AuctionReminder).where(AuctionReminder.id == reminder_id,
        AuctionReminder.monitor_id == monitor_id, AuctionReminder.organization_id == organization))
    if reminder is None:
        _fail("auction_reminder_not_found", 404)
    monitor, item = _item(session, user_id, monitor_id, reminder.item_id)
    ready = False
    try:
        ready, _ = eligible(session, monitor, item, reminder, now=now)
    except DomainError:
        pass
    current = item_view(session, monitor, item, now=now)
    visible = (current["state"] == "available" and item.profile_revision == reminder.profile_revision
        and item.deadline_generation == reminder.deadline_generation and item.deadline_hash == reminder.deadline_hash)
    return {"id": reminder.id, "monitor_id": monitor.id, "item_id": item.id,
        "version": reminder.version, "state": reminder.state,
        "due_at": _utc(reminder.due_at).isoformat() if visible else None,
        "ends_at": _utc(reminder.ends_at).isoformat() if visible else None,
        "hours": reminder.hours, "eligible": ready and reminder.state == "ready",
        "current": current}


def acknowledge(session, user_id, monitor_id, reminder_id, *, expected_version, now):
    from .auction_workflow import _monitor
    now = clock(now)
    with _savepoint(session):
        _monitor(session, user_id, monitor_id, write=True)
        value = view(session, user_id, monitor_id, reminder_id, now=now)
        _version(expected_version)
        if value["version"] != expected_version:
            _fail("auction_version_conflict")
        row = session.get(AuctionReminder, reminder_id)
        if row.state != "acknowledged":
            row.state, row.version, row.acknowledged_at, row.check_after = "acknowledged", row.version + 1, now, None
        session.flush()
        return view(session, user_id, monitor_id, reminder_id, now=now)


def page(session, user_id, *, now, monitor_id=None, cursor=None, limit=20):
    """Bounded private schedule, or current due reminders across active profiles."""
    from .auction_repository import owned
    now, organization = clock(now), _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 50:
        _fail("auction_page_invalid", 422)
    if monitor_id:
        owned(session, user_id, monitor_id)
    query = select(AuctionReminder).join(AuctionMonitor, and_(AuctionMonitor.id == AuctionReminder.monitor_id,
        AuctionMonitor.organization_id == AuctionReminder.organization_id)).join(AuctionItem, and_(
        AuctionItem.id == AuctionReminder.item_id, AuctionItem.organization_id == organization)).where(
        visible_to(AuctionMonitor, user_id), AuctionMonitor.organization_id == organization,
        AuctionReminder.organization_id == organization)
    if monitor_id:
        query = query.where(AuctionMonitor.id == monitor_id)
    else:
        query = query.where(AuctionMonitor.status == "active", AuctionReminder.state == "ready",
            AuctionItem.following.is_(True), AuctionItem.profile_revision == AuctionMonitor.revision,
            AuctionReminder.profile_revision == AuctionMonitor.revision,
            AuctionReminder.deadline_generation == AuctionItem.deadline_generation,
            AuctionReminder.ends_at > now, AuctionReminder.due_at <= now)
    if cursor:
        anchor = session.scalar(query.where(AuctionReminder.id == cursor))
        if anchor is None:
            _fail("auction_reminders_changed")
        query = query.where(or_(AuctionReminder.created_at < anchor.created_at,
            and_(AuctionReminder.created_at == anchor.created_at, AuctionReminder.id < anchor.id)))
    rows = list(session.scalars(query.order_by(AuctionReminder.created_at.desc(), AuctionReminder.id.desc()).limit(SCAN_LIMIT + 1)))
    result = {"items": [], "next_cursor": None, "unavailable_count": 0, "coverage_verified": False}
    for index, row in enumerate(rows[:SCAN_LIMIT]):
        value = view(session, user_id, row.monitor_id, row.id, now=now)
        if not monitor_id and not value["eligible"]:
            result["unavailable_count"] += 1
            continue
        value["href"] = f"/auction-watch?monitor={row.monitor_id}&reminder={row.id}"
        result["items"].append(value)
        if len(result["items"]) == limit:
            result["next_cursor"] = row.id if index + 1 < len(rows) else None
            return result
    result["next_cursor"] = rows[SCAN_LIMIT - 1].id if len(rows) > SCAN_LIMIT else None
    return result
