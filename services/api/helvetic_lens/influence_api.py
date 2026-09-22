"""Tenant-scoped dossier authoring; no public publication or outbound requests."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select, update

from .auth import Identity
from .config import DomainError
from .db import utcnow
from .influence_contract import Archive, Review, Save, fingerprint
from .influence_models import InfluenceDossier, InfluenceReview, InfluenceRevision
from .membership_locks import require_current_admin
from .models import OrganizationMembership, User


def conflict():
    raise DomainError(
        "This dossier changed. Reload the latest revision before saving.", 409, "influence_conflict"
    )


def require_member(session, actor):
    member = session.scalar(
        select(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(
            OrganizationMembership.user_id == actor.user_id,
            OrganizationMembership.organization_id == actor.organization_id,
            User.active.is_(True),
        )
    )
    if member is None:
        raise DomainError("Workspace access is no longer available.", 403, "influence_access")


def get_dossier(session, actor, identifier):
    require_member(session, actor)
    row = session.scalar(
        select(InfluenceDossier).where(
            InfluenceDossier.id == str(identifier), InfluenceDossier.organization_id == actor.organization_id
        )
    )
    if row is None:
        raise DomainError("Dossier not found.", 404, "influence_not_found")
    return row


def summary(row):
    return {
        "id": row.id,
        "title": row.title,
        "revision": row.revision,
        "archived": row.archived,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def review_value(row):
    return {
        "id": row.id,
        "revision": row.revision,
        "decision": row.decision,
        "note": row.note,
        "actorId": row.actor_user_id,
        "createdAt": row.created_at.isoformat(),
    }


def detail(session, row, revision=None):
    number = revision or row.revision
    version = session.scalar(
        select(InfluenceRevision).where(
            InfluenceRevision.dossier_id == row.id,
            InfluenceRevision.organization_id == row.organization_id,
            InfluenceRevision.revision == number,
        )
    )
    if version is None:
        raise DomainError("Revision not found.", 404, "influence_not_found")
    reviews = list(
        session.scalars(
            select(InfluenceReview)
            .where(
                InfluenceReview.dossier_id == row.id,
                InfluenceReview.organization_id == row.organization_id,
                InfluenceReview.revision == number,
            )
            .order_by(InfluenceReview.created_at.desc(), InfluenceReview.id.desc())
            .limit(50)
        )
    )
    # Hash binds the exact retained JSON, including pasted extracts. It is not a
    # claim that the live URL was fetched or the assertions independently verified.
    return {
        **summary(row),
        "viewedRevision": number,
        "document": version.document,
        "documentHash": version.document_hash,
        "note": version.note,
        "actorId": version.actor_user_id,
        "reviews": [review_value(item) for item in reviews],
    }


def append_revision(session, row, actor, *, document, action, body, request_hash):
    number = row.revision + 1
    if number > 500:
        raise DomainError("This dossier reached its 500-revision limit.", 409, "influence_limit")
    changed = session.execute(
        update(InfluenceDossier)
        .where(
            InfluenceDossier.id == row.id,
            InfluenceDossier.organization_id == actor.organization_id,
            InfluenceDossier.revision == body.expectedRevision,
        )
        .values(
            revision=number,
            title=document["title"],
            updated_at=utcnow(),
            archived=body.archived if isinstance(body, Archive) else row.archived,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        conflict()
    session.add(
        InfluenceRevision(
            dossier_id=row.id,
            organization_id=actor.organization_id,
            revision=number,
            request_key=str(body.requestId),
            request_hash=request_hash,
            document=document,
            document_hash=fingerprint(document),
            action=action,
            note=body.note,
            actor_user_id=actor.user_id,
        )
    )
    session.flush()
    session.refresh(row)


def influence_router(service):
    router = APIRouter(prefix="/api/influence/dossiers", tags=["influence"])

    def identity(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        actor = getattr(request.state, "identity", None)
        if actor is None:
            raise DomainError("Sign in to use workspace dossiers.", 401, "authentication_required")
        return actor

    @router.get("")
    def listing(
        archived: bool = False,
        after_id: UUID | None = None,
        limit: int = Query(default=20, ge=1, le=50),
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            require_member(session, actor)
            query = select(InfluenceDossier).where(
                InfluenceDossier.organization_id == actor.organization_id,
                InfluenceDossier.archived == archived,
            )
            if after_id:
                query = query.where(InfluenceDossier.id > str(after_id))
            rows = list(session.scalars(query.order_by(InfluenceDossier.id).limit(limit + 1)))
            return {
                "items": [summary(row) for row in rows[:limit]],
                "nextCursor": rows[limit - 1].id if len(rows) > limit else None,
            }

    @router.post("", status_code=201)
    def create(body: Save, actor: Identity = Depends(identity)):
        if body.expectedRevision != 0:
            conflict()
        request_hash = fingerprint(body.model_dump(mode="json", by_alias=True))
        with service.db.session() as session:
            require_current_admin(session, actor)
            existing = session.scalar(
                select(InfluenceDossier).where(
                    InfluenceDossier.organization_id == actor.organization_id,
                    InfluenceDossier.creation_key == str(body.requestId),
                )
            )
            if existing:
                if existing.creation_hash != request_hash:
                    conflict()
                return detail(session, existing)
            count = session.scalar(
                select(func.count())
                .select_from(InfluenceDossier)
                .where(InfluenceDossier.organization_id == actor.organization_id)
            )
            if count >= 100:
                raise DomainError("The workspace has reached its 100-dossier limit.", 409, "influence_limit")
            document = body.document.model_dump(mode="json", by_alias=True)
            row = InfluenceDossier(
                organization_id=actor.organization_id,
                creation_key=str(body.requestId),
                creation_hash=request_hash,
                title=document["title"],
                revision=1,
                archived=False,
            )
            session.add(row)
            session.flush()
            session.add(
                InfluenceRevision(
                    dossier_id=row.id,
                    organization_id=actor.organization_id,
                    revision=1,
                    request_key=str(body.requestId),
                    request_hash=request_hash,
                    document=document,
                    document_hash=fingerprint(document),
                    action="create",
                    note=body.note,
                    actor_user_id=actor.user_id,
                )
            )
            session.flush()
            result = detail(session, row)
            session.commit()
            return result

    @router.get("/{dossier_id}")
    def read(
        dossier_id: UUID,
        revision: int | None = Query(default=None, ge=1),
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            return detail(session, get_dossier(session, actor, dossier_id), revision)

    @router.patch("/{dossier_id}")
    def save(dossier_id: UUID, body: Save, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            require_current_admin(session, actor)
            row = get_dossier(session, actor, dossier_id)
            request_hash = fingerprint(body.model_dump(mode="json", by_alias=True))
            replay = session.scalar(
                select(InfluenceRevision).where(
                    InfluenceRevision.dossier_id == row.id,
                    InfluenceRevision.request_key == str(body.requestId),
                )
            )
            if replay:
                if replay.request_hash != request_hash or replay.action != "revise":
                    conflict()
                return detail(session, row)
            if row.archived or row.revision != body.expectedRevision:
                conflict()
            append_revision(
                session,
                row,
                actor,
                document=body.document.model_dump(mode="json", by_alias=True),
                action="revise",
                body=body,
                request_hash=request_hash,
            )
            result = detail(session, row)
            session.commit()
            return result

    @router.post("/{dossier_id}/archive")
    def archive(dossier_id: UUID, body: Archive, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            require_current_admin(session, actor)
            row = get_dossier(session, actor, dossier_id)
            request_hash = fingerprint(body.model_dump(mode="json"))
            replay = session.scalar(
                select(InfluenceRevision).where(
                    InfluenceRevision.dossier_id == row.id,
                    InfluenceRevision.request_key == str(body.requestId),
                )
            )
            if replay:
                if replay.request_hash != request_hash or replay.action not in {"archive", "restore"}:
                    conflict()
                return detail(session, row)
            if row.revision != body.expectedRevision or row.archived == body.archived:
                conflict()
            document = detail(session, row)["document"]
            append_revision(
                session,
                row,
                actor,
                document=document,
                action="archive" if body.archived else "restore",
                body=body,
                request_hash=request_hash,
            )
            result = detail(session, row)
            session.commit()
            return result

    @router.get("/{dossier_id}/history")
    def history(
        dossier_id: UUID,
        before_revision: int | None = Query(default=None, ge=1),
        limit: int = Query(default=20, ge=1, le=50),
        actor: Identity = Depends(identity),
    ):
        with service.db.session() as session:
            row = get_dossier(session, actor, dossier_id)
            query = select(InfluenceRevision).where(
                InfluenceRevision.dossier_id == row.id,
                InfluenceRevision.organization_id == actor.organization_id,
            )
            if before_revision:
                query = query.where(InfluenceRevision.revision < before_revision)
            versions = list(
                session.scalars(query.order_by(InfluenceRevision.revision.desc()).limit(limit + 1))
            )
            return {
                "items": [
                    {
                        "revision": version.revision,
                        "action": version.action,
                        "note": version.note,
                        "documentHash": version.document_hash,
                        "actorId": version.actor_user_id,
                        "createdAt": version.created_at.isoformat(),
                    }
                    for version in versions[:limit]
                ],
                "nextCursor": versions[limit - 1].revision if len(versions) > limit else None,
            }

    @router.post("/{dossier_id}/reviews", status_code=201)
    def review(dossier_id: UUID, body: Review, actor: Identity = Depends(identity)):
        with service.db.session() as session:
            require_current_admin(session, actor)
            row = get_dossier(session, actor, dossier_id)
            request_hash = fingerprint(body.model_dump(mode="json"))
            replay = session.scalar(
                select(InfluenceReview).where(
                    InfluenceReview.dossier_id == row.id, InfluenceReview.request_key == str(body.requestId)
                )
            )
            if replay:
                if replay.request_hash != request_hash:
                    conflict()
                return detail(session, row)
            if row.archived or row.revision != body.expectedRevision:
                conflict()
            count = session.scalar(
                select(func.count())
                .select_from(InfluenceReview)
                .where(InfluenceReview.dossier_id == row.id, InfluenceReview.revision == row.revision)
            )
            if count >= 50:
                raise DomainError("This revision has reached its 50-review limit.", 409, "influence_limit")
            session.add(
                InfluenceReview(
                    dossier_id=row.id,
                    organization_id=actor.organization_id,
                    revision=row.revision,
                    request_key=str(body.requestId),
                    request_hash=request_hash,
                    decision=body.decision,
                    note=body.note,
                    actor_user_id=actor.user_id,
                )
            )
            session.flush()
            result = detail(session, row)
            session.commit()
            return result

    return router
