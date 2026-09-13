"""Add bounded transport feed storage and private event history."""

import sqlalchemy as sa

from alembic import op

revision = "a7d9eb482baf"
down_revision = "f6c8da371a9e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commute_source_permissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("policy_reference", sa.String(length=500), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_age_seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_commute_source_permissions_source"), "commute_source_permissions", ["source"], unique=False
    )
    op.create_table(
        "commute_feed_states",
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("permission_id", sa.String(length=36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("static_version", sa.String(length=256), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["commute_source_permissions.id"]),
        sa.PrimaryKeyConstraint("source"),
    )
    op.create_table(
        "commute_developments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("monitor_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("permission_id", sa.String(length=36), nullable=False),
        sa.Column("entity_key", sa.String(length=256), nullable=False),
        sa.Column("service_day", sa.Date(), nullable=False),
        sa.Column("static_version", sa.String(length=256), nullable=False),
        sa.Column("checkpoints", sa.JSON(), nullable=False),
        sa.Column("observations", sa.JSON(), nullable=False),
        sa.Column("current", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("reviewed_sequence", sa.Integer(), nullable=False),
        sa.Column("muted", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["monitor_id", "organization_id"],
            ["commute_monitors.id", "commute_monitors.organization_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["commute_source_permissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_commute_development_scope"),
        sa.UniqueConstraint("monitor_id", "key", name="uq_commute_development_key"),
    )
    op.create_index(
        op.f("ix_commute_developments_monitor_id"), "commute_developments", ["monitor_id"], unique=False
    )
    op.create_index(
        op.f("ix_commute_developments_organization_id"),
        "commute_developments",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "commute_event_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("development_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["development_id", "organization_id"],
            ["commute_developments.id", "commute_developments.organization_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("development_id", "sequence", name="uq_commute_event_sequence"),
    )
    op.create_index(
        op.f("ix_commute_event_versions_development_id"),
        "commute_event_versions",
        ["development_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commute_event_versions_organization_id"),
        "commute_event_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "commute_signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("development_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("delivery_kind", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["development_id", "organization_id"],
            ["commute_developments.id", "commute_developments.organization_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("development_id", "sequence", name="uq_commute_signal_sequence"),
    )
    op.create_index(
        op.f("ix_commute_signals_development_id"), "commute_signals", ["development_id"], unique=False
    )
    op.create_index(
        op.f("ix_commute_signals_organization_id"), "commute_signals", ["organization_id"], unique=False
    )
    op.add_column(
        "commute_monitors",
        sa.Column(
            "next_poll_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("'1970-01-01 00:00:00+00:00'"),
            nullable=False,
        ),
    )
    op.add_column("commute_monitors", sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        op.f("ix_commute_monitors_next_poll_at"), "commute_monitors", ["next_poll_at"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_commute_monitors_next_poll_at"), table_name="commute_monitors")
    op.drop_column("commute_monitors", "last_poll_at")
    op.drop_column("commute_monitors", "next_poll_at")
    op.drop_index(op.f("ix_commute_signals_organization_id"), table_name="commute_signals")
    op.drop_index(op.f("ix_commute_signals_development_id"), table_name="commute_signals")
    op.drop_table("commute_signals")
    op.drop_index(op.f("ix_commute_event_versions_organization_id"), table_name="commute_event_versions")
    op.drop_index(op.f("ix_commute_event_versions_development_id"), table_name="commute_event_versions")
    op.drop_table("commute_event_versions")
    op.drop_index(op.f("ix_commute_developments_organization_id"), table_name="commute_developments")
    op.drop_index(op.f("ix_commute_developments_monitor_id"), table_name="commute_developments")
    op.drop_table("commute_developments")
    op.drop_table("commute_feed_states")
    op.drop_index(op.f("ix_commute_source_permissions_source"), table_name="commute_source_permissions")
    op.drop_table("commute_source_permissions")
