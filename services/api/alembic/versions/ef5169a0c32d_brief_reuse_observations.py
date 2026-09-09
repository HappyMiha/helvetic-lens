"""Daily aggregate observations of saved current brief projections."""
import sqlalchemy as sa

from alembic import op

revision = "ef5169a0c32d"
down_revision = "de40589fb21c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("brief_reuse_observations",
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("interest_event_assessments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("surface", sa.String(24), primary_key=True),
        sa.Column("projections", sa.BigInteger(), nullable=False),
        sa.Column("first_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("projections > 0", name="ck_brief_reuse_positive"),
        sa.CheckConstraint("surface IN ('reader', 'notifications', 'digest_preview')", name="ck_brief_reuse_surface"))


def downgrade():
    op.drop_table("brief_reuse_observations")
