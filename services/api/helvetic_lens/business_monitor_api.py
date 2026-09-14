"""Explicit sharing commands use the application's session, CSRF and tenant scope."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import business_monitor_sharing as sharing
from .auth import Identity
from .config import DomainError

Domain = Literal["tenders", "ip", "auctions"]


class ScopeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(strict=True, ge=1)
    visibility: Literal["private", "workspace"]
    responsible_user_id: UUID | None
    confirmed: bool = Field(strict=True)


def business_monitor_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        return actor

    def available(domain):
        flag = {"tenders": "tender_watch_enabled", "ip": "trademark_watch_enabled",
                "auctions": "auction_watch_enabled"}[domain]
        if not getattr(settings, flag):
            raise DomainError("Monitoring is unavailable.", 404, "business_monitor_unavailable")

    router = APIRouter(prefix="/api/monitoring-centre/business", tags=["monitoring-centre"])

    @router.get("/members")
    def members(after_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=50),
                actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return sharing.members(session, actor.user_id, after_id=str(after_id) if after_id else None, limit=limit)

    @router.get("/{domain}/{monitor_id}/scope")
    def read(domain: Domain, monitor_id: UUID, before_version: int | None = Query(default=None, ge=1),
             limit: int = Query(default=30, ge=1, le=50), actor: Identity = Depends(identity)):
        available(domain)
        with service.db.session() as session:
            return sharing.read(session, actor.user_id, domain, str(monitor_id), before_version=before_version, limit=limit)

    @router.put("/{domain}/{monitor_id}/scope")
    def configure(domain: Domain, monitor_id: UUID, body: ScopeBody, actor: Identity = Depends(identity)):
        available(domain)
        with service.db.session() as session:
            value = sharing.configure(session, actor.user_id, domain, str(monitor_id),
                expected_version=body.expected_version, visibility=body.visibility,
                responsible_user_id=str(body.responsible_user_id) if body.responsible_user_id else None,
                confirmed=body.confirmed, now=datetime.now(UTC))
            session.commit()
            return value

    return router
