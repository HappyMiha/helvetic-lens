"""Explicit unsaved configuration assistance, scoped to an authenticated editor."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from .analysis import ModelClient
from .auth import Identity
from .config import DomainError
from .monitoring_configuration_drafts import propose
from .monitoring_evidence_api import Locale
from .monitoring_evidence_ask import Domain
from .monitoring_subjects import _actor


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Domain
    locale: Locale
    configuration: dict
    request: str = Field(strict=True, min_length=1, max_length=2000, pattern=r"\S")
    request_key: str = Field(pattern=r"^[a-f0-9-]{36}$")


def configuration_router(service):
    router = APIRouter(prefix="/api/monitoring-centre/configuration", tags=["monitoring-centre"])

    def identity(request: Request):
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        return actor

    def check(actor):
        with service.db.session() as session:
            _actor(session, actor.user_id, write=True)

    @router.post("/draft")
    async def draft(body: DraftRequest, actor: Identity = Depends(identity)):
        check(actor)
        # Never attach the shared IntegrationLogger: these inputs can contain
        # private company or personal configuration, and are not retained.
        client = ModelClient(service.settings)
        result = await propose(client, domain=body.domain, current=body.configuration,
            request=body.request, locale=body.locale)
        check(actor)
        return {**result, "request_key": body.request_key}

    return router
