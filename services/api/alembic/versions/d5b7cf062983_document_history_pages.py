"""Indexes for saved document-history keysets; no evidence rewrite."""

from alembic import op

revision = "d5b7cf062983"
down_revision = "c3a5be941872"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_versions_law_saved_page", "versions", ["law_id", "created_at", "id"]),
    ("ix_comparisons_law_saved_page", "comparisons", ["law_id", "created_at", "id"]),
    ("ix_observations_org_law_saved_page", "observations", ["organization_id", "law_id", "created_at", "id"]),
)


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
