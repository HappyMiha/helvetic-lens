"""Explicit public contributions and private moderation/retry evidence."""
import sqlalchemy as sa

from alembic import op

revision = "f7c495bef124"
down_revision = "f6c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_public_contributions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("publication_id", sa.String(36), nullable=False),
        sa.Column("author_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publication_revision", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("author_label", sa.String(100), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("moderation_reason", sa.String(600), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id", "organization_id"],
            ["product_publications.id", "product_publications.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "publication_id", "organization_id", name="uq_public_contribution_scope"),
        sa.CheckConstraint("status IN ('visible', 'hidden', 'removed')", name="ck_public_contribution_status"))
    for field in ("organization_id", "author_user_id"):
        op.create_index(f"ix_product_public_contributions_{field}", "product_public_contributions", [field])
    op.create_index("ix_public_contribution_page", "product_public_contributions",
        ["publication_id", "status", "created_at", "id"])
    op.create_table("product_public_contribution_mutations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("publication_id", sa.String(36), nullable=False),
        sa.Column("contribution_id", sa.String(36), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(600), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contribution_id", "publication_id", "organization_id"],
            ["product_public_contributions.id", "product_public_contributions.publication_id",
             "product_public_contributions.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("publication_id", "request_key", name="uq_public_contribution_request"),
        sa.UniqueConstraint("contribution_id", "revision", name="uq_public_contribution_revision"))
    op.create_index("ix_product_public_contribution_mutations_organization_id",
        "product_public_contribution_mutations", ["organization_id"])


def downgrade():
    op.drop_table("product_public_contribution_mutations")
    op.drop_table("product_public_contributions")
