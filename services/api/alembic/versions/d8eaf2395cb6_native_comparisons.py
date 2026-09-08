"""Explicit organization native document comparisons; no inferred baselines."""

import sqlalchemy as sa

from alembic import op

revision = "d8eaf2395cb6"
down_revision = "d7d9f1284ba5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "native_document_comparisons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("old_version_id", sa.String(36), sa.ForeignKey("regulatory_document_versions.id"), nullable=False),
        sa.Column("new_version_id", sa.String(36), sa.ForeignKey("regulatory_document_versions.id"), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("diff", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "old_version_id", "new_version_id", "input_fingerprint",
                            name="uq_native_comparison_input"),
        sa.CheckConstraint("old_version_id <> new_version_id", name="ck_native_comparison_distinct"),
    )
    for column in ("organization_id", "old_version_id", "new_version_id"):
        op.create_index(f"ix_native_document_comparisons_{column}", "native_document_comparisons", [column])
    op.create_table(
        "native_event_comparison_selections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("regulatory_events.id"), nullable=False),
        sa.Column("comparison_id", sa.String(36), sa.ForeignKey("native_document_comparisons.id")),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "event_id", name="uq_native_event_comparison_org_event"),
        sa.CheckConstraint("revision >= 1", name="ck_native_selection_revision"),
    )
    for column in ("organization_id", "event_id"):
        op.create_index(f"ix_native_event_comparison_selections_{column}", "native_event_comparison_selections", [column])


def downgrade():
    op.drop_table("native_event_comparison_selections")
    op.drop_table("native_document_comparisons")
