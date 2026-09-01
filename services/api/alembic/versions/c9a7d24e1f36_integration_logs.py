"""Persist inspectable outbound integration requests and responses."""

import sqlalchemy as sa

from alembic import op

revision = "c9a7d24e1f36"
down_revision = "b87c20a6d941"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("operation", sa.String(60), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("request_headers", sa.JSON(), nullable=False),
        sa.Column("request_body", sa.JSON(), nullable=True),
        sa.Column("response_headers", sa.JSON(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("request_size", sa.Integer(), nullable=False),
        sa.Column("response_size", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_integration_logs_provider", "integration_logs", ["provider"])
    op.create_index("ix_integration_logs_operation", "integration_logs", ["operation"])
    op.create_index("ix_integration_logs_status", "integration_logs", ["status"])
    op.create_index("ix_integration_logs_created_at", "integration_logs", ["created_at"])


def downgrade():
    op.drop_index("ix_integration_logs_created_at", table_name="integration_logs")
    op.drop_index("ix_integration_logs_status", table_name="integration_logs")
    op.drop_index("ix_integration_logs_operation", table_name="integration_logs")
    op.drop_index("ix_integration_logs_provider", table_name="integration_logs")
    op.drop_table("integration_logs")
