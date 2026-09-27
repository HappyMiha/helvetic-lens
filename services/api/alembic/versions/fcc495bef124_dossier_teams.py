"""Explicit dossier teams; legacy audiences and permissions remain unchanged."""
import sqlalchemy as sa

from alembic import op

revision = "fcc495bef124"
down_revision = "fbc495bef124"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("product_dossiers") as batch:
        batch.add_column(sa.Column("team_managed", sa.Boolean(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("access_revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("product_dossier_members",
        sa.Column("dossier_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"], ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id", "user_id"], ["organization_memberships.organization_id", "organization_memberships.user_id"], ondelete="CASCADE"),
        sa.CheckConstraint("role IN ('OWNER', 'EDITOR', 'CONTRIBUTOR', 'VIEWER')", name="ck_dossier_member_role"))
    op.create_index("ix_product_dossier_members_organization_id", "product_dossier_members", ["organization_id"])
    op.create_table("product_dossier_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("recipient_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"], ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id", "recipient_user_id"], ["organization_memberships.organization_id", "organization_memberships.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dossier_id", "request_key", name="uq_dossier_invitation_request"),
        sa.CheckConstraint("role IN ('EDITOR', 'CONTRIBUTOR', 'VIEWER')", name="ck_dossier_invitation_role"))
    for column in ("dossier_id", "organization_id", "recipient_user_id"):
        op.create_index("ix_product_dossier_invitations_" + column, "product_dossier_invitations", [column])


def downgrade():
    op.drop_table("product_dossier_invitations")
    op.drop_table("product_dossier_members")
    with op.batch_alter_table("product_dossiers") as batch:
        batch.drop_column("access_revision")
        batch.drop_column("team_managed")
