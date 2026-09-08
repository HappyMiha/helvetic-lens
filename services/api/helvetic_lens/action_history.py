"""Read current action decisions and complete, scoped keyset history pages."""

import base64
from datetime import UTC

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import func, select, tuple_

from .config import DomainError
from .corpus_access import visible
from .db import utcnow
from .law_history import _serialize
from .models import ActionDecision, Analysis, Comparison, Law


def access(session, organization_id, comparison_id, analysis_id):
    found = session.scalar(
        select(Analysis.id)
        .join(Comparison, Comparison.id == Analysis.comparison_id)
        .join(Law, Law.id == Comparison.law_id)
        .where(
            Analysis.organization_id == organization_id,
            Analysis.id == analysis_id,
            Comparison.id == comparison_id,
            visible(Comparison, organization_id),
            visible(Law, organization_id),
        )
    )
    if found is None:
        raise DomainError("The requested record was not found.", 404, "not_found")


def _base(organization_id, comparison_id, analysis_id):
    return (
        select(ActionDecision)
        .join(Analysis, Analysis.id == ActionDecision.analysis_id)
        .join(Comparison, Comparison.id == Analysis.comparison_id)
        .join(Law, Law.id == Comparison.law_id)
        .where(
            ActionDecision.organization_id == organization_id,
            Analysis.organization_id == organization_id,
            ActionDecision.analysis_id == analysis_id,
            ActionDecision.comparison_id == comparison_id,
            Comparison.id == comparison_id,
            visible(Comparison, organization_id),
            visible(Law, organization_id),
        )
    )


def _columns():
    return [getattr(ActionDecision, col.key) for col in ActionDecision.__table__.columns]


def summary(session, organization_id, comparison_id, analysis_id):
    base = _base(organization_id, comparison_id, analysis_id)
    ranked = base.with_only_columns(
        ActionDecision.id,
        func.row_number()
        .over(
            partition_by=ActionDecision.action_key,
            order_by=(ActionDecision.created_at.desc(), ActionDecision.id.desc()),
        )
        .label("position"),
        func.count().over(partition_by=ActionDecision.action_key).label("total"),
    ).subquery()
    rows = (
        session.execute(
            base.with_only_columns(*_columns(), ranked.c.total)
            .join(ranked, ranked.c.id == ActionDecision.id)
            .where(ranked.c.position == 1)
        )
        .mappings()
        .all()
    )
    return {
        "current": {
            row["action_key"]: _serialize({key: value for key, value in row.items() if key != "total"})
            for row in rows
        },
        "history": [],
        "history_mode": "per_action",
        "counts": {row["action_key"]: row["total"] for row in rows},
    }


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    organization_id: str = Field(min_length=1, max_length=64)
    comparison_id: str = Field(min_length=1, max_length=64)
    analysis_id: str = Field(min_length=1, max_length=64)
    action_key: str = Field(min_length=1, max_length=200)
    limit: int = Field(ge=1, le=50)
    as_of: AwareDatetime
    at: AwareDatetime | None = None
    id: str = Field(default="", max_length=64)


def page(session, organization_id, comparison_id, analysis_id, action_key, *, cursor="", limit=20):
    access(session, organization_id, comparison_id, analysis_id)
    now = utcnow()
    scope = (organization_id, comparison_id, analysis_id, action_key, limit)
    try:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("Invalid limit")
        position = Cursor(
            organization_id=organization_id,
            comparison_id=comparison_id,
            analysis_id=analysis_id,
            action_key=action_key,
            limit=limit,
            as_of=now,
        )
        if cursor:
            if not isinstance(cursor, str) or len(cursor) > 2048:
                raise ValueError("Invalid cursor length")
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            position = Cursor.model_validate_json(raw)
            if scope != (
                position.organization_id,
                position.comparison_id,
                position.analysis_id,
                position.action_key,
                position.limit,
            ):
                raise ValueError("Cursor scope changed")
            if (
                position.as_of > now
                or (position.at is None) != (position.id == "")
                or (position.at and position.at > position.as_of)
            ):
                raise ValueError("Invalid boundary")
    except (TypeError, ValueError) as exc:
        raise DomainError(
            "This history page is no longer valid. Open the first page.", 422, "invalid_history_page"
        ) from exc
    base = _base(organization_id, comparison_id, analysis_id).where(
        ActionDecision.action_key == action_key, ActionDecision.created_at <= position.as_of
    )
    total = session.scalar(base.with_only_columns(func.count(), maintain_column_froms=True))
    query = base
    if position.at:
        query = query.where(
            tuple_(ActionDecision.created_at, ActionDecision.id) < tuple_(position.at, position.id)
        )
    rows = (
        session.execute(
            query.with_only_columns(*_columns())
            .order_by(ActionDecision.created_at.desc(), ActionDecision.id.desc())
            .limit(limit + 1)
        )
        .mappings()
        .all()
    )

    def encode(at=None, id_=""):
        value = position.model_copy(
            update={"at": at.replace(tzinfo=UTC) if at and at.tzinfo is None else at, "id": id_}
        )
        return base64.urlsafe_b64encode(value.model_dump_json().encode()).decode().rstrip("=")

    items = rows[:limit]
    return {
        "items": [_serialize(row) for row in items],
        "total": total,
        "limit": limit,
        "as_of": position.as_of.isoformat(),
        "first_cursor": encode(),
        "next_cursor": encode(items[-1]["created_at"], items[-1]["id"]) if len(rows) > limit else None,
    }
