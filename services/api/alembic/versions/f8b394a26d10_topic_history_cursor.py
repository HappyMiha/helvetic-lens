"""Index organization history admission cursors.

Revision ID: f8b394a26d10
Revises: f6a2c91d7e40
"""

from alembic import op

revision = "f8b394a26d10"
down_revision = "f6a2c91d7e40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_regulatory_event_state_history",
        "regulatory_event_states",
        ["organization_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_regulatory_event_state_history", table_name="regulatory_event_states")
