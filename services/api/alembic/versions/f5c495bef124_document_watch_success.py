"""Retain successful source checks separately from failed attempts."""
import sqlalchemy as sa

from alembic import op

revision = "f5c495bef124"
down_revision = "f4c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_watches", sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
    # Latest failed/reused/unknown attempts cannot establish a historical success time.
    # Only a known successful latest attempt with an accepted nonsynthetic version is safe.
    op.execute(sa.text("""UPDATE document_watches SET last_success_at = last_checked
        WHERE last_checked IS NOT NULL AND last_result IN ('baseline_created', 'changed', 'unchanged')
        AND EXISTS (SELECT 1 FROM laws JOIN versions ON versions.id = laws.current_version_id
                    WHERE laws.id = document_watches.law_id AND versions.synthetic = false)"""))


def downgrade():
    with op.batch_alter_table("document_watches") as batch:
        batch.drop_column("last_success_at")
