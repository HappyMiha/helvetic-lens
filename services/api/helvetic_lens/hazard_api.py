"""Private C1 configuration API, under existing auth/tenant/CSRF middleware."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import hazard_delivery, hazard_email_preferences, hazard_today
from . import hazard_events as events
from . import hazard_lifecycle as lifecycle
from . import hazard_repository as repository
from .auth import Identity
from .config import DomainError
from .db import utcnow
from .hazard_boundary_store import BoundaryStore
from .hazard_contracts import Hazard, HazardConfiguration
from .hazard_readiness import ready
from .monitoring_subjects import _actor


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationBody(Input):
    configuration: HazardConfiguration


class CreateBody(ConfigurationBody):
    request_key: UUID


class VersionBody(Input):
    expected_version: int = Field(strict=True, ge=1)


class EditBody(ConfigurationBody, VersionBody):
    pass


class ReviewBody(VersionBody):
    expected_revision: int = Field(strict=True, ge=1)
    action: Literal["reviewed", "not_relevant"]


class MuteBody(VersionBody):
    muted: bool = Field(strict=True)


class CommandBody(VersionBody):
    action: Literal["start", "resume", "pause", "archive"]


class EmailBody(VersionBody):
    configuration: hazard_email_preferences.EmailConfiguration
    consent: bool = Field(strict=True)


def hazard_router(service, settings):
    boundaries = BoundaryStore(settings.storage_path)
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not settings.hazard_watch_enabled:
            raise DomainError("Hazard Watch is unavailable.", 404, "hazard_watch_disabled")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/hazard-watch", tags=["hazard-watch"], dependencies=[Depends(identity)])

    @router.get("/capabilities")
    def capabilities():
        return {"drafts_available": True, "commands_available": True, "start_available": False, "live_results_checked": False,
                "blocking_reasons": ["hazard_source_not_configured", "hazard_location_not_verified"]}

    @router.get("/today")
    def today(limit: int = Query(default=20, ge=1, le=20), cursor: UUID | None = None,
              actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return hazard_today.page(session, settings, actor.user_id, store=boundaries, now=utcnow(),
                                     limit=limit, cursor=str(cursor) if cursor else None)

    @router.get("/inbox")
    def inbox(limit: int = Query(default=20, ge=1, le=20), cursor: UUID | None = None,
              actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return hazard_today.page(session, settings, actor.user_id, store=boundaries, now=utcnow(),
                                     limit=limit, cursor=str(cursor) if cursor else None, inbox=True)

    @router.post("/preview")
    def preview(body: ConfigurationBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.preview(session, actor.user_id, body.configuration.model_dump(mode="json"),
                geography_resolver=lambda location: boundaries.verify_location(location, now=utcnow()))
            try:
                ready(session, settings, body.configuration, store=boundaries, now=utcnow())
                result.update(start_available=True, blocking_reasons=[], source_scope_verified=True)
            except DomainError as error:
                reasons = [reason for reason in result["blocking_reasons"] if reason != "hazard_source_not_configured"]
                result.update(blocking_reasons=list(dict.fromkeys([error.code, *reasons])), source_scope_verified=False)
            return result

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

    @router.get("/monitors/{monitor_id}/readiness")
    def readiness(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            monitor = repository.owned(session, actor.user_id, str(monitor_id))
            config = repository.configuration(monitor.configuration)
            reasons = []
            try:
                ready(session, settings, config, store=boundaries, now=utcnow())
            except DomainError as error:
                reasons.append(error.code)
            return {"version": monitor.version, "configuration_hash": config.fingerprint(),
                    "start_available": not reasons and monitor.status in {"draft", "paused"},
                    "source_scope_verified": not reasons, "blocking_reasons": reasons,
                    "live_results_checked": False}

    @router.post("/monitors/{monitor_id}/commands")
    def command(monitor_id: UUID, body: CommandBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = lifecycle.command(session, actor.user_id, str(monitor_id), body.expected_version,
                                       body.action, settings=settings, store=boundaries, now=utcnow())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/actions")
    def actions(monitor_id: UUID, limit: int = Query(default=20, ge=1, le=20),
                before: int | None = Query(default=None, ge=1), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return lifecycle.history(session, actor.user_id, str(monitor_id), limit=limit, before=before)

    @router.get("/monitors/{monitor_id}/revisions")
    def revisions(monitor_id: UUID, before: int | None = Query(default=None, ge=1),
                  limit: int = Query(default=20, ge=1, le=100), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.revisions(session, actor.user_id, str(monitor_id), before=before, limit=limit)

    @router.post("/monitors/{monitor_id}/archive")
    def archive(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.archive_monitor(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
            return result

    @router.delete("/monitors/{monitor_id}")
    def delete(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            repository.delete_monitor(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
            return {"deleted": True}

    @router.get("/monitors/{monitor_id}/events")
    def event_list(monitor_id: UUID, limit: int = Query(default=20, ge=1, le=20), after_id: UUID | None = None,
                   actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.list_events(session, actor.user_id, str(monitor_id), store=boundaries, now=utcnow(),
                                      limit=limit, after_id=str(after_id) if after_id else None)

    @router.get("/monitors/{monitor_id}/events/{development_id}")
    def event_reader(monitor_id: UUID, development_id: UUID, revision: int | None = Query(default=None, ge=1),
                     actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.read_event(session, actor.user_id, str(monitor_id), str(development_id),
                                     store=boundaries, now=utcnow(), revision=revision)

    @router.get("/monitors/{monitor_id}/events/{development_id}/history")
    def event_history(monitor_id: UUID, development_id: UUID, limit: int = Query(default=20, ge=1, le=20),
                      before: int | None = Query(default=None, ge=1), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.history(session, actor.user_id, str(monitor_id), str(development_id),
                                  store=boundaries, now=utcnow(), limit=limit, before=before)

    @router.post("/monitors/{monitor_id}/events/{development_id}/review")
    def event_review(monitor_id: UUID, development_id: UUID, body: ReviewBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = events.set_review(session, actor.user_id, str(monitor_id), str(development_id),
                version=body.expected_version, expected_revision=body.expected_revision, action=body.action, store=boundaries, now=utcnow())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/events/{development_id}/reviews")
    def review_history(monitor_id: UUID, development_id: UUID, limit: int = Query(default=20, ge=1, le=20),
                       before_id: UUID | None = None, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.review_history(session, actor.user_id, str(monitor_id), str(development_id),
                                         limit=limit, before_id=str(before_id) if before_id else None)

    @router.get("/monitors/{monitor_id}/mutes")
    def mute_list(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.mutes(session, actor.user_id, str(monitor_id))

    @router.patch("/monitors/{monitor_id}/mutes/{hazard}")
    def mute_type(monitor_id: UUID, hazard: Hazard, body: MuteBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = events.set_mute(session, actor.user_id, str(monitor_id), hazard,
                version=body.expected_version, muted=body.muted, now=utcnow())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/email")
    def email_preferences(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return {**hazard_email_preferences.view(session, actor.user_id, str(monitor_id)),
                    "delivery_service_available": settings.auth_email_mode == "smtp" and settings.hazard_source_enabled}

    @router.put("/monitors/{monitor_id}/email")
    def save_email(monitor_id: UUID, body: EmailBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = hazard_email_preferences.configure(session, actor.user_id, str(monitor_id),
                expected_version=body.expected_version, configuration=body.configuration,
                consent=body.consent, now=utcnow())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/email-preview")
    def email_preview(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return hazard_delivery.preview(session, settings, actor.user_id, str(monitor_id),
                                           now=utcnow(), store=boundaries)

    return router
