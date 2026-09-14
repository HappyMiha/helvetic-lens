"""Owner-private material auction changes. Reads never collect, decide or send."""

from datetime import timedelta

from sqlalchemy import and_, exists, func, or_, select

from . import auction_sources as sources
from .auction_contracts import AuctionProfile, clock
from .auction_models import AuctionConfigurationRevision, AuctionMonitor
from .auction_repository import _fail
from .auction_source_models import AuctionSourceRecordRevision
from .auction_workflow import _item, _utc, item_view
from .auction_workflow_models import AuctionDecision, AuctionItem, AuctionItemEvent
from .business_monitor_access import visible_to
from .config import DomainError
from .monitoring_subjects import _actor

LOOKBACK = timedelta(days=2)
SCAN_LIMIT = 100


def _snapshot(session, item, revision_id, *, now):
    if revision_id is None:
        return None
    row = session.get(AuctionSourceRecordRevision, revision_id)
    if row is None or row.record_key != item.record_key:
        _fail("auction_event_evidence_invalid", 503)
    try:
        facts = sources.read_revision(session, row.permission_id, row.id, now=now, purpose="display")
        return {"state": "available", "facts": facts.model_dump(mode="json"), "sequence": row.sequence}
    except DomainError:
        return {"state": "unavailable", "facts": None, "sequence": row.sequence}


def detail(session, user_id, monitor_id, event_id, *, now):
    now = clock(now)
    organization = _actor(session, user_id)
    event = session.scalar(select(AuctionItemEvent).join(AuctionItem, and_(
        AuctionItem.id == AuctionItemEvent.item_id, AuctionItem.organization_id == AuctionItemEvent.organization_id))
        .where(AuctionItemEvent.id == event_id, AuctionItemEvent.organization_id == organization,
               AuctionItem.monitor_id == monitor_id))
    if event is None:
        _fail("auction_event_not_found", 404)
    monitor, item = _item(session, user_id, monitor_id, event.item_id)
    # A corrupt or mismatched configuration must not acquire an explanation
    # from today's edited profile. Source snapshots stay independently gated.
    configuration = session.scalar(select(AuctionConfigurationRevision).where(
        AuctionConfigurationRevision.monitor_id == monitor.id,
        AuctionConfigurationRevision.organization_id == organization,
        AuctionConfigurationRevision.revision == event.profile_revision))
    if configuration is None or AuctionProfile.model_validate(configuration.configuration).fingerprint() != configuration.configuration_hash:
        _fail("auction_event_configuration_invalid", 503)
    return {"id": event.id, "monitor_id": monitor.id, "item_id": item.id,
        "sequence": event.sequence, "detected_at": _utc(event.created_at).isoformat(),
        "change_codes": event.change_codes, "profile_revision": event.profile_revision,
        "current_configuration": event.profile_revision == monitor.revision,
        "newer_available": event.sequence < item.material_sequence,
        "snapshot": _snapshot(session, item, event.source_revision_id, now=now),
        "previous": _snapshot(session, item, event.previous_revision_id, now=now),
        "current": item_view(session, monitor, item, now=now)}


def page(session, settings, user_id, *, now, cursor=None, limit=20, inbox=False):
    now, organization = clock(now), _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 50 or type(inbox) is not bool:
        _fail("auction_page_invalid", 422)
    result = {"items": [], "next_cursor": None, "has_active_monitors": False,
              "unavailable_count": 0, "coverage_verified": False}
    if not settings.auction_watch_enabled:
        return result
    owners = (AuctionMonitor.organization_id == organization, visible_to(AuctionMonitor, user_id),
              AuctionMonitor.status == "active")
    result["has_active_monitors"] = session.scalar(select(AuctionMonitor.id).where(*owners).limit(1)) is not None
    # Keep the newest requested, unread change per lot. A later change whose
    # notification is disabled must not silently dismiss an earlier alert.
    # Profile/source replacement invalidates old alert eligibility.
    same_permission = exists(select(AuctionSourceRecordRevision.id).where(
        AuctionSourceRecordRevision.id == AuctionItemEvent.source_revision_id,
        AuctionSourceRecordRevision.permission_id == AuctionItem.permission_id)).correlate(AuctionItemEvent, AuctionItem)
    latest = select(func.max(AuctionItemEvent.sequence)).where(
        AuctionItemEvent.item_id == AuctionItem.id, AuctionItemEvent.organization_id == organization,
        AuctionItemEvent.profile_revision == AuctionMonitor.revision,
        AuctionItemEvent.notify.is_(True), same_permission).correlate(AuctionItem, AuctionMonitor).scalar_subquery()
    stopped = exists(select(AuctionDecision.id).where(AuctionDecision.item_id == AuctionItem.id,
        AuctionDecision.organization_id == organization, AuctionDecision.following.is_(False)))
    query = select(AuctionItem, AuctionMonitor, AuctionItemEvent).join(AuctionMonitor, and_(
        AuctionMonitor.id == AuctionItem.monitor_id, AuctionMonitor.organization_id == AuctionItem.organization_id)).join(
        AuctionItemEvent, and_(AuctionItemEvent.item_id == AuctionItem.id,
            AuctionItemEvent.organization_id == organization, AuctionItemEvent.sequence == latest)).where(
        *owners, AuctionItem.organization_id == organization, AuctionItem.profile_revision == AuctionMonitor.revision,
        AuctionItemEvent.sequence > AuctionItem.reviewed_sequence, AuctionItemEvent.notify.is_(True),
        AuctionItemEvent.created_at <= now,
        or_(AuctionItem.following.is_(True), and_(AuctionItemEvent.kind == "new_match", ~stopped)))
    if not inbox:
        query = query.where(AuctionItemEvent.created_at >= now - LOOKBACK)
    if cursor is not None:
        anchor = session.execute(query.where(AuctionItemEvent.id == cursor)).first()
        if anchor is None:
            _fail("auction_today_changed")
        timestamp = anchor[2].created_at
        query = query.where(or_(AuctionItemEvent.created_at < timestamp,
            and_(AuctionItemEvent.created_at == timestamp, AuctionItemEvent.id < cursor)))
    rows = list(session.execute(query.order_by(AuctionItemEvent.created_at.desc(), AuctionItemEvent.id.desc()).limit(SCAN_LIMIT + 1)))
    for index, (item, monitor, event) in enumerate(rows[:SCAN_LIMIT]):
        current = item_view(session, monitor, item, now=now)
        snapshot = _snapshot(session, item, event.source_revision_id, now=now)
        if current["state"] != "available" or snapshot["state"] != "available":
            result["unavailable_count"] += 1
            continue
        if not item.following and current["assessment"]["status"] != "match":
            continue
        facts = current["facts"]
        result["items"].append({"id": event.id, "monitor_id": monitor.id, "item_id": item.id,
            "name": monitor.configuration["name"], "title": facts["title"], "canton": facts["canton"],
            "auction_id": facts["auction_id"], "lot_id": facts["lot_id"], "attribution": current["attribution"],
            "sequence": event.sequence, "change_codes": event.change_codes,
            "detected_at": _utc(event.created_at).isoformat(), "observed_at": facts["observed_at"],
            "href": f"/auction-watch?monitor={monitor.id}&event={event.id}"})
        if len(result["items"]) == limit:
            result["next_cursor"] = event.id if index + 1 < len(rows) else None
            return result
    result["next_cursor"] = rows[SCAN_LIMIT - 1][2].id if len(rows) > SCAN_LIMIT else None
    return result
