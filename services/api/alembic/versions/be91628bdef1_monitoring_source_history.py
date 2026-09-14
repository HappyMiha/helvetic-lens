"""Bounded source-operation samples; no native evidence changes.

Revision ID: be91628bdef1
Revises: ad80517acef0
"""
import sqlalchemy as sa

from alembic import op

revision = "be91628bdef1"
down_revision = "ad80517acef0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("monitoring_operational_samples",
        sa.Column("channel", sa.String(40), primary_key=True),
        sa.Column("bucket_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False))
    op.create_index("ix_monitoring_operational_samples_bucket_at", "monitoring_operational_samples", ["bucket_at"])


def downgrade():
    op.drop_table("monitoring_operational_samples")
