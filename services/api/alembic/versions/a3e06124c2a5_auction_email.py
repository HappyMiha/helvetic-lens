"""Verified owner consent and durable auction email intents."""

import sqlalchemy as sa

from alembic import op

revision = "a3e06124c2a5"
down_revision = "92df5013b194"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auction_monitors", sa.Column("email_revision", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.create_table("auction_email_policies",
        sa.Column("monitor_id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("recipient_email", sa.String(320)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("revision >= 1", name="ck_auction_email_revision"))
    op.create_index("ix_auction_email_policies_organization_id", "auction_email_policies", ["organization_id"])
    op.create_table("auction_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("auction_item_events.id", ondelete="CASCADE")),
        sa.Column("reminder_id", sa.String(36), sa.ForeignKey("auction_reminders.id", ondelete="CASCADE")),
        sa.Column("consent_revision", sa.Integer(), nullable=False),
        sa.Column("signal_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id", "organization_id"], ["auction_items.id", "auction_items.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitor_id", "consent_revision"], ["auction_email_policies.monitor_id", "auction_email_policies.revision"], ondelete="CASCADE"),
        sa.UniqueConstraint("monitor_id", "signal_hash", "consent_revision", name="uq_auction_delivery_intent"),
        sa.CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_auction_delivery_state"),
        sa.CheckConstraint("(event_id IS NOT NULL AND reminder_id IS NULL) OR (event_id IS NULL AND reminder_id IS NOT NULL)", name="ck_auction_delivery_signal"))
    for column in ("organization_id", "monitor_id", "owner_user_id", "item_id", "signal_hash", "state", "due_at"):
        op.create_index(f"ix_auction_deliveries_{column}", "auction_deliveries", [column])


def downgrade():
    for column in ("due_at", "state", "signal_hash", "item_id", "owner_user_id", "monitor_id", "organization_id"):
        op.drop_index(f"ix_auction_deliveries_{column}", table_name="auction_deliveries")
    op.drop_table("auction_deliveries")
    op.drop_index("ix_auction_email_policies_organization_id", table_name="auction_email_policies")
    op.drop_table("auction_email_policies")
    op.drop_column("auction_monitors", "email_revision")
