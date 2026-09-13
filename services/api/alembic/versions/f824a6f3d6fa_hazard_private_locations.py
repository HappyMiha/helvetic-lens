"""Owner-private C1 locations and immutable configuration revisions."""

import sqlalchemy as sa

from alembic import op

revision = "f824a6f3d6fa"
down_revision = "e71395e2c5e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("hazard_monitors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_hazard_monitor_scope"),
        sa.UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_hazard_monitor_request"),
        sa.CheckConstraint("version >= 1 AND revision >= 1", name="ck_hazard_monitor_version"),
        sa.CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_hazard_monitor_status"))
    for name in ("organization_id", "owner_user_id"):
        op.create_index(f"ix_hazard_monitors_{name}", "hazard_monitors", [name])
    op.create_table("hazard_configuration_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("monitor_id", "revision", name="uq_hazard_configuration_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_hazard_configuration_revision"))
    for name in ("organization_id", "monitor_id"):
        op.create_index(f"ix_hazard_configuration_revisions_{name}", "hazard_configuration_revisions", [name])


def downgrade():
    op.drop_table("hazard_configuration_revisions")
    op.drop_table("hazard_monitors")
