"""Owner-private register developments, not an exhaustive trademark clearance."""

from datetime import timedelta

from sqlalchemy import and_, or_, select

from .business_monitor_access import visible_to
from .monitoring_subjects import _actor
from .trademark_models import TrademarkMonitor
from .trademark_repository import _fail
from .trademark_sources import _clock, _utc
from .trademark_workflow import candidate_view
from .trademark_workflow_models import TrademarkCandidate, TrademarkCandidateEvent

SCAN_LIMIT = 100


def page(session, settings, user_id, *, now, inbox=False, cursor=None, limit=20):
    now, organization = _clock(now), _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 50 or type(inbox) is not bool:
        _fail("trademark_page_invalid", 422)
    result = {"items": [], "next_cursor": None, "unavailable_count": 0, "coverage_verified": False, "legal_conflict_confirmed": False}
    if not settings.trademark_watch_enabled:
        return result
    query = select(TrademarkCandidate, TrademarkMonitor, TrademarkCandidateEvent).join(TrademarkMonitor, and_(
        TrademarkMonitor.id == TrademarkCandidate.monitor_id, TrademarkMonitor.organization_id == TrademarkCandidate.organization_id)).join(
        TrademarkCandidateEvent, and_(TrademarkCandidateEvent.candidate_id == TrademarkCandidate.id,
        TrademarkCandidateEvent.organization_id == organization, TrademarkCandidateEvent.sequence == TrademarkCandidate.sequence)).where(
        visible_to(TrademarkMonitor, user_id), TrademarkMonitor.organization_id == organization, TrademarkMonitor.status == "active",
        TrademarkCandidate.profile_revision == TrademarkMonitor.revision, TrademarkCandidate.sequence > TrademarkCandidate.reviewed_sequence,
        TrademarkCandidateEvent.created_at <= now)
    if not inbox:
        query = query.where(TrademarkCandidateEvent.created_at >= now - timedelta(days=2))
    if cursor:
        anchor = session.execute(query.where(TrademarkCandidateEvent.id == cursor)).first()
        if anchor is None:
            _fail("trademark_today_changed")
        query = query.where(or_(TrademarkCandidateEvent.created_at < anchor[2].created_at,
            and_(TrademarkCandidateEvent.created_at == anchor[2].created_at, TrademarkCandidateEvent.id < cursor)))
    rows = list(session.execute(query.order_by(TrademarkCandidateEvent.created_at.desc(), TrademarkCandidateEvent.id.desc()).limit(SCAN_LIMIT + 1)))
    for index, (candidate, monitor, event) in enumerate(rows[:SCAN_LIMIT]):
        current = candidate_view(session, monitor, candidate, now=now)
        if current["state"] != "available":
            result["unavailable_count"] += 1
            continue
        brand = next(b for b in monitor.configuration["brands"] if b["key"] == candidate.brand_key)
        result["items"].append({"id": event.id, "monitor_id": monitor.id, "candidate_id": candidate.id,
            "name": monitor.configuration["name"], "brand": brand["name"], "mark": current["facts"]["mark"],
            "priority": current["assessment"]["priority"] or "review", "change_codes": event.change_codes,
            "attribution": current["attribution"], "detected_at": _utc(event.created_at).isoformat(),
            "deadline_context": current.get("deadline_context"),
            "href": f"/trademark-watch?monitor={monitor.id}&candidate={candidate.id}&event={event.id}"})
        if len(result["items"]) == limit:
            result["next_cursor"] = event.id if index + 1 < len(rows) else None
            return result
    result["next_cursor"] = rows[SCAN_LIMIT - 1][2].id if len(rows) > SCAN_LIMIT else None
    return result
