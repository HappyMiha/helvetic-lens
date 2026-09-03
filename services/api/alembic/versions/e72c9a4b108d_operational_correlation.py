"""Add bounded request correlation to jobs and integration logs.

Revision ID: e72c9a4b108d
Revises: df27a1c49e60
"""

import sqlalchemy as sa

from alembic import op

revision = "e72c9a4b108d"
down_revision = "df27a1c49e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("integration_logs", "jobs"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("request_id", sa.String(length=36), nullable=True))
            batch.add_column(
                sa.Column("correlation", sa.JSON(), nullable=False, server_default="{}")
            )
            batch.create_index(f"ix_{table}_request_id", ["request_id"], unique=False)


def downgrade() -> None:
    for table in ("jobs", "integration_logs"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_request_id")
            batch.drop_column("correlation")
            batch.drop_column("request_id")
