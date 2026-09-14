"""Private location-story references and reviewed geographic bindings."""
import sqlalchemy as sa

from alembic import op

revision = "3c19fa035bde"
down_revision = "2b08e9a24acd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("related_place_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("feature_key", sa.String(64), nullable=False),
        sa.Column("source_revision", sa.String(64), nullable=False),
        sa.Column("binding", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("fingerprint", name="uq_related_place_fingerprint"))
    for column in ("feature_key", "source_revision"):
        op.create_index(f"ix_related_place_bindings_{column}", "related_place_bindings", [column])
    op.create_table("related_stories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_related_story_scope"),
        sa.UniqueConstraint("organization_id", "owner_user_id", "request_key", name="uq_related_story_request"),
        sa.CheckConstraint("version >= 1", name="ck_related_story_version"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_related_story_status"))
    for column in ("organization_id", "owner_user_id"):
        op.create_index(f"ix_related_stories_{column}", "related_stories", [column])
    op.create_table("related_story_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("previous_fingerprint", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["story_id", "organization_id"], ["related_stories.id", "related_stories.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("story_id", "revision", name="uq_related_story_revision"),
        sa.UniqueConstraint("story_id", "request_key", name="uq_related_revision_request"),
        sa.CheckConstraint("revision >= 1", name="ck_related_revision_number"),
        sa.CheckConstraint("action IN ('create','revise','split','merge','archive','restore')", name="ck_related_revision_action"))
    for column in ("story_id", "organization_id"):
        op.create_index(f"ix_related_story_revisions_{column}", "related_story_revisions", [column])


def downgrade():
    op.drop_table("related_story_revisions")
    op.drop_table("related_stories")
    op.drop_table("related_place_bindings")
