"""Scalar law-history metadata; preserve saved evidence without transferring its bodies."""

from datetime import UTC, datetime

from sqlalchemy import Float, case, cast, func, select

from .corpus_access import visible
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


def versions(session, organization_id, law_id):
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
    results = []
    for row in session.execute(statement).mappings():
        result = _serialize(row)
        page_count = result["page_count"]
        result["page_count"] = int(page_count) if page_count == int(page_count) else page_count
        result["evidence_url"] = f"/evidence/{row['id']}"
        result["artifact_url"] = f"/api/versions/{row['id']}/artifact"
        results.append(result)
    return results


def comparisons(session, organization_id, law_id):
    statement = (
        _scoped(
            select(
                *_fields(Comparison, {"diff"}),
                Comparison.diff["counts"].label("counts"),
            ),
            Comparison,
            organization_id,
            law_id,
        )
        .order_by(Comparison.created_at.desc(), Comparison.id.desc())
        .limit(50)
    )
    return [_serialize(row) for row in session.execute(statement).mappings()]


def observations(session, organization_id, law_id):
    statement = _scoped(select(*_fields(Observation, {"artifact_key"})), Observation, organization_id, law_id)
    statement = statement.order_by(Observation.created_at.desc(), Observation.id.desc()).limit(100)
    return [_serialize(row) for row in session.execute(statement).mappings()]
