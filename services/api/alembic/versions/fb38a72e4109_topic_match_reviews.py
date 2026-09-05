"""Preserve organization reviews of exact topic-match evidence.

Revision ID: fb38a72e4109
Revises: fa27c61d3098
"""
import sqlalchemy as sa

from alembic import op

revision = "fb38a72e4109"
down_revision = "fa27c61d3098"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("topic_match_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("match_id", sa.String(36), sa.ForeignKey("topic_event_matches.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_topic_match_review_request"),
        sa.CheckConstraint("decision IN ('confirmed', 'rejected')", name="ck_topic_match_review_decision"))
    op.create_index("ix_topic_match_reviews_organization_id", "topic_match_reviews", ["organization_id"])
    op.create_index("ix_topic_match_reviews_match_id", "topic_match_reviews", ["match_id"])
    op.create_index("ix_topic_match_review_history", "topic_match_reviews", ["organization_id", "match_id", "created_at", "id"])


def downgrade():
    op.drop_table("topic_match_reviews")
