"""Dossier roles and fixed team/workspace monitoring audiences in the native workspace.

Request context only selects the action. Every authorization decision reads the
current database membership under the shared organization lock for mutations.
Workers pass an explicit action and never rely on HTTP context.
"""
import re
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import and_, exists, or_, select

from .config import DomainError
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .models import OrganizationMembership, User
from .product_models import DossierMember, ProductDossier

_request = ContextVar("dossier_request", default=None)
RANK = {"VIEWER": 0, "CONTRIBUTOR": 1, "EDITOR": 2, "OWNER": 3}
LEVEL = {"read": 0, "contribute": 1, "edit": 2, "owner": 3, "activate": 3, "monitor": 2, "configure": 2}
PRODUCT_PATH = re.compile(r"/api/products/(pharma|loyer)/dossiers/([a-zA-Z0-9-]+)(?:/(.*))?")
PROFILE_PATH = re.compile(r"/api/monitoring-profiles/([a-zA-Z0-9-]+)(?:/(.*))?")
TOPIC_PATH = re.compile(r"/api/monitoring-topics/([a-zA-Z0-9-]+)(?:/(.*))?")


def fail(message="Your dossier role does not allow this action.", status=403):
    raise DomainError(message, status, "dossier_access_required")


@contextmanager
def request_context(path, method, identity):
    token = _request.set((path, method, identity))
    try:
        yield
    finally:
        _request.reset(token)


def request_grant(path=None, method=None):
    context = _request.get()
    if path is None:
        if not context:
            return None
        path, method, _ = context
    match = PRODUCT_PATH.fullmatch(path)
    if not match:
        return None
    product, identifier, suffix = match.groups()
    suffix = suffix or ""
    if method != "GET":
        post_routes = r"(?:follow(?:/read)?|evidence-search|web-research|monitoring-research|entries|files|discovery-references|discussion(?:/[^/]+/(?:replies|accept|research))?|investigations(?:/[^/]+/control)?|evidence-changes/[^/]+/review|sources/[^/]+/(?:reviews|monitor)|source-advice|improve|improvements/apply|searches|review|actions|publication(?:/(?:preview|withdraw))?|team/(?:enable|invitations(?:/[^/]+/revoke)?|members/[^/]+/remove))"
        put_routes = r"(?:work|domain-context|actions/[^/]+|team/members/[^/]+)"
        if not ((method == "POST" and re.fullmatch(post_routes, suffix)) or (method == "PUT" and re.fullmatch(put_routes, suffix))):
            return None
    if method == "GET" or suffix in {"evidence-search", "follow", "follow/read"}:
        action = "read"
    elif suffix.startswith(("team", "publication")):
        action = "owner"
    elif suffix in {"entries", "files", "discovery-references", "discussion"} or re.fullmatch(r"discussion/[^/]+/replies", suffix):
        action = "contribute"
    elif re.fullmatch(r"sources/[^/]+/monitor", suffix) or suffix in {"improvements/apply", "monitoring-research"}:
        action = "monitor"
    elif suffix in {"source-advice", "improve"}:
        action = "configure"
    elif re.fullmatch(r"investigations/[^/]+/control", suffix):
        # The endpoint additionally requires EDITOR, or CONTRIBUTOR for its own
        # retained contribution. Other people's investigations are not writable.
        action = "contribute"
    else:
        action = "edit"
    return product, identifier, action


def current_user_id():
    context = _request.get()
    return context[2].user_id if context and context[2] else None


def viewer_route(path, method):
    grant = request_grant(path, method)
    if grant:
        return grant[2] != "monitor"
    profile = PROFILE_PATH.fullmatch(path)
    if profile and (method == "PUT" or profile[2] in {"suggest", "preview"}):
        return True  # record() refuses native profiles without a dossier grant.
    return bool(re.fullmatch(r"/api/products/(pharma|loyer)/dossier-invitations/[^/]+/accept", path))


def action_for(row, user_id):
    context = _request.get()
    if not context or not context[2] or context[2].user_id != user_id:
        return "read"
    path, method, _ = context
    grant = request_grant(path, method)
    if grant and grant[:2] == (row.product, row.id):
        return grant[2]
    match = PROFILE_PATH.fullmatch(path)
    if match and match[1] == row.profile_id and method != "GET":
        return "activate" if match[2] == "activate" else "monitor" if match[2] == "status" else "configure"
    return "read"


def organization_member(session, user_id, organization_id):
    return session.scalar(select(OrganizationMembership).join(User, User.id == OrganizationMembership.user_id)
        .where(OrganizationMembership.user_id == user_id, OrganizationMembership.organization_id == organization_id,
               User.active.is_(True)).execution_options(populate_existing=True))


def role(session, row, profile, user_id):
    from .product_guest_access import guest_member

    explicit = session.get(DossierMember, (row.id, user_id), populate_existing=True)
    if row.team_managed and explicit and explicit.is_guest:
        return explicit.role if guest_member(session, row.id, user_id) else None
    member = organization_member(session, user_id, row.organization_id)
    if not member:
        return None
    if row.team_managed:
        explicit = session.get(DossierMember, (row.id, user_id), populate_existing=True)
        if explicit:
            return explicit.role
        if profile.status == "draft" or row.monitoring_audience == "team":
            return None
    elif profile.status == "draft" and profile.created_by_user_id != user_id:
        return None
    if profile.created_by_user_id == user_id and not row.team_managed:
        return "OWNER" if member.role == "organization_admin" else "VIEWER"
    return "EDITOR" if member.role == "organization_admin" else "VIEWER"


def require(session, row, profile, user_id, action=None):
    action = action or action_for(row, user_id)
    if not profile:
        fail("Dossier not found.", 404)
    if action != "read":
        lock_organization(session, row.organization_id)
        context = _request.get()
        if context and context[2] and context[2].user_id == user_id:
            from .db import utcnow
            from .product_provenance import principal

            principal(session, context[2], utcnow(), lock=True, dossier_id=row.id)
        session.refresh(row)
        session.refresh(profile)
    effective = role(session, row, profile, user_id)
    if effective is None:
        fail("Dossier not found.", 404)
    from .product_guest_access import guest_member

    if action in {"owner", "activate", "monitor", "configure"} and guest_member(session, row.id, user_id):
        fail("Guest access does not include workspace monitoring or ownership.")
    minimum = LEVEL[action]
    if not row.team_managed and action in {"owner", "activate"}:
        minimum = LEVEL["edit"]  # Preserve legacy explicit publication rights.
    if RANK[effective] < minimum:
        fail()
    if action in {"activate", "monitor"}:
        member = organization_member(session, user_id, row.organization_id)
        if not member or member.role != "organization_admin":
            fail("Shared monitoring changes also require a workspace administrator.")
    return effective


def profile_access(session, profile, user_id):
    row = session.scalar(select(ProductDossier).where(ProductDossier.profile_id == profile.id))
    if row:
        require(session, row, profile, user_id)
        return True
    context = _request.get()
    if context and context[1] != "GET" and PROFILE_PATH.fullmatch(context[0]):
        membership = organization_member(session, user_id, profile.organization_id)
        if not membership or membership.role != "organization_admin":
            fail("A workspace administrator must edit this native monitoring profile.")
    return False


def visible_profile(user_id):
    # This predicate serves the native profile list, product list, workbench,
    # workspace search and their counts. SQL applies visibility before paging.
    dossier = ProductDossier.__table__
    member = DossierMember.__table__
    managed = exists(select(1).where(dossier.c.profile_id == LegalMonitoringProfile.id,
        dossier.c.organization_id == LegalMonitoringProfile.organization_id, dossier.c.team_managed.is_(True)).correlate(LegalMonitoringProfile))
    private = exists(select(1).where(dossier.c.profile_id == LegalMonitoringProfile.id,
        dossier.c.organization_id == LegalMonitoringProfile.organization_id,
        dossier.c.monitoring_audience == "team").correlate(LegalMonitoringProfile))
    invited = exists(select(1).select_from(dossier.join(member,
        and_(member.c.dossier_id == dossier.c.id, member.c.organization_id == dossier.c.organization_id)))
        .where(dossier.c.profile_id == LegalMonitoringProfile.id,
               dossier.c.organization_id == LegalMonitoringProfile.organization_id,
               dossier.c.team_managed.is_(True), member.c.user_id == user_id).correlate(LegalMonitoringProfile))
    return or_(and_(LegalMonitoringProfile.status != "draft", ~private), invited,
               and_(LegalMonitoringProfile.status == "draft", ~managed, LegalMonitoringProfile.created_by_user_id == user_id))


def summary(session, row, profile, user_id):
    effective = role(session, row, profile, user_id)
    rank = RANK.get(effective, -1)
    member = organization_member(session, user_id, row.organization_id)
    from .product_guest_access import guest_member

    guest = bool(guest_member(session, row.id, user_id))
    admin = bool(not guest and member and member.role == "organization_admin")
    return {"managed": row.team_managed, "revision": row.access_revision, "is_guest": guest,
        "can_configure": rank >= 2 and not guest,
        "role": effective, "audience": "invited_team" if row.team_managed and profile.status == "draft"
            else "author" if profile.status == "draft" else row.monitoring_audience,
        "can_contribute": rank >= 1, "can_edit": rank >= 2,
        "can_manage": rank == 3 and row.team_managed,
        "can_enable": not row.team_managed and profile.created_by_user_id == user_id and admin,
        "can_publish": rank == 3 if row.team_managed else admin,
        "can_monitor": rank >= 2 and admin,
        "can_watch_pages": rank >= 2 and admin and row.monitoring_audience != "team",
        "can_activate": admin and (rank == 3 if row.team_managed else rank >= 2)}


def current_principal_grant(session, identity):
    grant = request_grant()
    if not grant or grant[2] == "read":
        return False
    row = session.get(ProductDossier, grant[1], populate_existing=True)
    if not row or row.product != grant[0]:
        fail("Dossier not found.", 404)
    profile = session.get(LegalMonitoringProfile, row.profile_id, populate_existing=True)
    require(session, row, profile, identity.user_id, grant[2])
    return True


def require_topic(session, topic_id, user_id):
    # Activated dossiers retain their chosen read audience. Explicit dossier roles
    # also govern native topic mutation endpoints, alongside native admin rights.
    for row, profile in session.execute(select(ProductDossier, LegalMonitoringProfile).join(LegalMonitoringProfile)
            .where(ProductDossier.team_managed.is_(True), LegalMonitoringProfile.status != "draft")):
        if topic_id in profile.topic_ids_json:
            require(session, row, profile, user_id, "monitor")


def owner_blockers(session, user_id, organization_id=None):
    query = select(DossierMember).where(DossierMember.user_id == user_id, DossierMember.role == "OWNER")
    if organization_id:
        query = query.where(DossierMember.organization_id == organization_id)
    result = []
    for member in session.scalars(query):
        other = session.scalar(select(DossierMember.user_id).join(User, User.id == DossierMember.user_id)
            .where(DossierMember.dossier_id == member.dossier_id, DossierMember.role == "OWNER",
                   DossierMember.user_id != user_id, User.active.is_(True)))
        if not other:
            result.append(member)
    return result
