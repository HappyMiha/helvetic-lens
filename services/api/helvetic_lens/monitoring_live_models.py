"""Durable runtime records, separate from synthetic draft evaluation evidence."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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


def _id():
    return str(uuid4())


class MonitoringRuntime(Base):
    __tablename__ = "monitoring_runtimes"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "organization_id"],
                             ["monitoring_subjects.id", "monitoring_subjects.organization_id"], ondelete="CASCADE"),
        CheckConstraint("version >= 1 AND configuration_revision >= 1", name="ck_runtime_versions"),
    )
    subject_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[str] = mapped_column(String(36))
    configuration_revision: Mapped[int] = mapped_column(Integer)
    email_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health: Mapped[str] = mapped_column(String(40), default="waiting")
    current_stream_ids: Mapped[list] = mapped_column(JSON, default=list)


class MonitoringCommand(Base):
    __tablename__ = "monitoring_commands"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "organization_id"],
                             ["monitoring_subjects.id", "monitoring_subjects.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("subject_id", "request_key", name="uq_monitoring_command_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    request_key: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MonitoringLiveStream(Base):
    __tablename__ = "monitoring_live_streams"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "organization_id"],
                             ["monitoring_subjects.id", "monitoring_subjects.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_live_stream_scope"),
        UniqueConstraint("subject_id", "run_id", "binding_hash", name="uq_live_stream_binding"),
        CheckConstraint("sequence >= 0", name="ck_live_stream_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    binding_hash: Mapped[str] = mapped_column(String(64))
    binding_json: Mapped[dict] = mapped_column(JSON)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MonitoringLiveEntry(Base):
    __tablename__ = "monitoring_live_entries"
    __table_args__ = (
        ForeignKeyConstraint(["stream_id", "organization_id"],
                             ["monitoring_live_streams.id", "monitoring_live_streams.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_live_entry_scope"),
        UniqueConstraint("stream_id", "sequence", name="uq_live_entry_sequence"),
        UniqueConstraint("stream_id", "input_hash", name="uq_live_entry_input"),
        UniqueConstraint("stream_id", "material_id", name="uq_live_entry_material"),
        CheckConstraint("sequence >= 1", name="ck_live_entry_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    stream_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    input_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(40))
    evidence_json: Mapped[dict] = mapped_column(JSON)
    material_id: Mapped[str | None] = mapped_column(String(64))
    signal_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MonitoringReview(Base):
    __tablename__ = "monitoring_reviews"
    __table_args__ = (
        ForeignKeyConstraint(["entry_id", "organization_id"],
                             ["monitoring_live_entries.id", "monitoring_live_entries.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("entry_id", "version", name="uq_monitoring_review_version"),
        CheckConstraint("version >= 1", name="ck_monitoring_review_version"),
        CheckConstraint("decision IN ('reviewed', 'not_relevant', 'continue', 'action_required')", name="ck_monitoring_review_decision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    entry_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MonitoringDelivery(Base):
    __tablename__ = "monitoring_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(["entry_id", "organization_id"],
                             ["monitoring_live_entries.id", "monitoring_live_entries.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("entry_id", "channel", name="uq_monitoring_delivery_entry"),
        CheckConstraint("state IN ('pending', 'sending', 'sent', 'suppressed', 'uncertain')", name="ck_monitoring_delivery_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    entry_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    signal_hash: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="email")
    configuration_revision: Mapped[int] = mapped_column(Integer)
    consent_version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MonitoringSourceArtifact(Base):
    """Public source artifact metadata only; body retained in content-addressed storage."""

    __tablename__ = "monitoring_source_artifacts"
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    identity: Mapped[str] = mapped_column(String(512))
    byte_count: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attribution: Mapped[str] = mapped_column(String(200))


class MonitoringSourceChannel(Base):
    """Shared fetch lease and health; contains only public channel identifiers."""

    __tablename__ = "monitoring_source_channels"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_fetch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
    failures: Mapped[int] = mapped_column(Integer, default=0)


class MonitoringSourceSample(Base):
    """Public normalized source revisions. No user configuration or location."""

    __tablename__ = "monitoring_source_samples"
    __table_args__ = (
        UniqueConstraint("series_hash", "valid_at", "revision", name="uq_source_sample_revision"),
        CheckConstraint("revision >= 1", name="ck_source_sample_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    channel_hash: Mapped[str] = mapped_column(String(64), index=True)
    series_hash: Mapped[str] = mapped_column(String(64), index=True)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=lambda: utcnow() + timedelta(days=30))
    content_hash: Mapped[str] = mapped_column(String(64))
    sample_json: Mapped[dict] = mapped_column(JSON)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
