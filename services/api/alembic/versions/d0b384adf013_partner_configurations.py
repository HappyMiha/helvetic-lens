"""Optional encrypted organization partner credentials; no provider enabled by migration."""
import sqlalchemy as sa

from alembic import op

revision = "d0b384adf013"
down_revision = "cfa2739cef02"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("partner_configurations",
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("provider", sa.String(30), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("api_key", sa.Text()),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("partner_configurations")
