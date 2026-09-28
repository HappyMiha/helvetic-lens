"""Add separate versioned dossier context without rewriting legacy work fields."""
import sqlalchemy as sa

from alembic import op

revision = "07d495bef125"
down_revision = "06d495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_dossiers", sa.Column("domain_context_json", sa.JSON(),
                                              nullable=False, server_default="{}"))


def downgrade():
    rows = op.get_bind().execute(sa.text("SELECT domain_context_json FROM product_dossiers")).scalars()
    if any(value not in (None, "{}", {}) for value in rows):
        raise RuntimeError("Retain saved domain context: roll back application code without removing the additive column.")
    with op.batch_alter_table("product_dossiers") as batch:
        batch.drop_column("domain_context_json")
