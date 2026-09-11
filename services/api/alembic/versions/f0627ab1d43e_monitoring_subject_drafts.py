"""Add generic private monitoring subjects and configuration revisions.

Revision ID: f0627ab1d43e
Revises: ef5169a0c32d
"""

import sqlalchemy as sa

from alembic import op

revision = "f0627ab1d43e"
down_revision = "ef5169a0c32d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monitoring_subjects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.String(80), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_subject_id_org"),
        sa.UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_subject_owner_request"),
        sa.CheckConstraint("status IN ('draft', 'active', 'paused', 'archived')", name="ck_subject_status"),
        sa.CheckConstraint("current_revision >= 1", name="ck_subject_revision"),
        sa.CheckConstraint("contract_version >= 1 AND template_version >= 1", name="ck_subject_versions"),
    )
    for column in ("organization_id", "owner_user_id"):
        op.create_index(f"ix_monitoring_subjects_{column}", "monitoring_subjects", [column])
    op.create_table(
        "monitoring_subject_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_id", "organization_id"],
                                ["monitoring_subjects.id", "monitoring_subjects.organization_id"],
                                ondelete="CASCADE", name="fk_subject_revision_scope"),
        sa.UniqueConstraint("subject_id", "revision", name="uq_subject_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_subject_revision_number"),
    )
    for column in ("organization_id", "subject_id"):
        op.create_index(f"ix_monitoring_subject_revisions_{column}", "monitoring_subject_revisions", [column])


def downgrade():
    op.drop_table("monitoring_subject_revisions")
    op.drop_table("monitoring_subjects")
