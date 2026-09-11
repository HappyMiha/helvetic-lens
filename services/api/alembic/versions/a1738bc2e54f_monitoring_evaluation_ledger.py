"""Add private evaluation checkpoints and immutable rehearsal evidence.

Revision ID: a1738bc2e54f
Revises: f0627ab1d43e
"""

import sqlalchemy as sa

from alembic import op

revision = "a1738bc2e54f"
down_revision = "f0627ab1d43e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monitoring_evaluation_streams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("binding_json", sa.JSON(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_id", "organization_id"],
                                ["monitoring_subjects.id", "monitoring_subjects.organization_id"],
                                ondelete="CASCADE", name="fk_evaluation_stream_scope"),
        sa.ForeignKeyConstraint(["subject_id", "configuration_revision"],
                                ["monitoring_subject_revisions.subject_id", "monitoring_subject_revisions.revision"],
                                ondelete="CASCADE", name="fk_evaluation_stream_revision"),
        sa.UniqueConstraint("id", "organization_id", name="uq_evaluation_stream_id_org"),
        sa.UniqueConstraint("subject_id", "binding_hash", name="uq_evaluation_stream_binding"),
        sa.CheckConstraint("sequence >= 1", name="ck_evaluation_stream_sequence"),
    )
    for column in ("organization_id", "subject_id"):
        op.create_index(f"ix_monitoring_evaluation_streams_{column}", "monitoring_evaluation_streams", [column])
    op.create_table(
        "monitoring_evaluation_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stream_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("material_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["stream_id", "organization_id"],
                                ["monitoring_evaluation_streams.id", "monitoring_evaluation_streams.organization_id"],
                                ondelete="CASCADE", name="fk_evaluation_entry_scope"),
        sa.UniqueConstraint("stream_id", "sequence", name="uq_evaluation_entry_sequence"),
        sa.UniqueConstraint("stream_id", "request_key", name="uq_evaluation_entry_request"),
        sa.UniqueConstraint("stream_id", "material_id", name="uq_evaluation_entry_material"),
        sa.CheckConstraint("sequence >= 1", name="ck_evaluation_entry_sequence"),
    )
    for column in ("organization_id", "stream_id"):
        op.create_index(f"ix_monitoring_evaluation_entries_{column}", "monitoring_evaluation_entries", [column])


def downgrade():
    op.drop_table("monitoring_evaluation_entries")
    op.drop_table("monitoring_evaluation_streams")
