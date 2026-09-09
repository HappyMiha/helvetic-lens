"""Personal acknowledgement of the displayed catalogue, never source activation."""

from datetime import UTC

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import DomainError
from .db import utcnow
from .models import PersonalSourceReview, SourcePackDefinition, SourcePackSubscription
from .source_packs import SOURCE_PACK_CATALOGUE_REVISION


class PackReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=100)
    revision: str = Field(min_length=1, max_length=100)
    enabled: bool


class SourceReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    catalogue_revision: str = Field(min_length=1, max_length=100)
    packs: list[PackReview] = Field(min_length=1, max_length=100)


def snapshot(session, organization_id):
    rows = session.execute(
        select(SourcePackDefinition.id, SourcePackDefinition.revision, SourcePackSubscription.enabled)
        .outerjoin(
            SourcePackSubscription,
            and_(
                SourcePackSubscription.pack_id == SourcePackDefinition.id,
                SourcePackSubscription.organization_id == organization_id,
            ),
        )
        .where(SourcePackDefinition.parent_id.is_not(None), SourcePackDefinition.active.is_(True))
        .order_by(SourcePackDefinition.id)
        .limit(101)
    ).all()
    if len(rows) > 100:
        raise DomainError(
            "The source catalogue is too large for this review. Contact the administrator.",
            409,
            "source_review_limit",
        )
    return {
        "catalogue_revision": SOURCE_PACK_CATALOGUE_REVISION,
        "packs": [{"id": row.id, "revision": row.revision, "enabled": bool(row.enabled)} for row in rows],
    }


def read(session, organization_id, principal):
    row = session.execute(
        select(
            PersonalSourceReview.snapshot_json,
            PersonalSourceReview.first_reviewed_at,
            PersonalSourceReview.reviewed_at,
        ).where(
            PersonalSourceReview.organization_id == organization_id,
            PersonalSourceReview.principal_key == principal,
        )
    ).first()
    if row is None:
        return None

    def date(value):
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()

    return {
        "snapshot": row.snapshot_json,
        "first_reviewed_at": date(row.first_reviewed_at),
        "reviewed_at": date(row.reviewed_at),
        "current": row.snapshot_json == snapshot(session, organization_id),
    }


def save(session, organization_id, principal, user_id, data):
    expected = data.model_dump()
    expected["packs"].sort(key=lambda item: item["id"])
    current = snapshot(session, organization_id)
    if expected != current:
        raise DomainError(
            "The source selection changed. Reload the source packages and review them again.",
            409,
            "source_review_changed",
        )
    now = utcnow()
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    session.execute(
        insert(PersonalSourceReview)
        .values(
            organization_id=organization_id,
            principal_key=principal,
            user_id=user_id,
            snapshot_json=current,
            first_reviewed_at=now,
            reviewed_at=now,
        )
        .on_conflict_do_nothing(index_elements=["organization_id", "principal_key"])
    )
    row = session.scalar(
        select(PersonalSourceReview)
        .where(
            PersonalSourceReview.organization_id == organization_id,
            PersonalSourceReview.principal_key == principal,
        )
        .with_for_update()
    )
    if row.snapshot_json != current:
        row.snapshot_json = current
        row.reviewed_at = now
    session.commit()
    return read(session, organization_id, principal)
