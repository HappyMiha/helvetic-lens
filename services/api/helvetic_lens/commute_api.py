"""Private commute configuration API under normal session/CSRF middleware."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import commute_delivery, commute_email_preferences, commute_today
from . import commute_events as events
from . import commute_repository as repository
from .auth import Identity
from .commute_catalog import catalog_page
from .commute_contracts import CommuteConfiguration
from .commute_sources import SOURCES, clock, read_feed
from .config import DomainError
from .monitoring_subjects import _actor


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationBody(Input):
    configuration: CommuteConfiguration


class CreateBody(ConfigurationBody):
    request_key: UUID


class VersionBody(Input):
    expected_version: int = Field(strict=True, ge=1)


class EditBody(ConfigurationBody, VersionBody):
    pass


class PreviewBody(ConfigurationBody):
    service_day: date
    static_version: str | None = Field(default=None, min_length=1, max_length=256)


class CommandBody(VersionBody):
    action: Literal["start", "pause", "resume", "archive", "pause_today", "unpause_today"]


class EventCommandBody(VersionBody):
    sequence: int = Field(strict=True, ge=1)
    muted: bool | None = Field(default=None, strict=True)


class EmailBody(VersionBody):
    configuration: commute_email_preferences.EmailConfiguration
    consent: bool = Field(strict=True)


def commute_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not settings.commute_watch_enabled:
            raise DomainError("Commute Watch is unavailable.", 404, "commute_disabled")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/commute-watch", tags=["commute-watch"], dependencies=[Depends(identity)])

    @router.get("/capabilities")
    def capabilities():
        reasons = []
        with service.db.session() as session:
            for source in SOURCES:
                try:
                    read_feed(session, source, now=clock(), require_fresh=True)
                except DomainError as error:
                    reasons.append(error.code)
        return {"drafts_available": True, "start_available": not reasons, "live_results_checked": False,
                "start_requires_journey_check": True, "blocking_reasons": list(dict.fromkeys(reasons)),
                "catalog_coverage": "imported_verified_legs_only"}

    @router.get("/catalog")
    def catalog(service_day: date, query: str = Query(default="", max_length=100),
                limit: int = Query(default=20, ge=1, le=100), after_id: UUID | None = None,
                actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return catalog_page(session, actor.user_id, service_day=service_day, query=query,
                                limit=limit, after_id=str(after_id) if after_id else None)

    @router.get("/today")
    def today(cursor: UUID | None = None, limit: int = Query(default=20, ge=1, le=50),
              actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return commute_today.today(session, settings, actor.user_id, now=clock(),
                                       before_id=str(cursor) if cursor else None, limit=limit)

    @router.get("/events/{event_id}")
    def event_detail(event_id: UUID, sequence: int | None = Query(default=None, ge=1),
                     monitor_id: UUID | None = None,
                     actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return commute_today.detail(session, actor.user_id, str(event_id), now=clock(), sequence=sequence,
                                        monitor_id=str(monitor_id) if monitor_id else None)

    @router.post("/preview")
    def preview(body: PreviewBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.preview(session, actor.user_id, body.configuration.model_dump(mode="json"),
                                      service_day=body.service_day, static_version=body.static_version, settings=settings, now=clock())

    @router.get("/monitors")
    def monitors(limit: int = Query(default=20, ge=1, le=100), after_id: UUID | None = None,
                 actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.list_monitors(session, actor.user_id, limit=limit, after_id=str(after_id) if after_id else None)

    @router.post("/monitors", status_code=201)
    def create(body: CreateBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.create_monitor(session, actor.user_id, body.configuration.model_dump(mode="json"), str(body.request_key))
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}")
    def monitor(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.get_monitor(session, actor.user_id, str(monitor_id))

    @router.patch("/monitors/{monitor_id}")
    def edit(monitor_id: UUID, body: EditBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.edit_monitor(session, actor.user_id, str(monitor_id), body.expected_version,
                                              body.configuration.model_dump(mode="json"))
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/commands")
    def command(monitor_id: UUID, body: CommandBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.command(session, actor.user_id, str(monitor_id), body.expected_version, body.action, settings=settings, now=clock())
            session.commit()
            return result

    @router.delete("/monitors/{monitor_id}", status_code=204)
    def remove(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            repository.remove_monitor(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.get("/monitors/{monitor_id}/revisions")
    def history(monitor_id: UUID, after_revision: int = Query(default=0, ge=0),
                limit: int = Query(default=20, ge=1, le=100), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.revisions(session, actor.user_id, str(monitor_id), after_revision=after_revision, limit=limit)

    @router.get("/monitors/{monitor_id}/events")
    def event_list(monitor_id: UUID, limit: int = Query(default=20, ge=1, le=100), after_id: UUID | None = None,
                   actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.events_page(session, actor.user_id, str(monitor_id), now=clock(), limit=limit,
                                      after_id=str(after_id) if after_id else None)

    @router.get("/events/{event_id}/history")
    def event_history(event_id: UUID, limit: int = Query(default=20, ge=1, le=100),
                      after_sequence: int = Query(default=0, ge=0), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.history_page(session, actor.user_id, str(event_id), now=clock(), limit=limit, after_sequence=after_sequence)

    @router.post("/events/{event_id}/review")
    def event_review(event_id: UUID, body: EventCommandBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = events.review_event(session, actor.user_id, str(event_id), body.expected_version, body.sequence,
                                          now=clock(), muted=body.muted)
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/email")
    def email_settings(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return {**commute_email_preferences.view(session, actor.user_id, str(monitor_id)),
                    "delivery_service_available": settings.auth_email_mode == "smtp" and settings.commute_source_enabled}

    @router.put("/monitors/{monitor_id}/email")
    def configure_email(monitor_id: UUID, body: EmailBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = commute_email_preferences.configure(session, actor.user_id, str(monitor_id),
                expected_version=body.expected_version, configuration=body.configuration.model_dump(mode="json"),
                consent=body.consent, now=clock())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/email-preview")
    def email_preview(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return commute_delivery.preview(session, settings, actor.user_id, str(monitor_id), now=clock())

    return router
