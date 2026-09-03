"""Celery entrypoint for durable Helvetic Lens work."""

from __future__ import annotations

import asyncio
import socket

from celery import Celery

from . import jobs
from .config import Settings
from .db import Database

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
    },
)


def _send(topic: str, queue: str, payload: dict, priority: int):
    celery_app.send_task(topic, kwargs=payload, queue=queue, priority=priority)


@celery_app.task(name="helvetic_lens.dispatch_outbox")
def dispatch_outbox():
    database = Database(settings)
    with database.session() as session:
        result = jobs.dispatch(session, _send)
        session.commit()
    database.engine.dispose()
    return result


@celery_app.task(name="helvetic_lens.recover_jobs")
def recover_jobs():
    database = Database(settings)
    with database.session() as session:
        result = jobs.reconcile(session, settings.job_lease_seconds)
        session.commit()
    database.engine.dispose()
    return result


@celery_app.task(name="helvetic_lens.run_job")
def run_job(job_id: str):
    # Import lazily so dispatch-only processes do not construct fetch/model clients.
    global _worker_service
    from .service import HelveticLens

    if _worker_service is None:
        _worker_service = HelveticLens(settings)
        _worker_service.initialize()
    return asyncio.run(_worker_service.execute_job(job_id, worker=socket.gethostname()))
