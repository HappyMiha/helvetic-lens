"""Append-only work history; exactly one native item and its evidence binding."""

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


class BusinessItemWorkEvent(Base):
    __tablename__ = "business_item_work_events"
    __table_args__ = (
        ForeignKeyConstraint(["tender_dossier_id", "organization_id"], ["tender_dossiers.id", "tender_dossiers.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trademark_candidate_id", "organization_id"], ["trademark_candidates.id", "trademark_candidates.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["auction_item_id", "organization_id"], ["auction_items.id", "auction_items.organization_id"], ondelete="CASCADE"),
        CheckConstraint("(CASE WHEN tender_dossier_id IS NULL THEN 0 ELSE 1 END + CASE WHEN trademark_candidate_id IS NULL THEN 0 ELSE 1 END + CASE WHEN auction_item_id IS NULL THEN 0 ELSE 1 END) = 1", name="ck_business_item_target"),
        CheckConstraint("item_version >= 1 AND length(comment) <= 4000", name="ck_business_item_values"),
        UniqueConstraint("tender_dossier_id", "item_version", name="uq_business_item_tender_version"),
        UniqueConstraint("trademark_candidate_id", "item_version", name="uq_business_item_trademark_version"),
        UniqueConstraint("auction_item_id", "item_version", name="uq_business_item_auction_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    tender_dossier_id: Mapped[str | None] = mapped_column(String(36), index=True)
    trademark_candidate_id: Mapped[str | None] = mapped_column(String(36), index=True)
    auction_item_id: Mapped[str | None] = mapped_column(String(36), index=True)
    item_version: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision: Mapped[str | None] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(Text, default="")
    evidence_binding: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
