"""Platform source configuration; no tenant data and no plaintext credentials."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class MonitoringConnectorConfiguration(Base):
    __tablename__ = "monitoring_connector_configurations"
    domain: Mapped[str] = mapped_column(String(16), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_revision: Mapped[int | None] = mapped_column(Integer)
    check_result: Mapped[dict | None] = mapped_column(JSON)
