"""Standing monitoring research policy; native session and source authority only."""
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, StrictBool
from sqlalchemy import select

from . import legal_profiles
from .config import DomainError
from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .product_access import require
from .product_api import Product, fail
from .product_investigation_models import MonitoringResearchPolicy as Policy
from .product_investigations import access
from .product_monitoring_research import fence, history, payload, profile_key
from .product_operations import fingerprint


class PolicyInput(legal_profiles.Input):
    request_key: UUID
    expected_revision: int = Field(ge=0, strict=True)
    enabled: StrictBool
    daily_limit: int = Field(ge=1, le=6, strict=True)
    standing_authority_confirmed: StrictBool = False
    include_page_changes: StrictBool = False


def routes(router, service, actor):
    root = "/dossiers/{dossier_id}/monitoring-research"

    @router.get(root)
    def read(product: Product, dossier_id: str, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            profile = session.get(LegalMonitoringProfile, parent.profile_id)
            try:
                require(session, parent, profile, identity.user_id, "monitor")
                can_manage = True
            except DomainError:
                can_manage = False
            policy = session.scalar(select(Policy).where(Policy.dossier_id == parent.id))
            return payload(session, parent, policy, can_manage, offset)

    @router.post(root)
    def update(product: Product, dossier_id: str, data: PolicyInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            parent = access(session, identity, product, dossier_id, write=True, action="monitor")
            profile = session.get(LegalMonitoringProfile, parent.profile_id)
            policy = session.scalar(select(Policy).where(Policy.dossier_id == parent.id))
            key = fingerprint({**data.model_dump(mode="json"), "actor": identity.user_id})
            if policy and policy.last_request_key == str(data.request_key):
                legacy_key = fingerprint({**data.model_dump(mode="json", exclude={"include_page_changes"}), "actor": identity.user_id})
                if policy.last_request_fingerprint != key and not (
                        not data.include_page_changes and not policy.include_page_changes and policy.last_request_fingerprint == legacy_key):
                    fail("This request key belongs to different research settings.", 409)
                return payload(session, parent, policy, True)
            if data.expected_revision != (policy.revision if policy else 0):
                fail("Research settings changed. Reload before saving.", 409)
            if data.enabled and not data.standing_authority_confirmed:
                fail("Confirm ongoing private research using the configured workspace model.", 422)
            if data.enabled and (profile.status != "active" or not profile.topic_ids_json):
                fail("Activate dossier monitoring before enabling ongoing research.", 409)
            if data.enabled and data.include_page_changes and parent.monitoring_audience == "team":
                fail("Workspace page watches are unavailable in members-only dossiers. Use topic-match research here.", 409)
            if not policy:
                policy = Policy(dossier_id=parent.id, organization_id=parent.organization_id)
                session.add(policy)
                session.flush()
            else:
                fence(session, policy, "Automatic research settings changed. Previous pending work was cancelled.")
                policy.revision += 1
            policy.enabled, policy.daily_limit = data.enabled, data.daily_limit
            policy.include_page_changes = data.include_page_changes
            policy.authorized_by_user_id = identity.user_id
            policy.profile_fingerprint = profile_key(parent, profile)
            policy.checked_at = None
            policy.starts_on = policy.next_check_at = utcnow()
            policy.last_request_key, policy.last_request_fingerprint = str(data.request_key), key
            history(policy, "enabled" if data.enabled else "disabled",
                "Automatic research enabled for future saved monitoring signals." if data.enabled
                else "Automatic research disabled. Completed findings remain available.")
            session.commit()
            return payload(session, parent, policy, True)
