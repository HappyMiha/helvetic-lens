"""Private warning summaries for Today/Inbox. Reads never collect, review or send."""

from datetime import timedelta

from sqlalchemy import and_, func, or_, select

from .config import DomainError
from .hazard_events import read_event
from .hazard_models import HazardDevelopment, HazardEventRevision, HazardMonitor
from .hazard_sources import _clock, _utc
from .monitoring_subjects import _actor

LOOKBACK = timedelta(days=2)
SCAN_LIMIT = 100


def page(session, settings, user_id, *, store, now, cursor=None, limit=20, inbox=False):
    now = _clock(now)
    organization = _actor(session, user_id)
    if type(limit) is not int or not 1 <= limit <= 20:
        raise DomainError("Choose a bounded warning page.", 422, "hazard_event_page_invalid")
    result = {"items": [], "next_cursor": None, "coverage_verified": False,
              "has_active_places": False, "unavailable_count": 0}
    if not settings.hazard_watch_enabled:
        return result
    owners = (HazardMonitor.organization_id == organization, HazardMonitor.owner_user_id == user_id,
              HazardMonitor.status == "active")
    result["has_active_places"] = session.scalar(select(HazardMonitor.id).where(*owners).limit(1)) is not None
    # Translation-only revisions do not reset the 48-hour material-change window.
    material = select(HazardEventRevision.development_id, HazardEventRevision.material_sequence,
        func.min(HazardEventRevision.created_at).label("detected_at")).where(
        HazardEventRevision.organization_id == organization).group_by(
        HazardEventRevision.development_id, HazardEventRevision.material_sequence).subquery()
    query = select(HazardDevelopment, HazardMonitor, HazardEventRevision, material.c.detected_at).join(
        HazardMonitor, and_(HazardMonitor.id == HazardDevelopment.monitor_id,
                           HazardMonitor.organization_id == HazardDevelopment.organization_id)).join(
        HazardEventRevision, and_(HazardEventRevision.development_id == HazardDevelopment.id,
            HazardEventRevision.organization_id == organization, HazardEventRevision.revision == HazardDevelopment.revision)).join(
        material, and_(material.c.development_id == HazardDevelopment.id,
                       material.c.material_sequence == HazardDevelopment.material_sequence)).where(
        *owners, HazardDevelopment.organization_id == organization,
        HazardDevelopment.configuration_revision == HazardMonitor.revision,
        HazardDevelopment.material_sequence > HazardDevelopment.reviewed_sequence,
        HazardDevelopment.material_sequence > HazardDevelopment.dismissed_sequence,
        HazardEventRevision.created_at <= now, material.c.detected_at <= now)
    if not inbox:
        query = query.where(material.c.detected_at >= now - LOOKBACK)
    if cursor is not None:
        anchor = session.execute(query.where(HazardEventRevision.id == cursor)).first()
        if anchor is None:
            raise DomainError("The warning list changed. Refresh it.", 409, "hazard_today_changed")
        query = query.where(or_(material.c.detected_at < anchor[3],
            and_(material.c.detected_at == anchor[3], HazardEventRevision.id < cursor)))
    rows = list(session.execute(query.order_by(material.c.detected_at.desc(), HazardEventRevision.id.desc()).limit(SCAN_LIMIT + 1)))
    for index, (development, monitor, revision, detected_at) in enumerate(rows[:SCAN_LIMIT]):
        try:
            event = read_event(session, user_id, monitor.id, development.id, store=store, now=now)
        except DomainError as error:
            if error.status != 404:
                raise
            event = {"state": "unavailable"}
        if event["state"] == "unavailable" or event["revision"] != revision.revision:
            result["unavailable_count"] += 1
            continue
        if not event["needs_review"] or event["muted"]:
            continue
        decision = event["decision"]
        if inbox and (event["state"] not in {"active", "planned"} or decision.get("importance") not in {"warning", "alarm"}):
            continue
        # Collection rows intentionally contain no source instructions, source
        # URLs or location coordinates. The exact reader rechecks all evidence.
        result["items"].append({"id": revision.id, "monitor_id": monitor.id, "name": monitor.configuration["name"],
            "event_id": development.id, "revision": event["revision"], "state": event["state"],
            "importance": decision.get("importance"), "certainty": decision.get("certainty"),
            "detected_at": _utc(detected_at).isoformat(), "last_seen_at": event["source"]["last_seen_at"],
            "attribution": event["source"]["attribution"],
            "href": f"/hazard-watch?monitor={monitor.id}&event={development.id}&revision={event['revision']}"})
        if len(result["items"]) == limit:
            result["next_cursor"] = revision.id if index + 1 < len(rows) else None
            return result
    # Filtered pages may be empty and still have a continuation. Never scan an
    # unbounded private history to fill the requested page.
    result["next_cursor"] = rows[SCAN_LIMIT - 1][2].id if len(rows) > SCAN_LIMIT else None
    return result
