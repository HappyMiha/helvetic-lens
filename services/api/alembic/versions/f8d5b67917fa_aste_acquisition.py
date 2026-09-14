"""Durable public Aste UEF acquisition queues and bounded source evidence."""

import sqlalchemy as sa

from alembic import op

revision = "f8d5b67917fa"
down_revision = "e7c4a56806e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("aste_collectors",
        sa.Column("source_key", sa.String(80), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("auction_source_permissions.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.JSON(), nullable=False) for name in ("listing_queue", "visited", "category_labels")],
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("discovery_due_at", "next_request_at")],
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in ("last_request_at", "last_record_at", "last_completed_at", "lease_until")],
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_job", sa.JSON()),
        sa.Column("prefer_listing", sa.Boolean(), nullable=False), sa.Column("last_error", sa.String(100)))
    op.create_table("aste_items",
        sa.Column("identifier", sa.String(20), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("auction_source_permissions.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("next_check_at", "last_seen_at")],
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in ("last_record_at", "detail_at", "payload_expires_at")],
        sa.Column("stage", sa.String(16), nullable=False), sa.Column("category_proofs", sa.JSON(), nullable=False),
        sa.Column("detail_payload", sa.LargeBinary()), sa.Column("documents", sa.JSON(), nullable=False),
        sa.Column("document_index", sa.Integer(), nullable=False), sa.Column("last_error", sa.String(100)))
    op.create_index("ix_aste_items_next_check_at", "aste_items", ["next_check_at"])
    op.create_table("aste_listing_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("auction_source_permissions.id"), nullable=False),
        sa.Column("url", sa.String(500), nullable=False), sa.Column("raw_payload", sa.LargeBinary()),
        sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("metadata_hash", sa.String(64), nullable=False),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("raw_expires_at", "normalized_expires_at", "observed_at")],
        sa.Column("category_id", sa.String(20)), sa.Column("category_label", sa.String(200)), sa.Column("identifiers", sa.JSON()))
    for name in ("permission_id", "raw_expires_at", "normalized_expires_at"):
        op.create_index("ix_aste_listing_evidence_" + name, "aste_listing_evidence", [name])


def downgrade():
    op.drop_table("aste_listing_evidence")
    op.drop_table("aste_items")
    op.drop_table("aste_collectors")
