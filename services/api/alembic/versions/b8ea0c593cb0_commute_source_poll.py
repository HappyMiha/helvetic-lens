"""Serialize permitted transport acquisition across workers and organizations."""

import sqlalchemy as sa

from alembic import op

revision = "b8ea0c593cb0"
down_revision = "a7d9eb482baf"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("commute_source_polls",
        sa.Column("source", sa.String(40), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("commute_source_permissions.id"), nullable=False),
        sa.Column("next_request_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("last_code", sa.String(50), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_table("commute_source_polls")
