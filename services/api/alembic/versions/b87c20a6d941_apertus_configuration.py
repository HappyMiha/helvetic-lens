"""Persist workspace Apertus configuration independently of document history."""

import sqlalchemy as sa

from alembic import op

revision = "b87c20a6d941"
down_revision = "7520cab4fdac"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "apertus_configuration",
        sa.Column("id", sa.String(30), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("key_source", sa.String(30), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("apertus_configuration")
