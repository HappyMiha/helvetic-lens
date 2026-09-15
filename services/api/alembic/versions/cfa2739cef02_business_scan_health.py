"""Retain unavailable source evidence across private scan pages."""

import sqlalchemy as sa

from alembic import op

revision = "cfa2739cef02"
down_revision = "be91628bdef1"
branch_labels = None
depends_on = None

TABLES = ("trademark_projection_cursors", "auction_private_source_cursors")


def upgrade():
    for table in TABLES:
        # Leave existing scans unknown; the normal worker restarts their scan.
        op.add_column(table, sa.Column("scan_unavailable_count", sa.Integer(), nullable=True))


def downgrade():
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("scan_unavailable_count")
