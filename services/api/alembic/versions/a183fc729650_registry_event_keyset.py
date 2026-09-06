"""Composite index supporting stable event registry keysets."""
from alembic import op

revision = "a183fc729650"
down_revision = "ff72eb61754d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_regulatory_event_registry_page", "regulatory_events", ["detected_at", "id"])


def downgrade():
    op.drop_index("ix_regulatory_event_registry_page", table_name="regulatory_events")
