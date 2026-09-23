"""Persist the five-step legal monitoring setup and its activated topic links."""

import sqlalchemy as sa

from alembic import op

revision = "f2c495bef124"
down_revision = "f1c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("legal_monitoring_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("creation_key", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("proposals_json", sa.JSON(), nullable=False),
        sa.Column("topic_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "creation_key", name="uq_legal_profile_creation"),
        sa.CheckConstraint("status IN ('draft', 'active', 'paused')", name="ck_legal_profile_status"))
    op.create_index("ix_legal_monitoring_profiles_organization_id", "legal_monitoring_profiles", ["organization_id"])
    op.create_index("ix_legal_monitoring_profiles_created_by_user_id", "legal_monitoring_profiles", ["created_by_user_id"])


def downgrade():
    op.drop_table("legal_monitoring_profiles")
