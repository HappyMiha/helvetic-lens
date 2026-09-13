"""Permission-scoped register evidence, independent of private brand portfolios."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
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


class TrademarkSourcePermission(Base):
    __tablename__ = "trademark_source_permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    policy: Mapped[dict] = mapped_column(JSON)
    policy_hash: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrademarkSourceSelection(Base):
    __tablename__ = "trademark_source_selections"
    __table_args__ = (CheckConstraint("generation >= 1 AND cursor_version >= 0", name="ck_trademark_source_selection"),)
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("trademark_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer)
    cursor_version: Mapped[int] = mapped_column(Integer, default=0)
    last_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrademarkRegisterRevision(Base):
    __tablename__ = "trademark_register_revisions"
    __table_args__ = (
        UniqueConstraint("permission_id", "record_key", "sequence", name="uq_trademark_register_sequence"),
        UniqueConstraint("id", "permission_id", "record_key", name="uq_trademark_register_scope"),
        CheckConstraint("sequence >= 1 AND material_sequence >= 1", name="ck_trademark_register_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("trademark_source_permissions.id"), index=True)
    record_key: Mapped[str] = mapped_column(String(64))
    sequence: Mapped[int] = mapped_column(Integer)
    material_sequence: Mapped[int] = mapped_column(Integer)
    material_hash: Mapped[str] = mapped_column(String(64))
    raw_hash: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    raw_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    normalized_hash: Mapped[str] = mapped_column(String(64))
    normalized_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    normalized_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrademarkRegisterHead(Base):
    __tablename__ = "trademark_register_heads"
    __table_args__ = (
        ForeignKeyConstraint(["revision_id", "permission_id", "record_key"],
            ["trademark_register_revisions.id", "trademark_register_revisions.permission_id", "trademark_register_revisions.record_key"],
            name="fk_trademark_head_revision"),
        CheckConstraint("generation >= 1", name="ck_trademark_head_generation"),
    )
    permission_id: Mapped[str] = mapped_column(ForeignKey("trademark_source_permissions.id"), primary_key=True)
    record_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision_id: Mapped[str] = mapped_column(String(36))
    generation: Mapped[int] = mapped_column(Integer)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrademarkSourceReceipt(Base):
    __tablename__ = "trademark_source_receipts"
    __table_args__ = (
        UniqueConstraint("permission_id", "generation", "request_key", name="uq_trademark_source_request"),
        ForeignKeyConstraint(["revision_id", "permission_id", "record_key"],
            ["trademark_register_revisions.id", "trademark_register_revisions.permission_id", "trademark_register_revisions.record_key"],
            name="fk_trademark_receipt_revision"),
        CheckConstraint("generation >= 1 AND cursor_version >= 1", name="ck_trademark_source_receipt"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("trademark_source_permissions.id"), index=True)
    record_key: Mapped[str] = mapped_column(String(64))
    revision_id: Mapped[str] = mapped_column(String(36))
    generation: Mapped[int] = mapped_column(Integer)
    cursor_version: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    change: Mapped[dict] = mapped_column(JSON)
