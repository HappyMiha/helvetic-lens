"""One leased shared FEDRO polling stream.

Revision ID: a3df51ae81a5
Revises: f2ce409d70f4
"""

import sqlalchemy as sa

from alembic import op

revision = "a3df51ae81a5"
down_revision = "f2ce409d70f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("road_source_polls",
        sa.Column("source", sa.String(40), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("road_source_permissions.id"), nullable=False),
        sa.Column("next_request_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("force_full", sa.Boolean(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("last_code", sa.String(80), nullable=False))


def downgrade():
    op.drop_table("road_source_polls")
