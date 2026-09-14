"""Private brand portfolios. Source evidence, calibration and consent are separate."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class TrademarkMonitor(Base):
    __tablename__ = "trademark_monitors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_trademark_monitor_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_trademark_monitor_request"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_trademark_monitor_version"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_trademark_monitor_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    email_revision: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrademarkConfigurationRevision(Base):
    __tablename__ = "trademark_configuration_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["trademark_monitors.id", "trademark_monitors.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "revision", name="uq_trademark_configuration_revision"),
        CheckConstraint("revision >= 1", name="ck_trademark_configuration_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
