"""Add product dossiers and retained organization evidence."""

import sqlalchemy as sa

from alembic import op

revision = "f3c495bef124"
down_revision = "f2c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_dossiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product", sa.String(20), nullable=False),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("legal_monitoring_profiles.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("creation_key", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_product_dossier_org"),
        sa.UniqueConstraint("organization_id", "product", "creation_key", name="uq_product_dossier_creation"))
    op.create_index("ix_product_dossiers_organization_id", "product_dossiers", ["organization_id"])
    op.create_table("product_dossier_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("artifact_key", sa.String(100)),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"], ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dossier_id", "request_key", name="uq_product_entry_request"))
    op.create_index("ix_product_dossier_entries_organization_id", "product_dossier_entries", ["organization_id"])
    op.create_index("ix_product_dossier_entries_dossier_id", "product_dossier_entries", ["dossier_id"])


def downgrade():
    op.drop_table("product_dossier_entries")
    op.drop_table("product_dossiers")
