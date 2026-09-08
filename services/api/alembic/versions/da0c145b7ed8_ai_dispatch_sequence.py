"""Retain AI tenant dispatch order across dispatcher restarts."""
import sqlalchemy as sa

from alembic import op

revision = "da0c145b7ed8"
down_revision = "d9fb034a6dc7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("dispatch_sequence", sa.BigInteger(), nullable=True))
    op.create_index("ix_jobs_dispatch_sequence", "jobs", ["dispatch_sequence"])


def downgrade():
    op.drop_index("ix_jobs_dispatch_sequence", table_name="jobs")
    op.drop_column("jobs", "dispatch_sequence")
