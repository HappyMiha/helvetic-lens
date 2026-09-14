"""Shared IPI acquisition evidence; never private portfolio queries or credentials."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class IPIIdentity(Base):
    __tablename__ = "ipi_identities"
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    canonical_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    origin: Mapped[str] = mapped_column(String(40))


class IPIAlias(Base):
    __tablename__ = "ipi_aliases"
    __table_args__ = (ForeignKeyConstraint(["source_key", "canonical_hash"],
        ["ipi_identities.source_key", "ipi_identities.canonical_hash"]),)
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    alias_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_hash: Mapped[str] = mapped_column(String(64))


class IPITraversal(Base):
    __tablename__ = "ipi_traversals"
    __table_args__ = (
        CheckConstraint("generation >= 1 AND next_offset >= 0 AND page_count >= 0 AND duplicate_count >= 0 AND unique_count >= 0",
            name="ck_ipi_traversal_counts"),
        CheckConstraint("state IN ('running', 'completed', 'abandoned')", name="ck_ipi_traversal_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_key: Mapped[str] = mapped_column(String(80), index=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("trademark_source_permissions.id"), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_offset: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    last_total: Mapped[int | None] = mapped_column(Integer)
    totals_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    next_request: Mapped[bytes | None] = mapped_column(LargeBinary)
    next_request_hash: Mapped[str | None] = mapped_column(String(64))
    request_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(100))


class IPIPageEvidence(Base):
    __tablename__ = "ipi_page_evidence"
    __table_args__ = (
        UniqueConstraint("traversal_id", "request_hash", name="uq_ipi_page_request"),
        CheckConstraint("page_index >= 0 AND item_offset >= 0 AND item_count >= 0 AND total_count >= 0",
            name="ck_ipi_page_counts"),
    )
    traversal_id: Mapped[str] = mapped_column(ForeignKey("ipi_traversals.id"), primary_key=True)
    page_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_hash: Mapped[str] = mapped_column(String(64))
    xml_hash: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    raw_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    item_offset: Mapped[int] = mapped_column(Integer)
    item_count: Mapped[int] = mapped_column(Integer)
    total_count: Mapped[int] = mapped_column(Integer)
    journal_cursor: Mapped[int] = mapped_column(Integer)


class IPISeenIdentity(Base):
    __tablename__ = "ipi_seen_identities"
    traversal_id: Mapped[str] = mapped_column(ForeignKey("ipi_traversals.id"), primary_key=True)
    canonical_hash: Mapped[str] = mapped_column(String(64), primary_key=True)


class IPITokenCache(Base):
    __tablename__ = "ipi_token_cache"
    account_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
