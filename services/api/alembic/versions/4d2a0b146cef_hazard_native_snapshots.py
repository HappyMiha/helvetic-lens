"""Native warning presence and explicitly incomplete imported history."""

import sqlalchemy as sa

from alembic import op

revision = "4d2a0b146cef"
down_revision = "3c19fa035bde"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hazard_source_selections", sa.Column("feed_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hazard_source_selections", sa.Column("feed_content_hash", sa.String(64), nullable=True))
    op.add_column("hazard_current_warnings", sa.Column("present", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("hazard_message_evidence", sa.Column("history_complete", sa.Boolean(), nullable=False, server_default="1"))
    op.create_table("hazard_source_polls",
        sa.Column("source_key", sa.String(80), sa.ForeignKey("hazard_source_selections.source_key"), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("hazard_source_permissions.id"), nullable=False),
        sa.Column("next_request_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_code", sa.String(100), nullable=False), sa.Column("failures", sa.Integer(), nullable=False))


def downgrade():
    op.drop_table("hazard_source_polls")
    op.drop_column("hazard_message_evidence", "history_complete")
    op.drop_column("hazard_current_warnings", "present")
    op.drop_column("hazard_source_selections", "feed_content_hash")
    op.drop_column("hazard_source_selections", "feed_updated_at")
