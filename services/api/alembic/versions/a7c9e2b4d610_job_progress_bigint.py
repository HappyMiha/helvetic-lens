"""Store durable-job progress counters as 64-bit integers.

Revision ID: a7c9e2b4d610
Revises: d4a8c1f6b205
"""

import sqlalchemy as sa

from alembic import op

revision = "a7c9e2b4d610"
down_revision = "d4a8c1f6b205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("jobs", "job_steps"):
        with op.batch_alter_table(table) as batch_op:
            for column in ("progress_current", "progress_total"):
                batch_op.alter_column(
                    column,
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                )


def downgrade() -> None:
    for table in ("jobs", "job_steps"):
        with op.batch_alter_table(table) as batch_op:
            for column in ("progress_current", "progress_total"):
                batch_op.alter_column(
                    column,
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                )
