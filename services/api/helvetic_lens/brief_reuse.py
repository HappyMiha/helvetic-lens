"""Best-effort aggregate server reuse observations; no personal activity log."""
import logging
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import DomainError
from .db import utcnow
from .models import BriefReuseObservation as Observation
from .models import InterestEventAssessment as Assessment
from .topic_matching import _iso

SURFACES = frozenset({"reader", "notifications", "digest_preview"})


def observe(db, organization, briefs, surface):
    """Call after the projection transaction closes; never fail its response."""
    if surface not in SURFACES:
        raise ValueError("Unsupported brief observation surface")
    identities = {row["assessment_id"] for row in briefs if isinstance(row, dict)
                  and row.get("status") == "available" and isinstance(row.get("assessment_id"), str)}
    if not identities:
        return
    try:
        with db.session() as session:
            now = utcnow()
            # Explicit organization scope also applies in privileged workers.
            allowed = session.scalars(select(Assessment.id).where(Assessment.organization_id == organization,
                Assessment.id.in_(identities), Assessment.status == "succeeded"))
            values = [dict(organization_id=organization, assessment_id=identity, day=now.date().isoformat(),
                surface=surface, projections=1, first_at=now, last_at=now) for identity in allowed]
            if not values:
                return
            insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
            statement = insert(Observation).values(values)
            session.execute(statement.on_conflict_do_update(
                index_elements=[Observation.organization_id, Observation.assessment_id, Observation.day, Observation.surface],
                set_={"projections": Observation.projections + 1,
                      "first_at": case((statement.excluded.first_at < Observation.first_at, statement.excluded.first_at), else_=Observation.first_at),
                      "last_at": case((statement.excluded.last_at > Observation.last_at, statement.excluded.last_at), else_=Observation.last_at)}))
            session.commit()
    except Exception:
        logging.getLogger(__name__).warning("Brief reuse observation could not be saved.")


def read(session, organization, assessment_id, *, days=7):
    if days not in {1, 7, 30, 90}:
        raise DomainError("Choose a supported observation period.", 422, "invalid_brief_diagnostics")
    if session.scalar(select(Assessment.id).where(Assessment.id == assessment_id, Assessment.organization_id == organization)) is None:
        raise DomainError("This assessment is unavailable.", 404, "not_found")
    today = utcnow().date()
    start = (today - timedelta(days=days-1)).isoformat()
    rows = session.execute(select(Observation.surface, func.sum(Observation.projections).label("projections"),
        func.min(Observation.first_at).label("first_at"), func.max(Observation.last_at).label("last_at"))
        .where(Observation.organization_id == organization, Observation.assessment_id == assessment_id,
               Observation.day >= start, Observation.day <= today.isoformat())
        .group_by(Observation.surface).order_by(Observation.surface))
    return {"assessment_id": assessment_id, "days": days, "start_day": start, "end_day": today.isoformat(),
        "calendar_timezone": "UTC", "items": [{"surface": row.surface, "projections": row.projections,
            "first_at": _iso(row.first_at), "last_at": _iso(row.last_at)} for row in rows],
        "ai_calls": 0, "observation_kind": "server_projection", "complete_accounting": False}
