"""Bounded scalar pages for the complete saved regulatory timeline and its metadata."""

import base64
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, literal, or_, select, union_all

from .config import DomainError
from .corpus_access import visible
from .db import utcnow
from .models import (
    Comparison,
    Observation,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryIdentifier,
    Version,
)

TimelineKind = Literal["timeline", "identifiers", "expressions", "relations", "source_provenance"]
KINDS = ("timeline", "identifiers", "expressions", "relations", "source_provenance")


def iso(value):
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    organization_id: str = Field(min_length=1, max_length=64)
    law_id: str = Field(min_length=1, max_length=36)
    work_id: str | None = Field(default=None, max_length=36)
    kind: TimelineKind
    limit: int = Field(ge=1, le=50)
    as_of: AwareDatetime
    at: AwareDatetime | None = None
    key: str = Field(default="", max_length=100)


def encoded(value):
    return base64.urlsafe_b64encode(value.model_dump_json().encode()).decode().rstrip("=")


def query(reader, header, law_id, kind):
    org, work = reader.organization_id, header.work_id
    if kind == "timeline":
        return union_all(
            select(
                (literal("event:") + RegulatoryEvent.id).label("_key"),
                RegulatoryEvent.detected_at.label("_at"),
                RegulatoryEvent.created_at.label("_admitted"),
                literal("event").label("type"),
                RegulatoryEvent.event_type.label("label"),
                RegulatoryEvent.provenance_method.label("detail"),
                RegulatoryEvent.source_url.label("url"),
            ).where(RegulatoryEvent.work_id == work, literal(work is not None)),
            select(
                (literal("version:") + Version.id).label("_key"),
                Version.created_at.label("_at"),
                Version.created_at.label("_admitted"),
                literal("version").label("type"),
                literal("Immutable version saved").label("label"),
                func.coalesce(Version.declared_date, Version.origin).label("detail"),
                (literal("/evidence/") + Version.id).label("url"),
            ).where(Version.law_id == law_id, visible(Version, org)),
            select(
                (literal("comparison:") + Comparison.id).label("_key"),
                Comparison.created_at.label("_at"),
                Comparison.created_at.label("_admitted"),
                literal("comparison").label("type"),
                literal("Comparison created").label("label"),
                Comparison.mode.label("detail"),
                (literal("/compare/") + Comparison.id).label("url"),
            ).where(Comparison.law_id == law_id, visible(Comparison, org)),
        ).subquery()
    if kind == "relations":
        return reader._timeline_relations_query(work).where(literal(work is not None)).subquery()
    if kind == "source_provenance":
        return select(
            Observation.id.label("_key"),
            Observation.created_at.label("_at"),
            Observation.created_at.label("_admitted"),
            Observation.origin,
            Observation.source_url,
            Observation.created_at.label("observed_at"),
        )
    model = RegulatoryIdentifier if kind == "identifiers" else RegulatoryExpression
    columns = (
        (model.scheme, model.value, model.source_url)
        if kind == "identifiers"
        else (
            model.id,
            model.language,
            model.title,
            model.official_url.label("url"),
        )
    )
    return (
        select(
            model.id.label("_key"),
            model.created_at.label("_at"),
            model.created_at.label("_admitted"),
            *columns,
        )
        .where(
            model.work_id == work,
            literal(work is not None),
        )
        .subquery()
    )


def page(session, reader, law_id, kind: TimelineKind, *, cursor="", limit=20, header=None, captured=None):
    if kind not in KINDS or type(limit) is not int or not 1 <= limit <= 50:
        raise DomainError("Choose a valid history page.", 422, "invalid_history_page")
    header = header if header is not None else reader._timeline_header(session, law_id)
    captured = captured or utcnow()
    position = Cursor(
        organization_id=reader.organization_id,
        law_id=law_id,
        work_id=header.work_id,
        kind=kind,
        limit=limit,
        as_of=captured,
    )
    if cursor:
        try:
            if len(cursor) > 2048:
                raise ValueError("Cursor too long")
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            saved = Cursor.model_validate_json(raw)
            if (
                (saved.organization_id, saved.law_id, saved.work_id, saved.kind, saved.limit)
                != (position.organization_id, law_id, header.work_id, kind, limit)
                or (saved.at is None) != (saved.key == "")
                or saved.as_of > captured
            ):
                raise ValueError("Cursor scope changed")
            position = saved
        except (ValueError, TypeError) as exc:
            raise DomainError(
                "This history page is no longer valid. Open the first page.", 422, "invalid_history_page"
            ) from exc
    if header.work_id is None and kind in {"identifiers", "expressions", "relations"}:
        return {
            "items": [],
            "total": 0,
            "limit": limit,
            "as_of": iso(position.as_of),
            "first_cursor": encoded(position.model_copy(update={"at": None, "key": ""})),
            "next_cursor": None,
        }
    rows = query(reader, header, law_id, kind)
    if kind == "source_provenance":
        rows = rows.where(
            Observation.law_id == law_id, Observation.organization_id == reader.organization_id
        ).subquery()
    base = select(rows).where(rows.c._admitted <= position.as_of)
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    selected = base
    if position.at is not None:
        selected = selected.where(
            or_(rows.c._at < position.at, and_(rows.c._at == position.at, rows.c._key < position.key))
        )
    values = list(
        session.execute(selected.order_by(rows.c._at.desc(), rows.c._key.desc()).limit(limit + 1)).mappings()
    )
    items = []
    for row in values[:limit]:
        item = {
            key: iso(value) if isinstance(value, datetime) else value
            for key, value in row.items()
            if not key.startswith("_")
        }
        if kind == "timeline":
            item.update(id=row["_key"], at=iso(row["_at"]))
            if item["type"] == "event":
                item["event_type"] = item["label"]
                item["label"] = item["label"].replace("_", " ").title()
                item["detail"] = item["detail"].replace("_", " ")
        elif kind == "relations":
            item = reader._timeline_relation_record(row)
        items.append(item)
    next_cursor = None
    if len(values) > limit:
        last = values[limit - 1]
        next_cursor = encoded(
            position.model_copy(update={"at": datetime.fromisoformat(iso(last["_at"])), "key": last["_key"]})
        )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "as_of": iso(position.as_of),
        "first_cursor": encoded(position.model_copy(update={"at": None, "key": ""})),
        "next_cursor": next_cursor,
    }
