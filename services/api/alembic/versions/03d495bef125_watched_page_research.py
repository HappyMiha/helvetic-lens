"""Explicit page scope and typed trigger identity, preserving topic receipts."""
import sqlalchemy as sa

from alembic import op

revision = "03d495bef125"
down_revision = "02d495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_monitoring_research_policies", sa.Column("include_page_changes", sa.Boolean(),
        nullable=False, server_default=sa.false()))
    table = "product_monitoring_research_triggers"
    op.add_column(table, sa.Column("source_kind", sa.String(20), nullable=False, server_default="topic_match"))
    op.add_column(table, sa.Column("source_identifier", sa.String(80)))
    op.add_column(table, sa.Column("source_revision", sa.String(64)))
    op.execute(sa.text("UPDATE product_monitoring_research_triggers SET source_identifier=match_id, source_revision=evaluation_fingerprint"))
    with op.batch_alter_table(table) as batch:
        batch.alter_column("source_identifier", existing_type=sa.String(80), nullable=False)
        batch.alter_column("source_revision", existing_type=sa.String(64), nullable=False)
        batch.alter_column("match_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column("evaluation_fingerprint", existing_type=sa.String(64), nullable=True)
        batch.create_unique_constraint("uq_monitor_research_source", ["dossier_id", "source_kind", "source_identifier", "source_revision"])
        batch.create_check_constraint("ck_monitor_research_source_kind", "source_kind IN ('topic_match','watched_page')")


def downgrade():
    db = op.get_bind()
    if (db.scalar(sa.text("SELECT COUNT(*) FROM product_monitoring_research_triggers WHERE source_kind != 'topic_match'"))
            or db.scalar(sa.text("SELECT COUNT(*) FROM product_monitoring_research_policies WHERE include_page_changes"))):
        raise RuntimeError("Retained monitoring research page scope must be explicitly handled before downgrading.")
    with op.batch_alter_table("product_monitoring_research_triggers") as batch:
        batch.drop_constraint("uq_monitor_research_source", type_="unique")
        batch.drop_constraint("ck_monitor_research_source_kind", type_="check")
        batch.alter_column("match_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("evaluation_fingerprint", existing_type=sa.String(64), nullable=False)
        batch.drop_column("source_revision")
        batch.drop_column("source_identifier")
        batch.drop_column("source_kind")
    with op.batch_alter_table("product_monitoring_research_policies") as batch:
        batch.drop_column("include_page_changes")
