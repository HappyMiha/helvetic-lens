"""Index bounded per-candidate analysis history reads.

Revision ID: fa27c61d3098
Revises: f9c208b5a431
"""

from alembic import op

revision = "fa27c61d3098"
down_revision = "f9c208b5a431"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_relation_analysis_org_candidate_time", "relation_impact_analyses",
                    ["organization_id", "organization_candidate_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_relation_analysis_org_candidate_time", table_name="relation_impact_analyses")
