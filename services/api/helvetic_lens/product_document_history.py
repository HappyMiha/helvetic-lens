"""Scoped product access to native saved-page metadata and evidence readers."""
import math
from datetime import datetime

from fastapi import Query, Request
from sqlalchemy import select

from . import evidence_pages, law_history
from .corpus_access import visible
from .db import utcnow
from .models import DocumentWatch, Law, Version
from .product_api import Product, dossier, fail
from .product_models import DossierEntry
from .product_provenance import principal

METADATA = ("id", "title", "content_hash", "evidence_revision", "content_type", "filename",
            "source_url", "origin", "synthetic", "declared_date", "date_provenance", "created_at",
            "characters", "passage_count")


def article_scope(value):
    value = value if isinstance(value, dict) else {}
    articles = value.get("articles") if isinstance(value.get("articles"), list) else []
    return {"scope": value.get("scope") if isinstance(value.get("scope"), str) else None,
            "official_version_date": value.get("official_version_date") if isinstance(value.get("official_version_date"), str) else None,
            "articles": [{"number": item["number"], "heading": item["heading"]} for item in articles
                         if isinstance(item, dict) and isinstance(item.get("number"), str) and isinstance(item.get("heading"), str)]}


def document(session, product, identifier, law_id, identity):
    principal(session, identity, utcnow())
    parent, _ = dossier(session, product, identifier, identity.user_id)
    found = session.execute(select(Law.id, Law.url, DocumentWatch.display_name.label("name"))
        .join(DocumentWatch, DocumentWatch.law_id == Law.id)
        .join(DossierEntry, DossierEntry.data_json["law_id"].as_string() == Law.id)
        .where(Law.id == law_id, visible(Law, session.info["organization_id"]),
               DocumentWatch.organization_id == session.info["organization_id"],
               DossierEntry.dossier_id == parent.id, DossierEntry.kind == "monitor").limit(1)).mappings().first()
    if found is None:
        fail("This page is not connected to an accessible dossier in this workspace.", 404)
    return dict(found)


def document_history_routes(router, service, actor):
    @router.get("/dossiers/{identifier}/discussion/{thread_id}/research/{entry_id}/sources/{source_id}/document")
    def research_document(product: Product, identifier: str, thread_id: str, entry_id: str,
                          source_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            parent, _ = dossier(session, product, identifier, identity.user_id)
            data = session.scalar(select(DossierEntry.data_json).where(DossierEntry.id == entry_id,
                DossierEntry.dossier_id == parent.id, DossierEntry.thread_id == thread_id, DossierEntry.kind == "research"))
            sources = data.get("sources") if isinstance(data, dict) else None
            source = next((item for item in sources if isinstance(item, dict) and item.get("id") == source_id), None) if isinstance(sources, list) else None
            if not source or source.get("kind") != "saved_page_extract" or not isinstance(source.get("key"), str):
                fail("This research source has no accessible saved page.", 404)
            version = session.execute(select(Version.id, Version.law_id, Version.evidence_revision)
                .where(Version.id == source["key"], visible(Version, session.info["organization_id"]))).mappings().first()
            if version is None:
                fail("The saved page used by this research note is no longer accessible.", 404)
            recorded = "document_id" in source or "evidence_revision" in source
            revision = source.get("evidence_revision")
            if recorded and (source.get("document_id") != version["law_id"] or type(revision) is not int or not 1 <= revision <= 2147483647):
                fail("The original document identity for this research source is unavailable.", 404)
            linked = document(session, product, identifier, version["law_id"], identity)
            return {"document_id": linked["id"], "version_id": version["id"],
                    "expected_revision": revision if recorded else None, "revision_recorded": recorded}

    @router.get("/dossiers/{identifier}/documents/{law_id}/checks")
    def checks(product: Product, identifier: str, law_id: str, request: Request,
               offset: int = Query(default=0, ge=0, le=100000), as_of: datetime | None = None):
        from .product_page_check_history import history

        identity = actor(request)
        with service.db.session() as session:
            linked = document(session, product, identifier, law_id, identity)
            parent, _ = dossier(session, product, identifier, identity.user_id)
            return history(session, parent, linked, offset=offset, as_of=as_of)

    @router.get("/dossiers/{identifier}/documents/{law_id}/versions")
    def history(product: Product, identifier: str, law_id: str, request: Request,
                cursor: str = Query(default="", max_length=2048)):
        identity = actor(request)
        with service.db.session() as session:
            document(session, product, identifier, law_id, identity)
            result = law_history.page(session, session.info["organization_id"], law_id, "versions", cursor=cursor, limit=20)
            items = [{**{key: item.get(key) for key in METADATA},
                      "selection_provenance": article_scope(item.get("selection_provenance"))} for item in result["items"]]
            return {**result, "document": document(session, product, identifier, law_id, identity), "items": items}

    @router.get("/dossiers/{identifier}/documents/{law_id}/versions/{version_id}")
    def snapshot(product: Product, identifier: str, law_id: str, version_id: str, request: Request,
                 offset: int = Query(default=0, ge=0, le=2147483647),
                 expected_revision: int | None = Query(default=None, ge=1, le=2147483647)):
        identity = actor(request)
        with service.db.session() as session:
            document(session, product, identifier, law_id, identity)
            base = select(Version.evidence_revision, Version.title, Version.content_hash).where(
                Version.id == version_id, Version.law_id == law_id, visible(Version, session.info["organization_id"]))
            version = session.execute(base).mappings().first()
            if version is None:
                fail("This saved version is not available for this connected page.", 404)
            revision = version["evidence_revision"]
            if expected_revision is not None and expected_revision != revision:
                fail("This saved version changed. Open its first page to read the current revision.", 409)
            result = evidence_pages.detail(session, session.info["organization_id"], version_id, service.settings, offset=offset, limit=50)
            if result["law_id"] != law_id or session.scalar(base.with_only_columns(Version.evidence_revision)) != revision:
                fail("This saved version changed while it was loading. Open its first page again.", 409)
            text = []
            omitted = 0
            for part in result["passages"]:
                if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                    omitted += 1
                    continue
                text.append({"id": part.get("id") if isinstance(part.get("id"), str) else None,
                             "text": part["text"], "page": part.get("page") if type(part.get("page")) in (int, float) and math.isfinite(part["page"]) and part["page"] > 0 else None})
            identity_data = result.get("identity_json")
            language = identity_data.get("language") if isinstance(identity_data, dict) else None
            return {**{key: result.get(key) for key in METADATA}, **dict(version), "document": document(session, product, identifier, law_id, identity),
                    "language": language if isinstance(language, str) else None,
                    "selection_provenance": article_scope(result.get("selection_provenance")),
                    "passages": text, "omitted_passages": omitted,
                    "plain_text": result["plain_text"], "pagination": result["pagination"]}
