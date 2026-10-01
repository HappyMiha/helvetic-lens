"""One explicitly authorized question starts existing private research and monitoring."""
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import Field, field_validator
from sqlalchemy import select

from . import domain_packs, legal_profiles
from . import product_exploration as exploration
from . import product_iterative_research as research
from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .membership_locks import lock_organization
from .product_access import organization_member
from .product_api import Product, dossier, fail, iso
from .product_investigation_models import Investigation, WebResearchPolicy
from .product_investigations import enqueue, event, summary
from .product_models import DossierEntry, PrivateDossierFollow, ProductDossier
from .product_operations import fingerprint
from .product_private_following import state as follow_state
from .product_web_research import DISCLOSURE, audience_key, history, readiness

CONTRACT = "question-start/v1"
START_DISCLOSURE = (
    "Start private research and daily monitoring of the submitted public question. "
    "The question and follow-ups derived from public evidence may be sent to search and decision providers; "
    "selected evidence is analysed by the workspace model. Research continues through the materials needed to address the question. "
    "Daily checks begin tomorrow under the recurring research policy. Updates stay in this dossier and "
    "in-app following; monitoring can be paused. Private notes and files are not public search queries."
)


class Start(legal_profiles.Input):
    request_key: UUID
    question: str = Field(min_length=5, max_length=300)
    public_monitoring_confirmed: Literal[True]

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Enter the question you want to research and follow.")
        return value

    @field_validator("public_monitoring_confirmed", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Confirm public research and daily monitoring of this question.")
        return value


class Explore(legal_profiles.Input):
    request_key: UUID
    question: str = Field(min_length=5, max_length=300)
    public_query_confirmed: Literal[True]

    _question = field_validator("question")(Start.clean_question.__func__)

    @field_validator("public_query_confirmed", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Confirm public research of this question.")
        return value


def monitoring_summary(session, parent, settings):
    policy = session.scalar(select(WebResearchPolicy).where(WebResearchPolicy.dossier_id == parent.id))
    if not policy:
        return None
    return {"enabled": policy.enabled, "cadence_hours": policy.cadence_hours,
        "next_run_at": iso(policy.next_run_at) if policy.enabled else None,
        "ready": readiness(settings, session)["configured"]}


def routes(router, service, actor):
    @router.get("/research-allowance")
    def allowance(product: Product, request: Request):
        from .product_research_admission import state

        identity = actor(request)
        with service.db.session() as session:
            return state(session, identity.user_id, product)

    @router.post("/start", status_code=202)
    def start(product: Product, data: Start, request: Request):
        return create(product, data, request, exploratory=False)

    @router.post("/explore", status_code=202)
    def explore(product: Product, data: Explore, request: Request):
        return create(product, data, request, exploratory=True)

    def create(product, data, request, *, exploratory):
        contract = exploration.CONTRACT if exploratory else CONTRACT
        disclosure = exploration.DISCLOSURE if exploratory else START_DISCLOSURE
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            member = organization_member(session, identity.user_id, identity.organization_id)
            if not member or member.role != "organization_admin":
                fail("Your current workspace role cannot create dossiers.", 403)
            key = fingerprint({"contract": contract, "question": data.question, "actor": identity.user_id})
            parent = session.scalar(select(ProductDossier).where(
                ProductDossier.product == product, ProductDossier.creation_key == str(data.request_key)))
            if parent:
                parent, profile = dossier(session, product, parent.id, identity.user_id)
                receipt = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == parent.id,
                    DossierEntry.kind == "question_start", DossierEntry.request_key == str(data.request_key)))
                if not receipt or receipt.data_json.get("fingerprint") != key:
                    fail("This request key belongs to a different dossier start.", 409)
                run = session.get(Investigation, receipt.data_json["investigation_id"])
                # Replay is a read of current state, never a request to resume/re-enable.
                return {"dossier_id": parent.id, "investigation": summary(run) if run else None,
                    "monitoring": monitoring_summary(session, parent, service.settings)}
            pack = domain_packs.for_product(product)
            profile = LegalMonitoringProfile(created_by_user_id=identity.user_id, creation_key=str(uuid4()), step=0,
                config_json=legal_profiles.ProfileConfig(name=data.question[:160], sector=pack.label,
                    goal=data.question, topics=[], source_pack_ids=[], delivery="keep").model_dump(mode="json"))
            session.add(profile)
            session.flush()
            parent = ProductDossier(product=product, profile_id=profile.id, creation_key=str(data.request_key))
            session.add(parent)
            session.flush()
            state = exploration.initial() if exploratory else research.initial(research.Limits())
            limits = research.Limits(**state["limits"])
            run = Investigation(dossier_id=parent.id, organization_id=parent.organization_id,
                request_key=str(data.request_key), question=data.question, created_by_user_id=identity.user_id,
                actor_user_id=identity.user_id, session_id=identity.session_id,
                session_organization_id=identity.organization_id,
                research_state={**state, "decision_order": "jev_first", "initial_limits": limits.model_dump()})
            session.add(run)
            session.flush()
            from .product_research_admission import admit_dossier, policy

            admit_dossier(session, identity.user_id, parent.id)
            run.research_state = {**run.research_state, "admission": policy(parent.id)}
            enqueue(session, run)
            event(session, run, "investigation_queued", question=run.question, disclosure=disclosure,
                origin=contract)
            if not exploratory:
                tomorrow = utcnow() + timedelta(hours=24)
                policy = WebResearchPolicy(dossier_id=parent.id, organization_id=parent.organization_id,
                    enabled=True, revision=1, question=data.question, cadence_hours=24,
                    authorized_by_user_id=identity.user_id, audience_fingerprint=audience_key(parent, profile),
                    next_run_at=tomorrow, next_check_at=tomorrow, history=[])
                session.add(policy)
                history(policy, "enabled", "Initial research queued. Daily public-question checks begin tomorrow; updates stay in this dossier.")
            session.add(PrivateDossierFollow(dossier_id=parent.id, organization_id=parent.organization_id,
                owner_user_id=identity.user_id, following=True,
                seen_marker=follow_state(session, parent, None)["marker"], research_seen_at=utcnow()))
            session.add(DossierEntry(dossier_id=parent.id, request_key=str(data.request_key), kind="question_start",
                actor_user_id=identity.user_id, title="Exploration started" if exploratory else "Research and daily monitoring started",
                body=disclosure,
                data_json={"contract": contract, "fingerprint": key, "investigation_id": run.id,
                    "public_question": data.question, "daily_public_research_confirmed": not exploratory,
                    "disclosure": disclosure, "recurring_disclosure": None if exploratory else DISCLOSURE, "initial_limits": limits.model_dump()}))
            session.flush()
            result = {"dossier_id": parent.id, "investigation": summary(run),
                "monitoring": monitoring_summary(session, parent, service.settings)}
            session.commit()
            return result
