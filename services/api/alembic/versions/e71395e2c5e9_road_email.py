"""Private road consent revisions and exact-version delivery attempts."""

import sqlalchemy as sa

from alembic import op

revision = "e71395e2c5e9"
down_revision = "d60284d1b4d8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("road_monitors", sa.Column("email_revision", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_table("road_email_policies",
        sa.Column("monitor_id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("revision >= 1", name="ck_road_email_revision"))
    op.create_index("ix_road_email_policies_organization_id", "road_email_policies", ["organization_id"])
    op.create_table("road_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("development_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("consent_revision", sa.Integer(), nullable=False),
        sa.Column("signal_hash", sa.String(64), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["road_monitors.id", "road_monitors.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["development_id", "organization_id"], ["road_developments.id", "road_developments.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["development_id", "sequence"], ["road_event_versions.development_id", "road_event_versions.sequence"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitor_id", "consent_revision"], ["road_email_policies.monitor_id", "road_email_policies.revision"], ondelete="CASCADE"),
        sa.UniqueConstraint("development_id", "sequence", "consent_revision", name="uq_road_delivery_intent"),
        sa.CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_road_delivery_state"))
    for name in ("organization_id", "monitor_id", "owner_user_id", "development_id", "signal_hash", "state", "due_at"):
        op.create_index(f"ix_road_deliveries_{name}", "road_deliveries", [name])


def downgrade():
    op.drop_table("road_deliveries")
    op.drop_table("road_email_policies")
    op.drop_column("road_monitors", "email_revision")
