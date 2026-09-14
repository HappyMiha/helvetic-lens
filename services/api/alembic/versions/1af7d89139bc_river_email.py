"""Private River email consent and durable notification intents."""

import sqlalchemy as sa

from alembic import op

revision = "1af7d89139bc"
down_revision = "09e6c78028ab"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("river_monitors", sa.Column("email_revision", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("river_email_policies",
        sa.Column("monitor_id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False), sa.Column("recipient_email", sa.String(320)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["river_monitors.id", "river_monitors.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("revision >= 1", name="ck_river_email_revision"))
    op.create_index("ix_river_email_policies_organization_id", "river_email_policies", ["organization_id"])
    op.create_table("river_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("river_changes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_revision", sa.Integer(), nullable=False),
        sa.Column("signal_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("due_at", "created_at")],
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in ("claimed_at", "sent_at")],
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["river_monitors.id", "river_monitors.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitor_id", "consent_revision"], ["river_email_policies.monitor_id", "river_email_policies.revision"], ondelete="CASCADE"),
        sa.UniqueConstraint("monitor_id", "signal_hash", "consent_revision", name="uq_river_delivery_intent"),
        sa.CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_river_delivery_state"))
    for name in ("organization_id", "monitor_id", "owner_user_id", "change_id", "signal_hash", "state", "due_at"):
        op.create_index("ix_river_deliveries_" + name, "river_deliveries", [name])


def downgrade():
    op.drop_table("river_deliveries")
    op.drop_table("river_email_policies")
    op.drop_column("river_monitors", "email_revision")
