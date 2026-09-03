"""Add private per-user impact inbox state.

Revision ID: c84d2e19a6f1
Revises: a63e1c92b7f4
"""

import sqlalchemy as sa

from alembic import op

revision = "c84d2e19a6f1"
down_revision = "a63e1c92b7f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regulatory_event_user_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("principal_key", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('unread', 'read', 'dismissed', 'muted')",
            name="ck_regulatory_event_user_state_value",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["regulatory_events.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "event_id",
            "principal_key",
            name="uq_regulatory_event_user_state_principal",
        ),
    )
    for column in ("organization_id", "event_id", "user_id", "principal_key", "state"):
        op.create_index(
            f"ix_regulatory_event_user_states_{column}",
            "regulatory_event_user_states",
            [column],
        )
    op.create_table(
        "organization_relation_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("organization_candidate_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('confirmed', 'rejected')",
            name="ck_organization_relation_review_decision",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["organization_candidate_id"],
            ["organization_relation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "organization_candidate_id",
        "decision",
        "actor_user_id",
        "created_at",
    ):
        op.create_index(
            f"ix_organization_relation_reviews_{column}",
            "organization_relation_reviews",
            [column],
        )


def downgrade() -> None:
    op.drop_table("organization_relation_reviews")
    op.drop_table("regulatory_event_user_states")
