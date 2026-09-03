"""Persist complete local inference provenance with AI results."""

import sqlalchemy as sa

from alembic import op

revision = "a21f8c4d9b10"
down_revision = "f19d71d8c2a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analyses", sa.Column("provenance", sa.JSON(), nullable=True))
    op.add_column("ask_records", sa.Column("provenance", sa.JSON(), nullable=True))
    op.execute("UPDATE analyses SET provenance = '{}' WHERE provenance IS NULL")
    op.execute("UPDATE ask_records SET provenance = '{}' WHERE provenance IS NULL")
    with op.batch_alter_table("analyses") as batch:
        batch.alter_column("provenance", nullable=False)
    with op.batch_alter_table("ask_records") as batch:
        batch.alter_column("provenance", nullable=False)


def downgrade():
    op.drop_column("ask_records", "provenance")
    op.drop_column("analyses", "provenance")
