from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


def new_id() -> str:
    return str(uuid4())


LEGACY_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(200))
    locale: Mapped[str] = mapped_column(String(5), default="en-CH")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccountToken(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')",
            name="ck_account_token_purpose",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(30), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_organization_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="organization_admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(40), default="viewer")
    recipient_locale: Mapped[str] = mapped_column(String(5), default="en-CH")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invited_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DigestPreference(Base):
    __tablename__ = "digest_preferences"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_digest_preference_org_user"),
        CheckConstraint("frequency IN ('daily', 'weekly')", name="ck_digest_frequency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency: Mapped[str] = mapped_column(String(20), default="weekly")
    severities: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    next_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DigestDelivery(Base):
    __tablename__ = "digest_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "preference_id", "period_end", name="uq_digest_delivery_preference_period"
        ),
        CheckConstraint(
            "status IN ('queued', 'succeeded', 'failed', 'skipped')",
            name="ck_digest_delivery_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    preference_id: Mapped[str] = mapped_column(ForeignKey("digest_preferences.id"), index=True)
    frequency: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    subject_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AdministrativeAudit(Base):
    __tablename__ = "administrative_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_kind: Mapped[str] = mapped_column(String(40), default="authenticated_user")
    scope: Mapped[str] = mapped_column(String(30), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(20), index=True)
    response_status: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class DocumentWatch(Base):
    __tablename__ = "document_watches"
    __table_args__ = (
        UniqueConstraint("organization_id", "law_id", name="uq_document_watch_organization_law"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    selected_baseline_version_id: Mapped[str | None] = mapped_column(ForeignKey("versions.id"))
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str] = mapped_column(String(40), default="baseline_created")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(250))
    url: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(Text, default="/")
    provider: Mapped[str] = mapped_column(String(30), default="native")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    discovery: Mapped[dict] = mapped_column(JSON, default=dict)


class SourcePackDefinition(Base):
    """Global, versioned source-selection contract shared by every organization."""

    __tablename__ = "source_pack_definitions"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_pack_definitions.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[str] = mapped_column(String(40))
    name_json: Mapped[dict] = mapped_column(JSON, default=dict)
    description_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_first_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourcePackSubscription(Base):
    __tablename__ = "source_pack_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "pack_id", name="uq_source_pack_subscription_org_pack"
        ),
        CheckConstraint(
            "state IN ('inactive', 'queued', 'backfilling', 'active', 'partial', 'failed')",
            name="ck_source_pack_subscription_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    pack_id: Mapped[str] = mapped_column(
        ForeignKey("source_pack_definitions.id"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(20), default="inactive", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    progress_current: Mapped[int] = mapped_column(BigInteger, default=0)
    progress_total: Mapped[int] = mapped_column(BigInteger, default=1)
    included_event_count: Mapped[int] = mapped_column(BigInteger, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    activated_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourcePackChangeRequest(Base):
    __tablename__ = "source_pack_change_requests"
    __table_args__ = (
        CheckConstraint(
            "requested_action IN ('activate', 'deactivate')",
            name="ck_source_pack_request_action",
        ),
        CheckConstraint(
            "status IN ('pending', 'fulfilled', 'cancelled')",
            name="ck_source_pack_request_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    pack_id: Mapped[str] = mapped_column(
        ForeignKey("source_pack_definitions.id"), index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    requested_action: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MonitoringTopic(Base):
    """An organization-owned interest whose plan changes through immutable revisions."""

    __tablename__ = "monitoring_topics"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_monitoring_topic_org_idempotency"
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name="ck_monitoring_topic_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    current_revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class MonitoringTopicRevision(Base):
    __tablename__ = "monitoring_topic_revisions"
    __table_args__ = (
        UniqueConstraint("topic_id", "revision", name="uq_monitoring_topic_revision"),
        CheckConstraint(
            "importance_floor IN ('high', 'medium', 'low', 'none')",
            name="ck_monitoring_topic_importance",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name="ck_monitoring_topic_revision_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("monitoring_topics.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(240))
    goal: Mapped[str] = mapped_column(Text)
    concepts_json: Mapped[list] = mapped_column(JSON, default=list)
    synonyms_json: Mapped[list] = mapped_column(JSON, default=list)
    exclusions_json: Mapped[list] = mapped_column(JSON, default=list)
    jurisdictions_json: Mapped[list] = mapped_column(JSON, default=list)
    languages_json: Mapped[list] = mapped_column(JSON, default=list)
    source_pack_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    document_kinds_json: Mapped[list] = mapped_column(JSON, default=list)
    event_kinds_json: Mapped[list] = mapped_column(JSON, default=list)
    importance_floor: Mapped[str] = mapped_column(String(20), default="low")
    author_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ai_provider: Mapped[str | None] = mapped_column(String(80))
    ai_model: Mapped[str | None] = mapped_column(String(200))
    prompt_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MonitoringTopicDraft(Base):
    """A model proposal that cannot activate monitoring without explicit confirmation."""

    __tablename__ = "monitoring_topic_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    goal_input: Mapped[str] = mapped_column(Text)
    plan_json: Mapped[dict] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(200))
    prompt_revision: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TopicEventMatch(Base):
    """A bounded, evidence-linked topic candidate; it is not a legal relation."""

    __tablename__ = "topic_event_matches"
    __table_args__ = (
        Index(
            "ix_topic_event_matches_org_topic_matched",
            "organization_id",
            "topic_id",
            "matched_at",
        ),
        UniqueConstraint("topic_revision_id", "event_id", name="uq_topic_event_match_revision_event"),
        CheckConstraint(
            "confidence_band IN ('high', 'medium', 'low')",
            name="ck_topic_event_match_confidence",
        ),
        CheckConstraint(
            "decision_status IN ('pending', 'confirmed', 'rejected', 'muted')",
            name="ck_topic_event_match_decision",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("monitoring_topics.id"), index=True)
    topic_revision_id: Mapped[str] = mapped_column(
        ForeignKey("monitoring_topic_revisions.id"), index=True
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("regulatory_events.id"), index=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    expression_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_expressions.id"))
    document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("regulatory_document_versions.id")
    )
    reason_signals_json: Mapped[list] = mapped_column(JSON, default=list)
    evidence_references_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    rule_fingerprint: Mapped[str] = mapped_column(String(100), index=True)
    model_provider: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(200))
    model_prompt_revision: Mapped[int | None] = mapped_column(Integer)
    confidence_band: Mapped[str] = mapped_column(String(20), index=True)
    decision_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Law(Base):
    __tablename__ = "laws"
    __table_args__ = (
        Index(
            "uq_public_law_canonical_identity",
            "canonical_identity",
            unique=True,
            postgresql_where=text("owner_organization_id IS NULL"),
            sqlite_where=text("owner_organization_id IS NULL"),
        ),
        Index(
            "uq_private_law_canonical_identity",
            "owner_organization_id",
            "canonical_identity",
            unique=True,
            postgresql_where=text("owner_organization_id IS NOT NULL"),
            sqlite_where=text("owner_organization_id IS NOT NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    canonical_identity: Mapped[str] = mapped_column(String(500))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    name: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(30), default="native")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Updated only by validated live observations; avoids a cyclic insert dependency.
    current_version_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str] = mapped_column(String(40), default="baseline_created")
    last_error: Mapped[str | None] = mapped_column(Text)


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (
        Index(
            "uq_public_version_content",
            "law_id",
            "content_hash",
            "extractor",
            unique=True,
            postgresql_where=text("owner_organization_id IS NULL"),
            sqlite_where=text("owner_organization_id IS NULL"),
        ),
        Index(
            "uq_private_version_content",
            "owner_organization_id",
            "law_id",
            "content_hash",
            "extractor",
            unique=True,
            postgresql_where=text("owner_organization_id IS NOT NULL"),
            sqlite_where=text("owner_organization_id IS NOT NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    extractor: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    passages: Mapped[list] = mapped_column(JSON)
    content_type: Mapped[str] = mapped_column(String(100))
    artifact_key: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(30))
    declared_date: Mapped[str | None] = mapped_column(String(10))
    date_provenance: Mapped[str | None] = mapped_column(String(30))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryWork(Base):
    """One authority-level legal or regulatory work, independent of language and URL."""

    __tablename__ = "regulatory_works"
    __table_args__ = (
        Index(
            "uq_public_regulatory_work_authority_key",
            "authority",
            "canonical_key",
            unique=True,
            postgresql_where=text("owner_organization_id IS NULL"),
            sqlite_where=text("owner_organization_id IS NULL"),
        ),
        Index(
            "uq_private_regulatory_work_authority_key",
            "owner_organization_id",
            "authority",
            "canonical_key",
            unique=True,
            postgresql_where=text("owner_organization_id IS NOT NULL"),
            sqlite_where=text("owner_organization_id IS NOT NULL"),
        ),
        CheckConstraint(
            "kind IN ('act', 'ordinance', 'parliamentary_business', 'initiative', 'bill', "
            "'court_decision', 'official_notice', 'consultation', 'unclassified_document')",
            name="ck_regulatory_work_kind",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    authority: Mapped[str] = mapped_column(String(80), index=True)
    canonical_key: Mapped[str] = mapped_column(String(700))
    title: Mapped[str] = mapped_column(Text, default="")
    stable_official_url: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[str | None] = mapped_column(String(60), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryIdentifier(Base):
    __tablename__ = "regulatory_identifiers"
    __table_args__ = (
        UniqueConstraint("authority", "scheme", "normalized_value", name="uq_regulatory_identifier_value"),
        UniqueConstraint("work_id", "scheme", "normalized_value", name="uq_regulatory_identifier_work_value"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    authority: Mapped[str] = mapped_column(String(80), index=True)
    scheme: Mapped[str] = mapped_column(String(50), index=True)
    value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str] = mapped_column(String(700))
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryExpression(Base):
    __tablename__ = "regulatory_expressions"
    __table_args__ = (
        UniqueConstraint("work_id", "language", "expression_key", name="uq_regulatory_expression_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    language: Mapped[str] = mapped_column(String(20), index=True)
    expression_key: Mapped[str] = mapped_column(String(700))
    title: Mapped[str] = mapped_column(Text, default="")
    official_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryDocumentVersion(Base):
    __tablename__ = "regulatory_document_versions"
    __table_args__ = (
        UniqueConstraint("expression_id", "version_key", name="uq_regulatory_document_version_key"),
        UniqueConstraint("legacy_version_id", name="uq_regulatory_document_version_legacy"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    expression_id: Mapped[str] = mapped_column(ForeignKey("regulatory_expressions.id"), index=True)
    version_key: Mapped[str] = mapped_column(String(700))
    legacy_version_id: Mapped[str | None] = mapped_column(ForeignKey("versions.id", ondelete="SET NULL"))
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    artifact_key: Mapped[str | None] = mapped_column(String(80))
    extractor: Mapped[str | None] = mapped_column(String(40))
    text: Mapped[str | None] = mapped_column(Text)
    passages: Mapped[list] = mapped_column(JSON, default=list)
    content_type: Mapped[str | None] = mapped_column(String(100))
    filename: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryDate(Base):
    """A source-stated date. String storage preserves year/month/day precision."""

    __tablename__ = "regulatory_dates"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "kind",
            "date_value",
            "precision",
            "provenance",
            name="uq_regulatory_date_fact",
        ),
        CheckConstraint(
            "kind IN ('detected_at', 'published_at', 'version_date', 'effective_from', "
            "'effective_to', 'decision_date', 'fetched_at')",
            name="ck_regulatory_date_kind",
        ),
        CheckConstraint(
            "precision IN ('instant', 'day', 'month', 'year', 'unknown')",
            name="ck_regulatory_date_precision",
        ),
        CheckConstraint(
            "entity_type IN ('work', 'expression', 'version', 'event')",
            name="ck_regulatory_date_entity_type",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    date_value: Mapped[str] = mapped_column(String(40))
    precision: Mapped[str] = mapped_column(String(20))
    provenance: Mapped[str] = mapped_column(String(60))
    source_url: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryEvent(Base):
    __tablename__ = "regulatory_events"
    __table_args__ = (
        UniqueConstraint("authority", "dedupe_key", name="uq_regulatory_event_dedupe"),
        CheckConstraint(
            "event_type IN ('created', 'new_version', 'amended', 'repealed', 'replaced', "
            "'status_changed', 'decided', 'notice_published')",
            name="ck_regulatory_event_type",
        ),
        CheckConstraint(
            "connector_health IN ('healthy', 'degraded', 'error', 'unknown')",
            name="ck_regulatory_event_connector_health",
        ),
        CheckConstraint(
            "analysis_state IN ('pending', 'queued', 'running', 'complete', 'failed', 'not_required')",
            name="ck_regulatory_event_analysis_state",
        ),
        CheckConstraint(
            "impact IN ('high', 'medium', 'low', 'none', 'unknown')",
            name="ck_regulatory_event_impact",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    expression_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_expressions.id"))
    document_version_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_document_versions.id"))
    authority: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(700))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    provenance_method: Mapped[str] = mapped_column(String(60))
    connector: Mapped[str] = mapped_column(String(80), index=True, default="unknown")
    connector_health: Mapped[str] = mapped_column(String(20), index=True, default="unknown")
    analysis_state: Mapped[str] = mapped_column(String(20), index=True, default="pending")
    impact: Mapped[str] = mapped_column(String(20), index=True, default="unknown")
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryEventState(Base):
    __tablename__ = "regulatory_event_states"
    __table_args__ = (
        UniqueConstraint("organization_id", "event_id", name="uq_regulatory_event_state_org_event"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("regulatory_events.id"), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryEventUserState(Base):
    """A user's private inbox state; it never changes the shared regulatory event."""

    __tablename__ = "regulatory_event_user_states"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "event_id",
            "principal_key",
            name="uq_regulatory_event_user_state_principal",
        ),
        CheckConstraint(
            "state IN ('unread', 'read', 'dismissed', 'muted')",
            name="ck_regulatory_event_user_state_value",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("regulatory_events.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    principal_key: Mapped[str] = mapped_column(String(80), index=True)
    state: Mapped[str] = mapped_column(String(20), default="unread", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RegulatoryRelation(Base):
    __tablename__ = "regulatory_relations"
    __table_args__ = (
        UniqueConstraint("authority", "dedupe_key", name="uq_regulatory_relation_dedupe"),
        CheckConstraint(
            "relation_type IN ('amends', 'repeals', 'replaces', 'implements', 'cites', "
            "'interprets', 'potentially_impacts')",
            name="ck_regulatory_relation_type",
        ),
        CheckConstraint(
            "state IN ('confirmed', 'proposed', 'rejected')",
            name="ck_regulatory_relation_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    object_work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    source_version_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_document_versions.id"))
    supersedes_relation_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_relations.id"))
    authority: Mapped[str] = mapped_column(String(80), index=True)
    relation_type: Mapped[str] = mapped_column(String(40), index=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    provenance_method: Mapped[str] = mapped_column(String(40), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(700))
    evidence_fingerprint: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    rule_or_model_revision: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RelationCandidate(Base):
    __tablename__ = "relation_candidates"
    __table_args__ = (
        UniqueConstraint("event_id", "target_work_id", name="uq_relation_candidate_event_target"),
        CheckConstraint(
            "status IN ('active', 'expired', 'promoted', 'rejected')",
            name="ck_relation_candidate_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("regulatory_events.id"), index=True)
    source_work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    target_work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    relation_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_relations.id"), index=True)
    source_version_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_document_versions.id"))
    target_version_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_document_versions.id"))
    status: Mapped[str] = mapped_column(String(20), index=True, default="active")
    score: Mapped[float] = mapped_column(Float)
    score_components_json: Mapped[dict] = mapped_column(JSON, default=dict)
    why_json: Mapped[list] = mapped_column(JSON, default=list)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    rule_revision: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrganizationRelationCandidate(Base):
    __tablename__ = "organization_relation_candidates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "candidate_id", name="uq_org_relation_candidate"
        ),
        CheckConstraint(
            "status IN ('pending', 'queued', 'analysed', 'dismissed', 'expired')",
            name="ck_org_relation_candidate_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("relation_candidates.id", ondelete="CASCADE"), index=True
    )
    watch_id: Mapped[str] = mapped_column(ForeignKey("document_watches.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrganizationRelationReview(Base):
    __tablename__ = "organization_relation_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('confirmed', 'rejected', 'annotated')",
            name="ck_organization_relation_review_decision",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    organization_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("organization_relation_candidates.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(20), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    workflow_variant: Mapped[str] = mapped_column(String(40), default="inbox_list_v1")
    review_duration_ms: Mapped[int | None] = mapped_column(Integer)
    evidence_opened: Mapped[bool] = mapped_column(Boolean, default=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class LegacyDocumentMapping(Base):
    __tablename__ = "legacy_document_mappings"
    __table_args__ = (UniqueConstraint("law_id", name="uq_legacy_document_mapping_law"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id", ondelete="CASCADE"), index=True)
    work_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    mapping_status: Mapped[str] = mapped_column(String(30), index=True)
    canonical_hint: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"), index=True)
    origin: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    artifact_key: Mapped[str] = mapped_column(String(80))
    declared_date: Mapped[str | None] = mapped_column(String(10))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comparison(Base):
    __tablename__ = "comparisons"
    __table_args__ = (
        UniqueConstraint("old_version_id", "new_version_id", "mode", name="uq_comparison_pair"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    old_version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"))
    new_version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"))
    mode: Mapped[str] = mapped_column(String(30))
    diff: Mapped[dict] = mapped_column(JSON)
    identity_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdentityDecision(Base):
    __tablename__ = "identity_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    identity_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(120), default="workspace_user")
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    total: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScanItem(Base):
    __tablename__ = "scan_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    baseline_version_id: Mapped[str | None] = mapped_column(ForeignKey("versions.id"))
    new_version_id: Mapped[str | None] = mapped_column(ForeignKey("versions.id"))
    comparison_id: Mapped[str | None] = mapped_column(ForeignKey("comparisons.id"))
    monitoring_comparison_id: Mapped[str | None] = mapped_column(ForeignKey("comparisons.id"))
    mode: Mapped[str] = mapped_column(String(30), default="monitoring")
    stage: Mapped[str] = mapped_column(String(30), default="queued")
    result: Mapped[str | None] = mapped_column(String(40))
    live_result: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    analysis_status: Mapped[str] = mapped_column(String(30), default="pending")
    events: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default="default")
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="My company")
    description: Mapped[str] = mapped_column(Text, default="")
    business_areas: Mapped[list] = mapped_column(JSON, default=lambda: ["Legal", "IT", "Operations"])
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ApertusConfiguration(Base):
    __tablename__ = "apertus_configuration"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default="default")
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    # AES-GCM ciphertext stays on the server and is never serialized to clients.
    api_key: Mapped[str | None] = mapped_column(Text)
    key_source: Mapped[str] = mapped_column(String(30), default="environment")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromptConfiguration(Base):
    __tablename__ = "prompt_configuration"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default="default")
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlatformPromptConfiguration(Base):
    __tablename__ = "platform_prompt_configuration"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default="default")
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromptRevision(Base):
    __tablename__ = "prompt_revisions"
    __table_args__ = (
        UniqueConstraint("organization_id", "revision", name="uq_prompt_revision_organization"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrganizationQuota(Base):
    __tablename__ = "organization_quotas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConnectorState(Base):
    __tablename__ = "connector_states"
    __table_args__ = (
        UniqueConstraint("connector", "stream", name="uq_connector_state_stream"),
        CheckConstraint(
            "health IN ('healthy', 'degraded', 'error', 'unknown')",
            name="ck_connector_state_health",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connector: Mapped[str] = mapped_column(String(80), index=True)
    stream: Mapped[str] = mapped_column(String(200), default="default")
    contract_version: Mapped[str] = mapped_column(String(80))
    connector_version: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[str] = mapped_column(String(80))
    cursor_json: Mapped[dict | None] = mapped_column(JSON)
    page_checkpoint_json: Mapped[dict] = mapped_column(JSON, default=dict)
    health: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    health_message: Mapped[str | None] = mapped_column(Text)
    source_contract_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConnectorPage(Base):
    __tablename__ = "connector_pages"
    __table_args__ = (
        UniqueConstraint("connector", "stream", "page_key", name="uq_connector_page_key"),
        CheckConstraint(
            "status IN ('processing', 'partial', 'persisted', 'degraded', 'failed')",
            name="ck_connector_page_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connector: Mapped[str] = mapped_column(String(80), index=True)
    stream: Mapped[str] = mapped_column(String(200), default="default")
    page_key: Mapped[str] = mapped_column(String(64))
    input_cursor_json: Mapped[dict | None] = mapped_column(JSON)
    output_cursor_json: Mapped[dict | None] = mapped_column(JSON)
    safe_checkpoint_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="processing", index=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    persisted_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_provenance_ref: Mapped[str] = mapped_column(Text)
    attribution: Mapped[str] = mapped_column(Text)
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConnectorReceipt(Base):
    __tablename__ = "connector_receipts"
    __table_args__ = (
        UniqueConstraint(
            "connector",
            "stream",
            "external_identity",
            "expression_key",
            "source_revision",
            name="uq_connector_receipt_revision",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connector: Mapped[str] = mapped_column(String(80), index=True)
    stream: Mapped[str] = mapped_column(String(200), default="default")
    external_identity: Mapped[str] = mapped_column(String(700), index=True)
    expression_key: Mapped[str] = mapped_column(String(700))
    source_revision: Mapped[str] = mapped_column(String(200))
    work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    expression_id: Mapped[str] = mapped_column(ForeignKey("regulatory_expressions.id"))
    document_version_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_document_versions.id"))
    canonical_url: Mapped[str] = mapped_column(Text)
    artifact_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    contract_version: Mapped[str] = mapped_column(String(80))
    connector_version: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[str] = mapped_column(String(80))
    persisted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConnectorItemError(Base):
    __tablename__ = "connector_item_errors"
    __table_args__ = (
        UniqueConstraint("page_id", "item_index", "attempt", name="uq_connector_item_error_attempt"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("connector_pages.id", ondelete="CASCADE"), index=True)
    item_index: Mapped[int] = mapped_column(Integer)
    external_identity: Mapped[str | None] = mapped_column(String(700))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    code: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
    retryable: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_provenance_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConnectorSchedule(Base):
    __tablename__ = "connector_schedules"
    __table_args__ = (
        UniqueConstraint("connector", "stream", name="uq_connector_schedule_stream"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connector: Mapped[str] = mapped_column(String(80), index=True)
    stream: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    interval_seconds: Mapped[int] = mapped_column(Integer)
    jitter_seconds: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[str | None] = mapped_column(String(5))
    window_end: Mapped[str | None] = mapped_column(String(5))
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_job_id: Mapped[str | None] = mapped_column(String(36))
    policy_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConnectorRun(Base):
    __tablename__ = "connector_runs"
    __table_args__ = (UniqueConstraint("job_id", name="uq_connector_run_job"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("connector_schedules.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    requested_by_organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    connector: Mapped[str] = mapped_column(String(80), index=True)
    stream: Mapped[str] = mapped_column(String(200))
    trigger: Mapped[str] = mapped_column(String(20), default="scheduled")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    input_cursor_json: Mapped[dict | None] = mapped_column(JSON)
    output_cursor_json: Mapped[dict | None] = mapped_column(JSON)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    fanout_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedState(Base):
    __tablename__ = "feed_states"
    __table_args__ = (
        UniqueConstraint("organization_id", "connector", "stream", name="uq_feed_state_organization_stream"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    connector: Mapped[str] = mapped_column(String(80))
    stream: Mapped[str] = mapped_column(String(200))
    cursor: Mapped[str | None] = mapped_column(Text)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationLog(Base):
    __tablename__ = "integration_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    correlation: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    operation: Mapped[str] = mapped_column(String(60), index=True)
    method: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    response_status: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    request_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    request_body: Mapped[dict | list | str | None] = mapped_column(JSON)
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    response_body: Mapped[dict | list | str | None] = mapped_column(JSON)
    request_size: Mapped[int] = mapped_column(Integer, default=0)
    response_size: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparisons.id"), index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    result: Mapped[dict | None] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_revision: Mapped[int] = mapped_column(Integer, default=1)
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActionDecision(Base):
    __tablename__ = "action_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('accepted', 'assigned', 'scheduled', 'dismissed', 'not_applicable')",
            name="ck_action_decision_value",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparisons.id"), index=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    action_key: Mapped[str] = mapped_column(String(64), index=True)
    decision: Mapped[str] = mapped_column(String(30), index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(200))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rationale: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_label: Mapped[str] = mapped_column(String(200), default="Workspace administrator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RelationImpactAnalysis(Base):
    __tablename__ = "relation_impact_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_relation_impact_analysis_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    organization_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("organization_relation_candidates.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(ForeignKey("relation_candidates.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("regulatory_events.id"), index=True)
    target_work_id: Mapped[str] = mapped_column(ForeignKey("regulatory_works.id"), index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict | None] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_revision: Mapped[int] = mapped_column(Integer, default=1)
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AskRecord(Base):
    __tablename__ = "ask_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparisons.id"), index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    result: Mapped[dict | None] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_revision: Mapped[int] = mapped_column(Integer, default=1)
    context_mode: Mapped[str] = mapped_column(String(30), default="automatic")
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AssistantConversation(Base):
    """Private assistant state for one principal and one validated product context."""

    __tablename__ = "assistant_conversations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "principal_key",
            "context_key",
            name="uq_assistant_conversation_principal_context",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    principal_key: Mapped[str] = mapped_column(String(80), index=True)
    context_key: Mapped[str] = mapped_column(String(100), index=True)
    route: Mapped[str] = mapped_column(String(40))
    entity_kind: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    locale: Mapped[str] = mapped_column(String(5), default="en-CH")
    draft: Mapped[str] = mapped_column(Text, default="")
    handoffs_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_job_organization_idempotency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    correlation: Mapped[dict] = mapped_column(JSON, default=dict)
    type: Mapped[str] = mapped_column(String(60), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    queue: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress_current: Mapped[int] = mapped_column(BigInteger, default=0)
    progress_total: Mapped[int] = mapped_column(BigInteger, default=1)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    result_type: Mapped[str | None] = mapped_column(String(40))
    result_id: Mapped[str | None] = mapped_column(String(36))
    result_url: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobStep(Base):
    __tablename__ = "job_steps"
    __table_args__ = (UniqueConstraint("job_id", "position", name="uq_job_step_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(30), default="pending")
    progress_current: Mapped[int] = mapped_column(BigInteger, default=0)
    progress_total: Mapped[int] = mapped_column(BigInteger, default=1)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    topic: Mapped[str] = mapped_column(String(80), default="helvetic_lens.run_job")
    queue: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Central policy used by the session boundary. Keeping this list beside the
# models makes a newly persisted tenant-owned record difficult to forget.
ORGANIZATION_SCOPED_MODELS = (
    OrganizationMembership,
    OrganizationInvitation,
    DigestPreference,
    DigestDelivery,
    DocumentWatch,
    Source,
    SourcePackSubscription,
    SourcePackChangeRequest,
    MonitoringTopic,
    MonitoringTopicRevision,
    MonitoringTopicDraft,
    TopicEventMatch,
    Observation,
    IdentityDecision,
    Scan,
    ScanItem,
    Profile,
    ApertusConfiguration,
    PromptConfiguration,
    PromptRevision,
    OrganizationQuota,
    FeedState,
    RegulatoryEventState,
    RegulatoryEventUserState,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    IntegrationLog,
    Analysis,
    ActionDecision,
    RelationImpactAnalysis,
    AskRecord,
    AssistantConversation,
    Job,
    JobStep,
    OutboxMessage,
)
SHARED_CORPUS_MODELS = (
    Law,
    Version,
    Comparison,
    RegulatoryWork,
    LegacyDocumentMapping,
)
