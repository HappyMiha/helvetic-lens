"""Personal public follows and contained, reviewed private copies."""
import sqlalchemy as sa

from alembic import op

revision = "f8c495bef124"
down_revision = "f7c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_public_follows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("product_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("following", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("seen_marker", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_user_id", "publication_id", name="uq_public_follow_owner"))
    for field in ("owner_user_id", "publication_id"):
        op.create_index(f"ix_product_public_follows_{field}", "product_public_follows", [field])
    op.create_table("product_public_copies",
        sa.Column("dossier_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"],
            ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"))
    op.create_index("ix_product_public_copies_organization_id", "product_public_copies", ["organization_id"])

    op.create_table("product_public_reuse_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dossier_id", sa.String(36), sa.ForeignKey("product_dossiers.id", ondelete="SET NULL")),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_public_reuse_request"))
    for field in ("organization_id", "actor_user_id"):
        op.create_index(f"ix_product_public_reuse_receipts_{field}", "product_public_reuse_receipts", [field])


def downgrade():
    op.drop_table("product_public_reuse_receipts")
    op.drop_table("product_public_copies")
    op.drop_table("product_public_follows")
