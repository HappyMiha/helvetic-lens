"""Support latest saved activity selection per monitored work."""
from alembic import op

revision = "b294ad830761"
down_revision = "a183fc729650"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_regulatory_event_work_latest", "regulatory_events", ["work_id", "detected_at", "id"])


def downgrade():
    op.drop_index("ix_regulatory_event_work_latest", table_name="regulatory_events")
