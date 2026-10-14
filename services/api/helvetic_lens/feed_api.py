"""Standalone Core feeds and explicit many-to-many dossier subscriptions."""
import hashlib
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

from . import domain_packs, feed_research, jobs, legal_profiles
from . import feed_operations as ops
from .db import utcnow
from .decision_search import public_url
from .feed_models import Feed, FeedCheck, FeedDossierLink, FeedImport, FeedUpdate
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .models import Job
from .product_access import organization_member, require
from .product_api import Product, dossier, fail, iso
from .product_investigation_models import Investigation
from .product_investigations import summary
from .product_models import DossierEntry, PrivateDossierFollow, ProductDossier
from .product_provenance import principal
from .research_contracts import SOURCES


class FeedFields(legal_profiles.Input):
    name: str = Field(min_length=1, max_length=160)
    query: str = Field(min_length=5, max_length=300)
    sources: list[Annotated[str, Field(min_length=1, max_length=2048)]] = Field(default_factory=list, max_length=50)
    status: Literal["active", "paused"] = "active"

    @field_validator("sources")
    @classmethod
    def source_scope(cls, values):
        for value in values:
            if value in SOURCES and SOURCES[value].kind == "catalogue":
                continue
            if not value.startswith("https://") or public_url(value) != value:
                raise ValueError("Select a source catalogue or provide a public HTTPS source URL.")
        return list(dict.fromkeys(values))


class NewFeed(FeedFields):
    request_key: UUID
    product: Literal["legal", "pharma", "loyer"]


class ChangeFeed(FeedFields):
    request_key: UUID
    expected_revision: int = Field(ge=1, strict=True)


class CheckFeed(legal_profiles.Input):
    request_key: UUID
    expected_revision: int = Field(ge=1, strict=True)


class RetryFeed(CheckFeed):
    investigation_id: UUID
    expected_investigation_revision: int = Field(ge=1, strict=True)


class AttachFeed(legal_profiles.Input):
    question: str | None = Field(default=None, min_length=5, max_length=300)
    feed_id: UUID
    request_key: UUID
    expected_feed_revision: int = Field(ge=1, strict=True)


class DossierFeed(FeedFields):
    proposal_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    question: str | None = Field(default=None, min_length=5, max_length=300)
    request_key: UUID


class NewDossier(CheckFeed):
    product: Literal["legal", "loyer", "pharma"]
    question: str = Field(min_length=5, max_length=300)



def intact_original(path, expected):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() == expected


def product_key(product):
    return "loyer" if product == "legal" else product


def link_payload(session, link, user_id):
    feed = session.get(Feed, link.feed_id)
    pending = session.scalar(select(func.count()).select_from(FeedImport).where(
        FeedImport.link_id == link.id, FeedImport.status == "pending"))
    run = session.scalar(select(Investigation).where(
        Investigation.research_state["feed_origin"]["link_id"].as_string() == link.id)
        .order_by(Investigation.created_at.desc(), Investigation.id.desc()).limit(1))
    member = organization_member(session, user_id, link.organization_id)
    own = bool(member and feed.owner_user_id == user_id)
    can_learn = False
    if own and member.role == "organization_admin" and link.status == "active":
        from .config import DomainError
        try:
            feed_research.authority(session, link)
            can_learn = True
        except DomainError:
            pass
    return {"id": link.id, "feed_id": link.feed_id, "dossier_id": link.dossier_id,
        "can_open_feed": own, "can_learn": can_learn, "can_retry": bool(own and member.role == "organization_admin"
            and link.status == "active" and run and run.status in {"failed", "paused", "cancelled"}),
        "status": link.status, "revision": link.revision, "cursor_sequence": link.cursor_sequence,
        "pending_count": pending, "question": link.public_question, "feed": {"id": feed.id, "name": feed.name,
            "product": "legal" if feed.product == "loyer" else feed.product, "status": feed.status},
        "investigation": summary(run) if run else None}


def create_feed(session, identity, product, data):
    feed = Feed(owner_user_id=identity.user_id, product=product_key(product), name=data.name,
        query=data.query, sources_json=data.sources, status=data.status)
    session.add(feed)
    session.flush()
    from .feed_following import initialize
    initialize(session, feed, identity.user_id)
    return feed


def attach(session, identity, feed, parent, *, public_question=None):
    link = session.scalar(select(FeedDossierLink).where(FeedDossierLink.feed_id == feed.id,
        FeedDossierLink.dossier_id == parent.id))
    if not link:
        previous = feed_research.previous_public(session, parent.id)
        question = public_question or (previous.question if previous else None)
        if not question:
            fail("Provide the dossier question you want researched using public sources.", 422, "feed_question_required")
        link = FeedDossierLink(feed_id=feed.id, dossier_id=parent.id, created_by_user_id=identity.user_id,
            public_question=question)
        session.add(link)
        session.flush()
    elif link.status != "active":
        link.status, link.revision, link.updated_at = "active", link.revision + 1, utcnow()
        link.created_by_user_id = identity.user_id
        link.public_question = public_question or link.public_question
        feed_research.recover_history(session, link)
    feed_research.attach_history(session, link)
    feed_research.start_pending(session, link, public_question=public_question)
    return link


def feed_router(service):
    router = APIRouter(prefix="/api", tags=["feeds"])

    def actor(request):
        identity = getattr(request.state, "identity", None)
        if not identity:
            fail("Sign in to open your feeds.", 401, "authentication_required")
        return identity

    def enter(session, identity, *, write=False):
        if write:
            lock_organization(session, identity.organization_id)
        principal(session, identity, utcnow(), write=write)

    def schedule(session, feed, request_key):
        if feed.status == "active":
            from .feed_worker import enqueue_check
            enqueue_check(session, feed, service.settings, request_key)

    @router.get("/feeds")
    def listing(request: Request, offset: int = Query(0, ge=0), q: str = Query("", max_length=300)):
        identity = actor(request)
        with service.db.session() as session:
            enter(session, identity)
            query = select(Feed).where(Feed.owner_user_id == identity.user_id)
            if q.strip():
                query = query.where(or_(Feed.name.icontains(q.strip(), autoescape=True),
                    Feed.query.icontains(q.strip(), autoescape=True)))
            records = session.scalars(query.order_by(Feed.updated_at.desc(), Feed.id).offset(offset).limit(50))
            return {"items": [ops.payload(session, feed, identity.user_id) for feed in records],
                "total": session.scalar(select(func.count()).select_from(query.subquery())), "offset": offset, "page_size": 50,
                "can_create": organization_member(session, identity.user_id, identity.organization_id).role == "organization_admin",
                "sources": [{"id": key, "label": value.label, "products": [p for p in ("legal", "pharma")
                    if key in domain_packs.for_product(p).discovery_sources]} for key, value in SOURCES.items()
                    if value.kind == "catalogue"]}

    @router.post("/feeds", status_code=201)
    def new(data: NewFeed, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            old, key = ops.receipt(session, identity, data.request_key, "create", data.model_dump(mode="json"))
            if old:
                return ops.payload(session, ops.owned(session, old.result_json["feed_id"], identity.user_id), identity.user_id)
            feed = create_feed(session, identity, data.product, data)
            schedule(session, feed, str(data.request_key))
            ops.remember(session, identity, data.request_key, "create", key, {"feed_id": feed.id})
            session.commit()
            return ops.payload(session, feed, identity.user_id)

    @router.get("/feeds/{feed_id}")
    def read(feed_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            enter(session, identity)
            return ops.payload(session, ops.owned(session, feed_id, identity.user_id), identity.user_id)

    @router.patch("/feeds/{feed_id}")
    def change(feed_id: str, data: ChangeFeed, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            feed = ops.owned(session, feed_id, identity.user_id, write=True)
            action = f"change:{feed_id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if not old:
                ops.revision(feed, data.expected_revision)
                changed = (feed.name, feed.query, feed.sources_json, feed.status) != (data.name, data.query, data.sources, data.status)
                if changed:
                    current_job = session.get(Job, feed.job_id) if feed.job_id else None
                    if current_job and current_job.state not in jobs.TERMINAL_STATES:
                        jobs.cancel(session, current_job.id)
                        check = session.scalar(select(FeedCheck).where(FeedCheck.job_id == current_job.id))
                        if check and check.status in {"queued", "running"}:
                            check.status, check.finished_at = "cancelled", utcnow()
                    feed.name, feed.query, feed.sources_json, feed.status = data.name, data.query, data.sources, data.status
                    feed.revision, feed.updated_at = feed.revision + 1, utcnow()
                    feed.next_check_at, feed.error = utcnow(), None
                    schedule(session, feed, str(data.request_key))
                ops.remember(session, identity, data.request_key, action, key, {"feed_id": feed.id})
                session.commit()
            return ops.payload(session, feed, identity.user_id)

    @router.post("/feeds/{feed_id}/check")
    def check(feed_id: str, data: CheckFeed, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            feed = ops.owned(session, feed_id, identity.user_id, write=True)
            action = f"check:{feed_id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if not old:
                ops.revision(feed, data.expected_revision)
                if feed.status != "active":
                    fail("Resume the feed before checking its sources.", 409, "feed_paused")
                schedule(session, feed, str(data.request_key))
                ops.remember(session, identity, data.request_key, action, key, {"feed_id": feed.id})
                session.commit()
            return ops.payload(session, feed, identity.user_id)

    @router.get("/feeds/{feed_id}/updates")
    def updates(feed_id: str, request: Request, after_sequence: int = Query(0, ge=0),
            before_sequence: int | None = Query(None, ge=1), order: Literal["oldest", "newest"] = "oldest",
            limit: int = Query(50, ge=1, le=100), view: Literal["main", "unrelated", "all"] = "main"):
        identity = actor(request)
        with service.db.session() as session:
            enter(session, identity)
            feed = ops.owned(session, feed_id, identity.user_id)
            from . import feed_assessments
            binding = feed_assessments.current_binding(session, feed)
            query = select(FeedUpdate).where(FeedUpdate.feed_id == feed_id)
            total_retained = session.scalar(select(func.count()).select_from(query.subquery()))
            verdict = feed_assessments.verdict_expression(binding)
            if view == "main":
                query = query.where(or_(verdict.is_(None), verdict != "unrelated"))
            elif view == "unrelated":
                query = query.where(verdict == "unrelated")
            page = query.where(FeedUpdate.sequence > after_sequence)
            if before_sequence is not None:
                page = page.where(FeedUpdate.sequence < before_sequence)
            rows = list(session.scalars(page.order_by(FeedUpdate.sequence.desc() if order == "newest"
                else FeedUpdate.sequence).limit(limit + 1)))
            return {"items": feed_assessments.history_payload(session, feed, rows[:limit], binding),
                "total_retained": total_retained, "view": view,
                "total": session.scalar(select(func.count()).select_from(query.subquery())),
                "next_sequence": rows[limit - 1].sequence if len(rows) > limit else None}

    @router.get("/feeds/{feed_id}/checks")
    def checks(feed_id: str, request: Request, offset: int = Query(0, ge=0)):
        identity = actor(request)
        with service.db.session() as session:
            enter(session, identity)
            ops.owned(session, feed_id, identity.user_id)
            query = select(FeedCheck).where(FeedCheck.feed_id == feed_id)
            rows = session.scalars(query.order_by(FeedCheck.created_at.desc(), FeedCheck.id).offset(offset).limit(20))
            return {"items": [{"id": row.id, "status": row.status, "feed_revision": row.feed_revision,
                "created_at": iso(row.created_at), "finished_at": iso(row.finished_at) if row.finished_at else None,
                "progress": ops.check_progress(row)} for row in rows],
                "total": session.scalar(select(func.count()).select_from(query.subquery())), "offset": offset, "page_size": 20}

    @router.get("/feeds/{feed_id}/updates/{update_id}/original")
    def original(feed_id: str, update_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            enter(session, identity)
            ops.owned(session, feed_id, identity.user_id)
            row = session.get(FeedUpdate, update_id)
            if not row or row.feed_id != feed_id:
                fail("Feed observation not found.", 404, "not_found")
            saved = row.snapshot_json.get("retained_document", {})
            if saved.get("artifact_key"):
                folder = service.environment_settings.storage_path / "artifacts"
                path = folder / saved["artifact_key"]
                if (path.parent != folder or not path.is_file()
                        or saved.get("sha256") != row.content_hash
                        or not intact_original(path, row.content_hash)):
                    fail("The retained original is temporarily unavailable.", 503, "feed_original_unavailable")
                return FileResponse(path, media_type="application/octet-stream", filename=saved.get("title") or "source",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
            return PlainTextResponse(row.source_text, headers={"Cache-Control": "no-store"})

    base = "/products/{product}/dossiers/{dossier_id}/feeds"

    @router.get(base)
    def links(product: Product, dossier_id: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            enter(session, identity)
            parent, profile = dossier(session, product, dossier_id, identity.user_id)
            from .product_access import role
            member = organization_member(session, identity.user_id, parent.organization_id)
            can_manage = bool(member and member.role == "organization_admin"
                and role(session, parent, profile, identity.user_id) in {"OWNER", "EDITOR"})
            rows = session.scalars(select(FeedDossierLink).where(FeedDossierLink.dossier_id == parent.id,
                FeedDossierLink.status == "active").order_by(FeedDossierLink.created_at, FeedDossierLink.id))
            return {"items": [link_payload(session, link, identity.user_id) for link in rows], "can_manage": can_manage}

    @router.post(base)
    def connect(product: Product, dossier_id: str, data: AttachFeed, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            parent, profile = dossier(session, product, dossier_id, identity.user_id)
            require(session, parent, profile, identity.user_id, "edit")
            feed = ops.owned(session, str(data.feed_id), identity.user_id, write=True)
            action = f"attach:{parent.id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if old:
                link = session.get(FeedDossierLink, old.result_json["link_id"])
            else:
                ops.revision(feed, data.expected_feed_revision)
                link = attach(session, identity, feed, parent, public_question=data.question)
                ops.remember(session, identity, data.request_key, action, key, {"link_id": link.id})
                session.commit()
            return link_payload(session, link, identity.user_id)

    @router.get(base + "/proposal")
    def monitoring_proposal(product: Product, dossier_id: str, request: Request):
        from . import feed_intelligence as intelligence

        identity = actor(request)
        with service.db.session() as session:
            enter(session, identity)
            parent, profile = dossier(session, product, dossier_id, identity.user_id)
            require(session, parent, profile, identity.user_id, "edit")
            member = organization_member(session, identity.user_id, parent.organization_id)
            if not member or member.role != "organization_admin":
                fail("An organization administrator must enable a public feed.", 403, "forbidden")
            return intelligence.proposal(session, parent, profile)

    @router.post(base + "/create", status_code=201)
    def new_linked(product: Product, dossier_id: str, data: DossierFeed, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            parent, profile = dossier(session, product, dossier_id, identity.user_id)
            require(session, parent, profile, identity.user_id, "edit")
            action = f"create-linked:{parent.id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if old:
                link = session.get(FeedDossierLink, old.result_json["link_id"])
            else:
                from . import feed_intelligence as intelligence

                proposed = None
                if data.proposal_fingerprint:
                    proposed = intelligence.proposal(session, parent, profile)
                    if proposed["proposal_fingerprint"] != data.proposal_fingerprint:
                        fail("The monitoring proposal changed. Review it again before enabling.", 409, "feed_context_changed")
                feed = create_feed(session, identity, product, data)
                link = attach(session, identity, feed, parent, public_question=data.question)
                if proposed and proposed["basis"] == "public_research":
                    context = intelligence.dossier_context(session, link, investigation_id=proposed["investigation_id"])
                    feed.config_json = {"intelligence": {"contract": intelligence.CONTRACT,
                        "contexts": [intelligence.context_pin(context)]}}
                schedule(session, feed, str(data.request_key))
                ops.remember(session, identity, data.request_key, action, key, {"link_id": link.id})
                session.commit()
            return link_payload(session, link, identity.user_id)

    @router.post(base + "/{link_id}/retry")
    def retry_link(product: Product, dossier_id: str, link_id: str, data: RetryFeed, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            parent, profile = dossier(session, product, dossier_id, identity.user_id)
            require(session, parent, profile, identity.user_id, "edit")
            link = session.get(FeedDossierLink, link_id)
            if not link or link.dossier_id != parent.id:
                fail("Feed link not found.", 404, "not_found")
            ops.owned(session, link.feed_id, identity.user_id, write=True)
            feed_research.authority(session, link)
            action = f"retry-link:{link_id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if not old:
                ops.revision(link, data.expected_revision)
                feed_research.retry_link(session, link, str(data.investigation_id), data.expected_investigation_revision)
                ops.remember(session, identity, data.request_key, action, key, {"link_id": link.id})
                session.commit()
            return link_payload(session, link, identity.user_id)

    @router.delete(base + "/{link_id}")
    def detach(product: Product, dossier_id: str, link_id: str, request: Request, expected_revision: int = Query(ge=1)):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            parent, profile = dossier(session, product, dossier_id, identity.user_id)
            require(session, parent, profile, identity.user_id, "edit")
            link = session.get(FeedDossierLink, link_id)
            if not link or link.dossier_id != parent.id:
                fail("Feed link not found.", 404, "not_found")
            if link.status != "detached":
                ops.revision(link, expected_revision)
                link.status, link.revision, link.updated_at = "detached", link.revision + 1, utcnow()
                feed_research.detach_work(session, link)
                session.commit()
            return link_payload(session, link, identity.user_id)

    @router.post("/feeds/{feed_id}/dossiers", status_code=201)
    def create_dossier(feed_id: str, data: NewDossier, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            enter(session, identity, write=True)
            feed = ops.owned(session, feed_id, identity.user_id, write=True)
            action = f"create-dossier:{feed_id}"
            old, key = ops.receipt(session, identity, data.request_key, action, data.model_dump(mode="json"))
            if old:
                parent, _ = dossier(session, product_key(data.product), old.result_json["dossier_id"], identity.user_id)
                link = session.get(FeedDossierLink, old.result_json["link_id"])
            else:
                ops.revision(feed, data.expected_revision)
                product = product_key(data.product)
                pack = domain_packs.for_product(product)
                profile = LegalMonitoringProfile(created_by_user_id=identity.user_id, creation_key=str(uuid4()),
                    config_json=legal_profiles.ProfileConfig(name=data.question[:160], sector=pack.label,
                        goal=data.question, topics=[], source_pack_ids=[], delivery="keep").model_dump(mode="json"))
                session.add(profile)
                session.flush()
                parent = ProductDossier(product=product, profile_id=profile.id, creation_key=str(data.request_key))
                session.add(parent)
                session.flush()
                from .product_private_following import state as follow_state
                from .product_research_admission import admit_dossier
                admit_dossier(session, identity.user_id, parent.id)
                link = attach(session, identity, feed, parent, public_question=data.question)
                run = feed_research.start_pending(session, link, force=True, public_question=data.question)
                if run is None:
                    run = session.scalar(select(Investigation).where(Investigation.dossier_id == parent.id)
                        .order_by(Investigation.created_at.desc()).limit(1))
                session.add(PrivateDossierFollow(dossier_id=parent.id, owner_user_id=identity.user_id, following=True,
                    seen_marker=follow_state(session, parent, None)["marker"], research_seen_at=utcnow()))
                session.add(DossierEntry(dossier_id=parent.id, request_key=str(data.request_key), kind="feed_origin",
                    actor_user_id=identity.user_id, title="Research started from a feed",
                    body="All retained feed history and future versions are linked. Research follows this dossier's own question.",
                    data_json={"feed_id": feed.id, "link_id": link.id, "investigation_id": run.id}))
                ops.remember(session, identity, data.request_key, action, key, {"dossier_id": parent.id, "link_id": link.id})
                session.commit()
            value = link_payload(session, link, identity.user_id)
            return {"dossier_id": parent.id, "product": "legal" if parent.product == "loyer" else parent.product,
                "link": value, "investigation": value["investigation"]}

    from .feed_following import routes as following_routes
    following_routes(router, service, actor)
    from .feed_intelligence_api import routes as intelligence_routes
    intelligence_routes(router, service, actor)
    return router
