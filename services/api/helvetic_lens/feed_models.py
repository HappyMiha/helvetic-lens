"""Owner-private reusable feeds, immutable observations and explicit dossier admission."""
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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class Feed(Base):
    __tablename__ = "product_feeds"
    __table_args__ = (UniqueConstraint("id", "organization_id"),
        CheckConstraint("status IN ('active','paused')"), CheckConstraint("product IN ('loyer','pharma')"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(160))
    query: Mapped[str] = mapped_column(String(300))
    sources_json: Mapped[list] = mapped_column(JSON, default=list)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(500))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedUpdate(Base):
    __tablename__ = "product_feed_updates"
    __table_args__ = (ForeignKeyConstraint(["feed_id", "organization_id"],
        ["product_feeds.id", "product_feeds.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("feed_id", "sequence"), UniqueConstraint("id", "organization_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    feed_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    source_key: Mapped[str] = mapped_column(String(2048), index=True)
    title: Mapped[str] = mapped_column(String(700))
    url: Mapped[str] = mapped_column(String(2048))
    summary: Mapped[str] = mapped_column(Text, default="")
    source_text: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64))
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedDossierLink(Base):
    __tablename__ = "product_feed_links"
    __table_args__ = (ForeignKeyConstraint(["feed_id", "organization_id"],
        ["product_feeds.id", "product_feeds.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["dossier_id", "organization_id"],
        ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("feed_id", "dossier_id"), UniqueConstraint("id", "organization_id"),
        CheckConstraint("status IN ('active','detached')"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    feed_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="active")
    public_question: Mapped[str] = mapped_column(String(300))
    cursor_sequence: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedImport(Base):
    __tablename__ = "product_feed_imports"
    __table_args__ = (ForeignKeyConstraint(["link_id", "organization_id"],
        ["product_feed_links.id", "product_feed_links.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["update_id", "organization_id"],
        ["product_feed_updates.id", "product_feed_updates.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("link_id", "update_id"), CheckConstraint("status IN ('pending','seeded')"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    link_id: Mapped[str] = mapped_column(String(36), index=True)
    update_id: Mapped[str] = mapped_column(String(36), index=True)
    investigation_id: Mapped[str | None] = mapped_column(ForeignKey("product_investigations.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedReceipt(Base):
    __tablename__ = "product_feed_receipts"
    __table_args__ = (UniqueConstraint("owner_user_id", "request_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedCheck(Base):
    __tablename__ = "product_feed_checks"
    __table_args__ = (ForeignKeyConstraint(["feed_id", "organization_id"],
        ["product_feeds.id", "product_feeds.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("job_id"), CheckConstraint("status IN ('queued','running','completed','partial','failed','cancelled')"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    feed_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    feed_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    receipts_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FeedAssessment(Base):
    __tablename__ = "product_feed_assessments"
    __table_args__ = (ForeignKeyConstraint(["feed_id", "organization_id"],
        ["product_feeds.id", "product_feeds.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["update_id", "organization_id"],
        ["product_feed_updates.id", "product_feed_updates.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("update_id", "spec_binding", "decision_key"),
        CheckConstraint("verdict IN ('relevant','uncertain','unrelated','unavailable')"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    feed_id: Mapped[str] = mapped_column(String(36), index=True)
    update_id: Mapped[str] = mapped_column(String(36), index=True)
    spec_binding: Mapped[str] = mapped_column(String(64), index=True)
    plan_binding: Mapped[str] = mapped_column(String(64))
    decision_key: Mapped[str] = mapped_column(String(64))
    verdict: Mapped[str] = mapped_column(String(16), index=True)
    decision_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


SCOPED = (Feed, FeedUpdate, FeedDossierLink, FeedImport, FeedReceipt, FeedCheck, FeedAssessment)
