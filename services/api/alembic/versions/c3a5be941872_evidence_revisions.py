"""Track evidence corrections independently of document identifiers.

Revision ID: c3a5be941872
Revises: b294ad830761
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "c3a5be941872"
down_revision = "b294ad830761"
branch_labels = None
depends_on = None

# Frozen migration contract. Operational timestamps/health/use counters do not
# change the evidence supplied to relation analysis. Future changes need a migration.
INPUT_COLUMNS = {
    "versions": (
        "owner_organization_id",
        "law_id",
        "title",
        "content_hash",
        "extractor",
        "text",
        "passages",
        "content_type",
        "artifact_key",
        "filename",
        "source_url",
        "origin",
        "declared_date",
        "date_provenance",
        "synthetic",
        "identity_json",
    ),
    "regulatory_document_versions": (
        "expression_id",
        "version_key",
        "legacy_version_id",
        "content_hash",
        "artifact_key",
        "extractor",
        "text",
        "passages",
        "content_type",
        "filename",
        "source_url",
        "metadata_json",
    ),
    "regulatory_works": (
        "owner_organization_id",
        "kind",
        "authority",
        "canonical_key",
        "title",
        "stable_official_url",
        "lifecycle_status",
        "metadata_json",
    ),
    "regulatory_events": (
        "work_id",
        "expression_id",
        "document_version_id",
        "authority",
        "event_type",
        "detected_at",
        "source_url",
        "provenance_method",
        "evidence_json",
    ),
    "regulatory_relations": (
        "subject_work_id",
        "object_work_id",
        "source_version_id",
        "supersedes_relation_id",
        "authority",
        "relation_type",
        "state",
        "provenance_method",
        "evidence_fingerprint",
        "confidence",
        "evidence_json",
        "rule_or_model_revision",
    ),
    "relation_candidates": (
        "event_id",
        "source_work_id",
        "target_work_id",
        "relation_id",
        "source_version_id",
        "target_version_id",
        "status",
        "score",
        "score_components_json",
        "why_json",
        "evidence_json",
        "rule_revision",
    ),
}


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Evidence revision triggers require SQLite or PostgreSQL.")
    epoch = op.create_table(
        "evidence_revision_epochs",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("epoch", sa.String(36), nullable=False),
    )
    op.bulk_insert(epoch, [{"id": "inputs", "epoch": str(uuid.uuid4())}])
    for table, columns in INPUT_COLUMNS.items():
        op.add_column(table, sa.Column("evidence_revision", sa.Integer(), nullable=False, server_default="1"))
        trigger = "hl_evidence_" + table
        fields = ", ".join(f'"{column}"' for column in columns)
        if dialect == "sqlite":
            changed = " OR ".join(f'OLD."{column}" IS NOT NEW."{column}"' for column in columns)
            op.execute(f'''CREATE TRIGGER "{trigger}" AFTER UPDATE OF {fields} ON "{table}"
                WHEN {changed}
                BEGIN UPDATE "{table}" SET evidence_revision = OLD.evidence_revision + 1
                WHERE id = NEW.id; END''')
        else:
            # JSON columns use their stored text; even reordered JSON can
            # conservatively invalidate an assessment, never hide a correction.
            changed = " OR ".join(
                f'OLD."{column}"::text IS DISTINCT FROM NEW."{column}"::text' for column in columns
            )
            op.execute(f'''CREATE FUNCTION "{trigger}"() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    IF {changed} THEN NEW.evidence_revision := OLD.evidence_revision + 1;
                    ELSE NEW.evidence_revision := OLD.evidence_revision; END IF;
                    RETURN NEW;
                END $$''')
            op.execute(f'''CREATE TRIGGER "{trigger}" BEFORE UPDATE OF {fields} ON "{table}"
                FOR EACH ROW EXECUTE FUNCTION "{trigger}"()''')


def downgrade():
    dialect = op.get_bind().dialect.name
    for table in reversed(INPUT_COLUMNS):
        trigger = "hl_evidence_" + table
        if dialect == "sqlite":
            op.execute(f'DROP TRIGGER "{trigger}"')
        else:
            op.execute(f'DROP TRIGGER "{trigger}" ON "{table}"')
            op.execute(f'DROP FUNCTION "{trigger}"()')
        op.drop_column(table, "evidence_revision")
    op.drop_table("evidence_revision_epochs")
