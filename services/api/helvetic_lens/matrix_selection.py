"""Batched matrix history selection; archived comparison/report bodies stay in SQL."""

from types import SimpleNamespace

from sqlalchemy import and_, case, func, or_, select

from .corpus_access import visible
from .models import Analysis, Comparison, DocumentWatch, Law

BATCH_SIZE = 50


def _comparisons(organization_id, law_ids):
    watched = (
        select(DocumentWatch.id)
        .where(
            DocumentWatch.law_id == Law.id,
            DocumentWatch.organization_id == organization_id,
            DocumentWatch.active.is_(True),
        )
        .correlate(Law)
        .exists()
    )
    return (
        select(Comparison)
        .join(Law, Law.id == Comparison.law_id)
        .where(
            Comparison.law_id.in_(law_ids),
            visible(Comparison, organization_id),
            visible(Law, organization_id),
            watched,
        )
    )


def comparisons(session, organization_id, law_ids):
    if not law_ids:
        return {}
    if len(law_ids) > BATCH_SIZE:
        raise ValueError("Matrix selection requires at most 50 laws.")
    base = _comparisons(organization_id, law_ids)
    ranked = base.with_only_columns(
        Comparison.id,
        func.row_number()
        .over(
            partition_by=Comparison.law_id,
            order_by=(Comparison.created_at.desc(), Comparison.id.desc()),
        )
        .label("position"),
    ).subquery()
    ids = select(ranked.c.id).where(ranked.c.position == 1)
    return {row.law_id: row for row in session.scalars(base.where(Comparison.id.in_(ids)))}


def reports(session, organization_id, selected, keys):
    """Return (state, chosen report, newest attempt) with at most one result per law."""
    if not selected:
        return {}
    if len(selected) > BATCH_SIZE:
        raise ValueError("Matrix selection requires at most 50 comparisons.")
    ids = [item.id for item in selected.values()]
    accessible = _comparisons(organization_id, list(selected)).with_only_columns(Comparison.id)
    base = select(Analysis).where(
        Analysis.organization_id == organization_id,
        Analysis.comparison_id.in_(ids),
        Analysis.comparison_id.in_(accessible),
    )
    json_type = func.json_typeof if session.bind.dialect.name == "postgresql" else func.json_type
    usable = and_(Analysis.status == "succeeded", json_type(Analysis.result) == "object")
    current = Analysis.cache_key == case(keys, value=Analysis.comparison_id)
    priority = case((and_(usable, current), 0), (usable, 1), else_=2)
    order = (Analysis.created_at.desc(), Analysis.id.desc())
    ranked = base.with_only_columns(
        Analysis.id,
        Analysis.comparison_id,
        Analysis.status,
        Analysis.created_at,
        priority.label("priority"),
        func.row_number().over(partition_by=Analysis.comparison_id, order_by=order).label("newest"),
        func.row_number()
        .over(partition_by=Analysis.comparison_id, order_by=(priority, *order))
        .label("preferred"),
    ).subquery()
    metadata = session.execute(select(ranked).where(or_(ranked.c.newest == 1, ranked.c.preferred == 1))).all()
    newest = {row.comparison_id: row for row in metadata if row.newest == 1}
    best = {row.comparison_id: row for row in metadata if row.preferred == 1}
    result_ids = [row.id for row in best.values() if row.priority < 2]
    # Repeat watch and ownership checks at payload materialization.
    bodies = (
        {
            row.id: SimpleNamespace(**row._mapping)
            for row in session.execute(
                base.with_only_columns(
                    Analysis.id,
                    Analysis.cache_key,
                    Analysis.status,
                    Analysis.created_at,
                    Analysis.result,
                ).where(Analysis.id.in_(result_ids), usable)
            )
        }
        if result_ids
        else {}
    )
    output = {}
    for comparison_id, row in best.items():
        latest = newest[comparison_id]
        body = bodies.get(row.id)
        if body:
            output[comparison_id] = (
                "current" if body.cache_key == keys[comparison_id] else "stale",
                body,
                latest,
            )
        elif latest.status == "failed":
            output[comparison_id] = (
                "failed",
                SimpleNamespace(
                    id=latest.id,
                    status=latest.status,
                    created_at=latest.created_at,
                    result=None,
                ),
                latest,
            )
        else:
            output[comparison_id] = ("unanalysed", None, latest)
    return output
