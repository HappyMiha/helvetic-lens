"""Private auction tracking and review metadata; source payloads stay in the journal."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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


class AuctionRuntime(Base):
    __tablename__ = "auction_runtimes"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    health: Mapped[str] = mapped_column(String(40), default="not_started")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AuctionSourceCursor(Base):
    __tablename__ = "auction_private_source_cursors"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("generation >= 1", name="ck_auction_private_cursor_generation"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("auction_source_permissions.id"))
    generation: Mapped[int] = mapped_column(Integer)
    after_key: Mapped[str | None] = mapped_column(String(64))


class AuctionItem(Base):
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    __tablename__ = "auction_items"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["source_revision_id", "permission_id", "record_key"],
            ["auction_source_record_revisions.id", "auction_source_record_revisions.permission_id", "auction_source_record_revisions.record_key"]),
        UniqueConstraint("id", "organization_id", name="uq_auction_item_scope"),
        UniqueConstraint("monitor_id", "record_key", name="uq_auction_item_identity"),
        CheckConstraint("version >= 1 AND material_sequence >= 1 AND reviewed_sequence >= 0 AND deadline_generation >= 1", name="ck_auction_item_versions"),
        CheckConstraint("decision IS NULL OR decision IN ('inspect','bid','no_bid','monitor')", name="ck_auction_item_decision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    record_key: Mapped[str] = mapped_column(String(64))
    source_key: Mapped[str] = mapped_column(String(80))
    permission_id: Mapped[str] = mapped_column(ForeignKey("auction_source_permissions.id"))
    source_revision_id: Mapped[str] = mapped_column(String(36))
    source_generation: Mapped[int] = mapped_column(Integer)
    profile_revision: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    material_sequence: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_sequence: Mapped[int] = mapped_column(Integer, default=0)
    following: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str | None] = mapped_column(String(12))
    deadline_generation: Mapped[int] = mapped_column(Integer, default=1)
    deadline_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuctionItemEvent(Base):
    __tablename__ = "auction_item_events"
    __table_args__ = (
        ForeignKeyConstraint(["item_id", "organization_id"], ["auction_items.id", "auction_items.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("item_id", "sequence", name="uq_auction_item_event_sequence"),
        CheckConstraint("sequence >= 1 AND profile_revision >= 1", name="ck_auction_item_event_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    source_revision_id: Mapped[str] = mapped_column(ForeignKey("auction_source_record_revisions.id"))
    previous_revision_id: Mapped[str | None] = mapped_column(ForeignKey("auction_source_record_revisions.id"))
    profile_revision: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))
    change_codes: Mapped[list] = mapped_column(JSON)
    notify: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AuctionDecision(Base):
    __tablename__ = "auction_decisions"
    __table_args__ = (
        ForeignKeyConstraint(["item_id", "organization_id"], ["auction_items.id", "auction_items.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("item_id", "item_version", name="uq_auction_decision_version"),
        CheckConstraint("decision IS NULL OR decision IN ('inspect','bid','no_bid','monitor')", name="ck_auction_decision_value"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    item_version: Mapped[int] = mapped_column(Integer)
    material_sequence: Mapped[int] = mapped_column(Integer)
    source_revision_id: Mapped[str] = mapped_column(ForeignKey("auction_source_record_revisions.id"))
    decision: Mapped[str | None] = mapped_column(String(12))
    following: Mapped[bool] = mapped_column(Boolean)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuctionReminder(Base):
    __tablename__ = "auction_reminders"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["item_id", "organization_id"], ["auction_items.id", "auction_items.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("item_id", "profile_revision", "deadline_generation", name="uq_auction_reminder_epoch"),
        CheckConstraint("version >= 1 AND profile_revision >= 1 AND deadline_generation >= 1 AND hours >= 1 AND hours <= 720", name="ck_auction_reminder_versions"),
        CheckConstraint("state IN ('scheduled','ready','acknowledged','invalidated')", name="ck_auction_reminder_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    profile_revision: Mapped[int] = mapped_column(Integer)
    deadline_generation: Mapped[int] = mapped_column(Integer)
    deadline_hash: Mapped[str] = mapped_column(String(64))
    hours: Mapped[int] = mapped_column(Integer)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="scheduled", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    check_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuctionEmailPolicy(Base):
    __tablename__ = "auction_email_policies"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        CheckConstraint("revision >= 1", name="ck_auction_email_revision"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuctionDelivery(Base):
    __tablename__ = "auction_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["item_id", "organization_id"], ["auction_items.id", "auction_items.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["monitor_id", "consent_revision"], ["auction_email_policies.monitor_id", "auction_email_policies.revision"], ondelete="CASCADE"),
        UniqueConstraint("monitor_id", "signal_hash", "consent_revision", name="uq_auction_delivery_intent"),
        CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_auction_delivery_state"),
        CheckConstraint("(event_id IS NOT NULL AND reminder_id IS NULL) OR (event_id IS NULL AND reminder_id IS NOT NULL)", name="ck_auction_delivery_signal"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("auction_item_events.id", ondelete="CASCADE"))
    reminder_id: Mapped[str | None] = mapped_column(ForeignKey("auction_reminders.id", ondelete="CASCADE"))
    consent_revision: Mapped[int] = mapped_column(Integer)
    signal_hash: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
