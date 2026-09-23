"""Persist separate monitored article scopes and immutable snapshot provenance."""

import sqlalchemy as sa

from alembic import op

revision = "f1c495bef124"
down_revision = "d1c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("laws", sa.Column("article_selection", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("versions", sa.Column("selection_provenance", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    # Native DROP COLUMN preserves the evidence-revision triggers on SQLite.
    # Neither additive column is referenced by an index or foreign key.
    op.drop_column("versions", "selection_provenance")
    op.drop_column("laws", "article_selection")
