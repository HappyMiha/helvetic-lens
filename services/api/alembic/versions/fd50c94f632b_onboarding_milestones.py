"""Retain first personal actions independently of current shared objects."""

import sqlalchemy as sa

from alembic import op

revision = "fd50c94f632b"
down_revision = "fc49b83e521a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "onboarding_milestones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("principal_key", sa.String(80), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("object_kind", sa.String(30), nullable=False),
        sa.Column("object_id", sa.String(36)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "principal_key", "kind", name="uq_onboarding_milestone_principal_kind"
        ),
        sa.CheckConstraint(
            "kind IN ('interest_saved', 'notifications_saved', 'evidence_displayed')",
            name="ck_onboarding_milestone_kind",
        ),
    )
    op.create_index("ix_onboarding_milestones_organization_id", "onboarding_milestones", ["organization_id"])


def downgrade():
    op.drop_table("onboarding_milestones")
