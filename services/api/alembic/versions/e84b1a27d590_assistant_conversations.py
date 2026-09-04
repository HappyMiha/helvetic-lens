"""Add private persisted assistant conversations.

Revision ID: e84b1a27d590
Revises: d4b92f03a8c1
"""

import sqlalchemy as sa

from alembic import op

revision = "e84b1a27d590"
down_revision = "d4b92f03a8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("principal_key", sa.String(length=80), nullable=False),
        sa.Column("context_key", sa.String(length=100), nullable=False),
        sa.Column("route", sa.String(length=40), nullable=False),
        sa.Column("entity_kind", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("draft", sa.Text(), nullable=False),
        sa.Column("handoffs_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "principal_key",
            "context_key",
            name="uq_assistant_conversation_principal_context",
        ),
    )
    op.create_index(
        "ix_assistant_conversations_organization_id",
        "assistant_conversations",
        ["organization_id"],
    )
    op.create_index(
        "ix_assistant_conversations_user_id", "assistant_conversations", ["user_id"]
    )
    op.create_index(
        "ix_assistant_conversations_principal_key",
        "assistant_conversations",
        ["principal_key"],
    )
    op.create_index(
        "ix_assistant_conversations_context_key",
        "assistant_conversations",
        ["context_key"],
    )
    op.create_index(
        "ix_assistant_conversations_entity_id", "assistant_conversations", ["entity_id"]
    )
    op.create_index(
        "ix_assistant_conversations_updated_at", "assistant_conversations", ["updated_at"]
    )


def downgrade() -> None:
    op.drop_table("assistant_conversations")
