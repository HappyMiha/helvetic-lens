"""bounded topic event matches

Revision ID: d4b92f03a8c1
Revises: c3a81e92f7b0
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4b92f03a8c1"
down_revision: str | None = "c3a81e92f7b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "topic_event_matches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("topic_id", sa.String(length=36), nullable=False),
        sa.Column("topic_revision_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("expression_id", sa.String(length=36), nullable=True),
        sa.Column("document_version_id", sa.String(length=36), nullable=True),
        sa.Column("reason_signals_json", sa.JSON(), nullable=False),
        sa.Column("evidence_references_json", sa.JSON(), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rule_fingerprint", sa.String(length=100), nullable=False),
        sa.Column("model_provider", sa.String(length=80), nullable=True),
        sa.Column("model_name", sa.String(length=200), nullable=True),
        sa.Column("model_prompt_revision", sa.Integer(), nullable=True),
        sa.Column("confidence_band", sa.String(length=20), nullable=False),
        sa.Column("decision_status", sa.String(length=20), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence_band IN ('high', 'medium', 'low')",
            name="ck_topic_event_match_confidence",
        ),
        sa.CheckConstraint(
            "decision_status IN ('pending', 'confirmed', 'rejected', 'muted')",
            name="ck_topic_event_match_decision",
        ),
        sa.ForeignKeyConstraint(["document_version_id"], ["regulatory_document_versions.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["regulatory_events.id"]),
        sa.ForeignKeyConstraint(["expression_id"], ["regulatory_expressions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["monitoring_topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["topic_revision_id"], ["monitoring_topic_revisions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["work_id"], ["regulatory_works.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "topic_revision_id", "event_id", name="uq_topic_event_match_revision_event"
        ),
    )
    for column in (
        "organization_id",
        "topic_id",
        "topic_revision_id",
        "event_id",
        "work_id",
        "evidence_fingerprint",
        "rule_fingerprint",
        "confidence_band",
        "decision_status",
        "expires_at",
    ):
        op.create_index(f"ix_topic_event_matches_{column}", "topic_event_matches", [column])
    op.create_index(
        "ix_topic_event_matches_org_topic_matched",
        "topic_event_matches",
        ["organization_id", "topic_id", "matched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_topic_event_matches_org_topic_matched", table_name="topic_event_matches"
    )
    for column in reversed(
        (
            "organization_id",
            "topic_id",
            "topic_revision_id",
            "event_id",
            "work_id",
            "evidence_fingerprint",
            "rule_fingerprint",
            "confidence_band",
            "decision_status",
            "expires_at",
        )
    ):
        op.drop_index(f"ix_topic_event_matches_{column}", table_name="topic_event_matches")
    op.drop_table("topic_event_matches")
