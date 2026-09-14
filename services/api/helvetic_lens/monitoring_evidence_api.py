"""Authenticated, non-persistent questions about selected Monitoring evidence."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .auth import Identity
from .config import DomainError
from .monitoring_evidence_ask import Domain, Record, answer, reference

Locale = Literal["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"]


class EvidenceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Domain
    monitor_id: UUID
    item_id: UUID
    sequence: int | None = Field(default=None, strict=True, ge=1, le=10000)
    locale: Locale
    question: str = Field(default="", strict=True, max_length=2000)
    expected_binding: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def selected_evidence_required(self):
        if self.question.strip() and self.expected_binding is None:
            raise ValueError("Open and select evidence before asking a question")
        return self


def evidence_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        return actor

    router = APIRouter(prefix="/api/monitoring-centre/evidence", tags=["monitoring-centre"])

    @router.get("/reference")
    def cited_reference(domain: Domain, monitor_id: UUID, item_id: UUID, locale: Locale,
                        expected_binding: str = Query(pattern=r"^[a-f0-9]{64}$"),
                        sequence: int | None = Query(default=None, ge=1, le=10000),
                        actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return reference(session, settings, actor.user_id,
                Record(domain, str(monitor_id), str(item_id), sequence), now=datetime.now(UTC),
                locale=locale, expected_binding=expected_binding)

    @router.post("/ask")
    def ask(body: EvidenceQuestion, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return answer(session, settings, actor.user_id,
                Record(body.domain, str(body.monitor_id), str(body.item_id), body.sequence),
                now=datetime.now(UTC), locale=body.locale, question=body.question,
                expected_binding=body.expected_binding)

    return router
