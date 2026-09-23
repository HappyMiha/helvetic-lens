"""Author-private setup drafts and shared, activated legal monitoring profiles."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class LegalMonitoringProfile(Base):
    __tablename__ = "legal_monitoring_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "creation_key", name="uq_legal_profile_creation"),
        CheckConstraint("status IN ('draft', 'active', 'paused')", name="ck_legal_profile_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    step: Mapped[int] = mapped_column(Integer, default=0)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    proposals_json: Mapped[dict] = mapped_column(JSON, default=dict)
    topic_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
