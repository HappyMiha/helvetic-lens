"""Internal source evidence only; private Road Watch models are separate."""

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
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class RoadMonitor(Base):
    __tablename__ = "road_monitors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_road_monitor_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_road_monitor_request"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_road_monitor_version"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_road_monitor_status"),
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
    health: Mapped[str] = mapped_column(String(40), default="not_started")
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
        server_default=text("'1970-01-01 00:00:00+00:00'"), index=True)
    email_revision: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoadConfigurationRevision(Base):
    __tablename__ = "road_configuration_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"],
                             ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "revision", name="uq_road_configuration_revision"),
        CheckConstraint("revision >= 1", name="ck_road_configuration_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoadDevelopment(Base):
    __tablename__ = "road_developments"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"],
                             ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_road_development_scope"),
        UniqueConstraint("monitor_id", "configuration_revision", "permission_id", "source_id", name="uq_road_development_identity"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    configuration_revision: Mapped[int] = mapped_column(Integer)
    permission_id: Mapped[str] = mapped_column(ForeignKey("road_source_permissions.id"))
    source_id: Mapped[str] = mapped_column(String(256))
    development_key: Mapped[str] = mapped_column(String(64))
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    payload_hash: Mapped[str] = mapped_column(String(64))
    material_hash: Mapped[str] = mapped_column(String(64))
    proof: Mapped[dict] = mapped_column(JSON)
    proof_hash: Mapped[str] = mapped_column(String(64))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_sequence: Mapped[int] = mapped_column(Integer, default=0)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RoadEventVersion(Base):
    __tablename__ = "road_event_versions"
    __table_args__ = (
        ForeignKeyConstraint(["development_id", "organization_id"], ["road_developments.id", "road_developments.organization_id"],
                             ondelete="CASCADE"),
        UniqueConstraint("development_id", "sequence", name="uq_road_event_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    development_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    payload_hash: Mapped[str] = mapped_column(String(64))
    proof: Mapped[dict] = mapped_column(JSON)
    proof_hash: Mapped[str] = mapped_column(String(64))
    content_size: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RoadSourcePermission(Base):
    __tablename__ = "road_source_permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    policy: Mapped[dict] = mapped_column(JSON)
    policy_hash: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoadTopologyRevision(Base):
    __tablename__ = "road_topology_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    country: Mapped[str] = mapped_column(String(16))
    table: Mapped[str] = mapped_column(String(16))
    version: Mapped[str] = mapped_column(String(64))
    asset_hash: Mapped[str] = mapped_column(String(64))
    topology_hash: Mapped[str] = mapped_column(String(64))
    policy: Mapped[dict] = mapped_column(JSON)
    binding_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_hash: Mapped[str] = mapped_column(String(64))
    content_size: Mapped[int] = mapped_column(Integer)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoadCorridorReference(Base):
    __tablename__ = "road_corridor_references"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    flow_key: Mapped[str] = mapped_column(String(64))
    identity_hash: Mapped[str] = mapped_column(String(64))
    generation: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean)


class RoadCorridorMap(Base):
    __tablename__ = "road_corridor_maps"
    __table_args__ = (UniqueConstraint("reference_id", "generation", name="uq_road_corridor_generation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    reference_id: Mapped[str] = mapped_column(ForeignKey("road_corridor_references.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    topology_id: Mapped[str] = mapped_column(ForeignKey("road_topology_revisions.id"), index=True)
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    binding_hash: Mapped[str] = mapped_column(String(64))
    review_reference: Mapped[str] = mapped_column(String(500))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RoadSourcePoll(Base):
    __tablename__ = "road_source_polls"
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("road_source_permissions.id"))
    next_request_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer, default=0)
    force_full: Mapped[bool] = mapped_column(Boolean, default=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_code: Mapped[str] = mapped_column(String(80), default="not_started")


class RoadSourceHead(Base):
    __tablename__ = "road_source_heads"
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("road_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_full_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_hash: Mapped[str | None] = mapped_column(String(64))


class RoadSourceEvidence(Base):
    __tablename__ = "road_source_evidence"
    __table_args__ = (
        UniqueConstraint("permission_id", "request_id", name="uq_road_evidence_request"),
        UniqueConstraint("permission_id", "generation", name="uq_road_evidence_generation"),
        UniqueConstraint("id", "permission_id", name="uq_road_evidence_permission"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("road_source_permissions.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    previous_generation: Mapped[int] = mapped_column(Integer)
    generation: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(8))
    continuous: Mapped[bool] = mapped_column(Boolean)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_size: Mapped[int] = mapped_column(Integer)
    raw_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RoadSituationVersion(Base):
    __tablename__ = "road_situation_versions"
    __table_args__ = (
        UniqueConstraint("id", "permission_id", "source_id", name="uq_road_version_binding"),
        ForeignKeyConstraint(["evidence_id", "permission_id"],
            ["road_source_evidence.id", "road_source_evidence.permission_id"], name="fk_road_version_evidence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("road_source_permissions.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(256), index=True)
    evidence_id: Mapped[str] = mapped_column(String(36))
    semantic_hash: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_size: Mapped[int] = mapped_column(Integer)
    version_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RoadCurrentSituation(Base):
    __tablename__ = "road_current_situations"
    __table_args__ = (
        ForeignKeyConstraint(["version_id", "permission_id", "source_id"],
            ["road_situation_versions.id", "road_situation_versions.permission_id", "road_situation_versions.source_id"],
            name="fk_road_current_version"),
    )
    permission_id: Mapped[str] = mapped_column(ForeignKey("road_source_permissions.id"), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    version_id: Mapped[str] = mapped_column(String(36))
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    present: Mapped[bool] = mapped_column(Boolean)


class RoadSourceChange(Base):
    __tablename__ = "road_source_changes"
    __table_args__ = (
        UniqueConstraint("permission_id", "generation", "source_id", name="uq_road_change_generation"),
        ForeignKeyConstraint(["evidence_id", "permission_id"],
            ["road_source_evidence.id", "road_source_evidence.permission_id"], name="fk_road_change_evidence"),
        ForeignKeyConstraint(["version_id", "permission_id", "source_id"],
            ["road_situation_versions.id", "road_situation_versions.permission_id", "road_situation_versions.source_id"],
            name="fk_road_change_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("road_source_permissions.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    source_id: Mapped[str] = mapped_column(String(256))
    development_id: Mapped[str] = mapped_column(String(64))
    evidence_id: Mapped[str] = mapped_column(String(36))
    version_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(32))
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    current_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RoadEmailPolicy(Base):
    __tablename__ = "road_email_policies"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("revision >= 1", name="ck_road_email_revision"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoadDelivery(Base):
    __tablename__ = "road_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["development_id", "organization_id"], ["road_developments.id", "road_developments.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["development_id", "sequence"], ["road_event_versions.development_id", "road_event_versions.sequence"], ondelete="CASCADE"),
        ForeignKeyConstraint(["monitor_id", "consent_revision"], ["road_email_policies.monitor_id", "road_email_policies.revision"], ondelete="CASCADE"),
        UniqueConstraint("development_id", "sequence", "consent_revision", name="uq_road_delivery_intent"),
        CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_road_delivery_state"),
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
