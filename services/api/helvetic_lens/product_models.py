"""Product workspaces reuse native monitoring profiles and evidence storage."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
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


class ProductDossier(Base):
    __tablename__ = "product_dossiers"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_product_dossier_org"),
        UniqueConstraint("organization_id", "product", "creation_key", name="uq_product_dossier_creation"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product: Mapped[str] = mapped_column(String(20))
    profile_id: Mapped[str] = mapped_column(ForeignKey("legal_monitoring_profiles.id", ondelete="CASCADE"), unique=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    priority: Mapped[str] = mapped_column(String(12), default="normal", server_default="normal")
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    next_review_on: Mapped[date | None] = mapped_column(Date)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DossierEntry(Base):
    __tablename__ = "product_dossier_entries"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("dossier_id", "request_key", name="uq_product_entry_request"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    thread_id: Mapped[str | None] = mapped_column(ForeignKey("product_research_threads.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(240), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_key: Mapped[str | None] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DossierAction(Base):
    __tablename__ = "product_dossier_actions"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("dossier_id", "creation_key", name="uq_product_action_creation"),
        CheckConstraint("status IN ('open', 'in_progress', 'done', 'cancelled')", name="ck_product_action_status"),
        CheckConstraint("priority IN ('normal', 'high', 'urgent')", name="ck_product_action_priority"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(240))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(12), default="normal")
    assignee_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_on: Mapped[date | None] = mapped_column(Date, index=True)
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchThread(Base):
    __tablename__ = "product_research_threads"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("dossier_id", "creation_key", name="uq_research_thread_creation"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    # Checked against this thread's entries on every acceptance; avoiding a FK
    # cycle keeps private dossier erasure in containment order.
    accepted_entry_id: Mapped[str | None] = mapped_column(String(36))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductPublication(Base):
    """Explicitly authored public projection; never serialize its private parent."""
    __tablename__ = "product_publications"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_product_publication_org"),
        UniqueConstraint("dossier_id", name="uq_product_publication_dossier"),
        CheckConstraint("status IN ('published', 'withdrawn')", name="ck_product_publication_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36))
    product: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(String(1500))
    body: Mapped[str] = mapped_column(Text)
    author_label: Mapped[str] = mapped_column(String(100))
    sources_json: Mapped[list] = mapped_column(JSON, default=list)
    first_published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicationRevision(Base):
    """Private immutable audit including idempotency and explicit public consent."""
    __tablename__ = "product_publication_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["publication_id", "organization_id"],
                             ["product_publications.id", "product_publications.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("publication_id", "revision", name="uq_product_publication_revision"),
        UniqueConstraint("publication_id", "request_key", name="uq_product_publication_request"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    publication_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(20))
    content_json: Mapped[dict] = mapped_column(JSON)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
