"""Private warning lifecycle and completed shared source poll markers."""

import sqlalchemy as sa

from alembic import op

revision = "2bd7e936a92d"
down_revision = "1ac6d825f81c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hazard_monitors", sa.Column("health", sa.String(32), nullable=False, server_default="not_started"))
    op.add_column("hazard_monitors", sa.Column("last_poll_at", sa.DateTime(timezone=True)))
    op.add_column("hazard_monitors", sa.Column("next_poll_at", sa.DateTime(timezone=True)))
    op.add_column("hazard_monitors", sa.Column("activation_proof", sa.JSON()))
    op.create_index("ix_hazard_monitors_next_poll_at", "hazard_monitors", ["next_poll_at"])
    op.add_column("hazard_source_selections", sa.Column("last_poll_at", sa.DateTime(timezone=True)))
    op.add_column("hazard_source_selections", sa.Column("last_poll_hash", sa.String(64)))
    op.add_column("hazard_source_selections", sa.Column("poll_cursor_version", sa.Integer()))
    op.create_table("hazard_monitor_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("previous_status", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("proof", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("monitor_id", "version", name="uq_hazard_monitor_action_version"),
        sa.CheckConstraint("action IN ('start','resume','pause','archive')", name="ck_hazard_monitor_action"))
    op.create_index("ix_hazard_monitor_actions_organization_id", "hazard_monitor_actions", ["organization_id"])
    op.create_index("ix_hazard_monitor_actions_monitor_id", "hazard_monitor_actions", ["monitor_id"])


def downgrade():
    op.drop_table("hazard_monitor_actions")
    for name in ("poll_cursor_version", "last_poll_hash", "last_poll_at"):
        op.drop_column("hazard_source_selections", name)
    op.drop_index("ix_hazard_monitors_next_poll_at", table_name="hazard_monitors")
    for name in ("activation_proof", "next_poll_at", "last_poll_at", "health"):
        op.drop_column("hazard_monitors", name)
