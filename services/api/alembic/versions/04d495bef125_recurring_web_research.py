"""Explicit recurring public queries and durable occurrence receipts."""
import sqlalchemy as sa

from alembic import op

revision = "04d495bef125"
down_revision = "03d495bef125"
branch_labels = None
depends_on = None


def contained():
    return [sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"],
            ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE")]


def upgrade():
    op.create_table("product_web_research_policies", *contained(),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("question", sa.String(300), nullable=False),
        sa.Column("cadence_hours", sa.Integer(), nullable=False),
        sa.Column("authorized_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("audience_fingerprint", sa.String(64), nullable=False),
        sa.Column("budget_day", sa.String(10), nullable=False),
        sa.Column("budget_used", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("last_request_key", sa.String(36), nullable=False),
        sa.Column("last_request_fingerprint", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dossier_id"), sa.UniqueConstraint("id", "dossier_id", "organization_id"),
        sa.CheckConstraint("cadence_hours IN (24,168)", name="ck_web_research_cadence"))
    op.create_table("product_web_research_triggers", *contained(),
        sa.Column("policy_id", sa.String(36), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("question", sa.String(300), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id", "dossier_id", "organization_id"],
            ["product_web_research_policies.id", "product_web_research_policies.dossier_id",
             "product_web_research_policies.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["investigation_id", "dossier_id", "organization_id"],
            ["product_investigations.id", "product_investigations.dossier_id", "product_investigations.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("investigation_id"),
        sa.UniqueConstraint("policy_id", "policy_revision", "scheduled_for", name="uq_web_research_occurrence"))
    for table in ("product_web_research_policies", "product_web_research_triggers"):
        for column in ("organization_id", "dossier_id"):
            op.create_index("ix_" + table + "_" + column, table, [column])
    op.create_index("ix_web_research_due", "product_web_research_policies", ["enabled", "next_check_at", "id"])


def downgrade():
    for table in ("product_web_research_policies", "product_web_research_triggers"):
        if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM " + table)):
            raise RuntimeError("Retained public-search authorizations must be handled before downgrading.")
    op.drop_table("product_web_research_triggers")
    op.drop_table("product_web_research_policies")
