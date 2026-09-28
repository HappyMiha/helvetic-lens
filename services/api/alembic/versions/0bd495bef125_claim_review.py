"""Add human claim decisions without migrating machine evidence statuses."""
import sqlalchemy as sa

from alembic import op

revision = "0bd495bef125"
down_revision = "0ad495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_claim_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        *[sa.Column(name, sa.String(36), nullable=False) for name in
          ("organization_id", "dossier_id", "investigation_id", "claim_id", "request_key")],
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("basis", sa.JSON(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id", "dossier_id", "organization_id"],
            ["product_investigations.id", "product_investigations.dossier_id", "product_investigations.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_dossier_claims.id", "product_dossier_claims.investigation_id",
             "product_dossier_claims.dossier_id", "product_dossier_claims.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("claim_id", "revision", name="uq_claim_review_revision"),
        sa.UniqueConstraint("dossier_id", "request_key", name="uq_claim_review_request"),
        sa.CheckConstraint("decision IN ('accepted','dismissed','needs_more_evidence')", name="ck_claim_review_decision"),
        sa.CheckConstraint("revision BETWEEN 1 AND 100", name="ck_claim_review_revision"))
    for name in ("organization_id", "dossier_id", "investigation_id", "claim_id"):
        op.create_index("ix_product_claim_reviews_" + name, "product_claim_reviews", [name])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_claim_reviews")):
        raise RuntimeError("Retain claim reviews: roll back code without dropping their history.")
    op.drop_table("product_claim_reviews")
