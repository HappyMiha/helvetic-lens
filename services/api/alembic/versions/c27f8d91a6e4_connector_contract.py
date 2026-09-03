"""Add global connector checkpoints, receipts, and extracted corpus text."""

import sqlalchemy as sa

from alembic import op

revision = "c27f8d91a6e4"
down_revision = "b94e1c62d7a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("regulatory_document_versions") as batch:
        batch.add_column(sa.Column("extractor", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("passages", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("content_type", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("filename", sa.Text(), nullable=True))

    op.create_table(
        "connector_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connector", sa.String(length=80), nullable=False),
        sa.Column("stream", sa.String(length=200), nullable=False),
        sa.Column("contract_version", sa.String(length=80), nullable=False),
        sa.Column("connector_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("cursor_json", sa.JSON(), nullable=True),
        sa.Column("page_checkpoint_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("health", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("health_message", sa.Text(), nullable=True),
        sa.Column("source_contract_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "health IN ('healthy', 'degraded', 'error', 'unknown')",
            name="ck_connector_state_health",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector", "stream", name="uq_connector_state_stream"),
    )
    op.create_index("ix_connector_states_connector", "connector_states", ["connector"])
    op.create_index("ix_connector_states_health", "connector_states", ["health"])

    op.create_table(
        "connector_pages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connector", sa.String(length=80), nullable=False),
        sa.Column("stream", sa.String(length=200), nullable=False),
        sa.Column("page_key", sa.String(length=64), nullable=False),
        sa.Column("input_cursor_json", sa.JSON(), nullable=True),
        sa.Column("output_cursor_json", sa.JSON(), nullable=True),
        sa.Column("safe_checkpoint_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("persisted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_provenance_ref", sa.Text(), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'partial', 'persisted', 'degraded', 'failed')",
            name="ck_connector_page_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector", "stream", "page_key", name="uq_connector_page_key"),
    )
    op.create_index("ix_connector_pages_connector", "connector_pages", ["connector"])
    op.create_index("ix_connector_pages_status", "connector_pages", ["status"])

    op.create_table(
        "connector_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connector", sa.String(length=80), nullable=False),
        sa.Column("stream", sa.String(length=200), nullable=False),
        sa.Column("external_identity", sa.String(length=700), nullable=False),
        sa.Column("expression_key", sa.String(length=700), nullable=False),
        sa.Column("source_revision", sa.String(length=200), nullable=False),
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("expression_id", sa.String(length=36), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=True),
        sa.Column("raw_provenance_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("contract_version", sa.String(length=80), nullable=False),
        sa.Column("connector_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("persisted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_version_id"], ["regulatory_document_versions.id"]),
        sa.ForeignKeyConstraint(["expression_id"], ["regulatory_expressions.id"]),
        sa.ForeignKeyConstraint(["work_id"], ["regulatory_works.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connector",
            "stream",
            "external_identity",
            "expression_key",
            "source_revision",
            name="uq_connector_receipt_revision",
        ),
    )
    op.create_index("ix_connector_receipts_connector", "connector_receipts", ["connector"])
    op.create_index("ix_connector_receipts_external_identity", "connector_receipts", ["external_identity"])
    op.create_index("ix_connector_receipts_work_id", "connector_receipts", ["work_id"])
    op.create_index("ix_connector_receipts_artifact_hash", "connector_receipts", ["artifact_hash"])

    op.create_table(
        "connector_item_errors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("page_id", sa.String(length=36), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("external_identity", sa.String(length=700), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("raw_provenance_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["page_id"], ["connector_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "item_index", "attempt", name="uq_connector_item_error_attempt"),
    )
    op.create_index("ix_connector_item_errors_page_id", "connector_item_errors", ["page_id"])


def downgrade():
    op.drop_table("connector_item_errors")
    op.drop_table("connector_receipts")
    op.drop_table("connector_pages")
    op.drop_table("connector_states")
    with op.batch_alter_table("regulatory_document_versions") as batch:
        batch.drop_column("filename")
        batch.drop_column("content_type")
        batch.drop_column("passages")
        batch.drop_column("text")
        batch.drop_column("extractor")
