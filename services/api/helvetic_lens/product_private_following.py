"""Personal research subscriptions do not grant dossier or monitoring rights."""
import hashlib
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Query, Request
from pydantic import StrictBool
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


class PrivateFollowInput(FollowInput):
    email_mode: Literal["off", "immediate", "daily", "weekly"] | None = None
    email_confirmed: StrictBool = False
    retry_email: StrictBool = False


def email_state(saved):
    value = saved.email_settings if saved else {}
    return {key: value.get(key) for key in ("state", "last_sent_at", "next_delivery_at")} | {"mode": value.get("mode", "off")}


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
    query = select(PrivateDossierFollow).where(PrivateDossierFollow.dossier_id == row.id,
        PrivateDossierFollow.owner_user_id == identity.user_id).execution_options(populate_existing=True)
    saved = session.scalar(query.with_for_update() if write else query)
    return row, saved


def state(session, row, saved):
    profile = session.get(LegalMonitoringProfile, row.profile_id)
    research = summary(session, row.id, saved)
    head = hashlib.sha256(canonical([row.id, marker(research)]).encode()).hexdigest()
    return {"dossier_id": row.id, "title": profile.config_json.get("name") or "Untitled dossier",
        "following": bool(saved and saved.following), "available": True,
        "delivery_mode": saved.delivery_mode if saved else "immediate",
        "email": email_state(saved),
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
    def change(product: Product, dossier_id: UUID, data: PrivateFollowInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            row, saved = selected(session, identity, product, dossier_id, write=True)
            current = state(session, row, saved)
            if not data.retry_email and current["following"] == data.following and (data.delivery_mode is None or data.delivery_mode == current["delivery_mode"]) and (data.email_mode is None or data.email_mode == current["email"]["mode"]):
                return current
            if current["revision"] != data.expected_revision:
                fail("Your following settings changed. Refresh before trying again.", 409)
            if data.retry_email or (data.email_mode and data.email_mode != "off"):
                user = session.get(User, identity.user_id)
                if not data.email_confirmed or not user or not user.active or not user.email_verified_at:
                    fail("Verify your email and explicitly enable dossier email updates.", 422)
            if not saved:
                saved = PrivateDossierFollow(organization_id=row.organization_id, dossier_id=row.id,
                    owner_user_id=identity.user_id, following=data.following, seen_marker=current["marker"], research_seen_at=utcnow())
                session.add(saved)
            else:
                saved.following, saved.revision, saved.updated_at = data.following, saved.revision + 1, utcnow()
                if data.following and not current["following"]:
                    saved.seen_marker, saved.research_seen_at = current["marker"], utcnow()
            if data.delivery_mode is not None:
                saved.delivery_mode = data.delivery_mode
            if data.email_mode is not None and data.email_mode != current["email"]["mode"]:
                from .product_dossier_delivery import next_delivery
                now = utcnow()
                saved.email_settings = {"mode": data.email_mode, "version": str(uuid4()), "state": "enabled" if data.email_mode != "off" else "off",
                    "after": now.isoformat(), "next_delivery_at": next_delivery(data.email_mode, now).isoformat()}
            if data.retry_email:
                if saved.email_settings.get("mode", "off") == "off":
                    fail("Enable dossier email before retrying delivery.", 422)
                saved.email_settings = {**saved.email_settings, "version": str(uuid4()), "pending": None,
                    "attempted": None, "state": "enabled", "next_delivery_at": utcnow().isoformat()}
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
