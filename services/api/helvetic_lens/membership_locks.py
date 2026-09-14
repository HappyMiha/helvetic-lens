"""Shared account/role locks for membership changes and account erasure."""

from sqlalchemy import or_, select, update

from .config import DomainError
from .models import Organization, OrganizationMembership, User


def lock_organization(session, identifier):
    if session.bind.dialect.name == "sqlite":
        session.execute(update(Organization).where(Organization.id == identifier).values(name=Organization.name)
            .execution_options(synchronize_session=False))
    return session.scalar(select(Organization).where(Organization.id == identifier).with_for_update()
        .execution_options(populate_existing=True))


def lock_platform_users(session, user_id):
    if session.bind.dialect.name == "sqlite":
        session.execute(update(User).where(User.id == user_id).values(active=User.active)
            .execution_options(synchronize_session=False))
    return list(session.scalars(select(User).where(or_(User.id == user_id, User.platform_admin.is_(True)))
        .order_by(User.id).with_for_update().execution_options(populate_existing=True)))


def require_current_admin(session, identity):
    organization = lock_organization(session, identity.organization_id)
    user = session.scalar(select(User).where(User.id == identity.user_id).with_for_update()
        .execution_options(populate_existing=True))
    membership = session.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == identity.organization_id,
        OrganizationMembership.user_id == identity.user_id).with_for_update()
        .execution_options(populate_existing=True))
    if not organization or not user or not user.active or not membership or membership.role != "organization_admin":
        raise DomainError("An active workspace administrator must perform this action.", 403, "admin_required")
    return membership
