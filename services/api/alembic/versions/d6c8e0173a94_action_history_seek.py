"""Index exact scoped action histories and seek directly to a saved boundary."""

from alembic import op

revision = "d6c8e0173a94"
down_revision = "d5b7cf062983"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_action_decision_scope_cursor",
        "action_decisions",
        ["organization_id", "analysis_id", "comparison_id", "action_key", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_decision_scope_cursor", table_name="action_decisions")
