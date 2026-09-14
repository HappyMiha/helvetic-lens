"""Explicit business-monitor scope; personal email never inherits workspace access."""

from sqlalchemy import or_, select

from .config import DomainError


def visible_to(model, user_id, *, personal_only=False):
    owner = model.owner_user_id == user_id
    return owner if personal_only else or_(owner, model.visibility == "workspace")


def require_private_owner(monitor, user_id):
    if monitor.owner_user_id != user_id:
        raise DomainError("Personal email settings are unavailable.", 404, "business_email_not_found")


def scope_view(monitor):
    return {"visibility": monitor.visibility, "owner_user_id": monitor.owner_user_id,
            "responsible_user_id": monitor.responsible_user_id}


def collection_actor(session, monitor):
    """A shared monitor never borrows an arbitrary colleague's identity."""
    from .models import OrganizationMembership, User
    actor = monitor.responsible_user_id if monitor.visibility == "workspace" else monitor.owner_user_id
    member = session.execute(select(User.active, OrganizationMembership.role).join(
        OrganizationMembership, OrganizationMembership.user_id == User.id).where(
        User.id == actor, OrganizationMembership.organization_id == monitor.organization_id)).first()
    if not member or not member.active or member.role != "organization_admin":
        raise DomainError("Assign an active workspace administrator before monitoring.", 403, "membership_required")
    return actor
