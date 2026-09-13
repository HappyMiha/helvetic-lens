"""Owner-controlled public monitoring; no bids, source registrations or messages."""

from datetime import UTC, datetime

from sqlalchemy import delete, select, update

from .config import DomainError
from .jobs import TERMINAL_STATES
from .models import Job
from .monitoring_subjects import _savepoint
from .simap_sources import aware
from .tender_jobs import enabled, enqueue
from .tender_models import TenderDossier, TenderMonitor
from .tender_repository import get_dossier, get_monitor, owned, owned_dossier, positive
from .tender_scan import queries


def cancel_work(session, monitor):
    session.execute(
        update(Job)
        .where(
            Job.organization_id == monitor.organization_id,
            Job.target_type == "tender_monitor",
            Job.target_id == monitor.id,
            Job.state.not_in(TERMINAL_STATES),
        )
        .values(cancel_requested=True)
    )


def command(session, settings, user_id, monitor_id, version, action, *, now=None):
    row = owned(session, user_id, monitor_id, write=True)
    positive(version)
    now = aware(now or datetime.now(UTC))
    transitions = {
        "start": ({"draft"}, "active"),
        "pause": ({"active"}, "paused"),
        "resume": ({"paused"}, "active"),
        "archive": ({"draft", "active", "paused"}, "archived"),
    }
    if action not in transitions:
        raise DomainError("Invalid tender action.", 422, "tender_action_invalid")
    allowed, target = transitions[action]
    if row.version != version or row.status not in allowed:
        raise DomainError("The monitor changed. Reload before continuing.", 409, "tender_version_conflict")
    if target == "active":
        if not enabled(settings):
            raise DomainError("The public SIMAP source is unavailable.", 409, "tender_source_not_ready")
        if not queries(row.configuration):
            raise DomainError(
                "Add a CPV code or a search phrase with at least three characters.",
                422,
                "tender_discovery_query_required",
            )
    with _savepoint(session):
        values = {"status": target, "version": version + 1}
        if target == "active":
            values["next_poll_at"] = now
        changed = session.execute(
            update(TenderMonitor)
            .where(
                TenderMonitor.id == row.id,
                TenderMonitor.organization_id == row.organization_id,
                TenderMonitor.owner_user_id == user_id,
                TenderMonitor.version == version,
                TenderMonitor.status.in_(allowed),
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise DomainError(
                "The monitor changed. Reload before continuing.", 409, "tender_version_conflict"
            )
        if target == "active":
            session.refresh(row)
            enqueue(session, row, now)
        else:
            cancel_work(session, row)
        session.flush()
    return get_monitor(session, user_id, monitor_id)


def remove(session, user_id, monitor_id, version):
    row = owned(session, user_id, monitor_id, write=True)
    positive(version)
    with _savepoint(session):
        cancel_work(session, row)
        changed = session.execute(
            delete(TenderMonitor)
            .where(
                TenderMonitor.id == row.id,
                TenderMonitor.organization_id == row.organization_id,
                TenderMonitor.owner_user_id == user_id,
                TenderMonitor.version == version,
            )
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise DomainError("The monitor changed. Reload before deleting.", 409, "tender_version_conflict")


def follow(session, user_id, dossier_id, version, following, *, now=None):
    row = owned_dossier(session, user_id, dossier_id, write=True)
    positive(version)
    if type(following) is not bool:
        raise DomainError("Choose whether to follow this tender.", 422, "tender_follow_invalid")
    # Serialize against ingestion and monitor transitions before applying the
    # dossier CAS. Turning following off never marks evidence reviewed.
    monitor = session.scalar(
        select(TenderMonitor)
        .where(TenderMonitor.id == row.monitor_id, TenderMonitor.organization_id == row.organization_id)
        .with_for_update()
    )
    if monitor.status == "archived":
        raise DomainError("Archived monitors cannot follow tenders.", 409, "tender_archived")
    with _savepoint(session):
        changed = session.execute(
            update(TenderDossier)
            .where(
                TenderDossier.id == row.id,
                TenderDossier.organization_id == row.organization_id,
                TenderDossier.version == version,
            )
            .values(following=following, version=version + 1)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise DomainError("The tender changed. Reload before continuing.", 409, "tender_version_conflict")
        result = get_dossier(session, user_id, dossier_id, now=now)
    return result
