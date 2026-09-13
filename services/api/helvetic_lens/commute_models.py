"""Shared verified timetable catalog and separately owned private commutes."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class CommuteStaticPoll(Base):
    __tablename__ = "commute_static_polls"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_code: Mapped[str] = mapped_column(String(80), default="not_started")
    renewal_state: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class CommuteStaticArchive(Base):
    __tablename__ = "commute_static_archives"
    version: Mapped[str] = mapped_column(String(256), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(36))
    resource_id: Mapped[str] = mapped_column(String(36))
    resource_url: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    present: Mapped[bool] = mapped_column(Boolean, default=True)


class CommuteInterchange(Base):
    __tablename__ = "commute_interchanges"
    __table_args__ = (
        ForeignKeyConstraint(["from_reference_id", "service_day", "static_version"],
            ["commute_dated_legs.reference_id", "commute_dated_legs.service_day", "commute_dated_legs.static_version"], ondelete="CASCADE"),
        ForeignKeyConstraint(["to_reference_id", "service_day", "static_version"],
            ["commute_dated_legs.reference_id", "commute_dated_legs.service_day", "commute_dated_legs.static_version"], ondelete="CASCADE"),
    )
    from_reference_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    to_reference_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_day: Mapped[date] = mapped_column(Date, primary_key=True)
    static_version: Mapped[str] = mapped_column(String(256), primary_key=True)
    proof: Mapped[dict] = mapped_column(JSON)
    proof_hash: Mapped[str] = mapped_column(String(64))


class CommuteLegReference(Base):
    __tablename__ = "commute_leg_references"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(500))
    identity: Mapped[dict] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class CommuteDatedLeg(Base):
    __tablename__ = "commute_dated_legs"
    reference_id: Mapped[str] = mapped_column(ForeignKey("commute_leg_references.id", ondelete="CASCADE"), primary_key=True)
    service_day: Mapped[date] = mapped_column(Date, primary_key=True)
    static_version: Mapped[str] = mapped_column(String(256), primary_key=True)
    resolved: Mapped[dict] = mapped_column(JSON)
    resolved_hash: Mapped[str] = mapped_column(String(64))


class CommuteMonitor(Base):
    __tablename__ = "commute_monitors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_commute_monitor_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_commute_monitor_request"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_commute_monitor_version"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_commute_monitor_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    email_revision: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    paused_on: Mapped[date | None] = mapped_column(Date)
    health: Mapped[str] = mapped_column(String(40), default="not_started")
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
        server_default=text("'1970-01-01 00:00:00+00:00'"), index=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommuteConfigurationRevision(Base):
    __tablename__ = "commute_configuration_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["commute_monitors.id", "commute_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "revision", name="uq_commute_configuration_revision"),
        CheckConstraint("revision >= 1", name="ck_commute_configuration_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommuteSourcePermission(Base):
    __tablename__ = "commute_source_permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(40), index=True)
    policy_reference: Mapped[str] = mapped_column(String(500))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_age_seconds: Mapped[int] = mapped_column(Integer)


class CommuteSourcePoll(Base):
    __tablename__ = "commute_source_polls"
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("commute_source_permissions.id"))
    next_request_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_code: Mapped[str | None] = mapped_column(String(50))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommuteFeedState(Base):
    __tablename__ = "commute_feed_states"
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("commute_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer, default=1)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    static_version: Mapped[str | None] = mapped_column(String(256))
    content_hash: Mapped[str] = mapped_column(String(64))
    # Only the latest bounded response per source is retained here.
    content: Mapped[bytes] = mapped_column(LargeBinary)


class CommuteDevelopment(Base):
    __tablename__ = "commute_developments"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["commute_monitors.id", "commute_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_commute_development_scope"),
        UniqueConstraint("monitor_id", "key", name="uq_commute_development_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    configuration_revision: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40))
    permission_id: Mapped[str] = mapped_column(ForeignKey("commute_source_permissions.id"))
    entity_key: Mapped[str] = mapped_column(String(256))
    service_day: Mapped[date] = mapped_column(Date)
    static_version: Mapped[str] = mapped_column(String(256))
    checkpoints: Mapped[dict] = mapped_column(JSON, default=dict)
    observations: Mapped[dict] = mapped_column(JSON, default=dict)
    current: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    reviewed_sequence: Mapped[int] = mapped_column(Integer, default=0)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommuteEventVersion(Base):
    __tablename__ = "commute_event_versions"
    __table_args__ = (
        ForeignKeyConstraint(["development_id", "organization_id"], ["commute_developments.id", "commute_developments.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("development_id", "sequence", name="uq_commute_event_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    development_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[dict] = mapped_column(JSON)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommuteSignal(Base):
    """Private review candidates, not permission to send an email."""

    __tablename__ = "commute_signals"
    __table_args__ = (
        ForeignKeyConstraint(["development_id", "organization_id"], ["commute_developments.id", "commute_developments.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("development_id", "sequence", name="uq_commute_signal_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    development_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    delivery_kind: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommuteEmailPolicy(Base):
    __tablename__ = "commute_email_policies"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["commute_monitors.id", "commute_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("revision >= 1", name="ck_commute_email_revision"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommuteDelivery(Base):
    __tablename__ = "commute_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["commute_monitors.id", "commute_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["development_id", "organization_id"], ["commute_developments.id", "commute_developments.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["development_id", "sequence"], ["commute_event_versions.development_id", "commute_event_versions.sequence"], ondelete="CASCADE"),
        ForeignKeyConstraint(["monitor_id", "consent_revision"], ["commute_email_policies.monitor_id", "commute_email_policies.revision"], ondelete="CASCADE"),
        UniqueConstraint("development_id", "sequence", "consent_revision", name="uq_commute_delivery_intent"),
        CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_commute_delivery_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    development_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    consent_revision: Mapped[int] = mapped_column(Integer)
    signal_hash: Mapped[str] = mapped_column(String(64), index=True)
    priority: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
