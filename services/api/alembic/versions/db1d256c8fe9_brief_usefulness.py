"""Append-only personal usefulness feedback on exact saved AI briefs."""
import sqlalchemy as sa

from alembic import op

revision = "db1d256c8fe9"
down_revision = "da0c145b7ed8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("interest_brief_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("interest_event_assessments.id"), nullable=False),
        sa.Column("principal_key", sa.String(80), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "principal_key", "request_key", name="uq_brief_feedback_request"),
        sa.CheckConstraint("decision IN ('useful', 'not_useful', 'withdrawn')", name="ck_brief_feedback_decision"))
    op.create_index("ix_brief_feedback_history", "interest_brief_feedback",
                    ["organization_id", "assessment_id", "principal_key", "created_at", "id"])


def downgrade():
    op.drop_table("interest_brief_feedback")
