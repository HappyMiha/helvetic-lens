"""Retain immutable non-passage context for offline brief history validation."""
import sqlalchemy as sa

from alembic import op

revision = "dd3f478ea10b"
down_revision = "dc2e367d90fa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interest_event_assessments", sa.Column("history_context", sa.JSON(), nullable=True))


def downgrade():
    # Native DROP preserves parent rows and their review/evidence foreign keys.
    op.drop_column("interest_event_assessments", "history_context")
