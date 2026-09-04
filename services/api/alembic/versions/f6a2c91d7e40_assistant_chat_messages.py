"""Add personal Marvin chat messages.

Revision ID: f6a2c91d7e40
Revises: e84b1a27d590
"""

import sqlalchemy as sa

from alembic import op

revision = "f6a2c91d7e40"
down_revision = "e84b1a27d590"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_conversations",
        sa.Column("messages_json", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("assistant_conversations", "messages_json")
