"""Personal shared directory and readers confined to one authorized dossier."""
from fastapi import Query, Request
from sqlalchemy import func, select

from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .models import Organization, OrganizationMembership, User
from .product_api import Product, dossier
from .product_guest_access import guest_request
from .product_models import DossierAction, DossierMember, ProductDossier
from .product_provenance import principal
from .topic_matching import list_matches


def assignees(session, dossier_id):
    query = select(User).join(OrganizationMembership, OrganizationMembership.user_id == User.id).where(
        OrganizationMembership.organization_id == session.info["organization_id"],
        OrganizationMembership.role == "organization_admin", User.active.is_(True))
    if guest_request(session):
        allowed = select(DossierMember.user_id).where(DossierMember.dossier_id == dossier_id)
        assigned = select(DossierAction.assignee_user_id).where(DossierAction.dossier_id == dossier_id)
        owner = select(ProductDossier.owner_user_id).where(ProductDossier.id == dossier_id)
        query = query.where(User.id.in_(allowed.union(assigned, owner)))
    return query.order_by(User.name, User.id)


def routes(router, service, actor):
    @router.get("/shared-dossiers")
    def shared(product: Product, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            user = principal(session, identity, utcnow())
            if not user.email_verified_at:
                return {"items": [], "total": 0}
            query = select(ProductDossier, LegalMonitoringProfile, Organization.name).join(
                LegalMonitoringProfile, LegalMonitoringProfile.id == ProductDossier.profile_id).join(
                DossierMember, DossierMember.dossier_id == ProductDossier.id).join(
                Organization, Organization.id == ProductDossier.organization_id).where(
                DossierMember.user_id == identity.user_id, DossierMember.is_guest.is_(True),
                ProductDossier.product == product, ProductDossier.team_managed.is_(True))
            return {"items": [{"id": row.id, "title": profile.config_json.get("name", "Dossier"),
                "organization_name": organization, "status": profile.status,
                "audience": "invited_team" if profile.status == "draft" else row.monitoring_audience}
                for row, profile, organization in session.execute(query.order_by(ProductDossier.created_at.desc(),
                    ProductDossier.id).offset(offset).limit(50))],
                "total": session.scalar(select(func.count()).select_from(query.subquery()))}

    @router.get("/dossiers/{identifier}/matches")
    def matches(product: Product, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            _, profile = dossier(session, product, identifier, identity.user_id)
            return [match for topic_id in profile.topic_ids_json for match in list_matches(session, topic_id, limit=100)]

    @router.get("/dossiers/{identifier}/assignees")
    def people(product: Product, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            principal(session, identity, utcnow())
            row, _ = dossier(session, product, identifier, identity.user_id)
            return [{"role": "organization_admin", "user": {"id": user.id, "name": user.name}}
                    for user in session.scalars(assignees(session, row.id).limit(200))]
