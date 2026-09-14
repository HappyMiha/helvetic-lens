"""Append-only workspace-scope and responsibility history for business monitors."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
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


class BusinessMonitorScopeEvent(Base):
    __tablename__ = "business_monitor_scope_events"
    __table_args__ = (
        ForeignKeyConstraint(["tender_monitor_id", "organization_id"], ["tender_monitors.id", "tender_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trademark_monitor_id", "organization_id"], ["trademark_monitors.id", "trademark_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["auction_monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("(CASE WHEN tender_monitor_id IS NULL THEN 0 ELSE 1 END + CASE WHEN trademark_monitor_id IS NULL THEN 0 ELSE 1 END + CASE WHEN auction_monitor_id IS NULL THEN 0 ELSE 1 END) = 1", name="ck_business_scope_target"),
        CheckConstraint("previous_scope IN ('private','workspace') AND scope IN ('private','workspace') AND monitor_version >= 1", name="ck_business_scope_values"),
        UniqueConstraint("tender_monitor_id", "monitor_version", name="uq_business_scope_tender_version"),
        UniqueConstraint("trademark_monitor_id", "monitor_version", name="uq_business_scope_trademark_version"),
        UniqueConstraint("auction_monitor_id", "monitor_version", name="uq_business_scope_auction_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    tender_monitor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    trademark_monitor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    auction_monitor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    monitor_version: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    previous_scope: Mapped[str] = mapped_column(String(12))
    scope: Mapped[str] = mapped_column(String(12))
    responsible_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
