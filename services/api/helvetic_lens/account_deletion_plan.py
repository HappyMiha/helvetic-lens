"""Read-only account erasure inventory; destructive execution rechecks this plan.

The caller supplies an authenticated user, never a body-provided subject. This
service intentionally spans that user's workspaces, including formerly owned
private monitors, but never selects another person's private configuration.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import or_, select

from .config import DomainError
from .db import Base
from .models import (
    AccountToken,
    AssistantConversation,
    DigestDelivery,
    DigestPreference,
    InterestBriefFeedback,
    OnboardingMilestone,
    Organization,
    OrganizationMembership,
    PersonalSourceReview,
    User,
    UserOnboarding,
    UserSession,
)
from .monitoring_centre import MODELS
from .related_models import RelatedStory

BUSINESS = {"tenders", "ip", "auctions"}
MAX_INVENTORY = 10000


def fail(code="account_deletion_changed", status=409):
    raise DomainError("Review account deletion again before continuing.", status, code)


@dataclass(frozen=True)
class DeletionPlan:
    public: dict
    # Internal exact scope. Not an authorization token and never accepted back
    # from the browser; execution rebuilds it under the required database locks.
    monitors: tuple
    erase_organizations: tuple


def bounded_ids(session, model, predicate):
    rows = list(session.scalars(select(model.id).where(predicate).order_by(model.id).limit(MAX_INVENTORY + 1)))
    if len(rows) > MAX_INVENTORY:
        fail("account_deletion_inventory_too_large", 422)
    return rows


def has_colleague_private_data(session, organization_id, user_id):
    for table in Base.metadata.sorted_tables:
        if "organization_id" not in table.c:
            continue
        conditions = []
        for key in table.foreign_key_constraints:
            if key.referred_table.name == "users" and (
                    key.ondelete == "CASCADE" or table.name in {"digest_preferences", "digest_deliveries"}):
                conditions.extend(column != user_id for column in key.columns)
        if "principal_key" in table.c:
            conditions.append(table.c.principal_key != f"user:{user_id}")
        if conditions and session.scalar(select(1).select_from(table).where(table.c.organization_id == organization_id,
                or_(*conditions)).limit(1)):
            return True
    return False


def inventory(session, user_id, organization_id):
    if not session.info.get("include_all_organizations"):
        # A tenant-filtered partial inventory is not an erasure plan.
        raise ValueError("Account deletion requires an explicitly cross-workspace session.")
    user = session.get(User, user_id, populate_existing=True)
    memberships = list(session.scalars(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user_id).order_by(OrganizationMembership.organization_id)
        .execution_options(populate_existing=True)))
    if not user or not user.active or organization_id not in {row.organization_id for row in memberships}:
        fail("authentication_required", 401)

    workspaces, blockers, erase, rosters = [], [], [], []
    member_orgs = {row.organization_id for row in memberships}
    for membership in memberships:
        organization = session.get(Organization, membership.organization_id)
        roster = list(session.execute(select(OrganizationMembership.user_id,
            OrganizationMembership.role, User.active).join(User, User.id == OrganizationMembership.user_id)
            .where(OrganizationMembership.organization_id == organization.id)
            .order_by(OrganizationMembership.user_id)))
        others = [person for person in roster if person.user_id != user_id]
        successor = any(person.role == "organization_admin" and person.active for person in others)
        # Inactive colleagues still own data. Their presence never grants a
        # departing account permission to erase the whole workspace.
        if not others and membership.role == "organization_admin" and has_colleague_private_data(
                session, organization.id, user_id):
            disposition = "retained_private_data"
            blockers.append({"kind": "workspace_private_data", "organization_id": organization.id})
        elif not others and membership.role == "organization_admin":
            disposition = "erase_private_workspace"
            erase.append(organization.id)
        elif not successor:
            disposition = "administrator_handover_required"
            blockers.append({"kind": "workspace_administrator", "organization_id": organization.id})
        else:
            disposition = "leave_workspace"
        workspaces.append({"id": organization.id, "name": organization.name,
            "role": membership.role, "other_members": len(others), "disposition": disposition})
        rosters.append([organization.id, [list(person) for person in roster]])

    if user.platform_admin and not session.scalar(select(User.id).where(
            User.id != user_id, User.active.is_(True), User.platform_admin.is_(True)).limit(1)):
        blockers.append({"kind": "platform_administrator"})

    monitors, categories = [], []
    for domain, model in sorted(MODELS.items()):
        # Column reads bypass ORM tenant criteria but remain explicitly owner
        # constrained. No payload, address, email policy or source secret is read.
        table = model.__table__
        version = table.c.current_revision if domain == "pollen" else table.c.version
        columns = [table.c.id, table.c.organization_id, version, table.c.status]
        if domain in BUSINESS:
            columns.append(table.c.visibility)
        rows = list(session.execute(select(*columns).where(table.c.owner_user_id == user_id)
            .order_by(table.c.id).limit(MAX_INVENTORY + 1)))
        if len(monitors) + len(rows) > MAX_INVENTORY:
            fail("account_deletion_inventory_too_large", 422)
        blocked = 0
        for row in rows:
            scope = row.visibility if domain in BUSINESS else "private"
            monitors.append((domain, row.id, row.organization_id, row[2], row.status, scope))
            if scope == "workspace" and row.organization_id not in erase:
                blocked += 1
                blockers.append({"kind": "monitor_owner", "domain": domain, "monitor_id": row.id,
                    "organization_id": row.organization_id if row.organization_id in member_orgs else None,
                    "membership_required": row.organization_id not in member_orgs})
        categories.append({"domain": domain, "owned": len(rows), "handover_required": blocked})

    principal = f"user:{user_id}"
    own = {}
    for label, model in (("sessions", UserSession), ("account_tokens", AccountToken),
                         ("digest_preferences", DigestPreference), ("digest_deliveries", DigestDelivery)):
        own[label] = bounded_ids(session, model, model.user_id == user_id)
    for label, model in (("conversations", AssistantConversation), ("onboarding", UserOnboarding),
                         ("milestones", OnboardingMilestone), ("source_reviews", PersonalSourceReview)):
        own[label] = bounded_ids(session, model, or_(model.user_id == user_id, model.principal_key == principal))
    own["feedback"] = bounded_ids(session, InterestBriefFeedback,
        or_(InterestBriefFeedback.actor_user_id == user_id, InterestBriefFeedback.principal_key == principal))
    own["related_stories"] = bounded_ids(session, RelatedStory, RelatedStory.owner_user_id == user_id)

    # The binding covers identities, roles, versions and explicit workspace
    # disposition, not only counts. Background sample arrival need not invalidate
    # a user's consent to erase a whole private monitor and its dependent rows.
    binding = {"version": 1, "user": user_id, "organization": organization_id,
        "platform_admin": user.platform_admin, "rosters": rosters,
        "monitors": monitors, "personal": own, "erase": erase, "blockers": blockers}
    fingerprint = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return DeletionPlan(public={"version": 1, "fingerprint": fingerprint,
        "categories": categories, "workspaces": workspaces, "blockers": blockers,
        "personal_counts": {label: len(ids) for label, ids in own.items()},
        "can_delete": not blockers, "workspace_erasure_confirmation_required": bool(erase),
        "retained": ["official_source_corpus", "other_members_private_data", "shared_workspace_decisions",
            "platform_connector_credentials", "source_retention_records", "backups_until_expiry",
            "already_delivered_external_copies"]}, monitors=tuple(monitors), erase_organizations=tuple(erase))
