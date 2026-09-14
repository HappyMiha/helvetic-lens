"""Private auction interest profiles. Source evidence, calibration and consent are separate."""

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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class AuctionMonitor(Base):
    __tablename__ = "auction_monitors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_auction_monitor_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_auction_monitor_request"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_auction_monitor_version"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_auction_monitor_status"),
        CheckConstraint("visibility IN ('private','workspace')", name="ck_auction_monitor_visibility"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    visibility: Mapped[str] = mapped_column(String(12), default="private", server_default="private")
    responsible_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    email_revision: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(12), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuctionConfigurationRevision(Base):
    __tablename__ = "auction_configuration_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "revision", name="uq_auction_configuration_revision"),
        CheckConstraint("revision >= 1", name="ck_auction_configuration_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
