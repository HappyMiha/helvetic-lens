"""Private named-location drafts. Source evidence and consent are separate."""

from datetime import datetime
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


class HazardMonitor(Base):
    __tablename__ = "hazard_monitors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_hazard_monitor_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_hazard_monitor_request"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_hazard_monitor_version"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_hazard_monitor_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    health: Mapped[str] = mapped_column(String(32), default="not_started", server_default="not_started")
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    email_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    activation_proof: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HazardConfigurationRevision(Base):
    __tablename__ = "hazard_configuration_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "revision", name="uq_hazard_configuration_revision"),
        CheckConstraint("revision >= 1", name="ck_hazard_configuration_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HazardMonitorAction(Base):
    __tablename__ = "hazard_monitor_actions"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "version", name="uq_hazard_monitor_action_version"),
        CheckConstraint("action IN ('start','resume','pause','archive')", name="ck_hazard_monitor_action"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(12))
    previous_status: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12))
    version: Mapped[int] = mapped_column(Integer)
    configuration_revision: Mapped[int] = mapped_column(Integer)
    proof: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HazardDevelopment(Base):
    __tablename__ = "hazard_developments"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_hazard_development_scope"),
        UniqueConstraint("monitor_id", "configuration_revision", "permission_id", "source_development_key", name="uq_hazard_private_development"),
        CheckConstraint("configuration_revision >= 1 AND revision >= 1 AND material_sequence >= 1 AND version >= 1", name="ck_hazard_development_version"),
        CheckConstraint("reviewed_sequence >= 0 AND reviewed_sequence <= material_sequence AND dismissed_sequence >= 0 AND dismissed_sequence <= material_sequence", name="ck_hazard_development_review"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    configuration_revision: Mapped[int] = mapped_column(Integer)
    permission_id: Mapped[str] = mapped_column(ForeignKey("hazard_source_permissions.id"))
    source_development_key: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    material_sequence: Mapped[int] = mapped_column(Integer, default=1)
    material_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_sequence: Mapped[int] = mapped_column(Integer, default=0)
    dismissed_sequence: Mapped[int] = mapped_column(Integer, default=0)


class HazardEventRevision(Base):
    __tablename__ = "hazard_event_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["development_id", "organization_id"], ["hazard_developments.id", "hazard_developments.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["evidence_id", "permission_id"], ["hazard_message_evidence.id", "hazard_message_evidence.permission_id"], name="fk_hazard_event_source"),
        UniqueConstraint("development_id", "revision", name="uq_hazard_event_revision"),
        UniqueConstraint("id", "organization_id", name="uq_hazard_event_scope"),
        CheckConstraint("revision >= 1 AND material_sequence >= 1", name="ck_hazard_event_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    development_id: Mapped[str] = mapped_column(String(36), index=True)
    permission_id: Mapped[str] = mapped_column(String(36))
    evidence_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    material_sequence: Mapped[int] = mapped_column(Integer)
    decision: Mapped[dict] = mapped_column(JSON)
    proof: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HazardReviewAction(Base):
    __tablename__ = "hazard_review_actions"
    __table_args__ = (
        ForeignKeyConstraint(["event_revision_id", "organization_id"], ["hazard_event_revisions.id", "hazard_event_revisions.organization_id"], ondelete="CASCADE"),
        CheckConstraint("action IN ('reviewed','not_relevant')", name="ck_hazard_review_action"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    event_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HazardMute(Base):
    __tablename__ = "hazard_mutes"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("hazard IN ('flood','storm','forest_fire','heavy_snow','power_outage','civil_protection_warning')", name="ck_hazard_mute_type"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    hazard: Mapped[str] = mapped_column(String(32), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    muted: Mapped[bool] = mapped_column(Boolean)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HazardEmailPolicy(Base):
    __tablename__ = "hazard_email_policies"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("revision >= 1", name="ck_hazard_email_revision"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HazardDelivery(Base):
    __tablename__ = "hazard_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["development_id", "organization_id"], ["hazard_developments.id", "hazard_developments.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["development_id", "revision"], ["hazard_event_revisions.development_id", "hazard_event_revisions.revision"], ondelete="CASCADE"),
        ForeignKeyConstraint(["monitor_id", "consent_revision"], ["hazard_email_policies.monitor_id", "hazard_email_policies.revision"], ondelete="CASCADE"),
        UniqueConstraint("development_id", "material_sequence", "consent_revision", name="uq_hazard_delivery_intent"),
        CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_hazard_delivery_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    development_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    material_sequence: Mapped[int] = mapped_column(Integer)
    consent_revision: Mapped[int] = mapped_column(Integer)
    signal_hash: Mapped[str] = mapped_column(String(64), index=True)
    priority: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
