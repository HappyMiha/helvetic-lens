"""Celery entrypoint for durable Helvetic Lens work."""

from __future__ import annotations

import asyncio
import socket

from celery import Celery

from . import jobs, synchronization
from .config import Settings
from .db import Database
from .maintenance import cleanup_operational_data
from .models import Job

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
    },
)


def _send(topic: str, queue: str, payload: dict, priority: int):
    celery_app.send_task(topic, kwargs=payload, queue=queue, priority=priority)


@celery_app.task(name="helvetic_lens.dispatch_outbox")
def dispatch_outbox():
    database = Database(settings)
    with database.session(include_all_organizations=True) as session:
        result = jobs.dispatch(session, _send)
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


@celery_app.task(name="helvetic_lens.cleanup_operational_data")
def cleanup_data():
    database = Database(settings)
    try:
        return cleanup_operational_data(database, settings)
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
    with _worker_service.db.organization_context(organization_id), _worker_service.organization_runtime():
        return asyncio.run(_worker_service.execute_job(job_id, worker=socket.gethostname()))
