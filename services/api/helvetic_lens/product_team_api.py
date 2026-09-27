"""Owner-managed teams and invitations to existing native workspace accounts."""
from datetime import UTC, timedelta
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field
from sqlalchemy import func, select

from . import legal_profiles
from . import product_access as access
from .db import utcnow
from .membership_locks import lock_organization
from .models import OrganizationMembership, User
from .product_api import Product, dossier, fail, iso
from .product_models import DossierInvitation, DossierMember, ProductDossier
from .product_operations import audit
from .product_provenance import principal


class Revision(legal_profiles.Input):
    expected_revision: int = Field(ge=1)


class Invite(Revision):
    request_key: UUID
    user_id: UUID
    role: Literal["EDITOR", "CONTRIBUTOR", "VIEWER"]


class ChangeRole(Revision):
    role: Literal["OWNER", "EDITOR", "CONTRIBUTOR", "VIEWER"]


def revision(row, expected):
    if row.access_revision != expected:
        fail("The team changed. Refresh before continuing.", 409, "dossier_team_conflict")


def initialize(session, row, user_id):
    row.team_managed = True
    session.flush()
    session.add(DossierMember(dossier_id=row.id, organization_id=row.organization_id, user_id=user_id, role="OWNER"))


def team(session, row, profile, user_id):
    permissions = access.summary(session, row, profile, user_id)
    members = list(session.execute(select(DossierMember, User).join(User, User.id == DossierMember.user_id)
        .where(DossierMember.dossier_id == row.id).order_by(DossierMember.created_at, DossierMember.user_id)))
    result = {**permissions, "members": [{"user_id": member.user_id, "name": user.name,
        "role": member.role, "active": user.active, "is_you": member.user_id == user_id} for member, user in members],
        "colleagues": [], "invitations": []}
    if permissions["can_manage"]:
        result["colleagues"] = [{"user_id": user.id, "name": user.name} for user in session.scalars(
            select(User).join(OrganizationMembership, OrganizationMembership.user_id == User.id)
            .where(OrganizationMembership.organization_id == row.organization_id, User.active.is_(True),
                   User.id.not_in([member.user_id for member, _ in members])).order_by(User.name, User.id).limit(200))]
        result["invitations"] = [invitation(session, item) for item in session.scalars(select(DossierInvitation)
            .where(DossierInvitation.dossier_id == row.id, DossierInvitation.accepted_at.is_(None),
                   DossierInvitation.revoked_at.is_(None), DossierInvitation.expires_at > utcnow())
            .order_by(DossierInvitation.created_at, DossierInvitation.id))]
    return result


def invitation(session, row):
    recipient = session.get(User, row.recipient_user_id)
    return {"id": row.id, "role": row.role, "recipient_name": recipient.name if recipient else "Former member",
        "recipient_user_id": row.recipient_user_id, "expires_at": iso(row.expires_at),
        "accepted_at": iso(row.accepted_at) if row.accepted_at else None,
        "revoked_at": iso(row.revoked_at) if row.revoked_at else None}


def changed(session, row, actor_id, kind, detail):
    row.access_revision += 1
    audit(session, row, actor_id, "team", kind, "Dossier access updated.", detail)


def routes(router, service, actor):
    root = "/dossiers/{identifier}/team"

    @router.get(root)
    def read(product: Product, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            row, profile = dossier(session, product, identifier, identity.user_id)
            return team(session, row, profile, identity.user_id)

    @router.post(root + "/enable")
    def enable(product: Product, identifier: str, data: Revision, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow())
            row, profile = dossier(session, product, identifier, identity.user_id)
            if not row.team_managed:
                revision(row, data.expected_revision)
                if not access.summary(session, row, profile, identity.user_id)["can_enable"]:
                    fail("The original creator must enable dossier team management.", 403)
                initialize(session, row, identity.user_id)
                changed(session, row, identity.user_id, "Team management enabled", {"owner_user_id": identity.user_id})
                session.commit()
            return team(session, row, profile, identity.user_id)

    @router.post(root + "/invitations", status_code=201)
    def invite(product: Product, identifier: str, data: Invite, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow())
            row, profile = dossier(session, product, identifier, identity.user_id)
            if not row.team_managed:
                fail("Enable team management first.", 409)
            previous = session.scalar(select(DossierInvitation).where(DossierInvitation.dossier_id == row.id,
                DossierInvitation.request_key == str(data.request_key)))
            if previous:
                if (previous.recipient_user_id, previous.role, previous.invited_by_user_id) != (str(data.user_id), data.role, identity.user_id):
                    fail("This invitation request key was already used.", 409)
                return {"invitation": invitation(session, previous), "team": team(session, row, profile, identity.user_id)}
            revision(row, data.expected_revision)
            if not access.organization_member(session, str(data.user_id), row.organization_id):
                fail("Select an active colleague in this workspace.", 404)
            if session.get(DossierMember, (row.id, str(data.user_id))):
                fail("This colleague already has a dossier role. Change it in the team list.", 409)
            pending = select(DossierInvitation).where(DossierInvitation.dossier_id == row.id,
                DossierInvitation.accepted_at.is_(None), DossierInvitation.revoked_at.is_(None), DossierInvitation.expires_at > utcnow())
            if session.scalar(select(func.count()).select_from(pending.subquery())) >= 100:
                fail("This dossier has 100 pending invitations. Revoke one before inviting another colleague.", 409)
            if session.scalar(pending.where(DossierInvitation.recipient_user_id == str(data.user_id))):
                fail("This colleague already has a pending invitation. Revoke it before changing the role.", 409)
            item = DossierInvitation(dossier_id=row.id, organization_id=row.organization_id,
                request_key=str(data.request_key), recipient_user_id=str(data.user_id), role=data.role,
                invited_by_user_id=identity.user_id, expires_at=utcnow() + timedelta(days=7))
            session.add(item)
            changed(session, row, identity.user_id, "Colleague invited", {"user_id": str(data.user_id), "role": data.role})
            session.commit()
            return {"invitation": invitation(session, item), "team": team(session, row, profile, identity.user_id)}

    @router.post(root + "/invitations/{invitation_id}/revoke")
    def revoke(product: Product, identifier: str, invitation_id: str, data: Revision, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow())
            row, profile = dossier(session, product, identifier, identity.user_id)
            item = session.get(DossierInvitation, invitation_id)
            if not item or item.dossier_id != row.id:
                fail("Invitation not found.", 404)
            if item.accepted_at:
                fail("The invitation was accepted. Change or remove the colleague's role in the team list.", 409)
            if not item.revoked_at:
                revision(row, data.expected_revision)
                item.revoked_at = utcnow()
                changed(session, row, identity.user_id, "Invitation revoked", {"invitation_id": item.id})
                session.commit()
            return team(session, row, profile, identity.user_id)

    @router.put(root + "/members/{user_id}")
    def change(product: Product, identifier: str, user_id: str, data: ChangeRole, request: Request):
        return member_change(product, identifier, user_id, data, request, data.role)

    @router.post(root + "/members/{user_id}/remove")
    def remove(product: Product, identifier: str, user_id: str, data: Revision, request: Request):
        return member_change(product, identifier, user_id, data, request, None)

    def member_change(product, identifier, user_id, data, request, role):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow())
            row, profile = dossier(session, product, identifier, identity.user_id)
            revision(row, data.expected_revision)
            member = session.get(DossierMember, (row.id, user_id), populate_existing=True)
            if not member:
                fail("Dossier member not found.", 404)
            if role == "OWNER" and not access.organization_member(session, user_id, row.organization_id):
                fail("Ownership needs an active workspace colleague.", 409)
            if member.role == "OWNER" and role != "OWNER" and any(
                    item.dossier_id == row.id for item in access.owner_blockers(session, user_id, row.organization_id)):
                fail("Assign another active owner before removing or changing the last owner.", 409)
            old_role = member.role
            if role:
                member.role = role
            else:
                session.delete(member)
            # Outstanding invitations issued by a demoted owner become revoked.
            if old_role == "OWNER" and role != "OWNER":
                for item in session.scalars(select(DossierInvitation).where(DossierInvitation.dossier_id == row.id,
                        DossierInvitation.invited_by_user_id == user_id, DossierInvitation.accepted_at.is_(None),
                        DossierInvitation.revoked_at.is_(None))):
                    item.revoked_at = utcnow()
            changed(session, row, identity.user_id, "Dossier role changed", {"user_id": user_id, "previous_role": old_role, "role": role})
            session.commit()
            if access.role(session, row, profile, identity.user_id) is None:
                return {"removed_self": True}
            return team(session, row, profile, identity.user_id)

    @router.get("/dossier-invitations")
    def inbox(product: Product, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            query = select(DossierInvitation, ProductDossier, legal_profiles.LegalMonitoringProfile).join(
                ProductDossier, ProductDossier.id == DossierInvitation.dossier_id).join(legal_profiles.LegalMonitoringProfile)
            issuer = DossierMember
            issuer_user = User
            query = query.join(issuer, (issuer.dossier_id == ProductDossier.id)
                & (issuer.user_id == DossierInvitation.invited_by_user_id)).join(issuer_user, issuer_user.id == issuer.user_id)
            query = query.where(issuer.role == "OWNER", issuer_user.active.is_(True),
                ProductDossier.product == product, DossierInvitation.recipient_user_id == identity.user_id,
                DossierInvitation.accepted_at.is_(None), DossierInvitation.revoked_at.is_(None), DossierInvitation.expires_at > utcnow())
            result = []
            for item, row, profile in session.execute(query.order_by(DossierInvitation.created_at.desc(), DossierInvitation.id).offset(offset).limit(50)):
                inviter = session.get(User, item.invited_by_user_id) if item.invited_by_user_id else None
                result.append({**invitation(session, item), "dossier_id": row.id, "title": profile.config_json.get("name", "Dossier"),
                    "invited_by": inviter.name if inviter else "Former member", "audience": "invited_team" if profile.status == "draft" else "workspace"})
            return {"items": result, "total": session.scalar(select(func.count()).select_from(query.subquery()))}

    @router.post("/dossier-invitations/{invitation_id}/accept")
    def accept(product: Product, invitation_id: str, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            principal(session, identity, utcnow(), lock=True)
            item = session.get(DossierInvitation, invitation_id, populate_existing=True)
            row = session.get(ProductDossier, item.dossier_id, populate_existing=True) if item else None
            if not item or not row or row.product != product or item.recipient_user_id != identity.user_id:
                fail("Invitation not found for this account and workspace.", 404)
            member = session.get(DossierMember, (row.id, identity.user_id))
            if item.accepted_at:
                if not member or member.role != item.role:
                    fail("The accepted role has since changed. Ask the owner for a new invitation.", 409)
                return {"dossier_id": row.id, "role": member.role}
            owner = session.get(DossierMember, (row.id, item.invited_by_user_id)) if item.invited_by_user_id else None
            if (item.revoked_at or item.expires_at.replace(tzinfo=UTC) <= utcnow() or not owner or owner.role != "OWNER"
                    or not access.organization_member(session, owner.user_id, row.organization_id)):
                fail("This invitation is no longer available. Ask the owner for a new one.", 409)
            if member:
                fail("Your dossier role changed since this invitation. Ask an owner to review it.", 409)
            if session.scalar(select(func.count()).select_from(DossierMember).where(DossierMember.dossier_id == row.id)) >= 100:
                fail("This dossier has reached its 100-member limit.", 409)
            session.add(DossierMember(dossier_id=row.id, organization_id=row.organization_id, user_id=identity.user_id, role=item.role))
            item.accepted_at = utcnow()
            changed(session, row, identity.user_id, "Invitation accepted", {"user_id": identity.user_id, "role": item.role})
            session.commit()
            return {"dossier_id": row.id, "role": item.role}
