"""Private candidate references and audit; licensed register facts stay in the journal."""

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


class TrademarkCalibration(Base):
    __tablename__ = "trademark_calibrations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrademarkCalibrationSelection(Base):
    __tablename__ = "trademark_calibration_selections"
    language: Mapped[str] = mapped_column(String(2), primary_key=True)
    calibration_id: Mapped[str] = mapped_column(ForeignKey("trademark_calibrations.id"))


class TrademarkRuntime(Base):
    __tablename__ = "trademark_runtimes"
    __table_args__ = (ForeignKeyConstraint(["monitor_id", "organization_id"],
        ["trademark_monitors.id", "trademark_monitors.organization_id"], ondelete="CASCADE"),)
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    health: Mapped[str] = mapped_column(String(24), default="waiting")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    unavailable_count: Mapped[int] = mapped_column(Integer, default=0)


class TrademarkProjectionCursor(Base):
    __tablename__ = "trademark_projection_cursors"
    __table_args__ = (ForeignKeyConstraint(["monitor_id", "organization_id"],
        ["trademark_monitors.id", "trademark_monitors.organization_id"], ondelete="CASCADE"),)
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("trademark_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer)
    after_key: Mapped[str | None] = mapped_column(String(64))


class TrademarkCandidate(Base):
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    deadline_binding: Mapped[dict | None] = mapped_column(JSON)
    __tablename__ = "trademark_candidates"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["trademark_monitors.id", "trademark_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_trademark_candidate_scope"),
        UniqueConstraint("monitor_id", "source_key", "record_key", "brand_key", name="uq_trademark_candidate_identity"),
        CheckConstraint("version >= 1 AND sequence >= 1 AND reviewed_sequence >= 0 AND reviewed_sequence <= sequence", name="ck_trademark_candidate_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    source_key: Mapped[str] = mapped_column(String(80))
    record_key: Mapped[str] = mapped_column(String(64))
    brand_key: Mapped[str] = mapped_column(String(64))
    permission_id: Mapped[str] = mapped_column(ForeignKey("trademark_source_permissions.id"))
    source_generation: Mapped[int] = mapped_column(Integer)
    source_revision_id: Mapped[str] = mapped_column(ForeignKey("trademark_register_revisions.id"))
    profile_revision: Mapped[int] = mapped_column(Integer)
    evaluation_hash: Mapped[str] = mapped_column(String(64))
    calibration_ids: Mapped[list] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_sequence: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrademarkCandidateEvent(Base):
    deadline_binding: Mapped[dict | None] = mapped_column(JSON)
    __tablename__ = "trademark_candidate_events"
    __table_args__ = (
        ForeignKeyConstraint(["candidate_id", "organization_id"], ["trademark_candidates.id", "trademark_candidates.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("candidate_id", "sequence", name="uq_trademark_candidate_event"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    source_revision_id: Mapped[str] = mapped_column(ForeignKey("trademark_register_revisions.id"))
    previous_revision_id: Mapped[str | None] = mapped_column(ForeignKey("trademark_register_revisions.id"))
    profile_revision: Mapped[int] = mapped_column(Integer)
    calibration_ids: Mapped[list] = mapped_column(JSON)
    evaluation_hash: Mapped[str] = mapped_column(String(64))
    change_codes: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrademarkReview(Base):
    __tablename__ = "trademark_reviews"
    __table_args__ = (
        ForeignKeyConstraint(["candidate_id", "organization_id"], ["trademark_candidates.id", "trademark_candidates.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("candidate_id", "candidate_version", name="uq_trademark_review_version"),
        CheckConstraint("decision IN ('reviewed','relevant','not_relevant','monitor','counsel')", name="ck_trademark_review_decision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    candidate_version: Mapped[int] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer)
    source_revision_id: Mapped[str] = mapped_column(ForeignKey("trademark_register_revisions.id"))
    profile_revision: Mapped[int] = mapped_column(Integer)
    evaluation_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrademarkExportPreparation(Base):
    """Short-lived private references; the permitted document is rebuilt on every read."""
    __tablename__ = "trademark_export_preparations"
    __table_args__ = (
        ForeignKeyConstraint(["candidate_id", "organization_id"], ["trademark_candidates.id", "trademark_candidates.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("candidate_id", "request_key", name="uq_trademark_export_request"),
        CheckConstraint("candidate_version >= 1 AND expires_at > created_at", name="ck_trademark_export_validity"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    candidate_version: Mapped[int] = mapped_column(Integer)
    source_revision_id: Mapped[str] = mapped_column(ForeignKey("trademark_register_revisions.id"))
    event_id: Mapped[str | None] = mapped_column(ForeignKey("trademark_candidate_events.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(5))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
