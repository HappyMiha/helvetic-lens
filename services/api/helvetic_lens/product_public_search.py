"""Typed anonymous knowledge search, filtered at the database before pagination."""
from urllib.parse import quote

from fastapi import Query
from sqlalchemy import func, literal, or_, select, union_all

from .product_api import Product, fail
from .product_investigation_models import DossierClaim, DossierEntity, Investigation, InvestigationSource
from .product_models import ProductPublication
from .product_public_research import eligible


def query(product, words):
    pub = ProductPublication
    queries = []
    for kind, model, label, text in [
        ("dossier", pub, pub.title, pub.summary + " " + pub.body),
        ("claim", DossierClaim, DossierClaim.statement, DossierClaim.status),
        ("entity", DossierEntity, DossierEntity.name, DossierEntity.kind),
        ("source", InvestigationSource, InvestigationSource.title, InvestigationSource.url),
        ("investigation", Investigation, Investigation.question, Investigation.stop_reason),
    ]:
        item = select(literal(kind).label("kind"), model.id.label("id"), label.label("label"),
            text.label("text"), pub.id.label("publication_id"), pub.title.label("dossier_title"),
            func.coalesce(pub.slug, pub.id).label("slug"),
            (literal("") if model is pub else Investigation.id).label("investigation_id"))
        if model is not pub:
            item = item.select_from(Investigation).join(pub, pub.id == Investigation.publication_id)
            if model is not Investigation:
                item = item.join(model, model.investigation_id == Investigation.id)
            item = item.where(eligible())
        item = item.where(pub.product == product, pub.status == "published")
        for word in words:
            item = item.where(or_(func.lower(label).contains(word, autoescape=True),
                                  func.lower(text).contains(word, autoescape=True)))
        queries.append(item)
    return union_all(*queries).subquery()


def routes(router, service, actor):
    @router.get("/public-knowledge")
    def search(product: Product, q: str = Query(default="", max_length=300),
               offset: int = Query(default=0, ge=0, le=100000)):
        words = list(dict.fromkeys(q.lower().split()))
        if len(words) > 12:
            fail("Use at most 12 search words.")
        with service.db.session(include_all_organizations=True) as session:
            table = query(product, words)
            total = session.scalar(select(func.count()).select_from(table))
            results = session.execute(select(table).order_by(table.c.kind, table.c.label, table.c.id)
                .offset(offset).limit(20)).mappings()
            items = []
            for row in results:
                value = dict(row)
                value["text"] = value["text"][:700]
                value["href"] = "/public-dossiers/" + quote(value["slug"], safe="")
                if value["investigation_id"]:
                    value["href"] += "?research=" + value["investigation_id"] + "#" + value["kind"] + "-" + value["id"]
                items.append(value)
            return {"items": items, "total": total, "offset": offset, "page_size": 20,
                "query": q.strip(), "method": "Literal word matching across explicitly public knowledge; no private index or model call."}
