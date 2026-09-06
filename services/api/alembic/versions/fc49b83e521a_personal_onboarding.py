"""Persist personal onboarding independently of shared monitoring data."""

import sqlalchemy as sa

from alembic import op

revision = "fc49b83e521a"
down_revision = "fb38a72e4109"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_onboarding",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("principal_key", sa.String(80), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("intent", sa.String(20)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("deferred_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "principal_key", name="uq_onboarding_org_principal"),
        sa.CheckConstraint(
            "intent IS NULL OR intent IN ('topic', 'law', 'explore')", name="ck_onboarding_intent"
        ),
    )
    op.create_index("ix_user_onboarding_organization_id", "user_onboarding", ["organization_id"])


def downgrade():
    op.drop_table("user_onboarding")
