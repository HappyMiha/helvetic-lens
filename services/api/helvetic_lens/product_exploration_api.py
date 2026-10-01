"""An explicit, replay-safe response starts the next bounded research episode."""
from uuid import UUID

from fastapi import Request
from pydantic import Field, model_validator
from sqlalchemy import select

from . import jobs
from . import product_early_clarification as clarification
from . import product_exploration as exploration
from . import product_exploration_followups as followups
from .membership_locks import lock_organization
from .product_api import Product, fail
from .product_investigation_models import Investigation
from .product_investigations import ACTIVE, enqueue, event, payload, record
from .product_operations import fingerprint
from .product_question_start import Explore


class Reply(Explore):
    continue_research: bool = Field(default=False, strict=True)
    expected_revision: int = Field(ge=0, strict=True)
    direction: int | None = Field(default=None, ge=0, le=2, strict=True)
    follow_up_id: UUID | None = None
    orientation_revision: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def single_choice(self):
        if not self.continue_research and self.expected_revision == 0:
            raise ValueError("A legacy reply requires a saved checkpoint.")
        if self.direction is not None and self.follow_up_id is not None:
            raise ValueError("Choose one saved check or one briefing direction.")
        if self.orientation_revision is not None and self.direction is None:
            raise ValueError("An early clarification requires its exact saved direction.")
        return self


def latest(session, dossier_id):
    # SQL JSON access works on both supported databases, and bounds the read.
    return session.scalar(select(Investigation).where(Investigation.dossier_id == dossier_id,
        Investigation.research_state["exploration"]["contract"].as_string() == exploration.CONTRACT)
        .order_by(Investigation.created_at.desc(), Investigation.id.desc()).limit(1))


def require_briefing(session, dossier_id):
    run = latest(session, dossier_id)
    if run and (run.status in ACTIVE or exploration.projection(session, run)["status"] != "ready"):
        fail("Finish a source-backed briefing and choose a public question before enabling monitoring.", 409)


def routes(router, service, actor):
    @router.post("/dossiers/{dossier_id}/investigations/{identifier}/exploration/reply", status_code=202)
    def reply(product: Product, dossier_id: str, identifier: str, data: Reply, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, identity.organization_id)
            previous = record(session, identity, product, dossier_id, identifier, write=True)
            if not exploration.enabled(previous):
                fail("This research does not have an exploratory checkpoint.", 409)
            state = previous.research_state["exploration"]
            command = data.model_dump(mode="json")
            if not data.continue_research:
                command.pop("continue_research")  # Preserve existing reply fingerprints.
            if data.orientation_revision is None:
                command.pop("orientation_revision")  # Preserve existing reply fingerprints.
            if data.follow_up_id is None:
                command.pop("follow_up_id")  # Preserve pre-1.54 retry fingerprints.
            key = fingerprint({**command, "actor": identity.user_id})
            if state.get("reply_key") == str(data.request_key):
                if state.get("reply_fingerprint") != key:
                    fail("This reply key belongs to a different direction.", 409)
                return payload(session, record(session, identity, product, dossier_id, state["continued_by"]))
            if state.get("continued_by") or data.expected_revision != state["revision"]:
                fail("This research checkpoint changed. Refresh to see the next episode.", 409)
            current = exploration.projection(session, previous)
            if not data.continue_research and ((current["status"] == "exploring" and previous.status not in {"paused", "cancelled"}) or previous.status in ACTIVE):
                fail("Pause or finish the preliminary episode before changing direction.", 409)
            if latest(session, dossier_id).id != previous.id:
                fail("A newer research episode exists. Reply to its checkpoint.", 409)
            if data.continue_research and (current["status"] == "evidence_changed"
                    or not exploration.adaptive_current(session, previous)):
                fail("Earlier research changed. Refresh it before continuing with its context.", 409)
            selected = {}
            if data.orientation_revision is not None:
                selected = clarification.select(session, previous, current, data.direction,
                    data.orientation_revision, data.question)
            elif data.direction is not None:
                choices = current["briefing"]["directions"] if current.get("briefing") else []
                if data.direction >= len(choices) or choices[data.direction]["question"] != data.question:
                    fail("The evidence-backed direction changed. Refresh before choosing.", 409)
            if session.scalar(select(Investigation.id).where(Investigation.dossier_id == dossier_id,
                    Investigation.id != previous.id,
                    Investigation.status.in_(ACTIVE)).limit(1)):
                fail("Another investigation is running. Pause or finish it first.", 409)
            if session.scalar(select(Investigation.id).where(Investigation.dossier_id == dossier_id,
                    Investigation.request_key == str(data.request_key)).limit(1)):
                fail("This request key is already used in the dossier.", 409)
            if data.follow_up_id:
                selected = followups.select(session, previous, str(data.follow_up_id), data.question)
            if data.continue_research and not selected:
                selected = {"user_refinement": {"question": data.question,
                    "original_question": previous.question, "reply_fingerprint": key}}
            # Validate before stopping. Rejection or enqueue failure rolls back
            # the entire handoff, including cancellation of the old worker lease.
            if previous.status in ACTIVE:
                if previous.job_id:
                    jobs.cancel(session, previous.job_id)
                previous.status, previous.stop_reason = "paused", "Continued with the user's refined question. Saved evidence is retained."
                event(session, previous, "investigation_pause", status=previous.status)
            run = Investigation(dossier_id=dossier_id, organization_id=identity.organization_id,
                request_key=str(data.request_key), question=data.question,
                created_by_user_id=identity.user_id, actor_user_id=identity.user_id,
                session_id=identity.session_id, session_organization_id=identity.organization_id,
                research_state=exploration.initial(previous={"investigation_id": previous.id,
                    "briefing_revision": state["revision"], **selected}))
            if previous.research_state.get("admission"):
                run.research_state["admission"] = dict(previous.research_state["admission"])
            session.add(run)
            session.flush()
            enqueue(session, run)
            exploration.update(previous, continued_by=run.id, reply_key=str(data.request_key), reply_fingerprint=key)
            event(session, previous, "exploration_direction_chosen", next_investigation_id=run.id,
                question=data.question, direction=data.direction, orientation_revision=data.orientation_revision,
                follow_up_id=str(data.follow_up_id) if data.follow_up_id else None, actor_user_id=identity.user_id)
            event(session, run, "investigation_queued", question=run.question, previous_investigation_id=previous.id,
                disclosure=exploration.DISCLOSURE, origin=exploration.CONTRACT)
            session.commit()
            return payload(session, run)
