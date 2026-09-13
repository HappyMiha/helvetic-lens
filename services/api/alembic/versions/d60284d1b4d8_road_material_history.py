"""Private road material developments and immutable history."""

import sqlalchemy as sa

from alembic import op

revision = "d60284d1b4d8"
down_revision = "c5f173c0a3c7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("road_monitors", sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=False,
        server_default=sa.text("'1970-01-01 00:00:00+00:00'")))
    op.add_column("road_monitors", sa.Column("last_poll_at", sa.DateTime(timezone=True)))
    op.create_index("ix_road_monitors_next_poll_at", "road_monitors", ["next_poll_at"])
    op.create_table("road_developments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("road_source_permissions.id"), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=False),
        sa.Column("development_key", sa.String(64), nullable=False),
        sa.Column("payload", sa.LargeBinary()),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("material_hash", sa.String(64), nullable=False),
        sa.Column("proof", sa.JSON(), nullable=False),
        sa.Column("proof_hash", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewed_sequence", sa.Integer(), nullable=False),
        sa.Column("muted", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "organization_id", name="uq_road_development_scope"),
        sa.UniqueConstraint("monitor_id", "configuration_revision", "permission_id", "source_id", name="uq_road_development_identity"))
    op.create_index("ix_road_developments_monitor_id", "road_developments", ["monitor_id"])
    op.create_index("ix_road_developments_organization_id", "road_developments", ["organization_id"])
    op.create_table("road_event_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("development_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload", sa.LargeBinary()),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("proof", sa.JSON(), nullable=False),
        sa.Column("proof_hash", sa.String(64), nullable=False),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["development_id", "organization_id"], ["road_developments.id", "road_developments.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("development_id", "sequence", name="uq_road_event_sequence"))
    op.create_index("ix_road_event_versions_development_id", "road_event_versions", ["development_id"])
    op.create_index("ix_road_event_versions_organization_id", "road_event_versions", ["organization_id"])


def downgrade():
    op.drop_table("road_event_versions")
    op.drop_table("road_developments")
    op.drop_index("ix_road_monitors_next_poll_at", table_name="road_monitors")
    op.drop_column("road_monitors", "last_poll_at")
    op.drop_column("road_monitors", "next_poll_at")
