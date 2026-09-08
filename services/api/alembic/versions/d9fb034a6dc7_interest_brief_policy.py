"""Persist organization automatic-brief policy without enabling existing tenants."""
import sqlalchemy as sa

from alembic import op

revision = "d9fb034a6dc7"
down_revision = "d8eaf2395cb6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("interest_brief_policies",
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("interest_brief_policies")
