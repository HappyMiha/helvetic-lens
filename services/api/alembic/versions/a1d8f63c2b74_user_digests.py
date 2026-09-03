"""Add opt-in digest preferences and bounded delivery history.

Revision ID: a1d8f63c2b74
Revises: e72c9a4b108d
"""

import sqlalchemy as sa

from alembic import op

revision = "a1d8f63c2b74"
down_revision = "e72c9a4b108d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digest_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("severities", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("next_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("frequency IN ('daily', 'weekly')", name="ck_digest_frequency"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "user_id", name="uq_digest_preference_org_user"
        ),
    )
    op.create_index(
        "ix_digest_preferences_organization_id",
        "digest_preferences",
        ["organization_id"],
    )
    op.create_index("ix_digest_preferences_user_id", "digest_preferences", ["user_id"])
    op.create_index(
        "ix_digest_preferences_next_delivery_at",
        "digest_preferences",
        ["next_delivery_at"],
    )
    op.create_table(
        "digest_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("preference_id", sa.String(length=36), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'succeeded', 'failed', 'skipped')",
            name="ck_digest_delivery_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["preference_id"], ["digest_preferences.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "preference_id", "period_end", name="uq_digest_delivery_preference_period"
        ),
    )
    op.create_index(
        "ix_digest_deliveries_organization_id", "digest_deliveries", ["organization_id"]
    )
    op.create_index("ix_digest_deliveries_user_id", "digest_deliveries", ["user_id"])
    op.create_index(
        "ix_digest_deliveries_preference_id", "digest_deliveries", ["preference_id"]
    )
    op.create_index("ix_digest_deliveries_status", "digest_deliveries", ["status"])


def downgrade() -> None:
    op.drop_table("digest_deliveries")
    op.drop_table("digest_preferences")
