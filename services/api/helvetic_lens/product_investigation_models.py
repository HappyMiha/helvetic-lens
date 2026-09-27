"""Durable research and evidence contained by the existing product dossier."""
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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class Contained:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def contained():
    return ForeignKeyConstraint(["dossier_id", "organization_id"],
        ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE")


def research_scope():
    return ForeignKeyConstraint(["investigation_id", "dossier_id", "organization_id"],
        ["product_investigations.id", "product_investigations.dossier_id", "product_investigations.organization_id"], ondelete="CASCADE")


class Investigation(Contained, Base):
    __tablename__ = "product_investigations"
    __table_args__ = (contained(), UniqueConstraint("id", "dossier_id", "organization_id"),
        UniqueConstraint("dossier_id", "request_key"),
        ForeignKeyConstraint(["trigger_entry_id", "dossier_id", "organization_id"],
            ["product_dossier_entries.id", "product_dossier_entries.dossier_id", "product_dossier_entries.organization_id"],
            name="fk_investigation_contribution", ondelete="CASCADE"),
        UniqueConstraint("trigger_entry_id", name="uq_investigation_contribution"),
        CheckConstraint("status IN ('queued','running','paused','completed','failed','cancelled')"))
    trigger_entry_id: Mapped[str | None] = mapped_column(String(36))
    external_discovery: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    request_key: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(String(300))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    session_id: Mapped[str | None] = mapped_column(ForeignKey("user_sessions.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)
    event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    stop_reason: Mapped[str] = mapped_column(String(500), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchRecord(Contained):
    investigation_id: Mapped[str] = mapped_column(String(36), index=True)


class InvestigationPlan(ResearchRecord, Base):
    __tablename__ = "product_investigation_plans"
    __table_args__ = (research_scope(), UniqueConstraint("investigation_id", "version"))
    version: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(700))
    document: Mapped[dict] = mapped_column(JSON)


class InvestigationBranch(ResearchRecord, Base):
    __tablename__ = "product_investigation_branches"
    __table_args__ = (research_scope(), UniqueConstraint("investigation_id", "query"))
    query: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    phase: Mapped[str] = mapped_column(String(24), default="search")
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(String(700))


class InvestigationSource(ResearchRecord, Base):
    __tablename__ = "product_investigation_sources"
    __table_args__ = (research_scope(), UniqueConstraint("id", "investigation_id", "dossier_id", "organization_id"),
        UniqueConstraint("investigation_id", "source_key"))
    source_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(700))
    url: Mapped[str] = mapped_column(String(2000), default="")
    sha256: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)


class DossierClaim(ResearchRecord, Base):
    __tablename__ = "product_dossier_claims"
    __table_args__ = (research_scope(), UniqueConstraint("id", "investigation_id", "dossier_id", "organization_id"),
        CheckConstraint("status IN ('UNVERIFIED','SUPPORTED','CONTESTED','HYPOTHESIS','DISPROVED','SUPERSEDED')"))
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    history: Mapped[list] = mapped_column(JSON, default=list)


class ClaimEvidence(ResearchRecord, Base):
    __tablename__ = "product_claim_evidence"
    __table_args__ = (research_scope(),
        ForeignKeyConstraint(["claim_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_dossier_claims.id", "product_dossier_claims.investigation_id", "product_dossier_claims.dossier_id", "product_dossier_claims.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["source_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_investigation_sources.id", "product_investigation_sources.investigation_id", "product_investigation_sources.dossier_id", "product_investigation_sources.organization_id"], ondelete="CASCADE"),
        CheckConstraint("relation IN ('SUPPORTS','CONTRADICTS','CONTEXT')"))
    claim_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(36))
    relation: Mapped[str] = mapped_column(String(16))
    quote: Mapped[str] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(String(100))


class DossierEntity(ResearchRecord, Base):
    __tablename__ = "product_dossier_entities"
    __table_args__ = (research_scope(), UniqueConstraint("id", "investigation_id", "dossier_id", "organization_id"))
    name: Mapped[str] = mapped_column(String(240))
    kind: Mapped[str] = mapped_column(String(80))
    evidence: Mapped[dict] = mapped_column(JSON)


class DossierRelationship(ResearchRecord, Base):
    __tablename__ = "product_dossier_relationships"
    __table_args__ = (research_scope(), *[
        ForeignKeyConstraint([field, "investigation_id", "dossier_id", "organization_id"],
            ["product_dossier_entities.id", "product_dossier_entities.investigation_id", "product_dossier_entities.dossier_id", "product_dossier_entities.organization_id"], ondelete="CASCADE")
        for field in ("subject_id", "object_id")])
    subject_id: Mapped[str] = mapped_column(String(36))
    object_id: Mapped[str] = mapped_column(String(36))
    predicate: Mapped[str] = mapped_column(String(120))
    evidence: Mapped[dict] = mapped_column(JSON)


class InvestigationEvent(ResearchRecord, Base):
    __tablename__ = "product_investigation_events"
    __table_args__ = (research_scope(), UniqueConstraint("investigation_id", "sequence"))
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON)


SCOPED = (Investigation, InvestigationPlan, InvestigationBranch, InvestigationSource,
          DossierClaim, ClaimEvidence, DossierEntity, DossierRelationship, InvestigationEvent)
