"""Opt-in daily direct-document checks; preserve all existing manual watches."""
import sqlalchemy as sa

from alembic import op

revision = "e1c495bef124"
down_revision = "d0b384adf013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_watches", sa.Column("auto_check_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("document_watches", sa.Column("next_auto_check_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_document_watches_next_auto_check_at", "document_watches", ["next_auto_check_at"])


def downgrade():
    op.drop_index("ix_document_watches_next_auto_check_at", table_name="document_watches")
    with op.batch_alter_table("document_watches") as batch:
        batch.drop_column("next_auto_check_at")
        batch.drop_column("auto_check_enabled")
