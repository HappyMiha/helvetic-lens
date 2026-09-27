"""Append-only team decisions about exact source URLs inside a private dossier."""
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field
from sqlalchemy import func, select

from . import legal_profiles
from .db import utcnow
from .product_api import Product, dossier, entry_payload, fail
from .product_models import DossierEntry
from .product_provenance import principal

LABELS = {"include": "Include in AI research", "exclude": "Exclude from AI research", "unreviewed": "Needs review; eligible for AI research"}


class ReviewInput(legal_profiles.Input):
    request_key: UUID
    expected_review_id: UUID | None
    decision: Literal["include", "exclude", "unreviewed"]
    reason: str = Field(min_length=3, max_length=2000)


def review_query(identifier, url=None):
    query = select(DossierEntry).where(DossierEntry.dossier_id == identifier, DossierEntry.kind == "source_review")
    return query.where(DossierEntry.url == url) if url is not None else query


def latest_review_query(identifier):
    ranked = review_query(identifier).with_only_columns(DossierEntry.id, func.row_number().over(
        partition_by=DossierEntry.url,
        order_by=(DossierEntry.data_json["revision"].as_integer().desc(), DossierEntry.id.desc())).label("position")).subquery()
    return select(DossierEntry).join(ranked, ranked.c.id == DossierEntry.id).where(ranked.c.position == 1)


def current_reviews(session, identifier):
    return {row.url: row for row in session.scalars(latest_review_query(identifier))}


def review_vector(reviews):
    return {url: row.id for url, row in reviews.items()}


def source_record(session, parent, identifier):
    source = session.get(DossierEntry, identifier)
    if not source or source.dossier_id != parent.id or source.kind != "reference" or not source.url:
        fail("This source reference is not available in this dossier.", 404)
    return source


def source_review_routes(router, service, actor):
    @router.get("/dossiers/{identifier}/sources/{reference_id}/reviews")
    def history(product: Product, identifier: str, reference_id: str, request: Request,
                offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            parent, _ = dossier(session, product, identifier, identity.user_id)
            source = source_record(session, parent, reference_id)
            query = review_query(parent.id, source.url)
            current = current_reviews(session, parent.id).get(source.url)
            items = session.scalars(query.order_by(DossierEntry.data_json["revision"].as_integer().desc(),
                DossierEntry.id.desc()).offset(offset).limit(50))
            return {"current": entry_payload(session, current) if current else None,
                    "items": [entry_payload(session, row) for row in items],
                    "total": session.scalar(select(func.count()).select_from(query.subquery()))}

    @router.post("/dossiers/{identifier}/sources/{reference_id}/reviews", status_code=201)
    def review(product: Product, identifier: str, reference_id: str, data: ReviewInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            principal(session, identity, utcnow(), write=True)
            parent, _ = dossier(session, product, identifier, identity.user_id)
            source = source_record(session, parent, reference_id)
            requested = {"reference_id": source.id, "decision": data.decision,
                         "expected_review_id": str(data.expected_review_id) if data.expected_review_id else None}
            previous = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == parent.id,
                DossierEntry.request_key == str(data.request_key)))
            if previous:
                if (previous.kind != "source_review" or previous.actor_user_id != identity.user_id
                        or previous.url != source.url or previous.body != data.reason
                        or any(previous.data_json.get(key) != value for key, value in requested.items())):
                    fail("This request key belongs to a different saved entry.", 409)
                return entry_payload(session, previous)
            current = current_reviews(session, parent.id).get(source.url)
            if requested["expected_review_id"] != (current.id if current else None):
                fail("The team reviewed this URL while you were working. Refresh the history and review the latest decision before saving.", 409)
            entry = DossierEntry(dossier_id=parent.id, request_key=str(data.request_key), kind="source_review",
                title=("Source review: " + (source.title or source.url))[:240], body=data.reason, url=source.url,
                actor_user_id=identity.user_id, data_json={**requested, "revision": current.data_json["revision"] + 1 if current else 1})
            session.add(entry)
            session.commit()
            return entry_payload(session, entry)
