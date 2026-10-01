"""Product workspaces reuse native monitoring profiles and evidence storage."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class DecisionSearchBudget(Base):
    """Aggregate operator spend guard; no account or query data."""
    __tablename__ = "product_decision_search_budgets"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    used: Mapped[int] = mapped_column(Integer, default=0)


class DecisionSearchRun(Base):
    __tablename__ = "product_decision_search_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "owner_user_id", "product", "request_key", name="uq_decision_search_request"),
        CheckConstraint("product IN ('pharma', 'loyer')", name="ck_decision_search_product"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product: Mapped[str] = mapped_column(String(12))
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    query: Mapped[str] = mapped_column(String(300))
    mode: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), default="running")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    labels_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ProductDossier(Base):
    __tablename__ = "product_dossiers"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_product_dossier_org"),
        UniqueConstraint("organization_id", "product", "creation_key", name="uq_product_dossier_creation"),
        CheckConstraint("monitoring_audience IN ('workspace', 'team')", name="ck_dossier_monitoring_audience"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product: Mapped[str] = mapped_column(String(20))
    profile_id: Mapped[str] = mapped_column(ForeignKey("legal_monitoring_profiles.id", ondelete="CASCADE"), unique=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    team_managed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    monitoring_audience: Mapped[str] = mapped_column(String(16), default="workspace", server_default="workspace")
    access_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    domain_context_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    template_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    priority: Mapped[str] = mapped_column(String(12), default="normal", server_default="normal")
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    next_review_on: Mapped[date | None] = mapped_column(Date)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DossierMember(Base):
    __tablename__ = "product_dossier_members"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["membership_organization_id", "user_id"],
                             ["organization_memberships.organization_id", "organization_memberships.user_id"],
                             name="fk_dossier_member_native_membership", ondelete="CASCADE"),
        CheckConstraint("(is_guest AND membership_organization_id IS NULL AND role <> 'OWNER') OR "
            "(NOT is_guest AND membership_organization_id IS NOT NULL AND membership_organization_id = organization_id)",
            name="ck_dossier_member_membership_scope"),
        CheckConstraint("role IN ('OWNER', 'EDITOR', 'CONTRIBUTOR', 'VIEWER')", name="ck_dossier_member_role"),
    )
    dossier_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    membership_organization_id: Mapped[str | None] = mapped_column(String(36))
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DossierInvitation(Base):
    """An account-bound invitation, not a bearer grant or organization invitation."""
    __tablename__ = "product_dossier_invitations"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["membership_organization_id", "recipient_user_id"],
                             ["organization_memberships.organization_id", "organization_memberships.user_id"],
                             name="fk_dossier_invitation_native_membership", ondelete="CASCADE"),
        CheckConstraint("(is_guest AND membership_organization_id IS NULL) OR "
            "(NOT is_guest AND membership_organization_id IS NOT NULL AND membership_organization_id = organization_id)",
            name="ck_dossier_invitation_membership_scope"),
        UniqueConstraint("dossier_id", "request_key", name="uq_dossier_invitation_request"),
        CheckConstraint("role IN ('EDITOR', 'CONTRIBUTOR', 'VIEWER')", name="ck_dossier_invitation_role"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    membership_organization_id: Mapped[str | None] = mapped_column(String(36))
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invited_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    request_key: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DossierEntry(Base):
    __tablename__ = "product_dossier_entries"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("dossier_id", "request_key", name="uq_product_entry_request"),
        UniqueConstraint("id", "dossier_id", "organization_id", name="uq_product_entry_scope"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    thread_id: Mapped[str | None] = mapped_column(ForeignKey("product_research_threads.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(240), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_key: Mapped[str | None] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DossierAction(Base):
    __tablename__ = "product_dossier_actions"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("dossier_id", "creation_key", name="uq_product_action_creation"),
        CheckConstraint("status IN ('open', 'in_progress', 'done', 'cancelled')", name="ck_product_action_status"),
        CheckConstraint("priority IN ('normal', 'high', 'urgent')", name="ck_product_action_priority"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(240))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(12), default="normal")
    assignee_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_on: Mapped[date | None] = mapped_column(Date, index=True)
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchThread(Base):
    __tablename__ = "product_research_threads"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("dossier_id", "creation_key", name="uq_research_thread_creation"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    # Checked against this thread's entries on every acceptance; avoiding a FK
    # cycle keeps private dossier erasure in containment order.
    accepted_entry_id: Mapped[str | None] = mapped_column(String(36))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductPublication(Base):
    """Explicitly authored public projection; never serialize its private parent."""
    __tablename__ = "product_publications"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", name="uq_product_publication_org"),
        UniqueConstraint("id", "dossier_id", "organization_id", name="uq_product_publication_research_scope"),
        UniqueConstraint("dossier_id", name="uq_product_publication_dossier"),
        CheckConstraint("status IN ('published', 'withdrawn')", name="ck_product_publication_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36))
    product: Mapped[str] = mapped_column(String(20), index=True)
    slug: Mapped[str | None] = mapped_column(String(180), unique=True)
    living_research: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(String(1500))
    body: Mapped[str] = mapped_column(Text)
    author_label: Mapped[str] = mapped_column(String(100))
    sources_json: Mapped[list] = mapped_column(JSON, default=list)
    first_published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicationRevision(Base):
    """Private immutable audit including idempotency and explicit public consent."""
    __tablename__ = "product_publication_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["publication_id", "organization_id"],
                             ["product_publications.id", "product_publications.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("publication_id", "revision", name="uq_product_publication_revision"),
        UniqueConstraint("publication_id", "request_key", name="uq_product_publication_request"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    publication_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(20))
    content_json: Mapped[dict] = mapped_column(JSON)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublicContribution(Base):
    """Deliberately public personal contribution, contained by the publication."""
    __tablename__ = "product_public_contributions"
    __table_args__ = (
        ForeignKeyConstraint(["publication_id", "organization_id"],
                             ["product_publications.id", "product_publications.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "publication_id", "organization_id", name="uq_public_contribution_scope"),
        CheckConstraint("status IN ('visible', 'hidden', 'removed')", name="ck_public_contribution_status"),
        Index("ix_public_contribution_page", "publication_id", "status", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    publication_id: Mapped[str] = mapped_column(String(36))
    author_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    publication_revision: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="visible")
    author_label: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[list] = mapped_column(JSON, default=list)
    kind: Mapped[str] = mapped_column(String(24), default="comment", server_default="comment")
    artifact_key: Mapped[str] = mapped_column(String(240), default="", server_default="")
    file_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    byte_size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sha256: Mapped[str] = mapped_column(String(64), default="", server_default="")
    content_type: Mapped[str] = mapped_column(String(100), default="", server_default="")
    moderation_reason: Mapped[str] = mapped_column(String(600), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublicContributionMutation(Base):
    """Private retry and moderation evidence; never retain removed text here."""
    __tablename__ = "product_public_contribution_mutations"
    __table_args__ = (
        ForeignKeyConstraint(["contribution_id", "publication_id", "organization_id"],
                             ["product_public_contributions.id", "product_public_contributions.publication_id",
                              "product_public_contributions.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("publication_id", "request_key", name="uq_public_contribution_request"),
        UniqueConstraint("contribution_id", "revision", name="uq_public_contribution_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    publication_id: Mapped[str] = mapped_column(String(36))
    contribution_id: Mapped[str] = mapped_column(String(36))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(600), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublicDossierFollow(Base):
    """Personal across workspaces; every query must constrain owner_user_id."""
    __tablename__ = "product_public_follows"
    __table_args__ = (UniqueConstraint("owner_user_id", "publication_id", name="uq_public_follow_owner"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    publication_id: Mapped[str] = mapped_column(ForeignKey("product_publications.id", ondelete="CASCADE"), index=True)
    following: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_mode: Mapped[str] = mapped_column(String(16), default="immediate", server_default="immediate")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    seen_marker: Mapped[str] = mapped_column(String(64))
    activity_seen_marker: Mapped[str | None] = mapped_column(String(64))
    research_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PrivateDossierFollow(Base):
    """Personal preference, contained by the dossier; always filter its owner."""
    __tablename__ = "product_private_follows"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
            ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("owner_user_id", "dossier_id", name="uq_private_follow_owner"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    following: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_mode: Mapped[str] = mapped_column(String(16), default="immediate", server_default="immediate")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    seen_marker: Mapped[str] = mapped_column(String(64))
    research_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublicDossierCopy(Base):
    """Reviewed public snapshot retained inside its new private native dossier."""
    __tablename__ = "product_public_copies"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
            ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
    )
    dossier_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublicReuseReceipt(Base):
    """Minimal durable retry tombstone; deleting the draft cannot recreate it."""
    __tablename__ = "product_public_reuse_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "request_key", name="uq_public_reuse_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dossier_id: Mapped[str | None] = mapped_column(ForeignKey("product_dossiers.id", ondelete="SET NULL"))
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))


class DossierAllowance(Base):
    __tablename__ = "product_dossier_allowances"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    limit: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class DossierAllowanceSlot(Base):
    __tablename__ = "product_dossier_allowance_slots"
    dossier_id: Mapped[str] = mapped_column(ForeignKey("product_dossiers.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class DossierLimitRequest(Base):
    __tablename__ = "product_dossier_limit_requests"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_dossier_limit_request"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_dossier_limit_request_status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    requested_limit: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    previous_limit: Mapped[int] = mapped_column(Integer)
    approved_limit: Mapped[int | None] = mapped_column(Integer)
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    mail_state: Mapped[str] = mapped_column(String(16), default="queued")
    mailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
