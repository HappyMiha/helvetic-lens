"""Durable native IPI identities, traversals and permission-bound page evidence."""

import sqlalchemy as sa

from alembic import op

revision = "d6b39457f5d8"
down_revision = "c5a28346e4c7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ipi_token_cache",
        sa.Column("account_hash", sa.String(64), primary_key=True),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.create_index("ix_ipi_token_cache_expires_at", "ipi_token_cache", ["expires_at"])
    op.create_table("ipi_identities",
        sa.Column("source_key", sa.String(80), primary_key=True),
        sa.Column("canonical_hash", sa.String(64), primary_key=True),
        sa.Column("origin", sa.String(40), nullable=False))
    op.create_table("ipi_aliases",
        sa.Column("source_key", sa.String(80), primary_key=True),
        sa.Column("alias_hash", sa.String(64), primary_key=True),
        sa.Column("canonical_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["source_key", "canonical_hash"], ["ipi_identities.source_key", "ipi_identities.canonical_hash"]))
    op.create_table("ipi_traversals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("trademark_source_permissions.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("next_offset", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("unique_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("last_total", sa.Integer()),
        sa.Column("totals_changed", sa.Boolean(), nullable=False),
        sa.Column("next_request", sa.LargeBinary()),
        sa.Column("next_request_hash", sa.String(64)),
        sa.Column("request_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(100)),
        sa.CheckConstraint("generation >= 1 AND next_offset >= 0 AND page_count >= 0 AND duplicate_count >= 0 AND unique_count >= 0", name="ck_ipi_traversal_counts"),
        sa.CheckConstraint("state IN ('running', 'completed', 'abandoned')", name="ck_ipi_traversal_state"))
    for name in ("source_key", "permission_id", "request_expires_at", "next_attempt_at"):
        op.create_index("ix_ipi_traversals_" + name, "ipi_traversals", [name])
    op.create_table("ipi_page_evidence",
        sa.Column("traversal_id", sa.String(36), sa.ForeignKey("ipi_traversals.id"), primary_key=True),
        sa.Column("page_index", sa.Integer(), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("xml_hash", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.LargeBinary()),
        sa.Column("raw_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_offset", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("journal_cursor", sa.Integer(), nullable=False),
        sa.UniqueConstraint("traversal_id", "request_hash", name="uq_ipi_page_request"),
        sa.CheckConstraint("page_index >= 0 AND item_offset >= 0 AND item_count >= 0 AND total_count >= 0", name="ck_ipi_page_counts"))
    op.create_index("ix_ipi_page_evidence_raw_expires_at", "ipi_page_evidence", ["raw_expires_at"])
    op.create_table("ipi_seen_identities",
        sa.Column("traversal_id", sa.String(36), sa.ForeignKey("ipi_traversals.id"), primary_key=True),
        sa.Column("canonical_hash", sa.String(64), primary_key=True))


def downgrade():
    for name in ("ipi_seen_identities", "ipi_page_evidence", "ipi_traversals", "ipi_aliases", "ipi_identities", "ipi_token_cache"):
        op.drop_table(name)
