"""Explicit daily watches use the normal tenant-scoped scan and evidence path."""
from datetime import timedelta

from sqlalchemy import select

from . import jobs
from .db import utcnow
from .models import DocumentWatch, Law, OrganizationMembership, Scan, ScanItem, User

INTERVAL = timedelta(days=1)


def has_operator(session, organization_id):
    return session.scalar(select(User.id).join(OrganizationMembership,
        OrganizationMembership.user_id == User.id).where(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.role == "organization_admin", User.active.is_(True)).limit(1)) is not None


def can_run(session, law_id):
    watch = session.scalar(select(DocumentWatch).where(DocumentWatch.law_id == law_id))
    return bool(watch and watch.active and watch.auto_check_enabled
                and has_operator(session, watch.organization_id))


def enqueue_due(database, settings, *, now=None):
    now = now or utcnow()
    with database.session(include_all_organizations=True) as session:
        eligible = select(OrganizationMembership.organization_id).join(User,
            User.id == OrganizationMembership.user_id).where(
            User.active.is_(True), OrganizationMembership.role == "organization_admin")
        organizations = list(session.scalars(select(DocumentWatch.organization_id).where(
            DocumentWatch.active.is_(True), DocumentWatch.auto_check_enabled.is_(True),
            DocumentWatch.next_auto_check_at <= now, DocumentWatch.organization_id.in_(eligible)
        ).distinct().order_by(DocumentWatch.organization_id).limit(20)))
    queued = documents = 0
    for organization_id in organizations:
        with database.organization_context(organization_id), database.session() as session:
            if not has_operator(session, organization_id):
                continue
            busy = select(ScanItem.law_id).join(Scan).where(Scan.status.in_(["queued", "running"]))
            watches = list(session.scalars(select(DocumentWatch).where(
                DocumentWatch.active.is_(True), DocumentWatch.auto_check_enabled.is_(True),
                DocumentWatch.next_auto_check_at <= now, DocumentWatch.law_id.not_in(busy)
            ).order_by(DocumentWatch.next_auto_check_at, DocumentWatch.id).limit(5).with_for_update(skip_locked=True)))
            if not watches:
                continue
            scan = Scan(total=len(watches))
            session.add(scan)
            session.flush()
            for watch in watches:
                law = session.get(Law, watch.law_id)
                session.add(ScanItem(scan_id=scan.id, law_id=law.id,
                    baseline_version_id=law.current_version_id, mode="monitoring",
                    events=[{"stage": "queued", "at": now.isoformat(), "trigger": "daily_watch"}]))
                watch.next_auto_check_at = now + INTERVAL
            jobs.enqueue(session, job_type="scan", target_type="scan", target_id=scan.id,
                queue="ingest", priority=3, idempotency_key=f"scan:{scan.id}",
                payload={"scan_id": scan.id, "automatic": True}, progress_total=len(watches),
                max_attempts=settings.job_max_attempts,
                steps=[("Scan " + watch.display_name, {"law_id": watch.law_id}) for watch in watches])
            session.commit()
            queued += 1
            documents += len(watches)
    return {"queued": queued, "documents": documents}
