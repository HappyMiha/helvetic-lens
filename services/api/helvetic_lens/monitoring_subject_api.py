"""Authenticated C01b draft routes; only explicit shadow grants can use them.

The existing app middleware supplies identity, workspace context, CSRF and rate
limits. No endpoint can set rollout policy or bypass the source/activation gate.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from . import monitoring_runtime as runtime
from . import monitoring_subjects as subjects
from .auth import Identity as AuthIdentity
from .config import DomainError, Settings
from .monitoring_contracts import ReaderMode
from .pollen_contracts import PollenConfiguration


class DraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configuration: PollenConfiguration


class CreateDraftBody(DraftBody):
    request_key: str = Field(min_length=1, max_length=120)


class RevisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(strict=True, ge=1)


class EditDraftBody(DraftBody, RevisionBody):
    pass


class RemoveBody(RevisionBody):
    expected_version: int | None = Field(default=None, strict=True, ge=1)


class StartBody(RevisionBody):
    expected_version: int = Field(default=0, strict=True, ge=0)
    request_key: str | None = Field(default=None, min_length=1, max_length=120)
    email_consent: bool = Field(default=False, strict=True)


class RuntimeCommandBody(RevisionBody):
    action: Literal["start", "pause", "resume", "archive", "mute", "unmute", "unsubscribe", "consent_email"]
    expected_version: int = Field(strict=True, ge=0)
    request_key: str = Field(min_length=1, max_length=120)
    email_consent: bool = Field(default=False, strict=True)


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["reviewed", "not_relevant", "continue", "action_required"]
    expected_version: int = Field(strict=True, ge=0)


def draft_router(service, settings: Settings) -> APIRouter:
    def identity(request: Request) -> AuthIdentity:
        actor = getattr(request.state, "identity", None)
        if actor is None:
            # Anonymous-development mode must not provide a personal identity.
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        mode = settings.monitoring_rollout.reader_mode(
            workspace_id=actor.organization_id, template_id="pollen-watch", template_version=1,
            implementation_ready=True, source_ready=True,
        )
        if settings.deployment_instance not in {"main", "monitoring-v2"} or mode not in {ReaderMode.SHADOW, ReaderMode.ENABLED}:
            raise DomainError("Monitoring drafts are not enabled for this workspace.", 404, "monitoring_not_enabled")
        return actor

    router = APIRouter(prefix="/api/monitoring-subjects", tags=["monitoring-drafts"], dependencies=[Depends(identity)])

    @router.post("/preview")
    def preview(data: DraftBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            if runtime._mode(settings, actor.organization_id) == ReaderMode.ENABLED:
                return runtime.preview(session, settings=settings, user_id=actor.user_id,
                    configuration=data.configuration.model_dump(mode="json"), now=datetime.now(UTC))
            return subjects.preview_draft(session, user_id=actor.user_id,
                                           configuration=data.configuration.model_dump(mode="json"))

    @router.post("", status_code=201)
    def create(data: CreateDraftBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            result = subjects.create_draft(session, user_id=actor.user_id, request_key=data.request_key,
                                           configuration=data.configuration.model_dump(mode="json"))
            session.commit()
            return result

    @router.get("")
    def listing(limit: int = Query(default=50, ge=1, le=100), cursor: UUID | None = None,
                actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return subjects.list_subjects_page(session, user_id=actor.user_id, limit=limit,
                                               after_id=str(cursor) if cursor else None)

    @router.get("/today")
    def today(cursor: UUID | None = None, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return runtime.today(session, settings=settings, user_id=actor.user_id, now=datetime.now(UTC),
                                 before_id=str(cursor) if cursor else None)

    @router.get("/{subject_id}")
    def detail(subject_id: UUID, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return subjects.get_subject(session, user_id=actor.user_id, subject_id=str(subject_id))

    @router.patch("/{subject_id}")
    def edit(subject_id: UUID, data: EditDraftBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            current = subjects.get_subject(session, user_id=actor.user_id, subject_id=str(subject_id))
            editor = runtime.revise_paused if current["status"] == "paused" else subjects.revise_draft
            result = editor(session, user_id=actor.user_id, subject_id=str(subject_id),
                                           expected_revision=data.expected_revision,
                                           **({"now": datetime.now(UTC)} if current["status"] == "paused" else {}),
                                           configuration=data.configuration.model_dump(mode="json"))
            session.commit()
            return result

    @router.get("/{subject_id}/history")
    def history(subject_id: UUID, limit: int = Query(default=50, ge=1, le=100),
                before_revision: int | None = Query(default=None, ge=1), actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return subjects.subject_history_page(session, user_id=actor.user_id, subject_id=str(subject_id),
                                                  limit=limit, before_revision=before_revision)

    @router.delete("/{subject_id}", status_code=204)
    def remove(subject_id: UUID, data: RemoveBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            current = subjects.get_subject(session, user_id=actor.user_id, subject_id=str(subject_id))
            if current["status"] == "draft":
                subjects.delete_draft(session, user_id=actor.user_id, subject_id=str(subject_id), expected_revision=data.expected_revision)
            else:
                runtime.remove(session, user_id=actor.user_id, subject_id=str(subject_id),
                    expected_revision=data.expected_revision, expected_version=data.expected_version)
            session.commit()
        return Response(status_code=204)

    @router.post("/{subject_id}/start")
    def start(subject_id: UUID, data: StartBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            current = subjects.get_subject(session, user_id=actor.user_id, subject_id=str(subject_id))
            if current["revision"] != data.expected_revision:
                raise DomainError("The draft changed; review its current settings.", 409, "subject_revision_conflict")
            if runtime._mode(settings, actor.organization_id) == ReaderMode.ENABLED:
                result = runtime.command(session, settings=settings, user_id=actor.user_id, subject_id=str(subject_id),
                    action="start", now=datetime.now(UTC), **data.model_dump())
                session.commit()
                return result
        raise DomainError("Official source and live workflow acceptance are still pending.",
                          409, "pollen_source_not_ready")

    @router.post("/{subject_id}/commands")
    def lifecycle(subject_id: UUID, data: RuntimeCommandBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            result = runtime.command(session, settings=settings, user_id=actor.user_id, subject_id=str(subject_id),
                now=datetime.now(UTC), **data.model_dump())
            session.commit()
            return result

    @router.get("/{subject_id}/state")
    def current_state(subject_id: UUID, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return runtime.state(session, settings=settings, user_id=actor.user_id,
                                 subject_id=str(subject_id), now=datetime.now(UTC))

    @router.get("/{subject_id}/activity")
    def activity(subject_id: UUID, limit: int = Query(default=20, ge=1, le=100), cursor: UUID | None = None,
                 material_only: bool = False, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return runtime.history(session, user_id=actor.user_id, subject_id=str(subject_id), limit=limit,
                                   before_id=str(cursor) if cursor else None, material_only=material_only,
                                   settings=settings, now=datetime.now(UTC))

    @router.get("/{subject_id}/activity/{entry_id}/artifacts/{artifact_hash}")
    def artifact(subject_id: UUID, entry_id: UUID, artifact_hash: str, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            path = runtime.artifact_path(session, settings=settings, user_id=actor.user_id,
                subject_id=str(subject_id), entry_id=str(entry_id), artifact_hash=artifact_hash, now=datetime.now(UTC))
        return FileResponse(path, media_type="application/octet-stream", filename=f"pollen-source-{artifact_hash}.bin",
                            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @router.get("/{subject_id}/activity/{entry_id}/reviews")
    def reviews(subject_id: UUID, entry_id: UUID, before_version: int | None = Query(default=None, ge=1),
                actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return runtime.review_history(session, user_id=actor.user_id, subject_id=str(subject_id),
                                          entry_id=str(entry_id), before_version=before_version)

    @router.get("/{subject_id}/export")
    def export(subject_id: UUID, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            subjects.get_subject(session, user_id=actor.user_id, subject_id=str(subject_id))
        return StreamingResponse(runtime.export_records(service.db, settings=settings, user_id=actor.user_id,
            organization_id=actor.organization_id, subject_id=str(subject_id)), media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="pollen-history-{subject_id}.jsonl"',
                     "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @router.post("/{subject_id}/activity/{entry_id}/review")
    def review(subject_id: UUID, entry_id: UUID, data: ReviewBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            result = runtime.review(session, user_id=actor.user_id, subject_id=str(subject_id),
                                    entry_id=str(entry_id), **data.model_dump())
            session.commit()
            return result

    return router
