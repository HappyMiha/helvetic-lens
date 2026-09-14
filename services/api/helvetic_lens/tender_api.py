"""Private B2 API, using normal session, CSRF and organization middleware."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import tender_lifecycle as lifecycle
from . import tender_repository as repository
from .auth import Identity
from .config import DomainError
from .monitoring_subjects import _actor
from .tender_contracts import TenderProfile
from .tender_email_preferences import EmailConfiguration
from .tender_jobs import enabled
from .tender_scan import CYCLE_HOURS, LOOKBACK_DAYS, queries


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigurationBody(Input):
    configuration: TenderProfile


class CreateBody(ConfigurationBody):
    request_key: UUID


class VersionBody(Input):
    expected_version: int = Field(strict=True, ge=1)


class EditBody(ConfigurationBody, VersionBody):
    pass


class CommandBody(VersionBody):
    action: Literal["start", "pause", "resume", "archive"]


class FollowBody(VersionBody):
    following: bool = Field(strict=True)


class DecisionBody(VersionBody):
    sequence: int = Field(strict=True, ge=1)
    decision: Literal["bid", "no_bid", "monitor"]
    request_key: UUID


class EmailBody(VersionBody):
    configuration: EmailConfiguration
    consent: bool = Field(strict=True)


def tender_router(service, settings):
    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to continue.", 401, "authentication_required")
        if not settings.tender_watch_enabled:
            raise DomainError("Tender Watch is unavailable.", 404, "tender_disabled")
        with service.db.session() as session:
            _actor(session, actor.user_id)
        return actor

    router = APIRouter(prefix="/api/tender-watch", tags=["tender-watch"], dependencies=[Depends(identity)])

    @router.get("/today")
    def today_dossiers(after_version: UUID | None = None,
                       review_state: Literal["pending", "new", "needs_review", "reviewed"] | None = None,
                       following: bool = False, limit: int = Query(default=20, ge=1, le=50),
                       actor: Identity = Depends(identity)):
        from .tender_today import today
        with service.db.session() as session:
            return today(session, actor.user_id, after_version=after_version, review_state=review_state,
                following=following, limit=limit)

    @router.get("/capabilities")
    def capabilities():
        return {
            "public_source_available": enabled(settings),
            "source_scope": "public_publications",
            "documents": "not_verified",
            "qa": "not_verified",
            "semantic_status": "disabled",
            "lookback_days": LOOKBACK_DAYS,
            "cycle_hours": CYCLE_HOURS,
            "decision_scope": "internal_only",
        }

    @router.post("/profile-check")
    def check_profile(body: ConfigurationBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            _actor(session, actor.user_id, write=True)
        config = body.configuration.model_dump(mode="json")
        plan = queries(config)
        return {
            "configuration": config,
            "configuration_hash": body.configuration.fingerprint(),
            "queries": plan,
            "start_available": bool(plan) and enabled(settings),
            "source_scope": "public_publications",
            "semantic_status": "disabled",
            "live_results_checked": False,
        }

    @router.get("/monitors")
    def monitors(
        limit: int = Query(default=20, ge=1, le=100),
        after_id: UUID | None = None,
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            return repository.list_monitors(
                session, actor.user_id, limit=limit, after_id=str(after_id) if after_id else None
            )

    @router.post("/monitors", status_code=201)
    def create(body: CreateBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.create_profile(
                session, actor.user_id, body.configuration.model_dump(mode="json"), str(body.request_key)
            )
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}")
    def monitor(monitor_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.get_monitor(session, actor.user_id, str(monitor_id))

    @router.patch("/monitors/{monitor_id}")
    def edit(monitor_id: UUID, body: EditBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.revise_profile(
                session,
                actor.user_id,
                str(monitor_id),
                body.expected_version,
                body.configuration.model_dump(mode="json"),
            )
            session.commit()
            return result

    @router.post("/monitors/{monitor_id}/command")
    def command(monitor_id: UUID, body: CommandBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = lifecycle.command(
                session, settings, actor.user_id, str(monitor_id), body.expected_version, body.action
            )
            session.commit()
            return result

    @router.delete("/monitors/{monitor_id}", status_code=204)
    def remove(monitor_id: UUID, body: VersionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            lifecycle.remove(session, actor.user_id, str(monitor_id), body.expected_version)
            session.commit()
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.get("/monitors/{monitor_id}/revisions")
    def revisions(
        monitor_id: UUID,
        limit: int = Query(default=20, ge=1, le=100),
        before_revision: int | None = Query(default=None, ge=1),
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            return repository.profile_history(
                session, actor.user_id, str(monitor_id), limit=limit, before_revision=before_revision
            )

    @router.get("/monitors/{monitor_id}/email")
    def email_settings(monitor_id: UUID, actor: Identity = Depends(identity)):
        from .tender_email_preferences import view

        with service.db.session() as session:
            return {
                **view(session, actor.user_id, str(monitor_id)),
                "delivery_service_available": settings.auth_email_mode == "smtp",
            }

    @router.patch("/monitors/{monitor_id}/email")
    def email_consent(monitor_id: UUID, body: EmailBody, actor: Identity = Depends(identity)):
        from .tender_email_preferences import configure

        with service.db.session() as session:
            result = configure(
                session,
                actor.user_id,
                str(monitor_id),
                expected_version=body.expected_version,
                configuration=body.configuration.model_dump(mode="json"),
                consent=body.consent,
            )
            session.commit()
            return result

    @router.get("/monitors/{monitor_id}/email-preview")
    def email_preview(monitor_id: UUID, actor: Identity = Depends(identity)):
        from .tender_delivery import preview

        with service.db.session() as session:
            return preview(session, settings, actor.user_id, str(monitor_id))

    @router.get("/monitors/{monitor_id}/dossiers")
    def dossiers(
        monitor_id: UUID,
        limit: int = Query(default=20, ge=1, le=100),
        after_id: UUID | None = None,
        following: bool | None = None,
        review_state: Literal["new", "needs_review", "reviewed"] | None = None,
        assignment: Literal["mine", "unassigned"] | None = None,
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            return repository.list_dossiers(
                session,
                actor.user_id,
                str(monitor_id),
                limit=limit,
                after_id=str(after_id) if after_id else None,
                following=following,
                review_state=review_state,
                assignment=assignment,
            )

    @router.get("/dossiers/{dossier_id}")
    def dossier(dossier_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.get_dossier(session, actor.user_id, str(dossier_id))

    @router.get("/dossiers/{dossier_id}/review-changes")
    def review_changes(
        dossier_id: UUID,
        through_sequence: int = Query(ge=1),
        reviewed_sequence: int = Query(ge=0),
        limit: int = Query(default=20, ge=1, le=100),
        after_sequence: int | None = Query(default=None, ge=0),
        actor: Identity = Depends(identity),
    ):
        from .tender_review_changes import review_changes as read_changes

        with service.db.session() as session:
            return read_changes(session, actor.user_id, str(dossier_id),
                                through_sequence=through_sequence, reviewed_sequence=reviewed_sequence,
                                limit=limit, after_sequence=after_sequence)

    @router.get("/dossiers/{dossier_id}/versions")
    def versions(
        dossier_id: UUID,
        limit: int = Query(default=20, ge=1, le=100),
        before_sequence: int | None = Query(default=None, ge=1),
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            return repository.version_index(
                session, actor.user_id, str(dossier_id), limit=limit, before_sequence=before_sequence
            )

    @router.get("/dossiers/{dossier_id}/versions/{version_id}/evidence")
    def evidence(dossier_id: UUID, version_id: UUID, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            return repository.evidence_version(session, actor.user_id, str(dossier_id), str(version_id))

    @router.get("/dossiers/{dossier_id}/documents")
    def documents(dossier_id: UUID, limit: int = Query(default=20, ge=1, le=100),
                  after_id: UUID | None = None, actor: Identity = Depends(identity)):
        from .tender_documents import index

        with service.db.session() as session:
            return index(session, actor.user_id, str(dossier_id), limit=limit,
                         after_id=str(after_id) if after_id else None)

    @router.get("/dossiers/{dossier_id}/document-observations/{observation_id}")
    def document_observation(dossier_id: UUID, observation_id: UUID,
                             limit: int = Query(default=20, ge=1, le=100),
                             after_item: str | None = Query(default=None, max_length=256),
                             actor: Identity = Depends(identity)):
        from datetime import UTC, datetime

        from .tender_document_observations import view

        with service.db.session() as session:
            return view(session, actor.user_id, str(dossier_id), str(observation_id),
                        now=datetime.now(UTC), limit=limit, after_item=after_item)

    @router.get("/dossiers/{dossier_id}/document-observations/{observation_id}/comparison")
    def document_comparison(dossier_id: UUID, observation_id: UUID,
                            item_id: str = Query(min_length=1, max_length=256),
                            actor: Identity = Depends(identity)):
        from datetime import UTC, datetime

        from .tender_document_observations import comparison

        with service.db.session() as session:
            return comparison(session, actor.user_id, str(dossier_id), str(observation_id), item_id,
                              now=datetime.now(UTC))

    @router.get("/dossiers/{dossier_id}/documents/{snapshot_id}/text")
    def document_text(dossier_id: UUID, snapshot_id: UUID, actor: Identity = Depends(identity)):
        from .tender_documents import read

        with service.db.session() as session:
            _, parsed = read(session, actor.user_id, str(dossier_id), str(snapshot_id))
            # Access-account and policy evidence stays inside the private store.
            return {"snapshot_id": str(parsed.snapshot_id), "content_sha256": parsed.content_sha256,
                    "parse_status": parsed.parse_status,
                    "passages": [p.model_dump() for p in parsed.passages]}

    @router.get("/dossiers/{dossier_id}/documents/{snapshot_id}/original")
    def document_original(dossier_id: UUID, snapshot_id: UUID, actor: Identity = Depends(identity)):
        from .docx_reader import EXTRACTOR as DOCX_EXTRACTOR
        from .tender_documents import read

        with service.db.session() as session:
            row, parsed = read(session, actor.user_id, str(dossier_id), str(snapshot_id))
            extension = "pdf" if row.body.startswith(b"%PDF") else "bin"
            if parsed.extractor_version == DOCX_EXTRACTOR and parsed.parse_status in {"complete", "partial"}:
                extension = "docx"
            return Response(row.body, media_type="application/octet-stream", headers={
                "Content-Disposition": f'attachment; filename="tender-{snapshot_id}.{extension}"',
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox",
            })

    @router.post("/dossiers/{dossier_id}/follow")
    def follow(dossier_id: UUID, body: FollowBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = lifecycle.follow(
                session, actor.user_id, str(dossier_id), body.expected_version, body.following
            )
            session.commit()
            return result

    @router.post("/dossiers/{dossier_id}/decision")
    def decision(dossier_id: UUID, body: DecisionBody, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            result = repository.record_decision(
                session,
                actor.user_id,
                str(dossier_id),
                version=body.expected_version,
                sequence=body.sequence,
                decision=body.decision,
                key=str(body.request_key),
            )
            session.commit()
            return result

    return router
