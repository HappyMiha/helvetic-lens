"""Transactional host-wide admission for durable background brief generation."""
from datetime import timedelta

from sqlalchemy import func, select, text

from . import jobs
from .config import DomainError
from .db import utcnow
from .models import Job


def require_capacity(session, settings, *, new_job=True):
    """Caller holds its org write lock and commits the job in this transaction.

    PostgreSQL needs a shared serialization point across organizations. The
    transaction advisory lock is never held across model/network calls. SQLite
    already serializes writers through the caller's organization UPDATE.
    No other organization's rows or usage figures leave this function.
    """
    if session.bind.dialect.name == "postgresql":
        # Reserved application lock namespace HLEN, interest brief admission.
        session.execute(text("SELECT pg_advisory_xact_lock(1212958030, 8901)"))
    pending_limit = settings.interest_brief_global_max_pending if settings else 16
    daily_limit = settings.interest_brief_global_max_daily if settings else 200
    scope = (Job.type == "interest_event_brief",)

    def count(*conditions):
        return session.scalar(select(func.count()).select_from(Job).where(*scope, *conditions)
            .execution_options(include_all_organizations=True))

    pending = count(Job.state.not_in(jobs.TERMINAL_STATES))
    # Retrying the SAME job consumes pending capacity again, but does not mint
    # another daily admission. Assessment/manual retry budgets remain enforced.
    daily = count(Job.created_at >= utcnow() - timedelta(hours=24)) if new_job else 0
    if pending >= pending_limit or (new_job and daily >= daily_limit):
        raise DomainError("Server background brief allowance reached; saved source evidence remains available.",
                          429, "interest_queue_limit")
