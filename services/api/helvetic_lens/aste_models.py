"""Resumable shared acquisition, isolated from private buyer profiles."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class AsteCollector(Base):
    __tablename__ = "aste_collectors"
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("auction_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer)
    listing_queue: Mapped[list] = mapped_column(JSON, default=list)
    visited: Mapped[list] = mapped_column(JSON, default=list)
    category_labels: Mapped[dict] = mapped_column(JSON, default=dict)
    discovery_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_request_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_record_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_job: Mapped[dict | None] = mapped_column(JSON)
    prefer_listing: Mapped[bool] = mapped_column(default=True)
    last_error: Mapped[str | None] = mapped_column(String(100))


class AsteItem(Base):
    __tablename__ = "aste_items"
    identifier: Mapped[str] = mapped_column(String(20), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("auction_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_record_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stage: Mapped[str] = mapped_column(String(16), default="detail")
    category_proofs: Mapped[dict] = mapped_column(JSON, default=dict)
    detail_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    detail_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    documents: Mapped[list] = mapped_column(JSON, default=list)
    document_index: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(100))


class AsteListingEvidence(Base):
    __tablename__ = "aste_listing_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    permission_id: Mapped[str] = mapped_column(ForeignKey("auction_source_permissions.id"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    raw_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    raw_hash: Mapped[str] = mapped_column(String(64))
    metadata_hash: Mapped[str] = mapped_column(String(64))
    raw_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    normalized_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category_id: Mapped[str | None] = mapped_column(String(20))
    category_label: Mapped[str | None] = mapped_column(String(200))
    identifiers: Mapped[list | None] = mapped_column(JSON)
