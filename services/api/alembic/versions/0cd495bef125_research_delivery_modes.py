"""Personal in-app immediate, daily digest or silent dossier updates."""
import sqlalchemy as sa

from alembic import op

revision = "0cd495bef125"
down_revision = "0bd495bef125"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("product_private_follows", "product_public_follows"):
        op.add_column(table, sa.Column("delivery_mode", sa.String(16), nullable=False, server_default="immediate"))
    op.add_column("product_public_follows", sa.Column("activity_seen_marker", sa.String(64)))


def downgrade():
    for table in ("product_private_follows", "product_public_follows"):
        if op.get_bind().scalar(sa.text(f"SELECT COUNT(*) FROM {table} WHERE delivery_mode <> 'immediate'")):
            raise RuntimeError("Retained delivery preferences must be handled before downgrade.")
    for table in ("product_private_follows", "product_public_follows"):
        op.drop_column(table, "delivery_mode")

    op.drop_column("product_public_follows", "activity_seen_marker")
