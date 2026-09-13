"""Durable owner-private auction deadline reminders."""

import sqlalchemy as sa

from alembic import op

revision = "92df5013b194"
down_revision = "81ce4f920a83"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auction_reminders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("profile_revision", sa.Integer(), nullable=False),
        sa.Column("deadline_generation", sa.Integer(), nullable=False),
        sa.Column("deadline_hash", sa.String(64), nullable=False),
        sa.Column("hours", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("check_after", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id", "organization_id"], ["auction_items.id", "auction_items.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("item_id", "profile_revision", "deadline_generation", name="uq_auction_reminder_epoch"),
        sa.CheckConstraint("version >= 1 AND profile_revision >= 1 AND deadline_generation >= 1 AND hours >= 1 AND hours <= 720", name="ck_auction_reminder_versions"),
        sa.CheckConstraint("state IN ('scheduled','ready','acknowledged','invalidated')", name="ck_auction_reminder_state"))
    for column in ("monitor_id", "organization_id", "item_id", "state", "check_after"):
        op.create_index(f"ix_auction_reminders_{column}", "auction_reminders", [column])


def downgrade():
    for column in ("check_after", "state", "item_id", "organization_id", "monitor_id"):
        op.drop_index(f"ix_auction_reminders_{column}", table_name="auction_reminders")
    op.drop_table("auction_reminders")
