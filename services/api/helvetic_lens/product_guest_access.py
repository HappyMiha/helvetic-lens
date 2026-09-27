"""Narrow guest scope selection; never creates or switches native memberships."""
import re

from sqlalchemy import select

from .models import OrganizationMembership, User
from .product_models import DossierInvitation, DossierMember, ProductDossier

ACCEPT_PATH = re.compile(r"/api/products/(pharma|loyer)/dossier-invitations/([a-zA-Z0-9-]+)/accept")


def guest_member(session, dossier_id, user_id):
    return session.scalar(select(DossierMember).join(User, User.id == DossierMember.user_id)
        .where(DossierMember.dossier_id == dossier_id, DossierMember.user_id == user_id,
               DossierMember.is_guest.is_(True), User.active.is_(True), User.email_verified_at.is_not(None))
        .execution_options(populate_existing=True))


def target(session, identity, path=None, method=None, dossier_id=None):
    from .product_access import PRODUCT_PATH

    user = session.get(User, identity.user_id, populate_existing=True)
    if not user or not user.active or not user.email_verified_at:
        return None
    match = PRODUCT_PATH.fullmatch(path or "")
    identifier = dossier_id or (match[2] if match else None)
    if identifier:
        row = session.get(ProductDossier, identifier, populate_existing=True)
        if (row and row.team_managed and (not match or row.product == match[1])
                and guest_member(session, row.id, identity.user_id)):
            return row.organization_id
    accept = ACCEPT_PATH.fullmatch(path or "") if method == "POST" else None
    if accept:
        item = session.get(DossierInvitation, accept[2], populate_existing=True)
        row = session.get(ProductDossier, item.dossier_id, populate_existing=True) if item else None
        if (item and item.is_guest and item.recipient_user_id == identity.user_id
                and row and row.team_managed and row.product == accept[1]):
            return row.organization_id
    return None


def request_organization(db, identity, path, method):
    from .product_access import PRODUCT_PATH

    if not identity or not (PRODUCT_PATH.fullmatch(path) or (method == "POST" and ACCEPT_PATH.fullmatch(path))):
        return None
    with db.session(include_all_organizations=True) as session:
        return target(session, identity, path, method)


def principal_scope(session, identity, dossier_id=None):
    from .product_access import _request

    context = _request.get()
    path, method = context[:2] if context and context[2] and context[2].user_id == identity.user_id else (None, None)
    organization = target(session, identity, path, method, dossier_id)
    if organization != session.info.get("organization_id"):
        return False
    # The original native login workspace remains required, independently of the
    # guest grant. Never treat the dossier's organization as the login authority.
    return bool(session.scalar(select(OrganizationMembership.user_id).where(
        OrganizationMembership.organization_id == identity.organization_id,
        OrganizationMembership.user_id == identity.user_id).execution_options(include_all_organizations=True)))


def guest_request(session):
    from .product_access import current_user_id, request_grant

    grant = request_grant()
    if grant and current_user_id() and guest_member(session, grant[1], current_user_id()):
        return grant[1]
    return None
