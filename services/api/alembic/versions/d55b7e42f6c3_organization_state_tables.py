"""Add organization-owned prompt history, quota, and connector state."""

import sqlalchemy as sa

from alembic import op

revision = "d55b7e42f6c3"
down_revision = "c44a6d31e5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prompt_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "revision", name="uq_prompt_revision_organization"),
    )
    op.create_index("ix_prompt_revisions_organization_id", "prompt_revisions", ["organization_id"])
    op.execute(
        'INSERT INTO prompt_revisions (id, organization_id, revision, "values", created_at) '
        'SELECT organization_id, organization_id, revision, "values", updated_at FROM prompt_configuration'
    )
    op.create_table(
        "organization_quotas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_organization_quotas_organization_id", "organization_quotas", ["organization_id"])
    op.create_table(
        "feed_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("connector", sa.String(length=80), nullable=False),
        sa.Column("stream", sa.String(length=200), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "connector", "stream", name="uq_feed_state_organization_stream"
        ),
    )
    op.create_index("ix_feed_states_organization_id", "feed_states", ["organization_id"])


def downgrade():
    op.drop_index("ix_feed_states_organization_id", table_name="feed_states")
    op.drop_table("feed_states")
    op.drop_index("ix_organization_quotas_organization_id", table_name="organization_quotas")
    op.drop_table("organization_quotas")
    op.drop_index("ix_prompt_revisions_organization_id", table_name="prompt_revisions")
    op.drop_table("prompt_revisions")
