"""Separate private story references and reviewed cross-source geography.

No source payload, original document or copied domain decision belongs here.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class RelatedPlaceBinding(Base):
    __tablename__ = "related_place_bindings"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_related_place_fingerprint"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    feature_key: Mapped[str] = mapped_column(String(64), index=True)
    source_revision: Mapped[str] = mapped_column(String(64), index=True)
    binding: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64))
    reviewed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RelatedStory(Base):
    __tablename__ = "related_stories"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_related_story_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_related_story_request"),
        CheckConstraint("version >= 1", name="ck_related_story_version"),
        CheckConstraint("status IN ('active','archived')", name="ck_related_story_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RelatedStoryRevision(Base):
    __tablename__ = "related_story_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["story_id", "organization_id"], ["related_stories.id", "related_stories.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("story_id", "revision", name="uq_related_story_revision"),
        UniqueConstraint("story_id", "request_key", name="uq_related_revision_request"),
        CheckConstraint("revision >= 1", name="ck_related_revision_number"),
        CheckConstraint("action IN ('create','revise','split','merge','archive','restore')", name="ck_related_revision_action"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    story_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(12))
    # User title + immutable member references + association proof, no source facts.
    snapshot: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64))
    previous_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
