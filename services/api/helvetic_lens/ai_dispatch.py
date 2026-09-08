"""Bounded broker handoff with persistent tenant turns and ready-work aging."""
from datetime import timedelta

from sqlalchemy import case, false, func, select, text, update

from .models import Job, OutboxMessage

QUEUES = ("ai_interactive", "ai_background")
READY = ("queued", "retrying", "waiting_for_model")
AGE_SECONDS = 60


def begin_turn(session):
    if session.bind.dialect.name == "postgresql":
        # Do not wait behind another dispatcher while a caller owns job locks.
        return session.scalar(text("SELECT pg_try_advisory_xact_lock(1212958030, 8902)"))
    # Start a SQLite write transaction without altering a row. This must precede
    # the capacity read; otherwise concurrent dispatchers could both fill a slot.
    session.execute(update(Job).where(false()).values(id=Job.id))
    return True


def free_slots(session, window):
    occupied = session.scalar(select(func.count()).select_from(Job).where(
        Job.queue.in_(QUEUES), Job.state == "dispatched")
        .execution_options(include_all_organizations=True))
    return max(0, window - occupied)


def candidates(session, now, limit):
    # Aging uses the later of job/outbox eligibility, never time spent in an
    # intentional future retry delay. CASE keeps the expression portable to SQLite.
    ready_at = case((Job.available_at > OutboxMessage.available_at, Job.available_at),
                    else_=OutboxMessage.available_at)
    priority = case(*[(ready_at <= now - timedelta(seconds=AGE_SECONDS * gain),
                      case((Job.priority + gain >= 9, 9), else_=Job.priority + gain))
                     for gain in range(9, 0, -1)], else_=Job.priority)
    recent = select(Job.organization_id.label("organization_id"),
                    func.max(Job.dispatch_sequence).label("last_turn"))\
        .where(Job.queue.in_(QUEUES)).group_by(Job.organization_id).subquery()
    ranked = select(OutboxMessage.id.label("message_id"), Job.id.label("job_id"),
        priority.label("priority"), ready_at.label("ready_at"),
        func.coalesce(recent.c.last_turn, 0).label("last_turn"),
        func.row_number().over(partition_by=Job.organization_id,
            order_by=(priority.desc(), ready_at, OutboxMessage.id)).label("tenant_position"))\
        .join(Job, Job.id == OutboxMessage.job_id)\
        .outerjoin(recent, recent.c.organization_id == Job.organization_id)\
        .where(OutboxMessage.state == "pending", OutboxMessage.queue.in_(QUEUES),
               OutboxMessage.available_at <= now, Job.available_at <= now,
               Job.state.in_(READY)).subquery()
    # Select tenant heads before applying the page limit: a noisy tenant cannot
    # hide another organization behind hundreds of its own older pending rows.
    return list(session.execute(select(ranked.c.message_id, ranked.c.job_id, ranked.c.priority)
        .where(ranked.c.tenant_position == 1)
        .order_by(ranked.c.priority.desc(), ranked.c.last_turn, ranked.c.ready_at, ranked.c.job_id)
        .limit(limit)))


def record_turn(session, job):
    # A logical sequence survives equal clocks and dispatcher restarts. Only
    # aggregate metadata bypasses tenant filtering; no private job is returned.
    latest = session.scalar(select(func.max(Job.dispatch_sequence))
        .execution_options(include_all_organizations=True)) or 0
    job.dispatch_sequence = latest + 1
    session.flush()
