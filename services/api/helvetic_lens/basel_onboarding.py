"""Bounded, explicitly requested first-use collection; no implicit activation."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from . import synchronization
from .basel_stadt_pilot import PACK_ID
from .config import DomainError
from .models import ConnectorSchedule, SourcePackSubscription


def collect(service):
    # The route uses the ordinary organization-admin/CSRF boundary. No arbitrary
    # connector, URL, model or organization is accepted from the caller.
    with service.write_guard, service.db.session() as session:
        enabled = session.scalar(select(SourcePackSubscription.id).where(
            SourcePackSubscription.organization_id == service.organization_id,
            SourcePackSubscription.pack_id == PACK_ID, SourcePackSubscription.enabled.is_(True)))
        if not enabled:
            raise DomainError("Enable the Basel-Stadt package before collecting its first-use sources.", 409, "source_pack_inactive")
        with service.db.session(include_all_organizations=True) as shared:
            schedule = shared.scalar(select(ConnectorSchedule).where(
                ConnectorSchedule.connector == PACK_ID, ConnectorSchedule.stream == "starter-de").with_for_update())
            if not schedule or not schedule.enabled:
                raise DomainError("The Basel-Stadt first-use source is disabled by the platform administrator.", 409, "connector_disabled")
            now = datetime.now(UTC)
            last = schedule.last_enqueued_at
            if last and (last.replace(tzinfo=UTC) if last.tzinfo is None else last) > now - timedelta(hours=1):
                return {"state": "recently_requested"}
            synchronization.enqueue_manual(shared, service.settings, PACK_ID, "starter-de", service.organization_id, now=now)
            shared.commit()
            # Shared jobs may belong to another organization: do not return IDs,
            # raw state, counts or failures from another tenant's job.
            return {"state": "queued"}
