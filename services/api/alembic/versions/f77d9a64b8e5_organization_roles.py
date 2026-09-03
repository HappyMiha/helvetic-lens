"""Add invitations and deployment-wide platform administrator flag."""

import sqlalchemy as sa

from alembic import op

revision = "f77d9a64b8e5"
down_revision = "e66c8f53a7d4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("platform_admin", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_organization_invitations_organization_id",
        "organization_invitations",
        ["organization_id"],
    )
    op.create_index("ix_organization_invitations_email", "organization_invitations", ["email"])
    op.create_index(
        "ix_organization_invitations_token_hash",
        "organization_invitations",
        ["token_hash"],
    )
    op.create_index(
        "ix_organization_invitations_expires_at",
        "organization_invitations",
        ["expires_at"],
    )


def downgrade():
    op.drop_index("ix_organization_invitations_expires_at", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_token_hash", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_email", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_organization_id", table_name="organization_invitations")
    op.drop_table("organization_invitations")
    op.drop_column("users", "platform_admin")
