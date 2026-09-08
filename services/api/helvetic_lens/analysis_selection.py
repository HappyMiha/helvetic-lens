"""Select one saved impact report without loading or truncating its attempt history."""

from sqlalchemy import and_, case, or_, select

from .corpus_access import visible
from .models import Analysis, Comparison, Law


def _base(organization_id, comparison_id):
    return (
        select(Analysis)
        .join(Comparison, Comparison.id == Analysis.comparison_id)
        .join(Law, Law.id == Comparison.law_id)
        .where(
            Analysis.organization_id == organization_id,
            Analysis.comparison_id == comparison_id,
            visible(Comparison, organization_id),
            visible(Law, organization_id),
        )
    )


def latest_attempt(session, organization_id, comparison_id):
    return session.execute(
        _base(organization_id, comparison_id)
        .with_only_columns(Analysis.id, Analysis.status, Analysis.error, Analysis.created_at)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(1)
    ).first()


def report(session, organization_id, comparison_id, current_key, latest):
    # Pin the observed upper boundary: a newer attempt waits for the next read.
    # This is not a transaction snapshot against corrections/backdated inserts.
    base = _base(organization_id, comparison_id).where(
        or_(
            Analysis.created_at < latest.created_at,
            and_(Analysis.created_at == latest.created_at, Analysis.id <= latest.id),
        )
    )
    priority = case(
        (and_(Analysis.status == "succeeded", Analysis.cache_key == current_key), 0),
        (Analysis.status == "succeeded", 1),
        else_=2,
    )
    selected_id = session.scalar(
        base.with_only_columns(Analysis.id)
        .order_by(priority, Analysis.created_at.desc(), Analysis.id.desc())
        .limit(1)
    )
    # Repeat ownership filters at materialization; no other result/plan bodies load.
    return session.scalar(base.where(Analysis.id == selected_id)) if selected_id else None
