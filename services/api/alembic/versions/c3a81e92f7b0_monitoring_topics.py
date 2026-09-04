"""durable monitoring topics

Revision ID: c3a81e92f7b0
Revises: b27f5a91c304
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3a81e92f7b0"
down_revision: str | None = "b27f5a91c304"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitoring_topics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'archived')", name="ck_monitoring_topic_status"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_monitoring_topic_org_idempotency"
        ),
    )
    op.create_index("ix_monitoring_topics_organization_id", "monitoring_topics", ["organization_id"])
    op.create_index("ix_monitoring_topics_status", "monitoring_topics", ["status"])
    op.create_index("ix_monitoring_topics_created_by_user_id", "monitoring_topics", ["created_by_user_id"])
    op.create_index("ix_monitoring_topics_archived_at", "monitoring_topics", ["archived_at"])
    op.create_table(
        "monitoring_topic_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("topic_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("concepts_json", sa.JSON(), nullable=False),
        sa.Column("synonyms_json", sa.JSON(), nullable=False),
        sa.Column("exclusions_json", sa.JSON(), nullable=False),
        sa.Column("jurisdictions_json", sa.JSON(), nullable=False),
        sa.Column("languages_json", sa.JSON(), nullable=False),
        sa.Column("source_pack_ids_json", sa.JSON(), nullable=False),
        sa.Column("document_kinds_json", sa.JSON(), nullable=False),
        sa.Column("event_kinds_json", sa.JSON(), nullable=False),
        sa.Column("importance_floor", sa.String(length=20), nullable=False),
        sa.Column("author_user_id", sa.String(length=36), nullable=True),
        sa.Column("ai_provider", sa.String(length=80), nullable=True),
        sa.Column("ai_model", sa.String(length=200), nullable=True),
        sa.Column("prompt_revision", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "importance_floor IN ('high', 'medium', 'low', 'none')",
            name="ck_monitoring_topic_importance",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name="ck_monitoring_topic_revision_status",
        ),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["monitoring_topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", "revision", name="uq_monitoring_topic_revision"),
    )
    op.create_index(
        "ix_monitoring_topic_revisions_organization_id",
        "monitoring_topic_revisions",
        ["organization_id"],
    )
    op.create_index("ix_monitoring_topic_revisions_topic_id", "monitoring_topic_revisions", ["topic_id"])
    op.create_index(
        "ix_monitoring_topic_revisions_author_user_id",
        "monitoring_topic_revisions",
        ["author_user_id"],
    )
    op.create_table(
        "monitoring_topic_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("goal_input", sa.Text(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_revision", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_monitoring_topic_drafts_organization_id",
        "monitoring_topic_drafts",
        ["organization_id"],
    )
    op.create_index(
        "ix_monitoring_topic_drafts_created_by_user_id",
        "monitoring_topic_drafts",
        ["created_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_monitoring_topic_drafts_created_by_user_id", table_name="monitoring_topic_drafts")
    op.drop_index("ix_monitoring_topic_drafts_organization_id", table_name="monitoring_topic_drafts")
    op.drop_table("monitoring_topic_drafts")
    op.drop_index("ix_monitoring_topic_revisions_author_user_id", table_name="monitoring_topic_revisions")
    op.drop_index("ix_monitoring_topic_revisions_topic_id", table_name="monitoring_topic_revisions")
    op.drop_index("ix_monitoring_topic_revisions_organization_id", table_name="monitoring_topic_revisions")
    op.drop_table("monitoring_topic_revisions")
    op.drop_index("ix_monitoring_topics_archived_at", table_name="monitoring_topics")
    op.drop_index("ix_monitoring_topics_created_by_user_id", table_name="monitoring_topics")
    op.drop_index("ix_monitoring_topics_status", table_name="monitoring_topics")
    op.drop_index("ix_monitoring_topics_organization_id", table_name="monitoring_topics")
    op.drop_table("monitoring_topics")
