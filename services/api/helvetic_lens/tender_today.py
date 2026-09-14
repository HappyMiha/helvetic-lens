"""Owner-private public-summary cards; no payload hydration or source/decision I/O."""
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select

from .business_monitor_access import visible_to
from .config import DomainError
from .monitoring_subjects import _actor
from .simap_sources import aware
from .tender_models import TenderDossier, TenderDossierVersion, TenderMonitor
from .tender_repository import timestamp
from .tender_rights import permitted


def today(session, user_id, *, after_version=None, review_state=None, following=False, limit=20, now=None):
    organization = _actor(session, user_id)
    now = aware(now or datetime.now(UTC))
    if type(limit) is not int or not 1 <= limit <= 50 or type(following) is not bool:
        raise DomainError("Invalid tender page.", 422, "tender_filter_invalid")
    if review_state not in {None, "pending", "new", "needs_review", "reviewed"}:
        raise DomainError("Invalid review filter.", 422, "tender_filter_invalid")
    dossier, version, monitor = TenderDossier, TenderDossierVersion, TenderMonitor
    # Immutable version timestamp and id form the page order. Dossier updated_at
    # also changes on follow/decision, so it is not a stable continuation anchor.
    join = and_(version.dossier_id == dossier.id, version.organization_id == dossier.organization_id,
                version.sequence == dossier.latest_sequence)
    scope = (dossier.organization_id == organization, monitor.organization_id == organization,
        visible_to(monitor, user_id), monitor.status != "archived", version.publish_after <= now,
        permitted(dossier.project_id, version.publication_id),
        or_(monitor.owner_user_id == user_id, version.document_observation_id.is_(None)),
        or_(dossier.following.is_(True), version.summary["verdict"].as_string().in_({"match", "needs_review"})))
    query = select(dossier, version.summary, version.id, version.profile_revision, version.observed_at,
        monitor.configuration["name"].as_string(), monitor.revision, monitor.status).join(version, join).join(
            monitor, monitor.id == dossier.monitor_id).where(*scope)
    # Count belongs to this owner's permitted queue and following scope, not to
    # all domains and not to undisclosed embargoed/restricted publications.
    count_query = select(func.count()).select_from(dossier).join(version, join).join(monitor,
        monitor.id == dossier.monitor_id).where(*scope, dossier.review_state != "reviewed")
    if following:
        query = query.where(dossier.following.is_(True))
        count_query = count_query.where(dossier.following.is_(True))
    count = session.scalar(count_query)
    if review_state:
        query = query.where(dossier.review_state != "reviewed" if review_state == "pending" else dossier.review_state == review_state)
    if after_version:
        anchor = session.execute(select(version.observed_at, version.id).join(dossier,
            and_(dossier.id == version.dossier_id, dossier.organization_id == version.organization_id)).join(
                monitor, monitor.id == dossier.monitor_id).where(version.id == str(after_version),
                    dossier.organization_id == organization, monitor.organization_id == organization,
                    visible_to(monitor, user_id),
                    or_(monitor.owner_user_id == user_id, version.document_observation_id.is_(None)))).first()
        if anchor is None:
            raise DomainError("Refresh the tender page.", 422, "tender_cursor_invalid")
        query = query.where(or_(version.observed_at < anchor.observed_at,
            and_(version.observed_at == anchor.observed_at, version.id < anchor.id)))
    rows = list(session.execute(query.order_by(version.observed_at.desc(), version.id.desc()).limit(limit + 1)))
    return {"items": [{"id": row.id, "monitor_id": row.monitor_id, "monitor_name": name,
        "project_id": row.project_id, "lot_id": row.lot_key or None,
        "monitor_status": status, "sequence": row.latest_sequence, "version": row.version,
        "following": row.following, "review_state": row.review_state, "decision": row.decision,
        "reviewed_sequence": row.reviewed_sequence, "summary": deepcopy(summary),
        "evidence_version_id": version_id, "profile_revision": profile_revision,
        "current_profile_revision": current_revision, "observed_at": timestamp(observed),
        "href": f"/tender-watch?monitor={row.monitor_id}&dossier={row.id}&version={version_id}"}
        for row, summary, version_id, profile_revision, observed, name, current_revision, status in rows[:limit]],
        "next_cursor": rows[limit - 1][2] if len(rows) > limit else None, "pending_count": count}
