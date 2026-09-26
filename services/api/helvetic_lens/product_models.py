"""Product workspaces reuse native monitoring profiles and evidence storage."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
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
