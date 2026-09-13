"""Immutable source interchange rules for exact dated journey pairs.

Revision ID: d0ac2e7b5ed2
Revises: c9fb1d6a4dc1
"""
import sqlalchemy as sa

from alembic import op

revision = "d0ac2e7b5ed2"
down_revision = "c9fb1d6a4dc1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("commute_interchanges",
        sa.Column("from_reference_id", sa.String(36), primary_key=True),
        sa.Column("to_reference_id", sa.String(36), primary_key=True),
        sa.Column("service_day", sa.Date(), primary_key=True),
        sa.Column("static_version", sa.String(256), primary_key=True),
        sa.Column("proof", sa.JSON(), nullable=False),
        sa.Column("proof_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["from_reference_id", "service_day", "static_version"],
            ["commute_dated_legs.reference_id", "commute_dated_legs.service_day", "commute_dated_legs.static_version"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_reference_id", "service_day", "static_version"],
            ["commute_dated_legs.reference_id", "commute_dated_legs.service_day", "commute_dated_legs.static_version"], ondelete="CASCADE"))


def downgrade():
    op.drop_table("commute_interchanges")
