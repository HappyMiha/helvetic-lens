"""Shared three-dossier allowance with owner-reviewed increase requests."""
import sqlalchemy as sa

from alembic import op

revision = "0dd495bef125"
down_revision = "0cd495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_dossier_allowances",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("product_dossier_allowance_slots",
        sa.Column("dossier_id", sa.String(36), sa.ForeignKey("product_dossiers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    op.create_index("ix_product_dossier_allowance_slots_user_id", "product_dossier_allowance_slots", ["user_id"])
    op.execute(sa.text("INSERT INTO product_dossier_allowance_slots (dossier_id, user_id) "
        "SELECT d.id, p.created_by_user_id FROM product_dossiers d JOIN legal_monitoring_profiles p ON p.id = d.profile_id "
        "WHERE p.created_by_user_id IS NOT NULL"))
    op.create_table("product_dossier_limit_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("previous_limit", sa.Integer(), nullable=False),
        sa.Column("approved_limit", sa.Integer()),
        sa.Column("decided_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mail_state", sa.String(16), nullable=False),
        sa.Column("mailed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "request_key", name="uq_dossier_limit_request"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_dossier_limit_request_status"))
    op.create_index("ix_product_dossier_limit_requests_user_id", "product_dossier_limit_requests", ["user_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_dossier_limit_requests")):
        raise RuntimeError("Retained limit decisions must be handled before downgrade.")
    op.drop_table("product_dossier_limit_requests")
    op.drop_table("product_dossier_allowance_slots")
    op.drop_table("product_dossier_allowances")
