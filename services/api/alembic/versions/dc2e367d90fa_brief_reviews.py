"""Preserve organization decisions on exact saved AI briefs."""
import sqlalchemy as sa

from alembic import op

revision = "dc2e367d90fa"
down_revision = "db1d256c8fe9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("interest_brief_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("interest_event_assessments.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("target_fingerprint", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_brief_review_request"),
        sa.CheckConstraint("decision IN ('confirmed', 'rejected', 'withdrawn')", name="ck_brief_review_decision"))
    op.create_index("ix_brief_review_history", "interest_brief_reviews",
                    ["organization_id", "assessment_id", "created_at", "id"])


def downgrade():
    op.drop_table("interest_brief_reviews")
