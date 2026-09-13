"""Private Road Watch profiles and immutable configuration history."""

import sqlalchemy as sa

from alembic import op

revision = "c5f173c0a3c7"
down_revision = "b4e062bf92b6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("road_monitors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("health", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_road_monitor_scope"),
        sa.UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_road_monitor_request"),
        sa.CheckConstraint("version >= 1 AND revision >= 1", name="ck_road_monitor_version"),
        sa.CheckConstraint("status IN ('draft','active','paused','archived')", name="ck_road_monitor_status"))
    op.create_index("ix_road_monitors_organization_id", "road_monitors", ["organization_id"])
    op.create_index("ix_road_monitors_owner_user_id", "road_monitors", ["owner_user_id"])
    op.create_table("road_configuration_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"],
                                ondelete="CASCADE"),
        sa.UniqueConstraint("monitor_id", "revision", name="uq_road_configuration_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_road_configuration_revision"))
    op.create_index("ix_road_configuration_revisions_monitor_id", "road_configuration_revisions", ["monitor_id"])
    op.create_index("ix_road_configuration_revisions_organization_id", "road_configuration_revisions", ["organization_id"])


def downgrade():
    op.drop_table("road_configuration_revisions")
    op.drop_table("road_monitors")
