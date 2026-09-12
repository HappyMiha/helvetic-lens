"""Additive C7 records; public measurements and private decisions stay separate."""

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


def identifier():
    return str(uuid4())


class AirSourceCache(Base):
    __tablename__ = "air_source_cache"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    next_fetch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(40))
    failures: Mapped[int] = mapped_column(Integer, default=0)


class AirMeasurement(Base):
    __tablename__ = "air_measurements"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    station_id: Mapped[str] = mapped_column(String(8), index=True)
    metric: Mapped[str] = mapped_column(String(12))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evidence: Mapped[dict] = mapped_column(JSON)


class AirMonitor(Base):
    __tablename__ = "air_monitors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_air_monitor_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_air_monitor_request"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_air_versions"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_air_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    health: Mapped[str] = mapped_column(String(40), default="waiting")
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AirRevision(Base):
    __tablename__ = "air_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["air_monitors.id", "air_monitors.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("monitor_id", "revision", name="uq_air_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AirChange(Base):
    __tablename__ = "air_changes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["air_monitors.id", "air_monitors.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("monitor_id", "sequence", name="uq_air_change_sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    development_id: Mapped[str] = mapped_column(String(64), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    priority: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[str | None] = mapped_column(String(24))
    review_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AirReadingVersion(Base):
    """Immutable source revisions, including withdrawals and corrected values."""

    __tablename__ = "air_reading_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    station_id: Mapped[str] = mapped_column(String(8), index=True)
    metric: Mapped[str] = mapped_column(String(12))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evidence: Mapped[dict] = mapped_column(JSON)
