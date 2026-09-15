"""Bounded, persistent queue turns before the durable handoff page limit."""

from datetime import timedelta

from sqlalchemy import case, func, select

from . import ai_dispatch
from .models import Job, OutboxMessage
from .monitoring_queues import (
    BULK,
    BULK_JOBS,
    DELIVERY,
    DELIVERY_JOBS,
    PROJECTION,
    PROJECTION_JOBS,
    SOURCE_JOBS,
    SOURCES,
)


def _lane():
    # Old pending records are classified like new admissions before pagination.
    return case((Job.type.in_(SOURCE_JOBS), SOURCES), (Job.type.in_(BULK_JOBS), BULK),
        (Job.type.in_(PROJECTION_JOBS), PROJECTION), (Job.type.in_(DELIVERY_JOBS), DELIVERY),
        (Job.queue.in_(ai_dispatch.QUEUES), "ai"), else_=Job.queue)


def candidates(session, now, limit, ai_slots):
    lane = _lane()
    ready_at = case((Job.available_at >= OutboxMessage.available_at, Job.available_at),
        else_=OutboxMessage.available_at)
    # Only eligible waiting time earns priority; future/backoff time does not.
    priority = case(*[(ready_at <= now - timedelta(seconds=ai_dispatch.AGE_SECONDS * gain),
        case((Job.priority + gain >= 9, 9), else_=Job.priority + gain))
        for gain in range(9, 0, -1)], else_=Job.priority)
    recent = select(lane.label("lane"), func.max(Job.dispatch_sequence).label("turn")).group_by(lane).subquery()
    ranked = select(OutboxMessage.id.label("message_id"), Job.id.label("job_id"),
        lane.label("lane"), priority.label("priority"), func.coalesce(recent.c.turn, 0).label("turn"),
        func.row_number().over(partition_by=lane,
            order_by=(priority.desc(), ready_at, OutboxMessage.created_at, OutboxMessage.id)).label("position"))\
        .join(Job, Job.id == OutboxMessage.job_id).outerjoin(recent, recent.c.lane == lane)\
        .where(OutboxMessage.state == "pending", OutboxMessage.available_at <= now,
            Job.queue.not_in(ai_dispatch.QUEUES), Job.state.in_(ai_dispatch.READY),
            Job.available_at <= now).subquery()
    rows = list(session.execute(select(ranked).order_by(ranked.c.position, ranked.c.turn, ranked.c.lane).limit(limit)))
    choices = [(row.position, row.turn, row.lane, row.message_id, row.job_id, row.priority, False) for row in rows]
    if ai_slots:
        ai_turn = session.scalar(select(func.max(Job.dispatch_sequence)).where(Job.queue.in_(ai_dispatch.QUEUES))) or 0
        for index, (message, job, effective_priority) in enumerate(ai_dispatch.candidates(session, now, limit)):
            choices.append((index + 1, ai_turn, "ai", message, job, effective_priority, True))
    choices.sort(key=lambda value: value[:3])
    # Keep bounded fallback heads: failed AI sends do not consume a window slot,
    # and skipping a full AI window must not reduce non-AI batch throughput.
    # The dispatcher enforces the total attempt limit under the same lock.
    return [value[3:] for value in choices]
