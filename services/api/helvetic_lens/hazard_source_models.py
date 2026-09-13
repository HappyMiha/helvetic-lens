"""Shared permitted public CAP evidence; contains no private locations or consent."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class HazardSourcePermission(Base):
    __tablename__ = "hazard_source_permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    policy: Mapped[dict] = mapped_column(JSON)
    policy_hash: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HazardSourceSelection(Base):
    __tablename__ = "hazard_source_selections"
    __table_args__ = (CheckConstraint("generation >= 1 AND cursor_version >= 0", name="ck_hazard_source_selection_version"),)
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("hazard_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer)
    cursor_version: Mapped[int] = mapped_column(Integer, default=0)
    last_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_poll_hash: Mapped[str | None] = mapped_column(String(64))
    poll_cursor_version: Mapped[int | None] = mapped_column(Integer)


class HazardMessageEvidence(Base):
    __tablename__ = "hazard_message_evidence"
    __table_args__ = (
        UniqueConstraint("permission_id", "message_key", name="uq_hazard_evidence_key"),
        UniqueConstraint("permission_id", "identifier", name="uq_hazard_evidence_identifier"),
        UniqueConstraint("id", "permission_id", name="uq_hazard_evidence_permission"),
        UniqueConstraint("id", "permission_id", "development_key", name="uq_hazard_evidence_development"),
        CheckConstraint("material_sequence >= 1", name="ck_hazard_evidence_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("hazard_source_permissions.id"), index=True)
    message_key: Mapped[str] = mapped_column(String(64))
    identifier: Mapped[str] = mapped_column(String(256))
    development_key: Mapped[str] = mapped_column(String(64))
    raw_hash: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    raw_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    normalized_hash: Mapped[str] = mapped_column(String(64))
    normalized_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    normalized_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    first_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    material_sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    material: Mapped[bool] = mapped_column(Boolean)
    classification: Mapped[dict] = mapped_column(JSON)
    reference_keys: Mapped[list] = mapped_column(JSON)


class HazardCurrentWarning(Base):
    __tablename__ = "hazard_current_warnings"
    __table_args__ = (
        ForeignKeyConstraint(["evidence_id", "permission_id", "development_key"],
            ["hazard_message_evidence.id", "hazard_message_evidence.permission_id", "hazard_message_evidence.development_key"],
            name="fk_hazard_current_evidence"),
        CheckConstraint("material_sequence >= 1 AND generation >= 1", name="ck_hazard_current_version"),
        CheckConstraint("state IN ('active','resolved','cancelled')", name="ck_hazard_current_state"),
    )
    permission_id: Mapped[str] = mapped_column(ForeignKey("hazard_source_permissions.id"), primary_key=True)
    development_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36))
    generation: Mapped[int] = mapped_column(Integer)
    material_sequence: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(12))


class HazardSourceReceipt(Base):
    __tablename__ = "hazard_source_receipts"
    __table_args__ = (
        UniqueConstraint("permission_id", "generation", "request_key", name="uq_hazard_receipt_request"),
        ForeignKeyConstraint(["evidence_id", "permission_id"], ["hazard_message_evidence.id", "hazard_message_evidence.permission_id"],
                             name="fk_hazard_receipt_evidence"),
        CheckConstraint("generation >= 1 AND cursor_version >= 1", name="ck_hazard_receipt_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("hazard_source_permissions.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(String(36))
    generation: Mapped[int] = mapped_column(Integer)
    cursor_version: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    change: Mapped[dict] = mapped_column(JSON)
