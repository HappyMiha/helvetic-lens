"""Personal in-app feed notifications; following never grants access."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
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


class FeedFollow(Base):
    __tablename__ = "product_feed_follows"
    __table_args__ = (
        ForeignKeyConstraint(["feed_id", "organization_id"],
            ["product_feeds.id", "product_feeds.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("feed_id", "owner_user_id"),
        CheckConstraint("seen_sequence >= 0 AND revision >= 1"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    feed_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    following: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    seen_sequence: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
