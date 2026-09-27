"""Explicit publication-scoped research using the existing investigation engine."""
import re
import unicodedata

import sqlalchemy as sa

from alembic import op

revision = "ffc495bef124"
down_revision = "fec495bef124"
branch_labels = None
depends_on = None

SCOPE = ("(publication_id IS NULL AND publication_revision IS NULL AND public_contribution_id IS NULL AND public_contribution_revision IS NULL) OR "
    "(publication_id IS NOT NULL AND publication_revision IS NOT NULL AND publication_revision > 0 AND "
    "public_contribution_id IS NOT NULL AND public_contribution_revision IS NOT NULL AND public_contribution_revision > 0 AND trigger_entry_id IS NULL)")
FILES = [("kind", sa.String(24), "comment"), ("artifact_key", sa.String(240), ""),
         ("file_name", sa.String(200), ""), ("byte_size", sa.Integer(), "0"),
         ("sha256", sa.String(64), ""), ("content_type", sa.String(100), "")]


def upgrade():
    with op.batch_alter_table("product_publications") as batch:
        batch.add_column(sa.Column("slug", sa.String(180), nullable=True))
        batch.add_column(sa.Column("living_research", sa.Boolean(), nullable=False, server_default="0"))
        batch.create_unique_constraint("uq_product_publications_slug", ["slug"])
        batch.create_unique_constraint("uq_product_publication_research_scope", ["id", "dossier_id", "organization_id"])
    connection = op.get_bind()
    for row in connection.execute(sa.text("SELECT id, title FROM product_publications")).mappings():
        title = re.sub(r"[\W_]+", "-", unicodedata.normalize("NFKC", row["title"]).casefold()).strip("-")[:110] or "dossier"
        connection.execute(sa.text("UPDATE product_publications SET slug = :slug WHERE id = :id"),
                           {"slug": title + "-" + row["id"], "id": row["id"]})
    with op.batch_alter_table("product_public_contributions") as batch:
        for name, kind, default in FILES:
            batch.add_column(sa.Column(name, kind, nullable=False, server_default=default))
    with op.batch_alter_table("product_investigations") as batch:
        for name, kind in [("publication_id", sa.String(36)), ("publication_revision", sa.Integer()),
                           ("public_contribution_id", sa.String(36)), ("public_contribution_revision", sa.Integer())]:
            batch.add_column(sa.Column(name, kind, nullable=True))
        batch.create_foreign_key("fk_investigation_publication", "product_publications",
            ["publication_id", "dossier_id", "organization_id"], ["id", "dossier_id", "organization_id"], ondelete="CASCADE")
        batch.create_foreign_key("fk_investigation_public_contribution", "product_public_contributions",
            ["public_contribution_id", "publication_id", "organization_id"], ["id", "publication_id", "organization_id"], ondelete="CASCADE")
        batch.create_unique_constraint("uq_public_contribution_investigation", ["public_contribution_id", "public_contribution_revision"])
        batch.create_check_constraint("ck_investigation_public_scope", SCOPE)
    op.create_index("ix_product_investigations_publication_id", "product_investigations", ["publication_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_investigations WHERE publication_id IS NOT NULL")):
        raise RuntimeError("Retained public research must be explicitly handled before downgrading its scope.")
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_public_contributions WHERE artifact_key <> ''")):
        raise RuntimeError("Retained public originals must be explicitly handled before downgrading.")
    op.drop_index("ix_product_investigations_publication_id", table_name="product_investigations")
    with op.batch_alter_table("product_investigations") as batch:
        batch.drop_constraint("ck_investigation_public_scope", type_="check")
        batch.drop_constraint("uq_public_contribution_investigation", type_="unique")
        batch.drop_constraint("fk_investigation_public_contribution", type_="foreignkey")
        batch.drop_constraint("fk_investigation_publication", type_="foreignkey")
        for name in ("public_contribution_revision", "public_contribution_id", "publication_revision", "publication_id"):
            batch.drop_column(name)
    with op.batch_alter_table("product_public_contributions") as batch:
        for name, _, _ in reversed(FILES):
            batch.drop_column(name)
    with op.batch_alter_table("product_publications") as batch:
        batch.drop_constraint("uq_product_publication_research_scope", type_="unique")
        batch.drop_constraint("uq_product_publications_slug", type_="unique")
        batch.drop_column("living_research")
        batch.drop_column("slug")
