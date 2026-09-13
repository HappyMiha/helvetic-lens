"""Private auction profiles and tracking under existing authentication/CSRF/tenant gates."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import auction_repository as repository
from . import auction_today
from . import auction_workflow as workflow
from .auction_contracts import AuctionProfile
from .auth import Identity
from .config import DomainError
from .monitoring_subjects import _actor


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationBody(Input):
    configuration: AuctionProfile


class CreateBody(ConfigurationBody):
    request_key: UUID


class VersionBody(Input):
    expected_version: int = Field(strict=True, ge=1)


class EditBody(ConfigurationBody, VersionBody):
    pass


class ItemVersionBody(VersionBody):
    expected_state_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class FollowBody(ItemVersionBody):
    following: bool = Field(strict=True)


class DecisionBody(ItemVersionBody):
    decision: Literal["inspect", "bid", "no_bid", "monitor"]


def _now():
    return datetime.now(UTC)


def auction_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not settings.auction_watch_enabled:
            raise DomainError("Auction Watch is unavailable.", 404, "auction_watch_disabled")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/auction-watch", tags=["auction-watch"], dependencies=[Depends(identity)])

    @router.get("/capabilities")
    def capabilities():
        return {"drafts_available": True, "start_available": False, "live_results_checked": False,
                "profile_preview_required": True, "tracking_available": True,
                "blocking_reasons": ["auction_profile_preview_required"]}

    @router.post("/preview")
    def preview(body: ConfigurationBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return workflow.preview(session, actor.user_id, body.configuration.model_dump(mode="json"), now=_now())

    @router.get("/today")
    def today(cursor: UUID | None = None, limit: int = Query(default=20, ge=1, le=50), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return auction_today.page(session, settings, actor.user_id, now=_now(), cursor=str(cursor) if cursor else None, limit=limit)

    @router.get("/inbox")
    def inbox(cursor: UUID | None = None, limit: int = Query(default=20, ge=1, le=50), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return auction_today.page(session, settings, actor.user_id, now=_now(), cursor=str(cursor) if cursor else None, limit=limit, inbox=True)

    @router.get("/monitors/{monitor_id}/events/{event_id}")
    def event(monitor_id: UUID, event_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return auction_today.detail(session, actor.user_id, str(monitor_id), str(event_id), now=_now())

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
            result = workflow.start(session, actor.user_id, str(monitor_id), body.expected_version, now=_now())
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/pause")
    def pause(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = workflow.pause(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/refresh")
    def refresh(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = workflow.refresh(session, actor.user_id, str(monitor_id), now=_now())
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/items")
    def items(monitor_id: UUID, limit: int = Query(default=20, ge=1, le=100), after_id: UUID | None = None,
              following_only: bool = False, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return workflow.list_items(session, actor.user_id, str(monitor_id), now=_now(), limit=limit,
                after=str(after_id) if after_id else None, following_only=following_only)

    @router.get("/monitors/{monitor_id}/items/{item_id}/history")
    def item_history(monitor_id: UUID, item_id: UUID, before: int | None = Query(default=None, ge=1),
                     limit: int = Query(default=20, ge=1, le=100), actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return workflow.history(session, actor.user_id, str(monitor_id), str(item_id), now=_now(), before=before, limit=limit)

    @router.post("/monitors/{monitor_id}/items/{item_id}/follow")
    def follow(monitor_id: UUID, item_id: UUID, body: FollowBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = workflow.follow(session, actor.user_id, str(monitor_id), str(item_id), now=_now(),
                expected_version=body.expected_version, expected_state_hash=body.expected_state_hash, following=body.following)
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/items/{item_id}/decision")
    def decision(monitor_id: UUID, item_id: UUID, body: DecisionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = workflow.decide(session, actor.user_id, str(monitor_id), str(item_id), now=_now(),
                expected_version=body.expected_version, expected_state_hash=body.expected_state_hash, decision=body.decision)
            session.commit()
            return result

    return router
