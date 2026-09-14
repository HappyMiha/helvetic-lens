"""Celery entrypoint for durable Helvetic Lens work."""

from __future__ import annotations

import asyncio
import socket

from celery import Celery

from . import digests, jobs, synchronization
from .config import Settings
from .db import Database
from .maintenance import cleanup_operational_data
from .models import Job
from .observability import correlation_context

settings = Settings()
_worker_service = None
celery_app = Celery("helvetic_lens", broker=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_backend=None,
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Redis consumes smaller priority numbers first. Preserve all ten levels;
    # _send translates our durable convention (9 = highest) at this boundary.
    broker_transport_options={"priority_steps": list(range(10)), "queue_order_strategy": "round_robin"},
    broker_connection_retry_on_startup=True,
    task_default_queue="maintenance",
    beat_schedule={
        "dispatch-durable-outbox": {
            "task": "helvetic_lens.dispatch_outbox",
            "schedule": 2.0,
        },
        "recover-durable-jobs": {
            "task": "helvetic_lens.recover_jobs",
            "schedule": 30.0,
        },
        "schedule-official-connectors": {
            "task": "helvetic_lens.schedule_connectors",
            "schedule": 15.0,
        },
        "cleanup-operational-data": {
            "task": "helvetic_lens.cleanup_operational_data",
            "schedule": 86400.0,
        },
        "schedule-user-digests": {
            "task": "helvetic_lens.schedule_digests",
            "schedule": 60.0,
        },
        "schedule-pollen-monitoring": {
            "task": "helvetic_lens.schedule_pollen_monitoring",
            "schedule": 60.0,
        },
        "schedule-air-monitoring": {
            "task": "helvetic_lens.schedule_air_monitoring", "schedule": 60.0,
        },
        "schedule-tender-monitoring": {
            "task": "helvetic_lens.schedule_tender_monitoring", "schedule": 15.0,
        },
        "schedule-commute-monitoring": {
            "task": "helvetic_lens.schedule_commute_monitoring", "schedule": 30.0,
        },
        "collect-commute-sources": {
            "task": "helvetic_lens.collect_commute_sources", "schedule": 60.0,
        },
        "collect-commute-static": {
            "task": "helvetic_lens.collect_commute_static", "schedule": 60.0,
        },
        "collect-road-source": {
            "task": "helvetic_lens.collect_road_source", "schedule": 60.0,
        },
        "schedule-road-monitoring": {
            "task": "helvetic_lens.schedule_road_monitoring", "schedule": 60.0,
        },
        "schedule-hazard-monitoring": {
            "task": "helvetic_lens.schedule_hazard_monitoring", "schedule": 60.0,
        },
        "cleanup-hazard-source": {
            "task": "helvetic_lens.cleanup_hazard_source", "schedule": 60.0,
        },
        "cleanup-trademark-source": {
            "task": "helvetic_lens.cleanup_trademark_source", "schedule": 60.0,
        },
        "cleanup-auction-source": {
            "task": "helvetic_lens.cleanup_auction_source", "schedule": 60.0,
        },
        "schedule-auction-monitoring": {
            "task": "helvetic_lens.schedule_auction_monitoring", "schedule": 15.0,
        },
        "schedule-trademark-monitoring": {
            "task": "helvetic_lens.schedule_trademark_monitoring", "schedule": 15.0,
        },
        "schedule-auction-reminders": {
            "task": "helvetic_lens.schedule_auction_reminders", "schedule": 15.0,
        },
        "schedule-auction-email": {
            "task": "helvetic_lens.schedule_auction_email", "schedule": 60.0,
        },
        "schedule-hazard-email": {
            "task": "helvetic_lens.schedule_hazard_email", "schedule": 60.0,
        },
        "schedule-road-email": {
            "task": "helvetic_lens.schedule_road_email", "schedule": 60.0,
        },
        "cleanup-road-source": {
            "task": "helvetic_lens.cleanup_road_source", "schedule": 60.0,
        },
        "schedule-commute-email": {
            "task": "helvetic_lens.schedule_commute_email", "schedule": 60.0,
        },
        "cleanup-air-measurements": {
            "task": "helvetic_lens.cleanup_air_measurements", "schedule": 86400.0,
        },
        "schedule-river-monitoring": {
            "task": "helvetic_lens.schedule_river_monitoring",
            "schedule": 60.0,
        },
        "cleanup-river-measurements": {
            "task": "helvetic_lens.cleanup_river_measurements",
            "schedule": 86400.0,
        },
    },
)


def _send(topic: str, queue: str, payload: dict, priority: int):
    celery_app.send_task(topic, kwargs=payload, queue=queue, priority=9 - max(0, min(9, priority)))


@celery_app.task(name="helvetic_lens.dispatch_outbox")
def dispatch_outbox():
    database = Database(settings)
    with database.session(include_all_organizations=True) as session:
        result = jobs.dispatch(session, _send, ai_window=settings.job_ai_dispatch_window)
        session.commit()
    database.engine.dispose()
    return result


@celery_app.task(name="helvetic_lens.recover_jobs")
def recover_jobs():
    database = Database(settings)
    with database.session(include_all_organizations=True) as session:
        result = jobs.reconcile(session, settings.job_lease_seconds)
        session.commit()
    database.engine.dispose()
    return result


@celery_app.task(name="helvetic_lens.schedule_connectors")
def schedule_connectors():
    database = Database(settings)
    with database.session(include_all_organizations=True) as session:
        result = synchronization.enqueue_due(session, settings)
        session.commit()
    database.engine.dispose()
    return result


@celery_app.task(name="helvetic_lens.schedule_digests")
def schedule_digests():
    database = Database(settings)
    try:
        return digests.enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.cleanup_operational_data")
def cleanup_data():
    database = Database(settings)
    try:
        return cleanup_operational_data(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_pollen_monitoring")
def schedule_pollen_monitoring():
    from .pollen_delivery import enqueue_due as enqueue_mail
    from .pollen_jobs import enqueue_due
    from .pollen_retention import cleanup
    database = Database(settings)
    try:
        return {"refresh": enqueue_due(database, settings), "delivery": enqueue_mail(database, settings), "retention": cleanup(database, settings)}
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_river_monitoring")
def schedule_river_monitoring():
    from .river_jobs import enqueue_due
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.cleanup_river_measurements")
def cleanup_river_measurements():
    from .river_sources import cleanup
    database = Database(settings)
    try:
        return cleanup(database)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_air_monitoring")
def schedule_air_monitoring():
    from .air_jobs import enqueue_due
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_tender_monitoring")
def schedule_tender_monitoring():
    from .tender_delivery import enqueue_due as enqueue_email
    from .tender_documents import cleanup as cleanup_documents
    from .tender_jobs import enqueue_due
    database = Database(settings)
    try:
        cleanup = cleanup_documents(database)
        return {"documents": cleanup, "refresh": enqueue_due(database, settings),
                "delivery": enqueue_email(database, settings)}
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.cleanup_air_measurements")
def cleanup_air_measurements():
    from .air_sources import cleanup
    database = Database(settings)
    try:
        return cleanup(database)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_commute_monitoring")
def schedule_commute_monitoring():
    from .commute_jobs import enqueue_due
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.collect_commute_sources")
def collect_commute_sources():
    from .commute_acquisition import collect_due
    database = Database(settings)
    try:
        return collect_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_road_email")
def schedule_road_email():
    from .road_delivery import enqueue_due
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_hazard_email")
def schedule_hazard_email():
    from .hazard_delivery import enqueue_due
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_commute_email")
def schedule_commute_email():
    from .commute_delivery import enqueue_due
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.collect_commute_static")
def collect_commute_static():
    from .commute_static_collector import collect
    database = Database(settings)
    try:
        return collect(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.collect_road_source")
def collect_road_source():
    from .road_acquisition import collect
    if not settings.road_watch_enabled or not settings.road_source_enabled:
        return {"state": "disabled"}
    database = Database(settings)
    try:
        return collect(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_hazard_monitoring")
def schedule_hazard_monitoring():
    from .hazard_jobs import enqueue_due
    if not settings.hazard_watch_enabled or not settings.hazard_source_enabled:
        return {"enqueued": 0}
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.cleanup_hazard_source")
def cleanup_hazard_source():
    from .hazard_jobs import cleanup
    database = Database(settings)
    try:
        return cleanup(database)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.cleanup_trademark_source")
def cleanup_trademark_source():
    from .trademark_sources import cleanup
    database = Database(settings)
    try:
        return cleanup(database)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.cleanup_auction_source")
def cleanup_auction_source():
    from .auction_sources import cleanup
    database = Database(settings)
    try:
        return cleanup(database)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_trademark_monitoring")
def schedule_trademark_monitoring():
    from .trademark_jobs import refresh_due
    database = Database(settings)
    try:
        return refresh_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_auction_monitoring")
def schedule_auction_monitoring():
    from .auction_jobs import refresh_due
    database = Database(settings)
    try:
        return refresh_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_auction_reminders")
def schedule_auction_reminders():
    from datetime import UTC, datetime

    from .auction_reminders import activate_due
    database = Database(settings)
    try:
        return activate_due(database, settings, now=datetime.now(UTC))
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_auction_email")
def schedule_auction_email():
    from .auction_delivery import enqueue_due
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.schedule_road_monitoring")
def schedule_road_monitoring():
    from .road_jobs import enqueue_due
    if not settings.road_watch_enabled:
        return {"enqueued": 0}
    database = Database(settings)
    try:
        return enqueue_due(database, settings)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.cleanup_road_source")
def cleanup_road_source():
    from .road_acquisition import cleanup
    database = Database(settings)
    try:
        return cleanup(database)
    finally:
        database.engine.dispose()


@celery_app.task(name="helvetic_lens.run_job")
def run_job(job_id: str):
    # Import lazily so dispatch-only processes do not construct fetch/model clients.
    global _worker_service
    from .service import HelveticLens

    if _worker_service is None:
        _worker_service = HelveticLens(settings)
        _worker_service.initialize()
    with _worker_service.db.session(include_all_organizations=True) as session:
        job = session.get(Job, job_id)
        if job is None:
            return {"state": "missing", "job_id": job_id}
        organization_id = job.organization_id
        correlation = dict(job.correlation or {})
    with (
        correlation_context(
            **{**correlation, "job_id": job_id, "organization_id": organization_id}
        ),
        _worker_service.db.organization_context(organization_id),
        _worker_service.organization_runtime(),
    ):
        return asyncio.run(_worker_service.execute_job(job_id, worker=socket.gethostname()))
