"""Private consent revisions and reference-only river notification intents."""

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


class RiverEmailPolicy(Base):
    __tablename__ = "river_email_policies"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["river_monitors.id", "river_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("revision >= 1", name="ck_river_email_revision"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RiverDelivery(Base):
    __tablename__ = "river_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["river_monitors.id", "river_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["monitor_id", "consent_revision"], ["river_email_policies.monitor_id", "river_email_policies.revision"], ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "signal_hash", "consent_revision", name="uq_river_delivery_intent"),
        CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_river_delivery_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("river_changes.id", ondelete="CASCADE"), index=True)
    consent_revision: Mapped[int] = mapped_column(Integer)
    signal_hash: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
