"""persist fixed-budget AI analysis plans

Revision ID: e31b8f6a2c90
Revises: b51a3e9d7c20
"""

import sqlalchemy as sa

from alembic import op

revision = "e31b8f6a2c90"
down_revision = "b51a3e9d7c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    empty = sa.text("'{}'")
    op.add_column(
        "analyses",
        sa.Column("analysis_plan", sa.JSON(), nullable=False, server_default=empty),
    )
    op.add_column(
        "ask_records",
        sa.Column("analysis_plan", sa.JSON(), nullable=False, server_default=empty),
    )


def downgrade() -> None:
    op.drop_column("ask_records", "analysis_plan")
    op.drop_column("analyses", "analysis_plan")
