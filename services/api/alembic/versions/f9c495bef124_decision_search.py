"""Private, attributable Jev/Laya search runs and relevance labels."""
import sqlalchemy as sa

from alembic import op

revision = "f9c495bef124"
down_revision = "f8c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("product_decision_search_budgets",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("used", sa.Integer(), nullable=False))
    op.create_table("product_decision_search_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product", sa.String(12), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("query", sa.String(300), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("labels_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "owner_user_id", "product", "request_key", name="uq_decision_search_request"),
        sa.CheckConstraint("product IN ('pharma', 'loyer')", name="ck_decision_search_product"))
    for field in ("organization_id", "owner_user_id", "created_at"):
        op.create_index(f"ix_product_decision_search_runs_{field}", "product_decision_search_runs", [field])


def downgrade():
    op.drop_table("product_decision_search_runs")
    op.drop_table("product_decision_search_budgets")
