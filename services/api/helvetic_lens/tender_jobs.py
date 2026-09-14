"""Durable public SIMAP collection: one bounded work item per scheduled step."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from . import jobs
from . import tender_scan as scan
from .business_monitor_access import collection_actor
from .config import DomainError
from .monitoring_subjects import _savepoint
from .simap_sources import PublicationEmbargo, PublicClient, SourceUnavailable
from .tender_models import TenderCollection, TenderMonitor, TenderSourceLease
from .tender_rights import SourceRestricted, require_permitted
from .tender_storage import StorageCapacity, StorageLimits, collect_unreferenced

LEASE_SECONDS = 120
# Application request budget, not a claim about an official SIMAP quota.
REQUEST_INTERVAL_SECONDS = 2


def enabled(settings):
    return settings.tender_watch_enabled and settings.simap_public_source_enabled


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def enqueue(session, row, now):
    active = session.scalar(
        select(jobs.Job.id)
        .where(
            jobs.Job.organization_id == row.organization_id,
            jobs.Job.target_type == "tender_monitor",
            jobs.Job.target_id == row.id,
            jobs.Job.state.not_in(jobs.TERMINAL_STATES),
        )
        .limit(1)
    )
    if active:
        return 0
    _, existed = jobs.enqueue(
        session,
        job_type="tender_refresh",
        target_type="tender_monitor",
        target_id=row.id,
        queue="ingest",
        priority=4,
        payload={"version": row.version},
        idempotency_key=f"tender:{row.id}:{row.version}:{int(now.timestamp()) // 15}",
    )
    return int(not existed)


def enqueue_due(database, settings, *, now=None):
    if not enabled(settings):
        return {"enqueued": 0}
    now = now or datetime.now(UTC)
    with database.session(include_all_organizations=True) as session:
        collect_unreferenced(session, now=now)
        session.commit()
        candidates = list(
            session.execute(
                select(TenderMonitor.id, TenderMonitor.organization_id)
                .where(
                    TenderMonitor.status == "active",
                    TenderMonitor.next_poll_at <= now,
                )
                .order_by(TenderMonitor.next_poll_at, TenderMonitor.id)
                .limit(100)
            )
        )
    count = 0
    for monitor_id, organization_id in candidates:
        with database.organization_context(organization_id), database.session() as session:
            row = session.scalar(
                select(TenderMonitor).where(TenderMonitor.id == monitor_id).with_for_update()
            )
            if row is None or row.status != "active" or utc(row.next_poll_at) > now:
                continue
            try:
                collection_actor(session, row)
                count += enqueue(session, row, now)
                row.next_poll_at = now + timedelta(seconds=15)
            except DomainError:
                row.health, row.next_poll_at = "access_unavailable", now + timedelta(hours=6)
            session.commit()
    return {"enqueued": count}


def _source_claim(database, token, now):
    with database.session() as session:
        if session.get(TenderSourceLease, "simap_public") is None:
            try:
                with _savepoint(session):
                    session.add(TenderSourceLease(key="simap_public", next_request_at=now))
                    session.flush()
            except IntegrityError:
                pass
        changed = session.execute(
            update(TenderSourceLease)
            .where(
                TenderSourceLease.key == "simap_public",
                TenderSourceLease.next_request_at <= now,
                or_(TenderSourceLease.lease_until.is_(None), TenderSourceLease.lease_until <= now),
            )
            .values(lease_token=token, lease_until=now + timedelta(seconds=LEASE_SECONDS))
            .execution_options(synchronize_session=False)
        )
        session.commit()
        return changed.rowcount == 1


def _release(database, monitor_id, token, *, now, cooldown=REQUEST_INTERVAL_SECONDS):
    # Release only our token. An expired worker cannot release a replacement's
    # lease or erase a longer Retry-After established by another worker.
    with database.session() as session:
        session.execute(
            update(TenderCollection)
            .where(
                TenderCollection.monitor_id == monitor_id,
                TenderCollection.organization_id == session.info["organization_id"],
                TenderCollection.lease_token == token,
            )
            .values(lease_token=None, lease_until=None)
        )
        session.execute(
            update(TenderSourceLease)
            .where(
                TenderSourceLease.key == "simap_public",
                TenderSourceLease.lease_token == token,
            )
            .values(lease_token=None, lease_until=None, next_request_at=now + timedelta(seconds=cooldown))
        )
        session.commit()


def _acquire(database, settings, monitor_id, version, token, now):
    with database.session() as session:
        monitor = session.scalar(
            select(TenderMonitor)
            .where(
                TenderMonitor.id == monitor_id,
                TenderMonitor.organization_id == session.info["organization_id"],
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            not enabled(settings)
            or monitor is None
            or monitor.status != "active"
            or monitor.version != version
        ):
            return None
        collection_actor(session, monitor)
        collection = session.get(TenderCollection, monitor_id)
        if collection is None:
            collection = TenderCollection(
                monitor_id=monitor_id,
                organization_id=monitor.organization_id,
                revision=monitor.revision,
                generation=0,
                state=scan.start(now),
            )
            session.add(collection)
            session.flush()
        if collection.lease_until and utc(collection.lease_until) > now:
            return None
        state = deepcopy(collection.state)
        if collection.revision != monitor.revision or not state:
            state = scan.start(now)
        if state.get("cycle_complete"):
            if scan.aware_from_text(state["restart_at"]) > now:
                monitor.next_poll_at = scan.aware_from_text(state["restart_at"])
                session.commit()
                return None
            state = scan.start(now)
        work = scan.next_work(session, monitor, state)
        if work is not None:
            try:
                require_permitted(session, work.get("project_id"), work.get("publication_id"))
            except SourceRestricted:
                monitor.health, monitor.next_poll_at = "source_rights_unavailable", now + timedelta(hours=6)
                session.commit()
                return None
        if work is None:
            restart = scan.next_cycle(state, now)
            state.update(cycle_complete=True, restart_at=restart.isoformat())
            collection.state, collection.revision = state, monitor.revision
            monitor.health = (
                "partial_public_coverage"
                if state["truncated"] or state["gaps"] or not scan.queries(monitor.configuration)
                else "public_cycle_complete"
            )
            monitor.last_poll_at, monitor.next_poll_at = now, restart
            session.commit()
            return None
        changed = session.execute(
            update(TenderCollection)
            .where(
                TenderCollection.monitor_id == monitor_id,
                TenderCollection.organization_id == monitor.organization_id,
                TenderCollection.generation == collection.generation,
                or_(TenderCollection.lease_until.is_(None), TenderCollection.lease_until <= now),
            )
            .values(
                lease_token=token,
                lease_until=now + timedelta(seconds=LEASE_SECONDS),
                generation=collection.generation + 1,
                revision=monitor.revision,
                state=state,
            )
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            session.rollback()
            return None
        monitor.next_poll_at = now + timedelta(seconds=LEASE_SECONDS)
        session.commit()
        return deepcopy(work)


def _request(client, work):
    kind = work["kind"]
    if kind == "search":
        return client.search(**{key: value for key, value in work.items() if key != "kind"})
    if kind == "header":
        return client.project_header(work["project_id"])
    if kind == "history":
        return client.publication_history(work["publication_id"], lot_id=work["lot_id"] or None)
    if kind == "publication":
        return client.publication(work["project_id"], work["publication_id"])
    if kind == "taxonomy":
        return client.cpv_ancestry(work["code"]).model_dump(mode="json")
    if kind == "apply":
        return None
    raise ValueError("Unknown source work")


def refresh(database, settings, *, monitor_id, version, checkpoint=lambda: None, now=None, client=None):
    """Never hold a tenant transaction during network I/O; recheck before save."""
    if not enabled(settings):
        return {"status": "disabled"}
    clock = (lambda: now) if now is not None else (lambda: datetime.now(UTC))
    token, cooldown = str(uuid4()), REQUEST_INTERVAL_SECONDS
    work, claimed = None, False
    try:
        checkpoint()
        try:
            work = _acquire(database, settings, monitor_id, version, token, clock())
        except DomainError:
            return {"status": "access_unavailable"}
        if work is None:
            return {"status": "inactive_or_waiting"}
        if work["kind"] != "apply":
            claimed = _source_claim(database, token, clock())
            if not claimed:
                with database.session() as session:
                    lease = session.get(TenderSourceLease, "simap_public")
                    retry = max(clock() + timedelta(seconds=15), utc(lease.next_request_at))
                    session.execute(
                        update(TenderMonitor)
                        .where(
                            TenderMonitor.id == monitor_id,
                            TenderMonitor.version == version,
                            TenderMonitor.organization_id == session.info["organization_id"],
                            TenderMonitor.status == "active",
                        )
                        .values(next_poll_at=retry)
                    )
                    session.commit()
                return {"status": "source_budget_wait"}
        error, raw = None, None
        try:
            checkpoint()
            raw = _request(client or PublicClient(), work)
        except SourceUnavailable as failure:
            error = failure
            cooldown = max(REQUEST_INTERVAL_SECONDS, failure.retry_after_seconds or 300)
        checkpoint()
        finished = clock()
        with database.session() as session:
            monitor = session.scalar(
                select(TenderMonitor)
                .where(
                    TenderMonitor.id == monitor_id,
                    TenderMonitor.organization_id == session.info["organization_id"],
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            collection = session.get(TenderCollection, monitor_id)
            lease = session.get(TenderSourceLease, "simap_public") if claimed else None
            if (
                not enabled(settings)
                or monitor is None
                or monitor.status != "active"
                or monitor.version != version
                or collection is None
                or collection.lease_token != token
                or utc(collection.lease_until) <= finished
                or claimed
                and (lease is None or lease.lease_token != token or utc(lease.lease_until) <= finished)
            ):
                return {"status": "inactive_or_superseded"}
            try:
                collection_actor(session, monitor)
            except DomainError:
                return {"status": "access_unavailable"}
            original_state = deepcopy(collection.state)
            state = deepcopy(original_state)
            changed = 0
            if error is not None:
                scan.failed(state, work, error.reason)
                health = error.reason
            else:
                try:
                    with _savepoint(session):
                        require_permitted(session, work.get("project_id"), work.get("publication_id"))
                        changed = scan.accept(
                            session,
                            monitor,
                            state,
                            work,
                            raw,
                            finished,
                            storage_limits=StorageLimits.from_settings(settings),
                        )
                        session.flush()
                    health = "collecting_public"
                except SourceRestricted:
                    state = deepcopy(original_state)
                    health, cooldown = "source_rights_unavailable", 6 * 60 * 60
                except StorageCapacity:
                    # Keep the precise work/buffer and all prior evidence. A
                    # retry after capacity is restored must apply this record.
                    state = deepcopy(original_state)
                    health, cooldown = "storage_capacity", 6 * 60 * 60
                except PublicationEmbargo as embargo:
                    state = deepcopy(original_state)
                    scan.finish_work(state, work)
                    scan.defer_publication(state, embargo.until)
                    health = "publication_withheld"
                except (ValueError, KeyError, TypeError):
                    state = deepcopy(original_state)
                    scan.failed(state, work, "invalid_source_contract")
                    health, cooldown = "invalid_source_contract", 300
            collection.state = state
            monitor.health, monitor.last_poll_at = health, finished
            monitor.next_poll_at = finished + timedelta(seconds=max(15, cooldown))
            session.commit()
        return {"status": health, "changed_dossiers": changed}
    finally:
        if work is not None:
            _release(database, monitor_id, token, now=clock(), cooldown=cooldown)
