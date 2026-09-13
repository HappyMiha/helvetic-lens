"""Private Road Watch routes under existing authentication, tenant and CSRF middleware."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import road_delivery, road_email_preferences, road_today
from . import road_events as events
from . import road_repository as repository
from .auth import Identity
from .config import DomainError
from .monitoring_subjects import _actor
from .road_contracts import RoadConfiguration


def clock():
    return datetime.now(UTC)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationBody(Input):
    configuration: RoadConfiguration


class CreateBody(ConfigurationBody):
    request_key: UUID


class VersionBody(Input):
    expected_version: int = Field(strict=True, ge=1)


class EditBody(ConfigurationBody, VersionBody):
    pass


class CommandBody(VersionBody):
    action: Literal["start", "pause", "resume", "archive"]


class ReviewBody(VersionBody):
    sequence: int = Field(strict=True, ge=1)
    muted: bool | None = Field(default=None, strict=True)


class EmailBody(VersionBody):
    configuration: road_email_preferences.EmailConfiguration
    consent: bool = Field(strict=True)


class PreviewBody(ConfigurationBody):
    country: str | None = Field(default=None, min_length=1, max_length=16)
    table: str | None = Field(default=None, min_length=1, max_length=16)
    table_version: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def complete_table(self):
        if any(v is not None for v in (self.country, self.table, self.table_version)) and not all((self.country, self.table, self.table_version)):
            raise ValueError("Supply all table identity fields or omit them")
        return self


def road_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not settings.road_watch_enabled:
            raise DomainError("Road Watch is unavailable.", 404, "road_watch_disabled")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/road-watch", tags=["road-watch"], dependencies=[Depends(identity)])

    @router.get("/capabilities")
    def capabilities():
        from .road_events import FIELDS
        from .road_sources import read_state, require_permission
        reasons = []
        if not settings.road_source_enabled or not settings.road_source_permission_id:
            reasons.append("road_source_not_ready")
        else:
            with service.db.session() as session:
                try:
                    require_permission(session, settings.road_source_permission_id, now=clock(), fields=FIELDS)
                    read_state(session, settings.road_source_permission_id, now=clock())
                except DomainError as error:
                    reasons.append(error.code)
        return {"drafts_available": True, "start_available": not reasons, "live_results_checked": False,
                "start_requires_corridor_check": True, "blocking_reasons": reasons, "catalog_coverage": "reviewed_corridors_only"}

    @router.get("/catalog")
    def catalog(country: str | None = Query(default=None, min_length=1, max_length=16), table: str | None = Query(default=None, min_length=1, max_length=16),
                table_version: str | None = Query(default=None, min_length=1, max_length=64), query: str = Query(default="", max_length=100),
                limit: int = Query(default=20, ge=1, le=100), after_id: UUID | None = None,
                actor: Identity = Depends(identity)):
        key = (country, table, table_version)
        if any(v is not None for v in key) and not all(key):
            raise DomainError("Supply the complete table identity.", 422, "road_corridor_table_invalid")
        with service.db.session() as session:
            return repository.catalog_page(session, actor.user_id, table_key=key if all(key) else None, now=clock(),
                query=query, limit=limit, after_id=str(after_id) if after_id else None)

    @router.get("/today")
    def today(cursor: UUID | None = None, limit: int = Query(default=20, ge=1, le=50),
              actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return road_today.today(session, settings, actor.user_id, now=clock(),
                                    cursor=str(cursor) if cursor else None, limit=limit)

    @router.get("/inbox")
    def road_inbox(cursor: UUID | None = None, limit: int = Query(default=20, ge=1, le=50),
                   actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return road_today.inbox(session, settings, actor.user_id, now=clock(),
                                    cursor=str(cursor) if cursor else None, limit=limit)

    @router.get("/events/{event_id}")
    def event_detail(event_id: UUID, sequence: int | None = Query(default=None, ge=1, le=10000), monitor_id: UUID | None = None,
                     actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return road_today.detail(session, actor.user_id, str(event_id), now=clock(), sequence=sequence,
                                    monitor_id=str(monitor_id) if monitor_id else None)

    @router.post("/preview")
    def preview(body: PreviewBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.preview(session, actor.user_id, body.configuration.model_dump(mode="json"),
                table_key=(body.country, body.table, body.table_version) if body.country else None, now=clock(), settings=settings)

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

    @router.get("/monitors/{monitor_id}/corridors")
    def saved_corridors(monitor_id: UUID, actor: Identity = Depends(identity)):
        from .road_catalog import CatalogReadBudget
        with service.db.session() as session:
            monitor = repository.owned(session, actor.user_id, str(monitor_id))
            budget, items = CatalogReadBudget(), []
            for identifier in monitor.configuration["corridor_reference_ids"]:
                try:
                    items.append(repository.describe_current_reference(session, identifier, now=clock(), budget=budget))
                except DomainError:
                    items.append({"id": identifier, "state": "unavailable"})
            return {"items": items, "next_cursor": None}

    @router.post("/monitors/{monitor_id}/commands")
    def command(monitor_id: UUID, body: CommandBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.command(session, actor.user_id, str(monitor_id), body.expected_version, body.action,
                                        settings=settings, now=clock())
            session.commit()
            return result

    @router.delete("/monitors/{monitor_id}", status_code=204)
    def remove(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            repository.remove_monitor(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.get("/monitors/{monitor_id}/revisions")
    def history(monitor_id: UUID, after_revision: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
                actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.revisions(session, actor.user_id, str(monitor_id), after_revision=after_revision, limit=limit)

    @router.get("/monitors/{monitor_id}/events")
    def event_list(monitor_id: UUID, limit: int = Query(default=20, ge=1, le=100), after_id: UUID | None = None,
                   actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.events_page(session, actor.user_id, str(monitor_id), now=clock(), limit=limit,
                                      after_id=str(after_id) if after_id else None)

    @router.get("/events/{event_id}/history")
    def event_history(event_id: UUID, after_sequence: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
                      actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return events.history_page(session, actor.user_id, str(event_id), now=clock(), after_sequence=after_sequence, limit=limit)

    @router.post("/events/{event_id}/review")
    def review(event_id: UUID, body: ReviewBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = events.review_event(session, actor.user_id, str(event_id), expected_version=body.expected_version,
                                          sequence=body.sequence, muted=body.muted)
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/email")
    def email_settings(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return {**road_email_preferences.view(session, actor.user_id, str(monitor_id)),
                    "delivery_service_available": settings.auth_email_mode == "smtp" and settings.road_source_enabled}

    @router.put("/monitors/{monitor_id}/email")
    def configure_email(monitor_id: UUID, body: EmailBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = road_email_preferences.configure(session, actor.user_id, str(monitor_id),
                expected_version=body.expected_version, configuration=body.configuration.model_dump(mode="json"),
                consent=body.consent, now=clock())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/email-preview")
    def email_preview(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return road_delivery.preview(session, settings, actor.user_id, str(monitor_id), now=clock())

    return router
