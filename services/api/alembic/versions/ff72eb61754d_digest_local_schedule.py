"""Optional local delivery clock, preserving existing elapsed-time schedules."""
import sqlalchemy as sa

from alembic import op

revision = "ff72eb61754d"
down_revision = "fe61da50643c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("digest_preferences", sa.Column("schedule_json", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("digest_preferences") as batch:
        batch.drop_column("schedule_json")
