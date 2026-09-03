"""Store user and invitation recipient locales.

Revision ID: df27a1c49e60
Revises: c84d2e19a6f1
"""

import sqlalchemy as sa

from alembic import op

revision = "df27a1c49e60"
down_revision = "c84d2e19a6f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("locale", sa.String(length=5), nullable=False, server_default="en-CH")
        )
        batch.create_check_constraint(
            "ck_users_locale", "locale IN ('de-CH', 'fr-CH', 'it-CH', 'rm-CH', 'en-CH')"
        )
    with op.batch_alter_table("organization_invitations") as batch:
        batch.add_column(
            sa.Column(
                "recipient_locale", sa.String(length=5), nullable=False, server_default="en-CH"
            )
        )
        batch.create_check_constraint(
            "ck_organization_invitations_recipient_locale",
            "recipient_locale IN ('de-CH', 'fr-CH', 'it-CH', 'rm-CH', 'en-CH')",
        )


def downgrade() -> None:
    with op.batch_alter_table("organization_invitations") as batch:
        batch.drop_constraint("ck_organization_invitations_recipient_locale", type_="check")
        batch.drop_column("recipient_locale")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_locale", type_="check")
        batch.drop_column("locale")
