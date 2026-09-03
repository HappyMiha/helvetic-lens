"""Persist organization review decisions for suggested actions.

Revision ID: f42c9d71a805
Revises: e31b8f6a2c90
"""

import sqlalchemy as sa

from alembic import op

revision = "f42c9d71a805"
down_revision = "e31b8f6a2c90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("comparison_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("action_key", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("assigned_to", sa.String(length=200), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_label", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('accepted', 'assigned', 'scheduled', 'dismissed', 'not_applicable')",
            name="ck_action_decision_value",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"]),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_decisions_organization_id", "action_decisions", ["organization_id"])
    op.create_index("ix_action_decisions_comparison_id", "action_decisions", ["comparison_id"])
    op.create_index("ix_action_decisions_analysis_id", "action_decisions", ["analysis_id"])
    op.create_index("ix_action_decisions_action_key", "action_decisions", ["action_key"])
    op.create_index("ix_action_decisions_decision", "action_decisions", ["decision"])
    op.create_index("ix_action_decisions_actor_user_id", "action_decisions", ["actor_user_id"])
    op.create_index("ix_action_decisions_created_at", "action_decisions", ["created_at"])


def downgrade() -> None:
    op.drop_table("action_decisions")
