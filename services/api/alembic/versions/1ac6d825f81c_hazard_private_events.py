"""Private CAP developments, immutable decisions and material review state."""

import sqlalchemy as sa

from alembic import op

revision = "1ac6d825f81c"
down_revision = "09b5c714e70b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("hazard_developments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monitor_id", sa.String(36), nullable=False),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("hazard_source_permissions.id"), nullable=False),
        sa.Column("source_development_key", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("material_sequence", sa.Integer(), nullable=False),
        sa.Column("material_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewed_sequence", sa.Integer(), nullable=False),
        sa.Column("dismissed_sequence", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "organization_id", name="uq_hazard_development_scope"),
        sa.UniqueConstraint("monitor_id", "configuration_revision", "permission_id", "source_development_key", name="uq_hazard_private_development"),
        sa.CheckConstraint("configuration_revision >= 1 AND revision >= 1 AND material_sequence >= 1 AND version >= 1", name="ck_hazard_development_version"),
        sa.CheckConstraint("reviewed_sequence >= 0 AND reviewed_sequence <= material_sequence AND dismissed_sequence >= 0 AND dismissed_sequence <= material_sequence", name="ck_hazard_development_review"))
    op.create_table("hazard_event_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("development_id", sa.String(36), nullable=False),
        sa.Column("permission_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("material_sequence", sa.Integer(), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=False),
        sa.Column("proof", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["development_id", "organization_id"], ["hazard_developments.id", "hazard_developments.organization_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id", "permission_id"], ["hazard_message_evidence.id", "hazard_message_evidence.permission_id"], name="fk_hazard_event_source"),
        sa.UniqueConstraint("development_id", "revision", name="uq_hazard_event_revision"),
        sa.UniqueConstraint("id", "organization_id", name="uq_hazard_event_scope"),
        sa.CheckConstraint("revision >= 1 AND material_sequence >= 1", name="ck_hazard_event_revision"))
    for table, columns in (("hazard_developments", ("organization_id", "monitor_id")),
                           ("hazard_event_revisions", ("organization_id", "development_id"))):
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_table("hazard_review_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_revision_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_revision_id", "organization_id"], ["hazard_event_revisions.id", "hazard_event_revisions.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("action IN ('reviewed','not_relevant')", name="ck_hazard_review_action"))
    for column in ("organization_id", "event_revision_id"):
        op.create_index(f"ix_hazard_review_actions_{column}", "hazard_review_actions", [column])
    op.create_table("hazard_mutes",
        sa.Column("monitor_id", sa.String(36), primary_key=True),
        sa.Column("hazard", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("muted", sa.Boolean(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id", "organization_id"], ["hazard_monitors.id", "hazard_monitors.organization_id"], ondelete="CASCADE"),
        sa.CheckConstraint("hazard IN ('flood','storm','forest_fire','heavy_snow','power_outage','civil_protection_warning')", name="ck_hazard_mute_type"))
    op.create_index("ix_hazard_mutes_organization_id", "hazard_mutes", ["organization_id"])


def downgrade():
    op.drop_table("hazard_mutes")
    op.drop_table("hazard_review_actions")
    op.drop_table("hazard_event_revisions")
    op.drop_table("hazard_developments")
