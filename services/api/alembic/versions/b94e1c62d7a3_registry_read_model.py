"""Add saved registry metadata and organization event read state."""

import sqlalchemy as sa

from alembic import op

revision = "b94e1c62d7a3"
down_revision = "a83d2f417c90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("regulatory_events") as batch:
        batch.add_column(
            sa.Column("connector", sa.String(length=80), nullable=False, server_default="unknown")
        )
        batch.add_column(
            sa.Column("connector_health", sa.String(length=20), nullable=False, server_default="unknown")
        )
        batch.add_column(
            sa.Column("analysis_state", sa.String(length=20), nullable=False, server_default="pending")
        )
        batch.add_column(sa.Column("impact", sa.String(length=20), nullable=False, server_default="unknown"))
        batch.create_check_constraint(
            "ck_regulatory_event_connector_health",
            "connector_health IN ('healthy', 'degraded', 'error', 'unknown')",
        )
        batch.create_check_constraint(
            "ck_regulatory_event_analysis_state",
            "analysis_state IN ('pending', 'queued', 'running', 'complete', 'failed', 'not_required')",
        )
        batch.create_check_constraint(
            "ck_regulatory_event_impact",
            "impact IN ('high', 'medium', 'low', 'none', 'unknown')",
        )
        batch.create_index("ix_regulatory_events_connector", ["connector"])
        batch.create_index("ix_regulatory_events_connector_health", ["connector_health"])
        batch.create_index("ix_regulatory_events_analysis_state", ["analysis_state"])
        batch.create_index("ix_regulatory_events_impact", ["impact"])

    op.create_table(
        "regulatory_event_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["event_id"], ["regulatory_events.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "event_id", name="uq_regulatory_event_state_org_event"),
    )
    op.create_index(
        "ix_regulatory_event_states_organization_id",
        "regulatory_event_states",
        ["organization_id"],
    )
    op.create_index("ix_regulatory_event_states_event_id", "regulatory_event_states", ["event_id"])
    op.create_index("ix_regulatory_event_states_read_at", "regulatory_event_states", ["read_at"])


def downgrade():
    op.drop_table("regulatory_event_states")
    with op.batch_alter_table("regulatory_events") as batch:
        batch.drop_index("ix_regulatory_events_impact")
        batch.drop_index("ix_regulatory_events_analysis_state")
        batch.drop_index("ix_regulatory_events_connector_health")
        batch.drop_index("ix_regulatory_events_connector")
        batch.drop_constraint("ck_regulatory_event_impact", type_="check")
        batch.drop_constraint("ck_regulatory_event_analysis_state", type_="check")
        batch.drop_constraint("ck_regulatory_event_connector_health", type_="check")
        batch.drop_column("impact")
        batch.drop_column("analysis_state")
        batch.drop_column("connector_health")
        batch.drop_column("connector")
