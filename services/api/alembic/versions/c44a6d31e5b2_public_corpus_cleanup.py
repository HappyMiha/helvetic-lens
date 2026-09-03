"""Remove organization-owned source pointers from shared corpus rows."""

import sqlalchemy as sa

from alembic import op

revision = "c44a6d31e5b2"
down_revision = "b32e2c9f6211"
branch_labels = None
depends_on = None

LEGACY_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


def upgrade():
    op.execute("UPDATE laws SET source_id = NULL WHERE owner_organization_id IS NULL")
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "organization_id",
            existing_type=sa.String(length=36),
            server_default=LEGACY_ORGANIZATION_ID,
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "organization_id",
            existing_type=sa.String(length=36),
            server_default="default",
            nullable=False,
        )
