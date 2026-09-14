"""Immutable reviewed registry; candidate bindings contain references/hashes only."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class TrademarkDeadlineRegistry(Base):
    __tablename__ = "trademark_deadline_registry"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)


class TrademarkDeadlineRule(Base):
    __tablename__ = "trademark_deadline_rules"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrademarkDeadlineCalendar(Base):
    __tablename__ = "trademark_deadline_calendars"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrademarkDeadlineRuleSelection(Base):
    __tablename__ = "trademark_deadline_rule_selections"
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    origin: Mapped[str] = mapped_column(String(40), primary_key=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("trademark_deadline_rules.id"))


class TrademarkDeadlineCalendarSelection(Base):
    __tablename__ = "trademark_deadline_calendar_selections"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(ForeignKey("trademark_deadline_calendars.id"))
