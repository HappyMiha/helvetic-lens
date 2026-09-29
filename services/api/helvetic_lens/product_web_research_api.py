"""Revision-pinned consent for one recurring public query per private dossier."""
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, StrictBool, field_validator
from sqlalchemy import select

from . import legal_profiles
from .config import DomainError
from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .product_access import require
from .product_api import Product, fail
from .product_investigation_models import WebResearchPolicy as Policy
from .product_investigations import access
from .product_operations import fingerprint
from .product_web_research import audience_key, fence, history, payload


class PolicyInput(legal_profiles.Input):
    request_key: UUID
    expected_revision: int = Field(ge=0, strict=True)
    enabled: StrictBool
    question: str = Field(max_length=300)
    cadence_hours: int = Field(strict=True)
    standing_public_query_confirmed: StrictBool = False

    @field_validator("question")
    @classmethod
    def question_text(cls, value):
        return value.strip()

    @field_validator("cadence_hours")
    @classmethod
    def cadence(cls, value):
        if value not in {24, 168}:
            raise ValueError("Choose a daily or weekly cadence.")
        return value


def routes(router, service, actor):
    root = "/dossiers/{dossier_id}/web-research"

    @router.get(root)
    def read(product: Product, dossier_id: str, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            try:
                require(session, parent, session.get(LegalMonitoringProfile, parent.profile_id), identity.user_id, "edit")
                can_manage = True
            except DomainError:
                can_manage = False
            policy = session.scalar(select(Policy).where(Policy.dossier_id == parent.id))
            return payload(session, parent, policy, can_manage, service.settings, offset)

    @router.post(root)
    def update(product: Product, dossier_id: str, data: PolicyInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            parent = access(session, identity, product, dossier_id, write=True)
            policy = session.scalar(select(Policy).where(Policy.dossier_id == parent.id))
            key = fingerprint({**data.model_dump(mode="json"), "actor": identity.user_id})
            if policy and policy.last_request_key == str(data.request_key):
                if policy.last_request_fingerprint != key:
                    fail("This request key belongs to different recurring-search settings.", 409)
                return payload(session, parent, policy, True, service.settings)
            if data.expected_revision != (policy.revision if policy else 0):
                fail("Recurring-search settings changed. Reload before saving.", 409)
            if data.enabled and (not data.standing_public_query_confirmed or len(data.question) < 5):
                fail("Enter a public question and explicitly confirm its recurring use by the providers.", 422)
            previously_enabled = policy and (
                (policy.enabled and policy.question == data.question and policy.cadence_hours == data.cadence_hours)
                or any(item.get("action") == "enabled" and item.get("question") == data.question
                    and item.get("cadence_hours") == data.cadence_hours for item in policy.history))
            if data.enabled and not previously_enabled:
                from .product_exploration_api import require_briefing

                require_briefing(session, parent.id)
            if not policy:
                policy = Policy(dossier_id=parent.id, organization_id=parent.organization_id)
                session.add(policy)
                session.flush()
            else:
                fence(session, policy, "Recurring-search settings changed. Unfinished work was cancelled.")
                policy.revision += 1
            policy.enabled, policy.question, policy.cadence_hours = data.enabled, data.question, data.cadence_hours
            policy.authorized_by_user_id = identity.user_id
            policy.audience_fingerprint = audience_key(parent, session.get(LegalMonitoringProfile, parent.profile_id))
            policy.checked_at = None
            policy.next_run_at = policy.next_check_at = utcnow()
            policy.last_request_key, policy.last_request_fingerprint = str(data.request_key), key
            history(policy, "enabled" if data.enabled else "disabled",
                "Recurring public search enabled. The first question is queued when capacity is available." if data.enabled
                else "Recurring public search paused. Completed evidence remains available.")
            session.commit()
            return payload(session, parent, policy, True, service.settings)
