"""Add the normalized regulatory corpus and preserve legacy document mappings."""

import sqlalchemy as sa

from alembic import op

revision = "a83d2f417c90"
down_revision = "f77d9a64b8e5"
branch_labels = None
depends_on = None


def _timestamps():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade():
    op.create_table(
        "regulatory_works",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_organization_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("authority", sa.String(length=80), nullable=False),
        sa.Column("canonical_key", sa.String(length=700), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("stable_official_url", sa.Text(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=60), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        _timestamps(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('act', 'ordinance', 'parliamentary_business', 'initiative', 'bill', "
            "'court_decision', 'official_notice', 'unclassified_document')",
            name="ck_regulatory_work_kind",
        ),
        sa.ForeignKeyConstraint(["owner_organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_regulatory_works_owner_organization_id",
        "regulatory_works",
        ["owner_organization_id"],
    )
    op.create_index(
        "uq_public_regulatory_work_authority_key",
        "regulatory_works",
        ["authority", "canonical_key"],
        unique=True,
        postgresql_where=sa.text("owner_organization_id IS NULL"),
        sqlite_where=sa.text("owner_organization_id IS NULL"),
    )
    op.create_index(
        "uq_private_regulatory_work_authority_key",
        "regulatory_works",
        ["owner_organization_id", "authority", "canonical_key"],
        unique=True,
        postgresql_where=sa.text("owner_organization_id IS NOT NULL"),
        sqlite_where=sa.text("owner_organization_id IS NOT NULL"),
    )
    op.create_index("ix_regulatory_works_kind", "regulatory_works", ["kind"])
    op.create_index("ix_regulatory_works_authority", "regulatory_works", ["authority"])
    op.create_index("ix_regulatory_works_lifecycle_status", "regulatory_works", ["lifecycle_status"])

    op.create_table(
        "regulatory_identifiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("authority", sa.String(length=80), nullable=False),
        sa.Column("scheme", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.String(length=700), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        _timestamps(),
        sa.ForeignKeyConstraint(["work_id"], ["regulatory_works.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("authority", "scheme", "normalized_value", name="uq_regulatory_identifier_value"),
        sa.UniqueConstraint(
            "work_id", "scheme", "normalized_value", name="uq_regulatory_identifier_work_value"
        ),
    )
    op.create_index("ix_regulatory_identifiers_work_id", "regulatory_identifiers", ["work_id"])
    op.create_index("ix_regulatory_identifiers_authority", "regulatory_identifiers", ["authority"])
    op.create_index("ix_regulatory_identifiers_scheme", "regulatory_identifiers", ["scheme"])

    op.create_table(
        "regulatory_expressions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("expression_key", sa.String(length=700), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        _timestamps(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["work_id"], ["regulatory_works.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "language", "expression_key", name="uq_regulatory_expression_key"),
    )
    op.create_index("ix_regulatory_expressions_work_id", "regulatory_expressions", ["work_id"])
    op.create_index("ix_regulatory_expressions_language", "regulatory_expressions", ["language"])

    op.create_table(
        "regulatory_document_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("expression_id", sa.String(length=36), nullable=False),
        sa.Column("version_key", sa.String(length=700), nullable=False),
        sa.Column("legacy_version_id", sa.String(length=36), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("artifact_key", sa.String(length=80), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        _timestamps(),
        sa.ForeignKeyConstraint(["expression_id"], ["regulatory_expressions.id"]),
        sa.ForeignKeyConstraint(["legacy_version_id"], ["versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expression_id", "version_key", name="uq_regulatory_document_version_key"),
        sa.UniqueConstraint("legacy_version_id", name="uq_regulatory_document_version_legacy"),
    )
    op.create_index(
        "ix_regulatory_document_versions_expression_id",
        "regulatory_document_versions",
        ["expression_id"],
    )
    op.create_index(
        "ix_regulatory_document_versions_content_hash",
        "regulatory_document_versions",
        ["content_hash"],
    )
    op.create_index(
        "ix_regulatory_document_versions_fetched_at",
        "regulatory_document_versions",
        ["fetched_at"],
    )

    op.create_table(
        "regulatory_dates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("date_value", sa.String(length=40), nullable=False),
        sa.Column("precision", sa.String(length=20), nullable=False),
        sa.Column("provenance", sa.String(length=60), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('detected_at', 'published_at', 'version_date', 'effective_from', "
            "'effective_to', 'decision_date', 'fetched_at')",
            name="ck_regulatory_date_kind",
        ),
        sa.CheckConstraint(
            "precision IN ('instant', 'day', 'month', 'year', 'unknown')",
            name="ck_regulatory_date_precision",
        ),
        sa.CheckConstraint(
            "entity_type IN ('work', 'expression', 'version', 'event')",
            name="ck_regulatory_date_entity_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "kind",
            "date_value",
            "precision",
            "provenance",
            name="uq_regulatory_date_fact",
        ),
    )
    op.create_index("ix_regulatory_dates_entity_type", "regulatory_dates", ["entity_type"])
    op.create_index("ix_regulatory_dates_entity_id", "regulatory_dates", ["entity_id"])
    op.create_index("ix_regulatory_dates_kind", "regulatory_dates", ["kind"])

    op.create_table(
        "regulatory_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("expression_id", sa.String(length=36), nullable=True),
        sa.Column("document_version_id", sa.String(length=36), nullable=True),
        sa.Column("authority", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("dedupe_key", sa.String(length=700), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("provenance_method", sa.String(length=60), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default="{}"),
        _timestamps(),
        sa.CheckConstraint(
            "event_type IN ('created', 'new_version', 'amended', 'repealed', 'replaced', "
            "'status_changed', 'decided', 'notice_published')",
            name="ck_regulatory_event_type",
        ),
        sa.ForeignKeyConstraint(["document_version_id"], ["regulatory_document_versions.id"]),
        sa.ForeignKeyConstraint(["expression_id"], ["regulatory_expressions.id"]),
        sa.ForeignKeyConstraint(["work_id"], ["regulatory_works.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("authority", "dedupe_key", name="uq_regulatory_event_dedupe"),
    )
    op.create_index("ix_regulatory_events_work_id", "regulatory_events", ["work_id"])
    op.create_index("ix_regulatory_events_authority", "regulatory_events", ["authority"])
    op.create_index("ix_regulatory_events_event_type", "regulatory_events", ["event_type"])
    op.create_index("ix_regulatory_events_detected_at", "regulatory_events", ["detected_at"])

    op.create_table(
        "regulatory_relations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_work_id", sa.String(length=36), nullable=False),
        sa.Column("object_work_id", sa.String(length=36), nullable=False),
        sa.Column("source_version_id", sa.String(length=36), nullable=True),
        sa.Column("supersedes_relation_id", sa.String(length=36), nullable=True),
        sa.Column("authority", sa.String(length=80), nullable=False),
        sa.Column("relation_type", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("provenance_method", sa.String(length=40), nullable=False),
        sa.Column("dedupe_key", sa.String(length=700), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("rule_or_model_revision", sa.String(length=100), nullable=True),
        _timestamps(),
        sa.CheckConstraint(
            "relation_type IN ('amends', 'repeals', 'replaces', 'implements', 'cites', "
            "'interprets', 'potentially_impacts')",
            name="ck_regulatory_relation_type",
        ),
        sa.CheckConstraint(
            "state IN ('confirmed', 'proposed', 'rejected')",
            name="ck_regulatory_relation_state",
        ),
        sa.ForeignKeyConstraint(["object_work_id"], ["regulatory_works.id"]),
        sa.ForeignKeyConstraint(["source_version_id"], ["regulatory_document_versions.id"]),
        sa.ForeignKeyConstraint(["subject_work_id"], ["regulatory_works.id"]),
        sa.ForeignKeyConstraint(["supersedes_relation_id"], ["regulatory_relations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("authority", "dedupe_key", name="uq_regulatory_relation_dedupe"),
    )
    op.create_index("ix_regulatory_relations_subject_work_id", "regulatory_relations", ["subject_work_id"])
    op.create_index("ix_regulatory_relations_object_work_id", "regulatory_relations", ["object_work_id"])
    op.create_index("ix_regulatory_relations_authority", "regulatory_relations", ["authority"])
    op.create_index("ix_regulatory_relations_relation_type", "regulatory_relations", ["relation_type"])
    op.create_index("ix_regulatory_relations_state", "regulatory_relations", ["state"])
    op.create_index(
        "ix_regulatory_relations_provenance_method",
        "regulatory_relations",
        ["provenance_method"],
    )

    op.create_table(
        "legacy_document_mappings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_organization_id", sa.String(length=36), nullable=True),
        sa.Column("law_id", sa.String(length=36), nullable=False),
        sa.Column("work_id", sa.String(length=36), nullable=True),
        sa.Column("mapping_status", sa.String(length=30), nullable=False),
        sa.Column("canonical_hint", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        _timestamps(),
        sa.ForeignKeyConstraint(["law_id"], ["laws.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["work_id"], ["regulatory_works.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("law_id", name="uq_legacy_document_mapping_law"),
    )
    op.create_index("ix_legacy_document_mappings_law_id", "legacy_document_mappings", ["law_id"])
    op.create_index(
        "ix_legacy_document_mappings_owner_organization_id",
        "legacy_document_mappings",
        ["owner_organization_id"],
    )
    op.create_index("ix_legacy_document_mappings_work_id", "legacy_document_mappings", ["work_id"])
    op.create_index(
        "ix_legacy_document_mappings_mapping_status",
        "legacy_document_mappings",
        ["mapping_status"],
    )

    # Keep every URL-driven record addressable. These provisional works are merged
    # into official authority identities by later connector ingestion, never guessed here.
    op.execute(
        "INSERT INTO regulatory_works "
        "(id, owner_organization_id, kind, authority, canonical_key, title, stable_official_url, lifecycle_status, "
        "metadata_json, created_at, updated_at) "
        "SELECT id, owner_organization_id, 'unclassified_document', provider, "
        "CASE WHEN owner_organization_id IS NULL THEN canonical_identity "
        "ELSE owner_organization_id || ':' || canonical_identity END, "
        "name, url, NULL, '{}', created_at, created_at FROM laws"
    )
    op.execute(
        "INSERT INTO regulatory_identifiers "
        "(id, work_id, authority, scheme, value, normalized_value, source_url, created_at) "
        "SELECT id, id, provider, 'legacy_canonical_identity', canonical_identity, "
        "CASE WHEN owner_organization_id IS NULL THEN canonical_identity "
        "ELSE owner_organization_id || ':' || canonical_identity END, url, created_at FROM laws"
    )
    op.execute(
        "INSERT INTO regulatory_expressions "
        "(id, work_id, language, expression_key, title, official_url, metadata_json, "
        "created_at, updated_at) "
        "SELECT id, id, 'und', canonical_identity, name, url, '{}', created_at, created_at FROM laws"
    )
    op.execute(
        "INSERT INTO regulatory_document_versions "
        "(id, expression_id, version_key, legacy_version_id, content_hash, artifact_key, "
        "source_url, fetched_at, metadata_json, created_at) "
        "SELECT id, law_id, content_hash || ':' || extractor, id, content_hash, artifact_key, "
        "source_url, created_at, '{}', created_at FROM versions"
    )
    op.execute(
        "INSERT INTO legacy_document_mappings "
        "(id, owner_organization_id, law_id, work_id, mapping_status, canonical_hint, reason, created_at) "
        "SELECT id, owner_organization_id, id, id, 'provisional', canonical_identity, "
        "'Awaiting an authority-scoped identifier from an official connector.', created_at FROM laws"
    )


def downgrade():
    for table in (
        "legacy_document_mappings",
        "regulatory_relations",
        "regulatory_events",
        "regulatory_dates",
        "regulatory_document_versions",
        "regulatory_expressions",
        "regulatory_identifiers",
        "regulatory_works",
    ):
        op.drop_table(table)
