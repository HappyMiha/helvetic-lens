"""Workspace influence dossiers; additive tables only, no source collection."""

import sqlalchemy as sa

from alembic import op

revision = "d1c495bef124"
down_revision = "e1c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "influence_dossiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("creation_key", sa.String(36), nullable=False),
        sa.Column("creation_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "organization_id", name="uq_influence_dossier_org"),
        sa.UniqueConstraint("organization_id", "creation_key", name="uq_influence_creation"),
    )
    op.create_index("ix_influence_dossiers_organization_id", "influence_dossiers", ["organization_id"])
    op.create_table(
        "influence_revisions",
        sa.Column("dossier_id", sa.String(36), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("document_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dossier_id", "organization_id"],
            ["influence_dossiers.id", "influence_dossiers.organization_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("dossier_id", "request_key", name="uq_influence_revision_request"),
    )
    op.create_index("ix_influence_revisions_organization_id", "influence_revisions", ["organization_id"])
    op.create_table(
        "influence_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dossier_id", "organization_id"],
            ["influence_dossiers.id", "influence_dossiers.organization_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dossier_id", "revision"],
            ["influence_revisions.dossier_id", "influence_revisions.revision"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("dossier_id", "request_key", name="uq_influence_review_request"),
    )
    op.create_index("ix_influence_reviews_dossier_id", "influence_reviews", ["dossier_id"])
    op.create_index("ix_influence_reviews_organization_id", "influence_reviews", ["organization_id"])


def downgrade():
    op.drop_table("influence_reviews")
    op.drop_table("influence_revisions")
    op.drop_table("influence_dossiers")
