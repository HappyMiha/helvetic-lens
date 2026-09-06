"""Scalar law-history metadata; preserve saved evidence without transferring its bodies."""

import base64
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import Float, case, cast, func, select

from .config import DomainError
from .corpus_access import visible
from .db import utcnow
from .models import Comparison, DocumentWatch, Law, Observation, Version


def _fields(model, omitted):
    return [getattr(model, column.key) for column in model.__table__.columns if column.key not in omitted]


def _serialize(row):
    return {
        key: (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()
        if isinstance(value, datetime)
        else value
        for key, value in row.items()
    }


def _scoped(statement, model, organization_id, law_id):
    return (
        statement.select_from(model)
        .join(Law, Law.id == model.law_id)
        .join(DocumentWatch, DocumentWatch.law_id == Law.id)
        .where(
            Law.id == law_id,
            visible(Law, organization_id),
            DocumentWatch.organization_id == organization_id,
            model.organization_id == organization_id
            if model is Observation
            else visible(model, organization_id),
        )
    )


def versions(session, organization_id, law_id, *, ids=None):
    postgres = session.bind.dialect.name == "postgresql"
    if postgres:
        parts = func.json_array_elements(Version.passages).table_valued("value").render_derived()
        page_json = parts.c.value.op("->")("page")
        page = case(
            (func.json_typeof(page_json) == "number", cast(parts.c.value.op("->>")("page"), Float)), else_=0
        )
    else:
        parts = func.json_each(Version.passages).table_valued("value")
        page = case(
            (
                func.json_type(parts.c.value, "$.page").in_(("integer", "real")),
                cast(func.json_extract(parts.c.value, "$.page"), Float),
            ),
            else_=0,
        )
    max_page = select(func.max(page)).select_from(parts).correlate(Version).scalar_subquery()
    statement = _scoped(
        select(
            *_fields(Version, {"text", "passages", "artifact_key"}),
            func.length(Version.text).label("characters"),
            func.json_array_length(Version.passages).label("passage_count"),
            func.coalesce(max_page, 0).label("page_count"),
        ),
        Version,
        organization_id,
        law_id,
    ).order_by(Version.created_at.desc(), Version.id.desc())
    if ids is not None:
        statement = statement.where(Version.id.in_(ids))
    results = []
    for row in session.execute(statement).mappings():
        result = _serialize(row)
        page_count = result["page_count"]
        result["page_count"] = int(page_count) if page_count == int(page_count) else page_count
        result["evidence_url"] = f"/evidence/{row['id']}"
        result["artifact_url"] = f"/api/versions/{row['id']}/artifact"
        results.append(result)
    return results


def comparisons(session, organization_id, law_id, *, ids=None):
    statement = _scoped(
        select(
            *_fields(Comparison, {"diff"}),
            Comparison.diff["counts"].label("counts"),
        ),
        Comparison,
        organization_id,
        law_id,
    ).order_by(Comparison.created_at.desc(), Comparison.id.desc())
    statement = statement.limit(50) if ids is None else statement.where(Comparison.id.in_(ids))
    return [_serialize(row) for row in session.execute(statement).mappings()]


def observations(session, organization_id, law_id, *, ids=None):
    statement = _scoped(select(*_fields(Observation, {"artifact_key"})), Observation, organization_id, law_id)
    statement = statement.order_by(Observation.created_at.desc(), Observation.id.desc())
    statement = statement.limit(100) if ids is None else statement.where(Observation.id.in_(ids))
    return [_serialize(row) for row in session.execute(statement).mappings()]


HistoryKind = Literal["versions", "comparisons", "observations"]
READERS = {
    "versions": (Version, versions),
    "comparisons": (Comparison, comparisons),
    "observations": (Observation, observations),
}


class HistoryCursor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = 1
    organization_id: str = Field(min_length=1, max_length=64)
    law_id: str = Field(min_length=1, max_length=64)
    kind: HistoryKind
    limit: int = Field(ge=1, le=50)
    as_of: AwareDatetime
    at: AwareDatetime | None = None
    id: str = Field(default="", max_length=64)


def page(session, organization_id, law_id, kind: HistoryKind, *, cursor="", limit=20):
    """Traverse metadata in stable saved-time/ID order, with access checked on every read.

    The cutoff excludes newer saves, not later corrections/backdated imports. It is
    deliberately not an immutable database snapshot. An unsigned cursor grants no access.
    """
    if kind not in READERS or type(limit) is not int or not 1 <= limit <= 50:
        raise DomainError("Choose a valid history page.", 422, "invalid_history_page")
    model, reader = READERS[kind]
    captured, position = utcnow(), None
    if cursor:
        try:
            if not isinstance(cursor, str) or len(cursor) > 2048:
                raise ValueError("Invalid cursor length")
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            position = HistoryCursor.model_validate_json(raw)
            if (
                (position.organization_id, position.law_id, position.kind, position.limit)
                != (organization_id, law_id, kind, limit)
                or (position.at is None) != (position.id == "")
                or (position.at is not None and position.at > position.as_of)
                or position.as_of > captured
            ):
                raise ValueError("Cursor scope changed")
            captured = position.as_of
        except (ValueError, TypeError) as exc:
            raise DomainError(
                "This history page is no longer valid. Open the first page.", 422, "invalid_history_page"
            ) from exc
    access = (
        select(DocumentWatch.id)
        .join(Law, Law.id == DocumentWatch.law_id)
        .where(
            DocumentWatch.organization_id == organization_id, Law.id == law_id, visible(Law, organization_id)
        )
    )
    if session.scalar(access) is None:
        raise DomainError("The requested record was not found.", 404, "not_found")
    base = _scoped(select(model.id, model.created_at), model, organization_id, law_id).where(
        model.created_at <= captured
    )
    total = session.scalar(base.with_only_columns(func.count(), maintain_column_froms=True))
    statement = base
    if position and position.at is not None:
        statement = statement.where(
            (model.created_at < position.at) | ((model.created_at == position.at) & (model.id < position.id))
        )
    rows = session.execute(
        statement.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)
    ).all()
    selected = rows[:limit]
    items = reader(session, organization_id, law_id, ids=[row.id for row in selected]) if selected else []

    def encode(at=None, id_=""):
        value = HistoryCursor(
            organization_id=organization_id,
            law_id=law_id,
            kind=kind,
            limit=limit,
            as_of=captured,
            at=at.replace(tzinfo=UTC) if at is not None and at.tzinfo is None else at,
            id=id_,
        )
        return base64.urlsafe_b64encode(value.model_dump_json().encode()).decode().rstrip("=")

    next_cursor = None
    if len(rows) > limit:
        last = selected[-1]
        next_cursor = encode(last.created_at, last.id)
    return {
        "items": items,
        "total": total,
        "as_of": captured.astimezone(UTC).isoformat(),
        "limit": limit,
        "first_cursor": encode(),
        "next_cursor": next_cursor,
    }
