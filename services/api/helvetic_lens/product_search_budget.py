"""Shared, transactionally reserved public-search budget."""
from sqlalchemy import text

from .config import DomainError
from .db import utcnow
from .product_models import DecisionSearchBudget


def reserve(session, settings, units=1):
    # Callers hold the native write guard. PostgreSQL additionally serializes
    # across organizations/processes. Reservation and checkpoint commit together.
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(1279607635)"))
    day = utcnow().date()
    budget = session.get(DecisionSearchBudget, day)
    if (budget.used if budget else 0) + units > settings.decision_search_daily_limit:
        raise DomainError("The platform's daily query budget is exhausted. Saved evidence remains available; resume tomorrow.",
                          429, "search_budget_exhausted")
    if budget is None:
        budget = DecisionSearchBudget(day=day, used=0)
        session.add(budget)
    budget.used += units
