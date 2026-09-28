"""Personal following of current public projections, with explicit read markers."""
import hashlib
import re
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field
from sqlalchemy import func, select

from .db import utcnow
from .legal_profiles import Input
from .membership_locks import lock_organization
from .models import User, UserSession
from .product_api import Product, fail, iso
from .product_models import ProductPublication, PublicContribution, PublicDossierFollow
from .product_provenance import canonical, principal
from .product_publications import public_payload
from .product_research_updates import EMPTY
from .product_research_updates import marker as research_marker
from .product_research_updates import page as research_page
from .product_research_updates import summary as research_summary

FOLLOW_WRITE = re.compile(r"^/api/products/(pharma|loyer)/public-dossiers/[0-9a-f-]{36}/follow(?:/read)?$")


class FollowInput(Input):
    expected_revision: int = Field(ge=0, strict=True)
    following: bool = Field(strict=True)


class ReadInput(Input):
    expected_revision: int = Field(ge=1, strict=True)
    marker: str = Field(pattern=r"^[0-9a-f]{64}$")


def visible_activity(session, identifiers):
    return {key: (count, iso(latest)) for key, count, latest in session.execute(
        select(PublicContribution.publication_id, func.count(), func.max(PublicContribution.updated_at))
        .where(PublicContribution.publication_id.in_(identifiers), PublicContribution.status == "visible")
        .group_by(PublicContribution.publication_id))} if identifiers else {}


def follow_state(session, row, saved, activity):
    available = row.status == "published"
    research = research_summary(session, row.dossier_id, saved, row) if available else dict(EMPTY)
    head = [row.revision, activity.get(row.id, (0, None))]
    if research["total"]:
        head.append(research_marker(research))
    marker = hashlib.sha256(canonical(head).encode()).hexdigest() if available else None
    return {"publication_id": row.id, "publication": public_payload(row, detail=False) if available else None,
        "available": available, "following": bool(saved and saved.following),
        "revision": saved.revision if saved else 0, "marker": marker, "research": research,
        "unread": bool(available and saved and saved.following and saved.seen_marker != marker)}


def owned(session, identity, identifier):
    return session.scalar(select(PublicDossierFollow).where(PublicDossierFollow.owner_user_id == identity.user_id,
        PublicDossierFollow.publication_id == str(identifier)).execution_options(populate_existing=True))


def selected(session, identity, product, identifier, *, write=False):
    query = select(ProductPublication).where(ProductPublication.id == str(identifier), ProductPublication.product == product)
    row = session.scalar(query)
    if not row:
        fail("This public dossier is not available.", 404)
    if write:
        for organization in sorted({identity.organization_id, row.organization_id}):
            lock_organization(session, organization)
        session.scalar(select(User).where(User.id == identity.user_id).with_for_update())
        session.scalar(select(UserSession).where(UserSession.id == identity.session_id).with_for_update())
    principal(session, identity, utcnow())
    row = session.scalar(query.with_for_update().execution_options(populate_existing=True) if write else query)
    saved = owned(session, identity, identifier)
    if not row or (row.status != "published" and not saved):
        fail("This public dossier is not available.", 404)
    return row, saved


def following_routes(router, service, actor):
    @router.get("/followed-dossiers")
    def listing(product: Product, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            principal(session, identity, utcnow())
            query = select(ProductPublication, PublicDossierFollow).join(PublicDossierFollow,
                PublicDossierFollow.publication_id == ProductPublication.id).where(
                    PublicDossierFollow.owner_user_id == identity.user_id, PublicDossierFollow.following.is_(True),
                    ProductPublication.product == product)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            rows = session.execute(query.order_by(PublicDossierFollow.updated_at.desc(), PublicDossierFollow.id)
                .offset(offset).limit(20)).all()
            activity = visible_activity(session, [row.id for row, _ in rows if row.status == "published"])
            return {"items": [follow_state(session, row, saved, activity) for row, saved in rows],
                "total": total, "offset": offset, "page_size": 20}

    @router.get("/public-dossiers/{publication_id}/follow")
    def read(product: Product, publication_id: UUID, request: Request):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            row, saved = selected(session, identity, product, publication_id)
            return follow_state(session, row, saved, visible_activity(session, [row.id]))

    @router.post("/public-dossiers/{publication_id}/follow")
    def change(product: Product, publication_id: UUID, data: FollowInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, saved = selected(session, identity, product, publication_id, write=True)
            activity = visible_activity(session, [row.id])
            state = follow_state(session, row, saved, activity)
            # A retry of an already achieved state is a no-op; an old opposite
            # command cannot undo a newer choice or acknowledge newer changes.
            if state["following"] == data.following:
                return state
            if data.expected_revision != state["revision"]:
                fail("Your following settings changed. Refresh before trying again.", 409)
            if data.following and not state["available"]:
                fail("This public dossier is no longer published.", 409)
            if not saved:
                saved = PublicDossierFollow(owner_user_id=identity.user_id, publication_id=row.id,
                    seen_marker=state["marker"], research_seen_at=utcnow(), following=True, revision=1)
                session.add(saved)
            else:
                saved.following, saved.revision, saved.updated_at = data.following, saved.revision + 1, utcnow()
                if data.following:
                    saved.seen_marker, saved.research_seen_at = state["marker"], utcnow()
            session.commit()
            return follow_state(session, row, saved, activity)

    @router.post("/public-dossiers/{publication_id}/follow/read")
    def acknowledge(product: Product, publication_id: UUID, data: ReadInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, saved = selected(session, identity, product, publication_id, write=True)
            activity = visible_activity(session, [row.id])
            state = follow_state(session, row, saved, activity)
            if not saved or not saved.following or not state["available"] or state["marker"] != data.marker:
                fail("The public dossier changed. Refresh before marking the update as seen.", 409)
            if saved.seen_marker == data.marker:
                return state
            if saved.revision != data.expected_revision:
                fail("Your following settings changed. Refresh before trying again.", 409)
            saved.seen_marker, saved.revision = data.marker, saved.revision + 1
            saved.research_seen_at = utcnow()
            session.commit()
            return follow_state(session, row, saved, activity)

    @router.get("/public-dossiers/{publication_id}/follow/updates")
    def updates(product: Product, publication_id: UUID, request: Request,
                offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            row, saved = selected(session, identity, product, publication_id)
            if row.status != "published":
                fail("This public dossier is no longer published.", 404)
            return research_page(session, row.dossier_id, saved, row, offset=offset)
