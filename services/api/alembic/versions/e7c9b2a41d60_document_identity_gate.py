"""Persist artifact identity, pair decisions, and review audit."""

import sqlalchemy as sa

from alembic import op

revision = "e7c9b2a41d60"
down_revision = "d4f6a18b0c52"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("versions", sa.Column("identity_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("comparisons", sa.Column("identity_json", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "identity_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("law_id", sa.String(36), sa.ForeignKey("laws.id"), nullable=False),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("versions.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("identity_fingerprint", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_identity_decisions_law_id", "identity_decisions", ["law_id"])
    op.create_index("ix_identity_decisions_version_id", "identity_decisions", ["version_id"])
    op.create_index("ix_identity_decisions_identity_fingerprint", "identity_decisions", ["identity_fingerprint"])


def downgrade():
    op.drop_index("ix_identity_decisions_identity_fingerprint", table_name="identity_decisions")
    op.drop_index("ix_identity_decisions_version_id", table_name="identity_decisions")
    op.drop_index("ix_identity_decisions_law_id", table_name="identity_decisions")
    op.drop_table("identity_decisions")
    op.drop_column("comparisons", "identity_json")
    op.drop_column("versions", "identity_json")
