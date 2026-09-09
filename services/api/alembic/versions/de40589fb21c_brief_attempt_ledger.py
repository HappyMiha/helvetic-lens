"""Keep fenced attempt outcomes and bounded diagnostic measurements."""
import sqlalchemy as sa

from alembic import op

revision = "de40589fb21c"
down_revision = "dd3f478ea10b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("interest_assessment_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("interest_event_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("measurement", sa.JSON(none_as_null=True)),
        sa.UniqueConstraint("organization_id", "assessment_id", "number", name="uq_brief_attempt_number"),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed', 'superseded')", name="ck_brief_attempt_status"))
    op.create_index("ix_brief_attempt_history", "interest_assessment_attempts", ["organization_id", "assessment_id", "number"])


def downgrade():
    op.drop_table("interest_assessment_attempts")
