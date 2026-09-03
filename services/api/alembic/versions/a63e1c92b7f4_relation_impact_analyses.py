"""Persist organization-scoped candidate impact analyses.

Revision ID: a63e1c92b7f4
Revises: f42c9d71a805
"""

import sqlalchemy as sa

from alembic import op

revision = "a63e1c92b7f4"
down_revision = "f42c9d71a805"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relation_impact_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("organization_candidate_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("target_work_id", sa.String(length=36), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("coverage", sa.JSON(), nullable=False),
        sa.Column("analysis_plan", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_revision", sa.Integer(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_relation_impact_analysis_status",
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["relation_candidates.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["regulatory_events.id"]),
        sa.ForeignKeyConstraint(
            ["organization_candidate_id"],
            ["organization_relation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["target_work_id"], ["regulatory_works.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "organization_candidate_id",
        "candidate_id",
        "event_id",
        "target_work_id",
        "cache_key",
        "status",
        "created_at",
    ):
        op.create_index(
            f"ix_relation_impact_analyses_{column}",
            "relation_impact_analyses",
            [column],
        )


def downgrade() -> None:
    op.drop_table("relation_impact_analyses")
