"""Private hazard consent revisions and exact-version delivery attempts."""

import sqlalchemy as sa

from alembic import op

revision = "3ce8fa47ba3e"
down_revision = "2bd7e936a92d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hazard_monitors", sa.Column("email_revision", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_table("hazard_email_policies",
        sa.Column("monitor_id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("revision >= 1", name="ck_hazard_email_revision"))
    op.create_index("ix_hazard_email_policies_organization_id", "hazard_email_policies", ["organization_id"])
    op.create_table("hazard_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("development_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("material_sequence", sa.Integer(), nullable=False),
        sa.Column("consent_revision", sa.Integer(), nullable=False),
        sa.Column("signal_hash", sa.String(64), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["development_id", "organization_id"], ["hazard_developments.id", "hazard_developments.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["development_id", "revision"], ["hazard_event_revisions.development_id", "hazard_event_revisions.revision"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitor_id", "consent_revision"], ["hazard_email_policies.monitor_id", "hazard_email_policies.revision"], ondelete="CASCADE"),
        sa.UniqueConstraint("development_id", "material_sequence", "consent_revision", name="uq_hazard_delivery_intent"),
        sa.CheckConstraint("state IN ('pending','sending','sent','uncertain','suppressed')", name="ck_hazard_delivery_state"))
    for name in ("organization_id", "monitor_id", "owner_user_id", "development_id", "signal_hash", "state", "due_at"):
        op.create_index(f"ix_hazard_deliveries_{name}", "hazard_deliveries", [name])


def downgrade():
    op.drop_table("hazard_deliveries")
    op.drop_table("hazard_email_policies")
    op.drop_column("hazard_monitors", "email_revision")
