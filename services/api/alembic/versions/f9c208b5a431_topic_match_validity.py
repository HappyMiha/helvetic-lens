"""Separate current topic eligibility from retained human decisions.

Revision ID: f9c208b5a431
Revises: f8b394a26d10
"""

import sqlalchemy as sa

from alembic import op

revision = "f9c208b5a431"
down_revision = "f8b394a26d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regulatory_event_states", sa.Column("topic_match_generation", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("regulatory_event_states", sa.Column("topic_match_input_fingerprint", sa.String(64), nullable=True))
    with op.batch_alter_table("topic_event_matches") as batch:
        # Old positive matches lack a complete input fingerprint. Do not certify
        # them retrospectively or invent a human review date/actor.
        batch.add_column(sa.Column("match_status", sa.String(20), nullable=False, server_default="unchecked"))
        batch.add_column(sa.Column("evaluation_fingerprint", sa.String(64), nullable=True))
        batch.add_column(sa.Column("evaluated_rule_fingerprint", sa.String(100), nullable=True))
        batch.add_column(sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("review_snapshot_json", sa.JSON(), nullable=True))
        batch.create_check_constraint("ck_topic_event_match_validity", "match_status IN ('unchecked', 'matching', 'not_matching')")


def downgrade() -> None:
    with op.batch_alter_table("regulatory_event_states") as batch:
        batch.drop_column("topic_match_input_fingerprint")
        batch.drop_column("topic_match_generation")
    with op.batch_alter_table("topic_event_matches") as batch:
        batch.drop_constraint("ck_topic_event_match_validity", type_="check")
        for name in ("review_snapshot_json", "evaluated_at", "evaluated_rule_fingerprint", "evaluation_fingerprint", "match_status"):
            batch.drop_column(name)
