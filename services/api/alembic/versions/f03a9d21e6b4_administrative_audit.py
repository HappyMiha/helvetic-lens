"""Add immutable administrative action outcomes."""

import sqlalchemy as sa

from alembic import op

revision = "f03a9d21e6b4"
down_revision = "e92f4b63c7d1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_prompt_configuration",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "administrative_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_kind", sa.String(40), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "organization_id",
        "actor_user_id",
        "scope",
        "action",
        "result",
        "created_at",
    ):
        op.create_index(f"ix_administrative_audit_{column}", "administrative_audit", [column])


def downgrade():
    op.drop_table("administrative_audit")
    op.drop_table("platform_prompt_configuration")
