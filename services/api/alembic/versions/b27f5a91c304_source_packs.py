"""Add global source-pack definitions and organization subscriptions.

Revision ID: b27f5a91c304
Revises: a7c9e2b4d610
"""

import sqlalchemy as sa

from alembic import op

revision = "b27f5a91c304"
down_revision = "a7c9e2b4d610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_pack_definitions",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("parent_id", sa.String(length=120), nullable=True),
        sa.Column("revision", sa.String(length=40), nullable=False),
        sa.Column("name_json", sa.JSON(), nullable=False),
        sa.Column("description_json", sa.JSON(), nullable=False),
        sa.Column("expected_first_data_json", sa.JSON(), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["source_pack_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_pack_definitions_parent_id", "source_pack_definitions", ["parent_id"]
    )
    op.create_table(
        "source_pack_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("pack_id", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("progress_current", sa.BigInteger(), nullable=False),
        sa.Column("progress_total", sa.BigInteger(), nullable=False),
        sa.Column("included_event_count", sa.BigInteger(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("activated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('inactive', 'queued', 'backfilling', 'active', 'partial', 'failed')",
            name="ck_source_pack_subscription_state",
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["pack_id"], ["source_pack_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "pack_id", name="uq_source_pack_subscription_org_pack"
        ),
    )
    for column in ("organization_id", "pack_id", "state", "activated_by_user_id"):
        op.create_index(
            f"ix_source_pack_subscriptions_{column}",
            "source_pack_subscriptions",
            [column],
        )
    op.create_table(
        "source_pack_change_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("pack_id", sa.String(length=120), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("requested_action", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "requested_action IN ('activate', 'deactivate')",
            name="ck_source_pack_request_action",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'fulfilled', 'cancelled')",
            name="ck_source_pack_request_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["pack_id"], ["source_pack_definitions.id"]),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "pack_id", "requested_by_user_id", "status"):
        op.create_index(
            f"ix_source_pack_change_requests_{column}",
            "source_pack_change_requests",
            [column],
        )


def downgrade() -> None:
    op.drop_table("source_pack_change_requests")
    op.drop_table("source_pack_subscriptions")
    op.drop_table("source_pack_definitions")
