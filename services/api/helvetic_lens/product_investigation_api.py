"""Ask / Investigate, durable controls and access-checked observable SSE."""
import asyncio
import json
import time
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field, field_validator
from sqlalchemy import func, select

from . import jobs, legal_profiles
from .config import DomainError
from .membership_locks import lock_organization
from .product_api import Product, fail, iso
from .product_investigation_models import Investigation, InvestigationEvent
from .product_investigations import ACTIVE, access, enqueue, event, payload, record, summary


class Ask(legal_profiles.Input):
    request_key: UUID
    question: str = Field(min_length=2, max_length=300)
    public_query_confirmed: Literal[True]

    @field_validator("question")
    @classmethod
    def question_text(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter a research question.")
        return value

    @field_validator("public_query_confirmed", mode="before")
    @classmethod
    def consent(cls, value):
        if value is not True:
            raise ValueError("The submitted question is used for public-source discovery.")
        return value


class Control(legal_profiles.Input):
    expected_revision: int = Field(ge=1)
    action: Literal["pause", "resume", "cancel", "retry"]


def routes(router, service, actor):
    root = "/dossiers/{dossier_id}/investigations"

    @router.post(root, status_code=202)
    def create(product: Product, dossier_id: str, data: Ask, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            access(session, identity, product, dossier_id, write=True)
            previous = session.scalar(select(Investigation).where(Investigation.dossier_id == dossier_id,
                                                                  Investigation.request_key == str(data.request_key)))
            if previous:
                if not previous.external_discovery or previous.trigger_entry_id or previous.question != data.question or previous.created_by_user_id != identity.user_id:
                    fail("This request key belongs to a different investigation.", 409)
                return payload(session, previous)
            if session.scalar(select(func.count()).select_from(Investigation).where(
                    Investigation.dossier_id == dossier_id, Investigation.status.in_(ACTIVE))):
                fail("An investigation is already running in this dossier. Pause or finish it before starting another.", 409)
            run = Investigation(dossier_id=dossier_id, organization_id=service.organization_id,
                request_key=str(data.request_key), question=data.question, created_by_user_id=identity.user_id, actor_user_id=identity.user_id,
                session_id=identity.session_id, session_organization_id=identity.organization_id)
            session.add(run)
            session.flush()
            enqueue(session, run)
            event(session, run, "investigation_queued", question=run.question,
                disclosure="The question and entity names found in public sources may be sent to external search. "
                    "Private dossier text is never used for external queries. Saved evidence may be analysed by the configured workspace model.")
            session.commit()
            return payload(session, run)

    @router.get(root)
    def listing(product: Product, dossier_id: str, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            access(session, identity, product, dossier_id)
            query = select(Investigation).where(Investigation.dossier_id == dossier_id)
            return {"items": [summary(r) for r in session.scalars(query.order_by(Investigation.created_at.desc(),
                Investigation.id).offset(offset).limit(20))],
                "total": session.scalar(select(func.count()).select_from(query.subquery()))}

    @router.get(root + "/{identifier}")
    def read(product: Product, dossier_id: str, identifier: str, request: Request):
        identity = actor(request)
        with service.db.session() as session:
            return payload(session, record(session, identity, product, dossier_id, identifier))

    @router.post(root + "/{identifier}/control")
    def control(product: Product, dossier_id: str, identifier: str, data: Control, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            lock_organization(session, service.organization_id)
            run = record(session, identity, product, dossier_id, identifier, write=True)
            if data.expected_revision != run.revision:
                fail("The investigation changed. Refresh before applying this action.", 409)
            if data.action in {"resume", "retry"}:
                from .product_monitoring_research import retry_authority
                from .product_web_research import retry_authority as web_retry_authority

                retry_authority(session, run)
                web_retry_authority(session, run)
                if data.action == "retry":
                    from .product_contributions import retry

                    retry(session, run)
                elif run.status != "paused":
                    fail("Only a paused investigation can resume. Start a new question for completed work.", 409)
                if not run.trigger_entry_id and session.scalar(select(Investigation.id).where(Investigation.dossier_id == dossier_id,
                        Investigation.id != run.id, Investigation.status.in_(ACTIVE)).limit(1)):
                    fail("Pause the active investigation before resuming this one.", 409)
                run.generation += 1
                run.actor_user_id, run.session_id = identity.user_id, identity.session_id
                run.session_organization_id = identity.organization_id
                run.status, run.stop_reason = "queued", ""
                enqueue(session, run)
            else:
                if run.status not in ACTIVE | {"paused"}:
                    fail("This investigation has already finished.", 409)
                if run.job_id:
                    jobs.cancel(session, run.job_id)
                run.status = "paused" if data.action == "pause" else "cancelled"
                run.stop_reason = "Paused by a dossier editor." if data.action == "pause" else "Cancelled by a dossier editor. Saved evidence is retained."
            event(session, run, "investigation_" + data.action, status=run.status)
            session.commit()
            return payload(session, run)

    @router.get(root + "/{identifier}/events")
    async def events(product: Product, dossier_id: str, identifier: str, request: Request,
                     after: int = Query(default=0, ge=0), wait: int = Query(default=40, ge=0, le=40)):
        identity = actor(request)
        header = request.headers.get("last-event-id", "")
        if header.isdecimal() and len(header) <= 12:
            after = max(after, int(header))
        with service.db.session() as session:
            record(session, identity, product, dossier_id, identifier)

        async def stream():
            cursor = after
            deadline = time.monotonic() + wait
            while True:
                if await request.is_disconnected():
                    return
                try:
                    # A fresh transaction and current session/membership check on
                    # every batch, including idle heartbeats and reconnects.
                    with service.db.session() as session:
                        run = record(session, identity, product, dossier_id, identifier)
                        values = session.scalars(select(InvestigationEvent).where(
                            InvestigationEvent.investigation_id == identifier, InvestigationEvent.sequence > cursor)
                            .order_by(InvestigationEvent.sequence).limit(250))
                        messages = [{"sequence": e.sequence, "kind": e.kind, "detail": e.detail,
                                     "created_at": iso(e.created_at)} for e in values]
                        running = run.status in ACTIVE
                except DomainError:
                    yield 'event: access_changed\ndata: {}\n\n'
                    return
                for value in messages:
                    cursor = value["sequence"]
                    yield f'id: {cursor}\nevent: activity\ndata: {json.dumps(value, ensure_ascii=False)}\n\n'
                if not running or time.monotonic() >= deadline:
                    yield 'event: checkpoint\ndata: {}\n\n'
                    return
                yield ': heartbeat\n\n'
                await asyncio.sleep(2)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={
            "Cache-Control": "private, no-store", "X-Accel-Buffering": "no"})
