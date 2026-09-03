"""Add persisted connector schedules and run history."""

import sqlalchemy as sa

from alembic import op

revision = "d81e7a42bc10"
down_revision = "c27f8d91a6e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "connector_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("connector", sa.String(80), nullable=False),
        sa.Column("stream", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("jitter_seconds", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.String(5), nullable=True),
        sa.Column("window_end", sa.String(5), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_job_id", sa.String(36), nullable=True),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("connector", "stream", name="uq_connector_schedule_stream"),
    )
    op.create_index("ix_connector_schedules_connector", "connector_schedules", ["connector"])
    op.create_index("ix_connector_schedules_enabled", "connector_schedules", ["enabled"])
    op.create_index("ix_connector_schedules_next_run_at", "connector_schedules", ["next_run_at"])
    op.create_table(
        "connector_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "schedule_id",
            sa.String(36),
            sa.ForeignKey("connector_schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column(
            "requested_by_organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        sa.Column("connector", sa.String(80), nullable=False),
        sa.Column("stream", sa.String(200), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_cursor_json", sa.JSON(), nullable=True),
        sa.Column("output_cursor_json", sa.JSON(), nullable=True),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("changed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("fanout_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_connector_run_job"),
    )
    for column in (
        "schedule_id",
        "job_id",
        "requested_by_organization_id",
        "connector",
        "status",
    ):
        op.create_index(f"ix_connector_runs_{column}", "connector_runs", [column])


def downgrade():
    for column in (
        "status",
        "connector",
        "requested_by_organization_id",
        "job_id",
        "schedule_id",
    ):
        op.drop_index(f"ix_connector_runs_{column}", table_name="connector_runs")
    op.drop_table("connector_runs")
    op.drop_index("ix_connector_schedules_next_run_at", table_name="connector_schedules")
    op.drop_index("ix_connector_schedules_enabled", table_name="connector_schedules")
    op.drop_index("ix_connector_schedules_connector", table_name="connector_schedules")
    op.drop_table("connector_schedules")
