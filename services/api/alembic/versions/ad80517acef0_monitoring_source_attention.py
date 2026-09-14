"""Personal source-attention receipts; no source or collector mutations.

Revision ID: ad80517acef0
Revises: 9c7f5069bdef
"""
import sqlalchemy as sa

from alembic import op

revision = "ad80517acef0"
down_revision = "9c7f5069bdef"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("monitoring_source_acknowledgements",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("issue_key", sa.String(100), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("monitoring_source_acknowledgements")
