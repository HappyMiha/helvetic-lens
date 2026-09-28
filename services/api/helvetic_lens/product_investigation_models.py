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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
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
        ForeignKeyConstraint(["publication_id", "dossier_id", "organization_id"],
            ["product_publications.id", "product_publications.dossier_id", "product_publications.organization_id"],
            name="fk_investigation_publication", ondelete="CASCADE"),
        ForeignKeyConstraint(["public_contribution_id", "publication_id", "organization_id"],
            ["product_public_contributions.id", "product_public_contributions.publication_id", "product_public_contributions.organization_id"],
            name="fk_investigation_public_contribution", ondelete="CASCADE"),
        UniqueConstraint("public_contribution_id", "public_contribution_revision", name="uq_public_contribution_investigation"),
        CheckConstraint("(publication_id IS NULL AND publication_revision IS NULL AND public_contribution_id IS NULL AND public_contribution_revision IS NULL) OR "
            "(publication_id IS NOT NULL AND publication_revision IS NOT NULL AND publication_revision > 0 AND "
            "public_contribution_id IS NOT NULL AND public_contribution_revision IS NOT NULL AND public_contribution_revision > 0 AND trigger_entry_id IS NULL)",
            name="ck_investigation_public_scope"),
        CheckConstraint("status IN ('queued','running','paused','completed','failed','cancelled')"))
    trigger_entry_id: Mapped[str | None] = mapped_column(String(36))
    publication_id: Mapped[str | None] = mapped_column(String(36), index=True)
    publication_revision: Mapped[int | None] = mapped_column(Integer)
    public_contribution_id: Mapped[str | None] = mapped_column(String(36))
    public_contribution_revision: Mapped[int | None] = mapped_column(Integer)
    external_discovery: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    request_key: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(String(300))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    session_id: Mapped[str | None] = mapped_column(ForeignKey("user_sessions.id", ondelete="SET NULL"))
    session_organization_id: Mapped[str | None] = mapped_column(String(36))
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
        UniqueConstraint("id", "claim_id", "investigation_id", "dossier_id", "organization_id", name="uq_claim_evidence_change_scope"),
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


class ClaimChange(ResearchRecord, Base):
    __tablename__ = "product_claim_changes"
    __table_args__ = (research_scope(),
        ForeignKeyConstraint(["evidence_id", "claim_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_claim_evidence.id", "product_claim_evidence.claim_id", "product_claim_evidence.investigation_id",
             "product_claim_evidence.dossier_id", "product_claim_evidence.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["previous_claim_id", "previous_investigation_id", "dossier_id", "organization_id"],
            ["product_dossier_claims.id", "product_dossier_claims.investigation_id", "product_dossier_claims.dossier_id",
             "product_dossier_claims.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["previous_evidence_id", "previous_claim_id", "previous_investigation_id", "dossier_id", "organization_id"],
            ["product_claim_evidence.id", "product_claim_evidence.claim_id", "product_claim_evidence.investigation_id",
             "product_claim_evidence.dossier_id", "product_claim_evidence.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("evidence_id", "previous_claim_id", name="uq_claim_change_evidence"),
        CheckConstraint("kind IN ('CORROBORATES','CONTRADICTS','UPDATES')", name="ck_claim_change_kind"),
        CheckConstraint("status IN ('active','dismissed')", name="ck_claim_change_status"),
        CheckConstraint("previous_investigation_id <> investigation_id", name="ck_claim_change_other_run"))
    evidence_id: Mapped[str] = mapped_column(String(36))
    claim_id: Mapped[str] = mapped_column(String(36), index=True)
    previous_claim_id: Mapped[str] = mapped_column(String(36), index=True)
    previous_evidence_id: Mapped[str] = mapped_column(String(36))
    previous_investigation_id: Mapped[str] = mapped_column(String(36))
    previous_revision: Mapped[int] = mapped_column(Integer)
    previous_status: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    history: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    last_request_key: Mapped[str] = mapped_column(String(36), default="", server_default="")
    last_request_fingerprint: Mapped[str] = mapped_column(String(64), default="", server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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


class MonitoringResearchPolicy(Contained, Base):
    __tablename__ = "product_monitoring_research_policies"
    __table_args__ = (contained(), UniqueConstraint("dossier_id"),
        UniqueConstraint("id", "dossier_id", "organization_id"),
        CheckConstraint("daily_limit BETWEEN 1 AND 6", name="ck_monitor_research_limit"),
        Index("ix_monitor_research_due", "enabled", "next_check_at", "id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    include_page_changes: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    authorized_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    profile_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    starts_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    daily_limit: Mapped[int] = mapped_column(Integer, default=3)
    budget_day: Mapped[str] = mapped_column(String(10), default="")
    budget_used: Mapped[int] = mapped_column(Integer, default=0)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500), default="Automatic research is off.")
    history: Mapped[list] = mapped_column(JSON, default=list)
    last_request_key: Mapped[str] = mapped_column(String(36), default="")
    last_request_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MonitoringResearchTrigger(Contained, Base):
    __tablename__ = "product_monitoring_research_triggers"
    __table_args__ = (contained(),
        ForeignKeyConstraint(["policy_id", "dossier_id", "organization_id"],
            ["product_monitoring_research_policies.id", "product_monitoring_research_policies.dossier_id",
             "product_monitoring_research_policies.organization_id"], ondelete="CASCADE"),
        research_scope(), UniqueConstraint("investigation_id"),
        UniqueConstraint("dossier_id", "match_id", "evaluation_fingerprint", name="uq_monitor_research_trigger"),
        UniqueConstraint("dossier_id", "source_kind", "source_identifier", "source_revision", name="uq_monitor_research_source"),
        CheckConstraint("source_kind IN ('topic_match','watched_page')", name="ck_monitor_research_source_kind"),
        CheckConstraint("state IN ('pending','started','skipped')", name="ck_monitor_research_trigger_state"),
        Index("ix_monitor_research_pending", "policy_id", "state", "created_at", "id"))
    policy_id: Mapped[str] = mapped_column(String(36))
    policy_revision: Mapped[int] = mapped_column(Integer)
    investigation_id: Mapped[str | None] = mapped_column(String(36))
    # Historical identity, deliberately retained after the live match expires.
    match_id: Mapped[str | None] = mapped_column(String(36))
    evaluation_fingerprint: Mapped[str | None] = mapped_column(String(64))
    source_kind: Mapped[str] = mapped_column(String(20), default="topic_match", server_default="topic_match")
    source_identifier: Mapped[str] = mapped_column(String(80), default=lambda ctx: ctx.get_current_parameters()["match_id"])
    source_revision: Mapped[str] = mapped_column(String(64), default=lambda ctx: ctx.get_current_parameters()["evaluation_fingerprint"])
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    reason: Mapped[str] = mapped_column(String(500), default="Waiting for research capacity.")
    source_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebResearchPolicy(Contained, Base):
    __tablename__ = "product_web_research_policies"
    __table_args__ = (contained(), UniqueConstraint("dossier_id"),
        UniqueConstraint("id", "dossier_id", "organization_id"),
        CheckConstraint("cadence_hours IN (24,168)", name="ck_web_research_cadence"),
        Index("ix_web_research_due", "enabled", "next_check_at", "id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    question: Mapped[str] = mapped_column(String(300), default="")
    cadence_hours: Mapped[int] = mapped_column(Integer, default=24)
    authorized_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    audience_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    budget_day: Mapped[str] = mapped_column(String(10), default="")
    budget_used: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500), default="Recurring public search is off.")
    history: Mapped[list] = mapped_column(JSON, default=list)
    last_request_key: Mapped[str] = mapped_column(String(36), default="")
    last_request_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WebResearchTrigger(Contained, Base):
    __tablename__ = "product_web_research_triggers"
    __table_args__ = (contained(), research_scope(),
        ForeignKeyConstraint(["policy_id", "dossier_id", "organization_id"],
            ["product_web_research_policies.id", "product_web_research_policies.dossier_id",
             "product_web_research_policies.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("investigation_id"),
        UniqueConstraint("policy_id", "policy_revision", "scheduled_for", name="uq_web_research_occurrence"))
    policy_id: Mapped[str] = mapped_column(String(36))
    policy_revision: Mapped[int] = mapped_column(Integer)
    investigation_id: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(String(300))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))


SCOPED = (WebResearchPolicy, WebResearchTrigger, MonitoringResearchPolicy, MonitoringResearchTrigger, Investigation, InvestigationPlan, InvestigationBranch, InvestigationSource,
          DossierClaim, ClaimEvidence, ClaimChange, DossierEntity, DossierRelationship, InvestigationEvent)
