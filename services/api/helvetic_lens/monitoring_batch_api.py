"""Authenticated explicit preview/apply boundary for native review batches."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import monitoring_batch_review as batch
from .auth import Identity
from .config import DomainError
from .monitoring_evidence_api import Locale
from .monitoring_evidence_ask import Domain, Record


class SelectedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Domain
    monitor_id: UUID
    item_id: UUID
    sequence: int | None = Field(default=None, strict=True, ge=1, le=10000)

    def native(self):
        return Record(self.domain, str(self.monitor_id), str(self.item_id), self.sequence)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: SelectedRecord
    expected_binding: str = Field(pattern=r"^[a-f0-9]{64}$")
    action: str = Field(strict=True, min_length=1, max_length=32)


class Preview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[SelectedRecord] = Field(min_length=1, max_length=batch.MAX_ITEMS)
    locale: Locale


class Apply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: list[Selection] = Field(min_length=1, max_length=batch.MAX_ITEMS)
    locale: Locale


def batch_router(service, settings):
    router = APIRouter(prefix="/api/monitoring-centre/review", tags=["monitoring-centre"])

    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        return actor

    @router.post("/preview")
    def preview(body: Preview, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return batch.preview(session, settings, actor.user_id, [row.native() for row in body.records],
                now=datetime.now(UTC), locale=body.locale)

    @router.post("/apply")
    def apply(body: Apply, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = batch.apply(session, settings, actor.user_id,
                [(row.record.native(), row.expected_binding, row.action) for row in body.selections],
                now=datetime.now(UTC), locale=body.locale)
            session.commit()
            return result

    return router
