"""Permission-bound Road Watch source history.

Revision ID: f2ce409d70f4
Revises: e1bd3f8c6fe3
"""

import sqlalchemy as sa

from alembic import op

revision = "f2ce409d70f4"
down_revision = "e1bd3f8c6fe3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("road_source_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_table("road_source_heads",
        sa.Column("source", sa.String(40), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("road_source_permissions.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("last_full_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot_hash", sa.String(64)))
    op.create_table("road_source_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("road_source_permissions.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("previous_generation", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("continuous", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary()),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("raw_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("permission_id", "request_id", name="uq_road_evidence_request"),
        sa.UniqueConstraint("permission_id", "generation", name="uq_road_evidence_generation"),
        sa.UniqueConstraint("id", "permission_id", name="uq_road_evidence_permission"))
    op.create_table("road_situation_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("road_source_permissions.id"), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("semantic_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary()),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("version_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "permission_id", "source_id", name="uq_road_version_binding"),
        sa.ForeignKeyConstraint(["evidence_id", "permission_id"],
            ["road_source_evidence.id", "road_source_evidence.permission_id"], name="fk_road_version_evidence"))
    op.create_index("ix_road_situation_versions_permission_id", "road_situation_versions", ["permission_id"])
    op.create_index("ix_road_situation_versions_source_id", "road_situation_versions", ["source_id"])
    op.create_table("road_current_situations",
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("road_source_permissions.id"), primary_key=True),
        sa.Column("source_id", sa.String(256), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["version_id", "permission_id", "source_id"],
            ["road_situation_versions.id", "road_situation_versions.permission_id", "road_situation_versions.source_id"],
            name="fk_road_current_version"))
    op.create_table("road_source_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("road_source_permissions.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=False),
        sa.Column("development_id", sa.String(64), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("permission_id", "generation", "source_id", name="uq_road_change_generation"),
        sa.ForeignKeyConstraint(["evidence_id", "permission_id"],
            ["road_source_evidence.id", "road_source_evidence.permission_id"], name="fk_road_change_evidence"),
        sa.ForeignKeyConstraint(["version_id", "permission_id", "source_id"],
            ["road_situation_versions.id", "road_situation_versions.permission_id", "road_situation_versions.source_id"],
            name="fk_road_change_version"))
    op.create_index("ix_road_source_changes_permission_id", "road_source_changes", ["permission_id"])


def downgrade():
    for table in ("road_source_changes", "road_current_situations", "road_situation_versions", "road_source_evidence",
                  "road_source_heads", "road_source_permissions"):
        op.drop_table(table)
