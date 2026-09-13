"""Private brand portfolio drafts under existing authentication/CSRF/tenant gates."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import trademark_repository as repository
from .auth import Identity
from .config import DomainError
from .monitoring_subjects import _actor
from .trademark_contracts import TrademarkPortfolio


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationBody(Input):
    configuration: TrademarkPortfolio


class CreateBody(ConfigurationBody):
    request_key: UUID


class VersionBody(Input):
    expected_version: int = Field(strict=True, ge=1)


class EditBody(ConfigurationBody, VersionBody):
    pass


def trademark_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not settings.trademark_watch_enabled:
            raise DomainError("Trademark Watch is unavailable.", 404, "trademark_watch_disabled")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/trademark-watch", tags=["trademark-watch"], dependencies=[Depends(identity)])

    @router.get("/capabilities")
    def capabilities():
        return {"drafts_available": True, "start_available": False, "live_results_checked": False,
                "blocking_reasons": ["trademark_source_not_configured", "trademark_similarity_calibration_unavailable"]}

    @router.post("/preview")
    def preview(body: ConfigurationBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.preview(session, actor.user_id, body.configuration.model_dump(mode="json"))

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

    return router
