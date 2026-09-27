"""Bind new private monitoring topics to their existing dossier team."""
import sqlalchemy as sa

from alembic import op

revision = "fdc495bef124"
down_revision = "fcc495bef124"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("product_dossiers") as batch:
        batch.add_column(sa.Column("monitoring_audience", sa.String(16), nullable=False, server_default="workspace"))
        batch.create_check_constraint("ck_dossier_monitoring_audience", "monitoring_audience IN ('workspace', 'team')")
    with op.batch_alter_table("monitoring_topics") as batch:
        batch.add_column(sa.Column("dossier_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_topic_private_dossier", "product_dossiers", ["dossier_id", "organization_id"],
                                 ["id", "organization_id"], ondelete="CASCADE")
        batch.create_index("ix_monitoring_topics_dossier_id", ["dossier_id"])


def downgrade():
    # Refuse to turn retained private monitoring into workspace data.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM monitoring_topics WHERE dossier_id IS NOT NULL")):
        raise RuntimeError("Archive and explicitly migrate private dossier monitoring before removing its access schema.")
    with op.batch_alter_table("monitoring_topics") as batch:
        batch.drop_index("ix_monitoring_topics_dossier_id")
        batch.drop_constraint("fk_topic_private_dossier", type_="foreignkey")
        batch.drop_column("dossier_id")
    with op.batch_alter_table("product_dossiers") as batch:
        batch.drop_constraint("ck_dossier_monitoring_audience", type_="check")
        batch.drop_column("monitoring_audience")
