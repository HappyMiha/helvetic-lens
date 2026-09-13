"""Durable shared archive lease and immutable version binding.

Revision ID: e1bd3f8c6fe3
Revises: d0ac2e7b5ed2
"""
import sqlalchemy as sa

from alembic import op

revision = "e1bd3f8c6fe3"
down_revision = "d0ac2e7b5ed2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("commute_static_polls",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("last_code", sa.String(80), nullable=False),
        sa.Column("renewal_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.create_table("commute_static_archives",
        sa.Column("version", sa.String(256), primary_key=True),
        sa.Column("dataset_id", sa.String(36), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("resource_url", sa.String(1000), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False))


def downgrade():
    op.drop_table("commute_static_archives")
    op.drop_table("commute_static_polls")
