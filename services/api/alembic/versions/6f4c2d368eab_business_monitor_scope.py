"""Explicit business monitor workspace scope; all existing records stay private."""

import sqlalchemy as sa

from alembic import op

revision = "6f4c2d368eab"
down_revision = "5e3b1c257dfa"
branch_labels = None
depends_on = None


def upgrade():
    for kind in ("tender", "trademark", "auction"):
        with op.batch_alter_table(f"{kind}_monitors") as batch:
            batch.add_column(sa.Column("visibility", sa.String(12), nullable=False, server_default="private"))
            batch.add_column(sa.Column("responsible_user_id", sa.String(36), nullable=True))
            batch.create_foreign_key(f"fk_{kind}_responsible_user", "users", ["responsible_user_id"], ["id"], ondelete="SET NULL")
            batch.create_check_constraint(f"ck_{kind}_monitor_visibility", "visibility IN ('private','workspace')")
    op.create_table("business_monitor_scope_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tender_monitor_id", sa.String(36)), sa.Column("trademark_monitor_id", sa.String(36)),
        sa.Column("auction_monitor_id", sa.String(36)), sa.Column("monitor_version", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("previous_scope", sa.String(12), nullable=False), sa.Column("scope", sa.String(12), nullable=False),
        sa.Column("responsible_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tender_monitor_id", "organization_id"], ["tender_monitors.id", "tender_monitors.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trademark_monitor_id", "organization_id"], ["trademark_monitors.id", "trademark_monitors.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["auction_monitor_id", "organization_id"], ["auction_monitors.id", "auction_monitors.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("(CASE WHEN tender_monitor_id IS NULL THEN 0 ELSE 1 END + CASE WHEN trademark_monitor_id IS NULL THEN 0 ELSE 1 END + CASE WHEN auction_monitor_id IS NULL THEN 0 ELSE 1 END) = 1", name="ck_business_scope_target"),
        sa.CheckConstraint("previous_scope IN ('private','workspace') AND scope IN ('private','workspace') AND monitor_version >= 1", name="ck_business_scope_values"),
        sa.UniqueConstraint("tender_monitor_id", "monitor_version", name="uq_business_scope_tender_version"),
        sa.UniqueConstraint("trademark_monitor_id", "monitor_version", name="uq_business_scope_trademark_version"),
        sa.UniqueConstraint("auction_monitor_id", "monitor_version", name="uq_business_scope_auction_version"))
    for column in ("organization_id", "tender_monitor_id", "trademark_monitor_id", "auction_monitor_id"):
        op.create_index(f"ix_business_monitor_scope_events_{column}", "business_monitor_scope_events", [column])


def downgrade():
    op.drop_table("business_monitor_scope_events")
    for kind in ("auction", "trademark", "tender"):
        with op.batch_alter_table(f"{kind}_monitors") as batch:
            batch.drop_constraint(f"ck_{kind}_monitor_visibility", type_="check")
            batch.drop_constraint(f"fk_{kind}_responsible_user", type_="foreignkey")
            batch.drop_column("responsible_user_id")
            batch.drop_column("visibility")
