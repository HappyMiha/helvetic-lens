"""Private expiring references for explicitly downloaded evidence packets."""

import sqlalchemy as sa

from alembic import op

revision = "c5a28346e4c7"
down_revision = "b4f17235d3b6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("trademark_export_preparations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("source_revision_id", sa.String(36), sa.ForeignKey("trademark_register_revisions.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("trademark_candidate_events.id", ondelete="CASCADE")),
        sa.Column("locale", sa.String(5), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["candidate_id", "organization_id"], ["trademark_candidates.id", "trademark_candidates.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("candidate_id", "request_key", name="uq_trademark_export_request"),
        sa.CheckConstraint("candidate_version >= 1 AND expires_at > created_at", name="ck_trademark_export_validity"),
    )
    for column in ("organization_id", "candidate_id", "expires_at"):
        op.create_index("ix_trademark_export_preparations_" + column, "trademark_export_preparations", [column])


def downgrade():
    op.drop_table("trademark_export_preparations")
