"""Persist reusable organization event briefs and their immutable references."""

import sqlalchemy as sa

from alembic import op

revision = "d7d9f1284ba5"
down_revision = "d6c8e0173a94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interest_event_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("regulatory_events.id"), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt_key", sa.String(36)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "event_id", "input_fingerprint", name="uq_interest_assessment_input"),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'superseded')",
                           name="ck_interest_assessment_status"),
    )
    for column in ("organization_id", "event_id"):
        op.create_index(f"ix_interest_event_assessments_{column}", "interest_event_assessments", [column])
    op.create_index("ix_interest_assessment_history", "interest_event_assessments",
                    ["organization_id", "event_id", "created_at", "id"])
    op.create_table(
        "interest_assessment_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("assessment_id", sa.String(36),
                  sa.ForeignKey("interest_event_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("reference_id", sa.String(160), nullable=False),
        sa.Column("revision", sa.String(160), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("assessment_id", "kind", "reference_id", name="uq_interest_assessment_binding"),
        sa.CheckConstraint("kind IN ('topic', 'law', 'direct_watch', 'evidence')", name="ck_interest_binding_kind"),
    )
    op.create_index("ix_interest_assessment_bindings_organization_id", "interest_assessment_bindings", ["organization_id"])
    op.create_index("ix_interest_binding_reference", "interest_assessment_bindings",
                    ["organization_id", "kind", "reference_id", "assessment_id"])


def downgrade() -> None:
    op.drop_table("interest_assessment_bindings")
    op.drop_table("interest_event_assessments")
