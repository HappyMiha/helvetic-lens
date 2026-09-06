"""Keep personal source decisions separate from shared subscriptions."""

import sqlalchemy as sa

from alembic import op

revision = "fe61da50643c"
down_revision = "fd50c94f632b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "personal_source_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("principal_key", sa.String(80), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("first_reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "principal_key", name="uq_source_review_principal"),
    )
    op.create_index(
        "ix_personal_source_reviews_organization_id", "personal_source_reviews", ["organization_id"]
    )


def downgrade():
    op.drop_table("personal_source_reviews")
