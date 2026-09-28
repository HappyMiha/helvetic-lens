"""Source-contained, exact-input local retrieval cache."""
import sqlalchemy as sa

from alembic import op

revision = "06d495bef125"
down_revision = "05d495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_evidence_vectors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36)),
        sa.Column("record_key", sa.String(80), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dossier_id", "record_key", name="uq_evidence_vector_record"),
        sa.ForeignKeyConstraint(["investigation_id", "dossier_id", "organization_id"],
            ["product_investigations.id", "product_investigations.dossier_id", "product_investigations.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_investigation_sources.id", "product_investigation_sources.investigation_id",
             "product_investigation_sources.dossier_id", "product_investigation_sources.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_dossier_claims.id", "product_dossier_claims.investigation_id",
             "product_dossier_claims.dossier_id", "product_dossier_claims.organization_id"], ondelete="CASCADE"))
    for column in ("organization_id", "dossier_id", "investigation_id"):
        op.create_index("ix_product_evidence_vectors_" + column, "product_evidence_vectors", [column])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_evidence_vectors")):
        raise RuntimeError("Discard the derived evidence cache explicitly before downgrading; originals are separate.")
    op.drop_table("product_evidence_vectors")
