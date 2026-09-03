"""Add privacy-bounded relation review workflow metrics.

Revision ID: d4a8c1f6b205
Revises: c3b9d2e7f104
"""

import sqlalchemy as sa

from alembic import op

revision = "d4a8c1f6b205"
down_revision = "c3b9d2e7f104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_relation_reviews",
        sa.Column(
            "workflow_variant",
            sa.String(length=40),
            nullable=False,
            server_default="inbox_list_v1",
        ),
    )
    op.add_column(
        "organization_relation_reviews",
        sa.Column("review_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "organization_relation_reviews",
        sa.Column("evidence_opened", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("organization_relation_reviews", "evidence_opened")
    op.drop_column("organization_relation_reviews", "review_duration_ms")
    op.drop_column("organization_relation_reviews", "workflow_variant")
