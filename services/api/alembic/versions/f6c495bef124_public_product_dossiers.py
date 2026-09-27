"""Explicit public projections, retaining private dossier authorization."""
import sqlalchemy as sa

from alembic import op

revision = "f6c495bef124"
down_revision = "f5c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_publications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("product", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.String(1500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_label", sa.String(100), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("first_published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"], ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "organization_id", name="uq_product_publication_org"),
        sa.UniqueConstraint("dossier_id", name="uq_product_publication_dossier"),
        sa.CheckConstraint("status IN ('published', 'withdrawn')", name="ck_product_publication_status"))
    for field in ("organization_id", "product", "status"):
        op.create_index(f"ix_product_publications_{field}", "product_publications", [field])
    op.create_table("product_publication_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("publication_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id", "organization_id"], ["product_publications.id", "product_publications.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("publication_id", "revision", name="uq_product_publication_revision"),
        sa.UniqueConstraint("publication_id", "request_key", name="uq_product_publication_request"))
    for field in ("organization_id", "publication_id"):
        op.create_index(f"ix_product_publication_revisions_{field}", "product_publication_revisions", [field])


def downgrade():
    op.drop_table("product_publication_revisions")
    op.drop_table("product_publications")
