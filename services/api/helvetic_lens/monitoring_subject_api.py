"""Authenticated C01b draft routes; only explicit shadow grants can use them.

The existing app middleware supplies identity, workspace context, CSRF and rate
limits. No endpoint can set rollout policy or bypass the source/activation gate.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

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


def draft_router(service, settings: Settings) -> APIRouter:
    def identity(request: Request) -> AuthIdentity:
        actor = getattr(request.state, "identity", None)
        if actor is None:
            # Anonymous-development mode must not provide a personal identity.
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        mode = settings.monitoring_rollout.reader_mode(
            workspace_id=actor.organization_id, template_id="pollen-watch", template_version=1,
            implementation_ready=True, source_ready=False,
        )
        if settings.deployment_instance != "monitoring-v2" or mode != ReaderMode.SHADOW:
            raise DomainError("Monitoring drafts are not enabled for this workspace.", 404, "monitoring_not_enabled")
        return actor

    router = APIRouter(prefix="/api/monitoring-subjects", tags=["monitoring-drafts"], dependencies=[Depends(identity)])

    @router.post("/preview")
    def preview(data: DraftBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
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

    @router.get("/{subject_id}")
    def detail(subject_id: UUID, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            return subjects.get_subject(session, user_id=actor.user_id, subject_id=str(subject_id))

    @router.patch("/{subject_id}")
    def edit(subject_id: UUID, data: EditDraftBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            result = subjects.revise_draft(session, user_id=actor.user_id, subject_id=str(subject_id),
                                           expected_revision=data.expected_revision,
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
    def remove(subject_id: UUID, data: RevisionBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            subjects.delete_draft(session, user_id=actor.user_id, subject_id=str(subject_id),
                                   expected_revision=data.expected_revision)
            session.commit()
        return Response(status_code=204)

    @router.post("/{subject_id}/start")
    def start(subject_id: UUID, data: RevisionBody, actor: AuthIdentity = Depends(identity)):
        with service.db.session() as session:
            current = subjects.get_subject(session, user_id=actor.user_id, subject_id=str(subject_id))
            if current["revision"] != data.expected_revision:
                raise DomainError("The draft changed; review its current settings.", 409, "subject_revision_conflict")
        raise DomainError("Official source and live workflow acceptance are still pending.",
                          409, "pollen_source_not_ready")

    return router
