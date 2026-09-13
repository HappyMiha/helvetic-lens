"""Permission-bound public CAP journal, independent of private monitor locations."""

import sqlalchemy as sa

from alembic import op

revision = "09b5c714e70b"
down_revision = "f824a6f3d6fa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("hazard_source_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_table("hazard_source_selections",
        sa.Column("source_key", sa.String(80), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("hazard_source_permissions.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("cursor_version", sa.Integer(), nullable=False),
        sa.Column("last_received_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("generation >= 1 AND cursor_version >= 0", name="ck_hazard_source_selection_version"))
    op.create_table("hazard_message_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("hazard_source_permissions.id"), nullable=False),
        sa.Column("message_key", sa.String(64), nullable=False),
        sa.Column("identifier", sa.String(256), nullable=False),
        sa.Column("development_key", sa.String(64), nullable=False),
        sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.LargeBinary()),
        sa.Column("raw_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("normalized_hash", sa.String(64), nullable=False),
        sa.Column("normalized_payload", sa.LargeBinary()),
        sa.Column("normalized_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("material_sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("material", sa.Boolean(), nullable=False),
        sa.Column("classification", sa.JSON(), nullable=False),
        sa.Column("reference_keys", sa.JSON(), nullable=False),
        sa.UniqueConstraint("permission_id", "message_key", name="uq_hazard_evidence_key"),
        sa.UniqueConstraint("permission_id", "identifier", name="uq_hazard_evidence_identifier"),
        sa.UniqueConstraint("id", "permission_id", name="uq_hazard_evidence_permission"),
        sa.UniqueConstraint("id", "permission_id", "development_key", name="uq_hazard_evidence_development"),
        sa.CheckConstraint("material_sequence >= 1", name="ck_hazard_evidence_sequence"))
    for column in ("permission_id", "raw_expires_at", "normalized_expires_at"):
        op.create_index(f"ix_hazard_message_evidence_{column}", "hazard_message_evidence", [column])
    op.create_table("hazard_current_warnings",
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("hazard_source_permissions.id"), primary_key=True),
        sa.Column("development_key", sa.String(64), primary_key=True),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("material_sequence", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id", "permission_id", "development_key"],
            ["hazard_message_evidence.id", "hazard_message_evidence.permission_id", "hazard_message_evidence.development_key"],
            name="fk_hazard_current_evidence"),
        sa.CheckConstraint("material_sequence >= 1 AND generation >= 1", name="ck_hazard_current_version"),
        sa.CheckConstraint("state IN ('active','resolved','cancelled')", name="ck_hazard_current_state"))
    op.create_table("hazard_source_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("hazard_source_permissions.id"), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("cursor_version", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change", sa.JSON(), nullable=False),
        sa.UniqueConstraint("permission_id", "generation", "request_key", name="uq_hazard_receipt_request"),
        sa.ForeignKeyConstraint(["evidence_id", "permission_id"],
            ["hazard_message_evidence.id", "hazard_message_evidence.permission_id"], name="fk_hazard_receipt_evidence"),
        sa.CheckConstraint("generation >= 1 AND cursor_version >= 1", name="ck_hazard_receipt_version"))
    op.create_index("ix_hazard_source_receipts_permission_id", "hazard_source_receipts", ["permission_id"])


def downgrade():
    for table in ("hazard_source_receipts", "hazard_current_warnings", "hazard_message_evidence",
                  "hazard_source_selections", "hazard_source_permissions"):
        op.drop_table(table)
