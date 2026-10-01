"""Explicit per-dossier personal email consent and durable delivery position."""
import sqlalchemy as sa

from alembic import op

revision = "0ed495bef125"
down_revision = "0dd495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_private_follows", sa.Column("email_settings", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    table = sa.table("product_private_follows", sa.column("email_settings", sa.JSON()))
    if any(row[0] for row in op.get_bind().execute(sa.select(table.c.email_settings))):
        raise RuntimeError("Retained dossier email consent and delivery history cannot be discarded.")
    op.drop_column("product_private_follows", "email_settings")
