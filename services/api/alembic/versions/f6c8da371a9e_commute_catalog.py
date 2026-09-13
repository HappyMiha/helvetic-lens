"""Verified transport catalog and private commute configurations."""

import sqlalchemy as sa

from alembic import op

revision = "f6c8da371a9e"
down_revision = "e5b7cf26098d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("commute_leg_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("identity_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("identity", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False))
    op.create_table("commute_dated_legs",
        sa.Column("reference_id", sa.String(36), sa.ForeignKey("commute_leg_references.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("service_day", sa.Date(), primary_key=True),
        sa.Column("static_version", sa.String(256), primary_key=True),
        sa.Column("resolved", sa.JSON(), nullable=False),
        sa.Column("resolved_hash", sa.String(64), nullable=False))
    op.create_table("commute_monitors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("paused_on", sa.Date(), nullable=True),
        sa.Column("health", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_commute_monitor_scope"),
        sa.UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_commute_monitor_request"),
        sa.CheckConstraint("version >= 1 AND revision >= 1", name="ck_commute_monitor_version"),
        sa.CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_commute_monitor_status"))
    for column in ("organization_id", "owner_user_id"):
        op.create_index(f"ix_commute_monitors_{column}", "commute_monitors", [column])
    op.create_table("commute_configuration_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["commute_monitors.id", "commute_monitors.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("monitor_id", "revision", name="uq_commute_configuration_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_commute_configuration_revision"))
    for column in ("monitor_id", "organization_id"):
        op.create_index(f"ix_commute_configuration_revisions_{column}", "commute_configuration_revisions", [column])


def downgrade():
    op.drop_table("commute_configuration_revisions")
    op.drop_table("commute_monitors")
    op.drop_table("commute_dated_legs")
    op.drop_table("commute_leg_references")
