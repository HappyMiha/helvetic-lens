"""Public reads are a separate, allowlisted projection of explicitly published text."""
import hashlib
import hmac
import ipaddress
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import Query, Request
from pydantic import Field, StrictBool, field_validator
from sqlalchemy import case, func, or_, select

from . import legal_profiles
from .db import utcnow
from .product_api import EntryInput, Product, dossier, fail, iso
from .product_models import ProductPublication, PublicationRevision
from .product_provenance import canonical, principal, signature

PUBLIC_READ = re.compile(r"^/api/products/(pharma|loyer)/(?:public-knowledge|public-dossiers"
    r"(?:/[\w-]{1,180}(?:/discussion|/files/[0-9a-f-]{36}|/research(?:/[0-9a-f-]{36}(?:/events)?)?)?)?)$")
LIFETIME = timedelta(minutes=30)


class PublicSource(legal_profiles.Input):
    title: str = Field(min_length=1, max_length=240)
    url: str = Field(min_length=1, max_length=2000)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        EntryInput.valid_url(value)
        host = (urlsplit(value).hostname or "").lower().rstrip(".")
        if "." not in host or host.endswith((".local", ".localhost", ".internal")):
            raise ValueError("Use a public HTTPS source address.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and not address.is_global:
            raise ValueError("Use a public HTTPS source address.")
        return value


class PublicContent(legal_profiles.Input):
    title: str = Field(min_length=3, max_length=240)
    summary: str = Field(min_length=10, max_length=1500)
    body: str = Field(min_length=20, max_length=30000)
    author_label: str = Field(min_length=2, max_length=100)
    sources: list[PublicSource] = Field(default_factory=list, max_length=30)

    @field_validator("sources")
    @classmethod
    def unique_sources(cls, value):
        if len({item.url for item in value}) != len(value):
            raise ValueError("List each source address once.")
        return value


class PublicationDraft(legal_profiles.Input):
    expected_revision: int = Field(ge=0)
    content: PublicContent
    living_research: StrictBool = False


class PublishInput(PublicationDraft):
    request_key: UUID
    confirm_public: bool
    preview_token: str = Field(min_length=64, max_length=64)
    preview_expires_at: datetime


class WithdrawInput(legal_profiles.Input):
    expected_revision: int = Field(ge=1)
    request_key: UUID


def content(row):
    # Never merge private records, profile settings, source metadata or arbitrary JSON.
    return {"title": row.title, "summary": row.summary, "body": row.body,
            "author_label": row.author_label,
            "sources": [{"title": item["title"], "url": item["url"]} for item in row.sources_json]}


def public_payload(row, *, detail=True):
    result = {"id": row.id, "product": row.product, "revision": row.revision,
              "slug": row.slug or row.id, "living_research": row.living_research,
              "title": row.title, "summary": row.summary, "author_label": row.author_label,
              "first_published_at": iso(row.first_published_at), "updated_at": iso(row.updated_at)}
    if detail:
        result.update(content(row))
    return result


def owner_payload(row):
    return {**public_payload(row), "status": row.status} if row else None


def current(session, parent):
    return session.scalar(select(ProductPublication).where(ProductPublication.dossier_id == parent.id))


def check_revision(row, expected):
    if expected != (row.revision if row else 0):
        fail("The public version changed. Reload it and preview your changes again.", 409)


def preview_value(product, identifier, draft, expires_at):
    return {"purpose": "public-dossier-preview-v1", "product": product, "dossier": identifier,
            "draft": draft.model_dump(mode="json"), "expires_at": expires_at.isoformat()}


def replay(session, row, data, action, actor_id):
    fingerprint = hashlib.sha256(canonical({"action": action, "draft": data.model_dump(mode="json",
        exclude={"request_key", "preview_token", "preview_expires_at"})}).encode()).hexdigest()
    previous = session.scalar(select(PublicationRevision).where(PublicationRevision.publication_id == row.id,
        PublicationRevision.request_key == str(data.request_key))) if row else None
    if previous and (previous.fingerprint != fingerprint or previous.actor_user_id != actor_id):
        fail("This request was already used for a different publication change.", 409)
    return previous, fingerprint


def record(session, row, data, action, actor_id, fingerprint):
    session.add(PublicationRevision(organization_id=row.organization_id, publication_id=row.id,
        revision=row.revision, request_key=str(data.request_key), fingerprint=fingerprint, action=action,
        content_json={"content": content(row), "public_consent": action == "publish",
                      "living_research": row.living_research}, actor_user_id=actor_id))
    session.commit()
    return {"publication": owner_payload(row)}


def publication_routes(router, service, actor):
    @router.get("/public-dossiers")
    def catalogue(product: Product, q: str = Query(default="", max_length=300),
                  offset: int = Query(default=0, ge=0, le=100000)):
        words = list(dict.fromkeys(q.lower().split()))
        if len(words) > 12:
            fail("Use at most 12 search words.")
        # The only cross-organization read is this explicitly published projection.
        with service.db.session(include_all_organizations=True) as session:
            query = select(ProductPublication).where(ProductPublication.product == product,
                ProductPublication.status == "published")
            title_scores = []
            for word in words:
                title = func.lower(ProductPublication.title).contains(word, autoescape=True)
                query = query.where(or_(title, func.lower(ProductPublication.summary).contains(word, autoescape=True),
                    func.lower(ProductPublication.body).contains(word, autoescape=True)))
                title_scores.append(case((title, 1), else_=0))
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            if title_scores:
                query = query.order_by(sum(title_scores).desc())
            items = session.scalars(query.order_by(ProductPublication.updated_at.desc(), ProductPublication.id)
                .offset(offset).limit(20))
            return {"items": [public_payload(row, detail=False) for row in items], "total": total,
                    "offset": offset, "page_size": 20, "query": q.strip()}

    @router.get("/public-dossiers/{publication_id}")
    def reader(product: Product, publication_id: str):
        with service.db.session(include_all_organizations=True) as session:
            row = session.scalar(select(ProductPublication).where(or_(ProductPublication.id == publication_id, ProductPublication.slug == publication_id),
                ProductPublication.product == product, ProductPublication.status == "published"))
            if not row:
                fail("This public dossier is not available.", 404)
            return public_payload(row)

    @router.get("/dossiers/{identifier}/publication")
    def owner(product: Product, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            parent, _ = dossier(session, product, identifier, identity.user_id)
            row = current(session, parent)
            revisions = session.scalars(select(PublicationRevision).where(PublicationRevision.publication_id == row.id)
                .order_by(PublicationRevision.revision.desc()).limit(20)) if row else []
            return {"publication": owner_payload(row), "history": [{"revision": revision.revision,
                "action": revision.action, "created_at": iso(revision.created_at)} for revision in revisions]}

    @router.post("/dossiers/{identifier}/publication/preview")
    def preview(product: Product, identifier: str, data: PublicationDraft, request: Request):
        identity = actor(request)
        now = utcnow()
        with service.db.session() as session:
            user = principal(session, identity, now, write=True)
            parent, _ = dossier(session, product, identifier, identity.user_id)
            check_revision(current(session, parent), data.expected_revision)
            expires = now + LIFETIME
            return {**data.model_dump(mode="json"), "preview_expires_at": expires.isoformat(),
                "preview_token": signature(user, identity, preview_value(product, identifier, data, expires))}

    @router.post("/dossiers/{identifier}/publication")
    def publish(product: Product, identifier: str, data: PublishInput, request: Request):
        identity = actor(request)
        now = utcnow()
        with service.write_guard, service.db.session() as session:
            user = principal(session, identity, now, write=True)
            parent, _ = dossier(session, product, identifier, identity.user_id)
            row = current(session, parent)
            previous, fingerprint = replay(session, row, data, "publish", identity.user_id)
            if previous:
                return {"publication": owner_payload(row), "replayed_revision": previous.revision}
            check_revision(row, data.expected_revision)
            expires = data.preview_expires_at
            if (not data.confirm_public or expires.tzinfo is None or expires <= now or expires > now + LIFETIME):
                fail("Preview the current text and confirm that it may be published for everyone.", 409)
            draft = PublicationDraft(expected_revision=data.expected_revision, content=data.content, living_research=data.living_research)
            expected = signature(user, identity, preview_value(product, identifier, draft, expires))
            if not hmac.compare_digest(expected, data.preview_token):
                fail("Your preview no longer matches this content or session. Preview it again.", 409)
            if not row:
                row = ProductPublication(id=str(uuid4()), organization_id=parent.organization_id, dossier_id=parent.id,
                    product=product, revision=0, first_published_at=now)
                session.add(row)
            for key, value in data.content.model_dump().items():
                setattr(row, "sources_json" if key == "sources" else key, value)
            if not row.slug:
                title = re.sub(r"[\W_]+", "-", unicodedata.normalize("NFKC", row.title).casefold()).strip("-")[:110] or "dossier"
                row.slug = title + "-" + row.id
            from .product_public_research import invalidate

            if row.revision:
                invalidate(session, row.id)
            row.living_research = data.living_research
            row.status, row.updated_at, row.revision = "published", now, row.revision + 1
            session.flush()
            return record(session, row, data, "publish", identity.user_id, fingerprint)

    @router.post("/dossiers/{identifier}/publication/withdraw")
    def withdraw(product: Product, identifier: str, data: WithdrawInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            principal(session, identity, utcnow(), write=True)
            parent, _ = dossier(session, product, identifier, identity.user_id)
            row = current(session, parent)
            if not row:
                fail("No public version exists for this dossier.", 404)
            previous, fingerprint = replay(session, row, data, "withdraw", identity.user_id)
            if previous:
                return {"publication": owner_payload(row), "replayed_revision": previous.revision}
            check_revision(row, data.expected_revision)
            if row.status != "published":
                fail("This version has already been withdrawn.", 409)
            row.status, row.updated_at, row.revision = "withdrawn", utcnow(), row.revision + 1
            from .product_public_research import invalidate

            invalidate(session, row.id)
            return record(session, row, data, "withdraw", identity.user_id, fingerprint)
