"""Personal research subscriptions do not grant dossier or monitoring rights."""
import hashlib
from uuid import UUID

from fastapi import Query, Request
from sqlalchemy import and_, exists, func, or_, select

from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .models import OrganizationMembership, User
from .product_access import visible_profile
from .product_api import Product, fail
from .product_following import FollowInput, ReadInput
from .product_investigations import access
from .product_models import DossierMember, PrivateDossierFollow, ProductDossier
from .product_provenance import canonical, principal
from .product_research_updates import marker, page, summary


def visible(identity):
    """Selected native workspace plus verified, narrowly invited guest dossiers."""
    native = exists(select(OrganizationMembership.user_id).where(
        OrganizationMembership.user_id == identity.user_id,
        OrganizationMembership.organization_id == ProductDossier.organization_id))
    guest = exists(select(DossierMember.user_id).join(User, User.id == DossierMember.user_id).where(
        DossierMember.dossier_id == ProductDossier.id, DossierMember.organization_id == ProductDossier.organization_id,
        DossierMember.user_id == identity.user_id, DossierMember.is_guest.is_(True),
        User.active.is_(True), User.email_verified_at.is_not(None)))
    guest_grant = exists(select(DossierMember.user_id).where(DossierMember.dossier_id == ProductDossier.id,
        DossierMember.user_id == identity.user_id, DossierMember.is_guest.is_(True)))
    return and_(visible_profile(identity.user_id), or_(
        and_(ProductDossier.organization_id == identity.organization_id, native,
            or_(ProductDossier.team_managed.is_(False), ~guest_grant)),
        and_(ProductDossier.team_managed.is_(True), guest)))


def selected(session, identity, product, identifier, *, write=False):
    row = access(session, identity, product, str(identifier), write=write, action="read")
    saved = session.scalar(select(PrivateDossierFollow).where(PrivateDossierFollow.dossier_id == row.id,
        PrivateDossierFollow.owner_user_id == identity.user_id).execution_options(populate_existing=True))
    return row, saved


def state(session, row, saved):
    profile = session.get(LegalMonitoringProfile, row.profile_id)
    research = summary(session, row.id, saved)
    head = hashlib.sha256(canonical([row.id, marker(research)]).encode()).hexdigest()
    return {"dossier_id": row.id, "title": profile.config_json.get("name") or "Untitled dossier",
        "following": bool(saved and saved.following), "available": True,
        "revision": saved.revision if saved else 0, "marker": head,
        "unread": research["unseen"] > 0, "research": research}


def routes(router, service, actor):
    root = "/dossiers/{dossier_id}/follow"

    @router.get("/followed-private-dossiers")
    def listing(product: Product, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            principal(session, identity, utcnow())
            query = select(ProductDossier, PrivateDossierFollow).join(LegalMonitoringProfile,
                LegalMonitoringProfile.id == ProductDossier.profile_id).join(PrivateDossierFollow,
                    PrivateDossierFollow.dossier_id == ProductDossier.id).where(
                        ProductDossier.product == product, visible(identity),
                        PrivateDossierFollow.owner_user_id == identity.user_id, PrivateDossierFollow.following.is_(True))
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            records = session.execute(query.order_by(PrivateDossierFollow.updated_at.desc(), PrivateDossierFollow.id)
                .offset(offset).limit(20)).all()
            return {"items": [state(session, row, saved) for row, saved in records],
                "total": total, "offset": offset, "page_size": 20}

    @router.get(root)
    def read(product: Product, dossier_id: UUID, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            row, saved = selected(session, identity, product, dossier_id)
            return state(session, row, saved)

    @router.get(root + "/updates")
    def updates(product: Product, dossier_id: UUID, request: Request,
                offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            row, saved = selected(session, identity, product, dossier_id)
            return page(session, row.id, saved, offset=offset)

    @router.post(root)
    def change(product: Product, dossier_id: UUID, data: FollowInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            row, saved = selected(session, identity, product, dossier_id, write=True)
            current = state(session, row, saved)
            if current["following"] == data.following:
                return current
            if current["revision"] != data.expected_revision:
                fail("Your following settings changed. Refresh before trying again.", 409)
            if not saved:
                saved = PrivateDossierFollow(organization_id=row.organization_id, dossier_id=row.id,
                    owner_user_id=identity.user_id, seen_marker=current["marker"], research_seen_at=utcnow())
                session.add(saved)
            else:
                saved.following, saved.revision, saved.updated_at = data.following, saved.revision + 1, utcnow()
                if data.following:
                    saved.seen_marker, saved.research_seen_at = current["marker"], utcnow()
            session.commit()
            return state(session, row, saved)

    @router.post(root + "/read")
    def acknowledge(product: Product, dossier_id: UUID, data: ReadInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            row, saved = selected(session, identity, product, dossier_id, write=True)
            current = state(session, row, saved)
            if not saved or not saved.following or data.marker != current["marker"]:
                fail("The research changed. Refresh before marking updates as seen.", 409)
            if saved.seen_marker == data.marker:
                return current
            if saved.revision != data.expected_revision:
                fail("Your following settings changed. Refresh before trying again.", 409)
            saved.seen_marker, saved.research_seen_at = data.marker, utcnow()
            saved.revision += 1
            session.commit()
            return state(session, row, saved)
