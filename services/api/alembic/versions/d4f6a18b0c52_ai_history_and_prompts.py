"""Persist AI question history, prompt settings, and cache usage."""

import sqlalchemy as sa

from alembic import op

revision = "d4f6a18b0c52"
down_revision = "c9a7d24e1f36"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prompt_configuration",
        sa.Column("id", sa.String(30), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "analyses", sa.Column("prompt_revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "analyses", sa.Column("use_count", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "analyses", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "ask_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("comparison_id", sa.String(36), sa.ForeignKey("comparisons.id"), nullable=False),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("coverage", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_revision", sa.Integer(), nullable=False),
        sa.Column("context_mode", sa.String(30), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ask_records_comparison_id", "ask_records", ["comparison_id"])
    op.create_index("ix_ask_records_cache_key", "ask_records", ["cache_key"])
    op.create_index("ix_ask_records_status", "ask_records", ["status"])
    op.create_index("ix_ask_records_created_at", "ask_records", ["created_at"])


def downgrade():
    op.drop_index("ix_ask_records_created_at", table_name="ask_records")
    op.drop_index("ix_ask_records_status", table_name="ask_records")
    op.drop_index("ix_ask_records_cache_key", table_name="ask_records")
    op.drop_index("ix_ask_records_comparison_id", table_name="ask_records")
    op.drop_table("ask_records")
    op.drop_column("analyses", "last_used_at")
    op.drop_column("analyses", "use_count")
    op.drop_column("analyses", "prompt_revision")
    op.drop_table("prompt_configuration")
