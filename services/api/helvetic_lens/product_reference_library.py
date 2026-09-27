"""Private source retrieval independent of the bounded mixed dossier activity feed."""
from typing import Literal

from fastapi import Query, Request
from sqlalchemy import and_, func, or_, select

from .db import utcnow
from .product_api import Product, dossier, entry_payload, fail
from .product_models import DossierEntry
from .product_provenance import principal
from .product_source_reviews import latest_review_query, source_record

PAGE_SIZE = 30


def reference_routes(router, service, actor):
    @router.get("/dossiers/{identifier}/references/{reference_id}")
    def reference(product: Product, identifier: str, reference_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            parent, _ = dossier(session, product, identifier, identity.user_id)
            return entry_payload(session, source_record(session, parent, reference_id))

    @router.get("/dossiers/{identifier}/references")
    def references(product: Product, identifier: str, request: Request,
                   q: str = Query(default="", max_length=300),
                   decision: Literal["all", "include", "exclude", "unreviewed"] = "all",
                   offset: int = Query(default=0, ge=0, le=2147483647)):
        identity = actor(request)
        terms = list(dict.fromkeys(q.strip().lower().split()))
        if len(terms) > 12:
            fail("Use up to 12 distinct words to find saved sources.", 422)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            parent, _ = dossier(session, product, identifier, identity.user_id)
            latest = latest_review_query(parent.id).subquery()
            current = func.coalesce(latest.c.data_json["decision"].as_string(), "unreviewed")
            query = select(DossierEntry).select_from(DossierEntry).outerjoin(latest, latest.c.url == DossierEntry.url).where(
                DossierEntry.dossier_id == parent.id, DossierEntry.kind == "reference")
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            if terms:
                origin = DossierEntry.data_json["discovery"]
                fields = [DossierEntry.title, DossierEntry.body, DossierEntry.url,
                    origin["query"].as_string(), origin["provider"].as_string(),
                    origin["record"]["title"].as_string(), origin["record"]["provider"].as_string(),
                    origin["record"]["id"].as_string()]
                query = query.where(and_(*(or_(*(field.icontains(term, autoescape=True) for field in fields)) for term in terms)))
            counts = {"include": 0, "exclude": 0, "unreviewed": 0}
            counts.update(dict(session.execute(query.with_only_columns(current, func.count()).group_by(current)).all()))
            counts["all"] = sum(counts.values())
            if decision != "all":
                query = query.where(current == decision)
            rows = session.scalars(query.order_by(DossierEntry.created_at.desc(), DossierEntry.id).offset(offset).limit(PAGE_SIZE))
            return {"items": [entry_payload(session, row) for row in rows], "total": counts[decision],
                    "dossier_total": total, "counts": counts, "query": q.strip(), "decision": decision,
                    "offset": offset, "page_size": PAGE_SIZE}
