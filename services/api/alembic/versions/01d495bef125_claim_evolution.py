"""Contained source-linked comparisons across existing dossier investigations."""
import sqlalchemy as sa

from alembic import op

revision = "01d495bef125"
down_revision = "ffc495bef124"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("product_claim_evidence") as batch:
        batch.create_unique_constraint("uq_claim_evidence_change_scope", ["id", "claim_id", "investigation_id", "dossier_id", "organization_id"])
    op.create_table("product_claim_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("previous_claim_id", sa.String(36), nullable=False),
        sa.Column("previous_evidence_id", sa.String(36), nullable=False),
        sa.Column("previous_investigation_id", sa.String(36), nullable=False),
        sa.Column("previous_revision", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("explanation", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("last_request_key", sa.String(36), nullable=False, server_default=""),
        sa.Column("last_request_fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id", "dossier_id", "organization_id"],
            ["product_investigations.id", "product_investigations.dossier_id", "product_investigations.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id", "claim_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_claim_evidence.id", "product_claim_evidence.claim_id", "product_claim_evidence.investigation_id",
             "product_claim_evidence.dossier_id", "product_claim_evidence.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_claim_id", "previous_investigation_id", "dossier_id", "organization_id"],
            ["product_dossier_claims.id", "product_dossier_claims.investigation_id", "product_dossier_claims.dossier_id",
             "product_dossier_claims.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("evidence_id", "previous_claim_id", name="uq_claim_change_evidence"),
        sa.ForeignKeyConstraint(["previous_evidence_id", "previous_claim_id", "previous_investigation_id", "dossier_id", "organization_id"],
            ["product_claim_evidence.id", "product_claim_evidence.claim_id", "product_claim_evidence.investigation_id",
             "product_claim_evidence.dossier_id", "product_claim_evidence.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("kind IN ('CORROBORATES','CONTRADICTS','UPDATES')", name="ck_claim_change_kind"),
        sa.CheckConstraint("status IN ('active','dismissed')", name="ck_claim_change_status"),
        sa.CheckConstraint("previous_investigation_id <> investigation_id", name="ck_claim_change_other_run"))
    for name in ("organization_id", "dossier_id", "investigation_id", "claim_id", "previous_claim_id"):
        op.create_index("ix_product_claim_changes_" + name, "product_claim_changes", [name])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_claim_changes")):
        raise RuntimeError("Retained claim changes must be explicitly handled before downgrading.")
    op.drop_table("product_claim_changes")
    with op.batch_alter_table("product_claim_evidence") as batch:
        batch.drop_constraint("uq_claim_evidence_change_scope", type_="unique")
