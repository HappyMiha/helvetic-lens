"""Private B2 profiles, dossier evidence and internal decisions."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


def identifier():
    return str(uuid4())


class TenderMonitor(Base):
    __tablename__ = "tender_monitors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_tender_monitor_scope"),
        UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_tender_monitor_request"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_tender_monitor_version"),
        CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_tender_monitor_status"),
        CheckConstraint("visibility IN ('private','workspace')", name="ck_tender_monitor_visibility"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    visibility: Mapped[str] = mapped_column(String(12), default="private", server_default="private")
    responsible_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    configuration: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    email_revision: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    health: Mapped[str] = mapped_column(String(40), default="waiting")
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenderProfileRevision(Base):
    __tablename__ = "tender_profile_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["tender_monitors.id", "tender_monitors.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("monitor_id", "revision", name="uq_tender_profile_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenderCollection(Base):
    """Private query/checkpoint data; never placed in a shared source cache."""

    __tablename__ = "tender_collections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["tender_monitors.id", "tender_monitors.organization_id"],
            ondelete="CASCADE",
        ),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenderSourceLease(Base):
    """Shared request budget with no private queries, owners or source content."""

    __tablename__ = "tender_source_leases"
    key: Mapped[str] = mapped_column(String(24), primary_key=True)
    next_request_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenderCpvCache(Base):
    """Public official taxonomy only; no company profiles or discovery queries."""

    __tablename__ = "tender_cpv_cache"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    ancestry: Mapped[dict] = mapped_column(JSON)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TenderDossier(Base):
    __tablename__ = "tender_dossiers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["tender_monitors.id", "tender_monitors.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "organization_id", name="uq_tender_dossier_scope"),
        # Empty lot_key means the project has no lots; SQL NULL is not unique.
        UniqueConstraint("monitor_id", "project_id", "lot_key", name="uq_tender_dossier_identity"),
        CheckConstraint(
            "version >= 1 AND latest_sequence >= 0 AND latest_ordinal >= 0", name="ck_tender_dossier_version"
        ),
        CheckConstraint("review_state IN ('new','needs_review','reviewed')", name="ck_tender_dossier_review"),
        CheckConstraint(
            "decision IS NULL OR decision IN ('bid','no_bid','monitor')", name="ck_tender_dossier_decision"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    lot_key: Mapped[str] = mapped_column(String(36), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    following: Mapped[bool] = mapped_column(Boolean, default=False)
    latest_sequence: Mapped[int] = mapped_column(Integer, default=0)
    latest_ordinal: Mapped[int] = mapped_column(Integer, default=0)
    review_state: Mapped[str] = mapped_column(String(16), default="new")
    decision: Mapped[str | None] = mapped_column(String(12))
    reviewed_sequence: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class TenderDocumentAccess(Base):
    """Explicit reviewed private grant; there is no public grant endpoint."""
    __tablename__ = "tender_document_access"
    __table_args__ = (
        ForeignKeyConstraint(["dossier_id", "organization_id"],
                             ["tender_dossiers.id", "tender_dossiers.organization_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", "dossier_id", name="uq_tender_document_access_scope"),
        CheckConstraint("retain_until >= valid_until", name="ck_tender_document_retention"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(100))
    publication_id: Mapped[str] = mapped_column(String(36))
    account_reference: Mapped[str] = mapped_column(String(200))
    policy_reference: Mapped[str] = mapped_column(String(500))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    retain_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observation_id: Mapped[str | None] = mapped_column(String(36))
    last_observation_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenderDocumentSnapshot(Base):
    """Private immutable bytes/projection; retention purges leave metadata only."""
    __tablename__ = "tender_document_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(["access_id", "organization_id", "dossier_id"],
                             ["tender_document_access.id", "tender_document_access.organization_id",
                              "tender_document_access.dossier_id"], ondelete="CASCADE"),
        UniqueConstraint("access_id", "item_id", "content_sha256", "text_sha256", "extractor_version",
                         name="uq_tender_document_projection"),
        CheckConstraint("stored_bytes >= 0", name="ck_tender_document_stored_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    access_id: Mapped[str] = mapped_column(String(36), index=True)
    item_id: Mapped[str] = mapped_column(String(256))
    content_sha256: Mapped[str] = mapped_column(String(64))
    text_sha256: Mapped[str] = mapped_column(String(64))
    extractor_version: Mapped[str] = mapped_column(String(100))
    content_type: Mapped[str] = mapped_column(String(100))
    body: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    parsed: Mapped[dict | None] = mapped_column(JSON, deferred=True)
    stored_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenderDocumentObservation(Base):
    """Immutable private document-set evidence; content expires with its grant."""
    __tablename__ = "tender_document_observations"
    __table_args__ = (
        ForeignKeyConstraint(["access_id", "organization_id", "dossier_id"],
                             ["tender_document_access.id", "tender_document_access.organization_id",
                              "tender_document_access.dossier_id"], ondelete="CASCADE"),
        UniqueConstraint("id", "organization_id", "dossier_id", name="uq_tender_doc_observation_scope"),
        UniqueConstraint("access_id", "sequence", name="uq_tender_doc_observation_sequence"),
        CheckConstraint("stored_bytes >= 0 AND sequence >= 1", name="ck_tender_doc_observation_bounds"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    access_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[dict | None] = mapped_column(JSON, deferred=True)
    deltas: Mapped[list | None] = mapped_column(JSON, deferred=True)
    previous_id: Mapped[str | None] = mapped_column(String(36))
    stored_bytes: Mapped[int] = mapped_column(BigInteger)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenderPublicationSnapshot(Base):
    """One immutable anonymous public original, referenced by private versions."""

    __tablename__ = "tender_publication_snapshots"
    __table_args__ = (CheckConstraint("payload_bytes > 0", name="ck_tender_snapshot_size"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    publication_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    evidence: Mapped[dict] = mapped_column(JSON)
    payload_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class TenderMaterialSection(Base):
    """Content-addressed public normalized fields; never profile or review data."""

    __tablename__ = "tender_material_sections"
    __table_args__ = (CheckConstraint("payload_bytes > 0", name="ck_tender_material_size"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    payload_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class TenderStorageState(Base):
    """Serialized accounting for public payloads; contains no tenant identifiers."""

    __tablename__ = "tender_storage_state"
    __table_args__ = (CheckConstraint("used_bytes >= 0", name="ck_tender_storage_nonnegative"),)
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)


class TenderSourceRestriction(Base):
    """An operator-recorded restriction, never a grant of restricted API rights."""

    __tablename__ = "tender_source_restrictions"
    __table_args__ = (
        CheckConstraint("scope IN ('project','publication')", name="ck_tender_restriction_scope"),
    )
    scope: Mapped[str] = mapped_column(String(12), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_reference: Mapped[str] = mapped_column(String(500))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenderDossierVersion(Base):
    __tablename__ = "tender_dossier_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dossier_id", "organization_id"],
            ["tender_dossiers.id", "tender_dossiers.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("dossier_id", "sequence", name="uq_tender_dossier_sequence"),
        UniqueConstraint(
            "dossier_id",
            "publication_id",
            "source_hash",
            "profile_revision",
            "observation_key",
            name="uq_tender_dossier_evidence",
        ),
        UniqueConstraint("id", "organization_id", name="uq_tender_version_scope"),
        ForeignKeyConstraint(["document_observation_id", "organization_id", "dossier_id"],
                             ["tender_document_observations.id", "tender_document_observations.organization_id",
                              "tender_document_observations.dossier_id"]),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    publication_id: Mapped[str] = mapped_column(String(36))
    publication_ordinal: Mapped[int] = mapped_column(Integer)
    profile_revision: Mapped[int] = mapped_column(Integer)
    observation_key: Mapped[str] = mapped_column(String(36), default="")
    document_observation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    source_hash: Mapped[str] = mapped_column(ForeignKey("tender_publication_snapshots.id"), index=True)
    publish_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    material_keys: Mapped[list] = mapped_column(JSON)
    summary: Mapped[dict] = mapped_column(JSON)
    snapshot: Mapped[TenderPublicationSnapshot] = relationship(lazy="selectin", viewonly=True)
    sections: Mapped[list["TenderVersionSection"]] = relationship(lazy="selectin", viewonly=True)
    match: Mapped[dict] = mapped_column(JSON)
    changes: Mapped[list] = mapped_column(JSON)
    kind: Mapped[str] = mapped_column(String(24))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def evidence(self):
        return self.snapshot.evidence

    @property
    def material(self):
        from .tender_evidence import resolve_material

        return resolve_material(self)


class TenderVersionSection(Base):
    __tablename__ = "tender_version_sections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["version_id", "organization_id"],
            ["tender_dossier_versions.id", "tender_dossier_versions.organization_id"],
            ondelete="CASCADE",
        ),
    )
    version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str] = mapped_column(ForeignKey("tender_material_sections.id"), index=True)
    locator: Mapped[str] = mapped_column(String(300))
    section: Mapped[TenderMaterialSection] = relationship(lazy="selectin", viewonly=True)


class TenderDecision(Base):
    __tablename__ = "tender_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dossier_id", "organization_id"],
            ["tender_dossiers.id", "tender_dossiers.organization_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["dossier_id", "sequence"],
            ["tender_dossier_versions.dossier_id", "tender_dossier_versions.sequence"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("dossier_id", "request_key", name="uq_tender_decision_request"),
        CheckConstraint("decision IN ('bid','no_bid','monitor')", name="ck_tender_decision_value"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    dossier_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(12))
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenderEmailPolicy(Base):
    """Immutable owner consent, bound to a verified address and exact settings."""

    __tablename__ = "tender_email_policies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["tender_monitors.id", "tender_monitors.organization_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("revision >= 1", name="ck_tender_email_revision"),
    )
    monitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    configuration: Mapped[dict] = mapped_column(JSON)
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenderDelivery(Base):
    __tablename__ = "tender_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["tender_monitors.id", "tender_monitors.organization_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["evidence_version_id", "organization_id"],
            ["tender_dossier_versions.id", "tender_dossier_versions.organization_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["monitor_id", "consent_revision"],
            ["tender_email_policies.monitor_id", "tender_email_policies.revision"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("evidence_version_id", "consent_revision", name="uq_tender_delivery_intent"),
        CheckConstraint(
            "state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_tender_delivery_state"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    monitor_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    evidence_version_id: Mapped[str] = mapped_column(String(36), index=True)
    consent_revision: Mapped[int] = mapped_column(Integer)
    signal_hash: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
