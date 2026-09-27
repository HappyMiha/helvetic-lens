"""Original contributions bound to durable, private investigations."""
import sqlalchemy as sa

from alembic import op

revision = "fbc495bef124"
down_revision = "fac495bef124"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("product_dossier_entries") as batch:
        batch.create_unique_constraint("uq_product_entry_scope", ["id", "dossier_id", "organization_id"])
    with op.batch_alter_table("product_investigations") as batch:
        batch.add_column(sa.Column("trigger_entry_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("external_discovery", sa.Boolean(), nullable=False, server_default="1"))
        batch.create_unique_constraint("uq_investigation_contribution", ["trigger_entry_id"])
        batch.create_foreign_key("fk_investigation_contribution", "product_dossier_entries",
            ["trigger_entry_id", "dossier_id", "organization_id"], ["id", "dossier_id", "organization_id"], ondelete="CASCADE")


def downgrade():
    with op.batch_alter_table("product_investigations") as batch:
        batch.drop_constraint("fk_investigation_contribution", type_="foreignkey")
        batch.drop_constraint("uq_investigation_contribution", type_="unique")
        batch.drop_column("external_discovery")
        batch.drop_column("trigger_entry_id")
    with op.batch_alter_table("product_dossier_entries") as batch:
        batch.drop_constraint("uq_product_entry_scope", type_="unique")
