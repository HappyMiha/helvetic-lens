"""Workspace dossiers with immutable evidence revisions and editorial decisions."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class InfluenceDossier(Base):
    __tablename__ = "influence_dossiers"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_influence_dossier_org"),
        UniqueConstraint("organization_id", "creation_key", name="uq_influence_creation"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    creation_key: Mapped[str] = mapped_column(String(36))
    creation_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(240))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InfluenceRevision(Base):
    __tablename__ = "influence_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dossier_id", "organization_id"],
            ["influence_dossiers.id", "influence_dossiers.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("dossier_id", "request_key", name="uq_influence_revision_request"),
    )
    dossier_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict] = mapped_column(JSON)
    document_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(12))
    note: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InfluenceReview(Base):
    __tablename__ = "influence_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dossier_id", "organization_id"],
            ["influence_dossiers.id", "influence_dossiers.organization_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["dossier_id", "revision"],
            ["influence_revisions.dossier_id", "influence_revisions.revision"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("dossier_id", "request_key", name="uq_influence_review_request"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
