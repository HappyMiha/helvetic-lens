"""Reviewed deadline registry and reference-only private calculation bindings."""

import sqlalchemy as sa

from alembic import op

revision = "e7c4a56806e9"
down_revision = "d6b39457f5d8"
branch_labels = None
depends_on = None


def upgrade():
    registry = op.create_table("trademark_deadline_registry",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.bulk_insert(registry, [{"id": "main", "revision": 1}])
    for name in ("rules", "calendars"):
        op.create_table("trademark_deadline_" + name,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("configuration", sa.JSON(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_table("trademark_deadline_rule_selections",
        sa.Column("source_key", sa.String(80), primary_key=True),
        sa.Column("origin", sa.String(40), primary_key=True),
        sa.Column("rule_id", sa.String(64), sa.ForeignKey("trademark_deadline_rules.id"), nullable=False))
    op.create_table("trademark_deadline_calendar_selections",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("calendar_id", sa.String(64), sa.ForeignKey("trademark_deadline_calendars.id"), nullable=False))
    for name in ("trademark_candidates", "trademark_candidate_events"):
        op.add_column(name, sa.Column("deadline_binding", sa.JSON(), nullable=True))


def downgrade():
    for name in ("trademark_candidate_events", "trademark_candidates"):
        op.drop_column(name, "deadline_binding")
    for name in ("calendar_selections", "rule_selections", "calendars", "rules", "registry"):
        op.drop_table("trademark_deadline_" + name)
