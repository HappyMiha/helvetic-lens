"""Private brand portfolio drafts under existing authentication/CSRF/tenant gates."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import trademark_exports, trademark_history, trademark_today, trademark_workflow
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


class ReviewBody(VersionBody):
    expected_evaluation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["reviewed", "relevant", "not_relevant", "monitor", "counsel"]


class ExportBody(VersionBody):
    expected_evaluation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_key: UUID
    event_id: UUID | None = None
    locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"] = "en-CH"


class DownloadBody(Input):
    expected_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _now():
    return datetime.now(UTC)


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
                "tracking_available": True, "profile_preview_required": True,
                "blocking_reasons": ["trademark_profile_preview_required"]}

    @router.get("/source-status")
    def source_status():
        from . import ipi_acquisition, ipi_collector
        state = ipi_collector.readiness(settings)
        if state != "configured":
            return {"state": state, "coverage_verified": False, "traversal": None}
        with service.db.session() as session:
            try:
                ipi_acquisition._scope(session, settings.ipi_source_permission_id, _now())
                result = ipi_acquisition.read_status(session, settings.ipi_source_permission_id, now=_now())
                return {"state": "configured", "coverage_verified": False, "traversal": result}
            except DomainError:
                return {"state": "permission_unavailable", "coverage_verified": False, "traversal": None}

    @router.post("/preview")
    def preview(body: ConfigurationBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_workflow.preview(session, actor.user_id, body.configuration.model_dump(mode="json"), now=_now())

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

    @router.post("/monitors/{monitor_id}/start")
    def start(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = trademark_workflow.start(session, actor.user_id, str(monitor_id), body.expected_version, now=_now())
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/pause")
    def pause(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = trademark_workflow.pause(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/refresh")
    def refresh(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = trademark_workflow.refresh(session, actor.user_id, str(monitor_id), now=_now())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/candidates")
    def candidates(monitor_id: UUID, after_id: UUID | None = None, limit: int = Query(default=20, ge=1, le=100), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_workflow.list_candidates(session, actor.user_id, str(monitor_id), now=_now(),
                after=str(after_id) if after_id else None, limit=limit)

    @router.get("/monitors/{monitor_id}/candidates/{candidate_id}")
    def candidate(monitor_id: UUID, candidate_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            monitor, row = trademark_workflow.candidate_for(session, actor.user_id, str(monitor_id), str(candidate_id))
            return trademark_workflow.candidate_view(session, monitor, row, now=_now())

    @router.post("/monitors/{monitor_id}/candidates/{candidate_id}/review")
    def review(monitor_id: UUID, candidate_id: UUID, body: ReviewBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = trademark_workflow.review(session, actor.user_id, str(monitor_id), str(candidate_id),
                expected_version=body.expected_version, expected_evaluation_hash=body.expected_evaluation_hash, decision=body.decision, now=_now())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/candidates/{candidate_id}/history")
    def history(monitor_id: UUID, candidate_id: UUID, before: int | None = Query(default=None, ge=1),
                limit: int = Query(default=20, ge=1, le=100), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_history.history(session, actor.user_id, str(monitor_id), str(candidate_id), now=_now(), before=before, limit=limit)

    @router.get("/monitors/{monitor_id}/candidates/{candidate_id}/reviews")
    def reviews(monitor_id: UUID, candidate_id: UUID, before: int | None = Query(default=None, ge=1),
                limit: int = Query(default=20, ge=1, le=100), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_history.reviews(session, actor.user_id, str(monitor_id), str(candidate_id), before=before, limit=limit)

    @router.get("/monitors/{monitor_id}/candidates/{candidate_id}/events/{event_id}")
    def event(monitor_id: UUID, candidate_id: UUID, event_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_history.event_detail(session, actor.user_id, str(monitor_id), str(candidate_id), str(event_id), now=_now())

    @router.get("/today")
    def today(cursor: UUID | None = None, limit: int = Query(default=20, ge=1, le=50), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_today.page(session, settings, actor.user_id, now=_now(), cursor=str(cursor) if cursor else None, limit=limit)

    @router.post("/monitors/{monitor_id}/candidates/{candidate_id}/exports")
    def prepare_export(monitor_id: UUID, candidate_id: UUID, body: ExportBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = trademark_exports.prepare(session, actor.user_id, str(monitor_id), str(candidate_id),
                expected_version=body.expected_version, expected_evaluation_hash=body.expected_evaluation_hash,
                request_key=str(body.request_key), event_id=str(body.event_id) if body.event_id else None, locale=body.locale, now=_now())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/candidates/{candidate_id}/exports/{preparation_id}")
    def read_export(monitor_id: UUID, candidate_id: UUID, preparation_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_exports.read(session, actor.user_id, str(monitor_id), str(candidate_id), str(preparation_id), now=_now())

    @router.post("/monitors/{monitor_id}/candidates/{candidate_id}/exports/{preparation_id}/download")
    def download_export(monitor_id: UUID, candidate_id: UUID, preparation_id: UUID, body: DownloadBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = trademark_exports.read(session, actor.user_id, str(monitor_id), str(candidate_id), str(preparation_id),
                download_hash=body.expected_content_sha256, now=_now())
            session.commit()
            return result

    @router.get("/inbox")
    def inbox(cursor: UUID | None = None, limit: int = Query(default=20, ge=1, le=50), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return trademark_today.page(session, settings, actor.user_id, now=_now(), inbox=True, cursor=str(cursor) if cursor else None, limit=limit)

    return router
