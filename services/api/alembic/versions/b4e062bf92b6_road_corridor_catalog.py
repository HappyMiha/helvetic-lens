"""Reviewed road topology and stable corridor references.

Revision ID: b4e062bf92b6
Revises: a3df51ae81a5
"""

import sqlalchemy as sa

from alembic import op

revision = "b4e062bf92b6"
down_revision = "a3df51ae81a5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("road_topology_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("country", sa.String(16), nullable=False),
        sa.Column("table", sa.String(16), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("asset_hash", sa.String(64), nullable=False),
        sa.Column("topology_hash", sa.String(64), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_table("road_corridor_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("flow_key", sa.String(64), nullable=False),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False))
    op.create_table("road_corridor_maps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference_id", sa.String(36), sa.ForeignKey("road_corridor_references.id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("topology_id", sa.String(36), sa.ForeignKey("road_topology_revisions.id"), nullable=False),
        sa.Column("content", sa.LargeBinary()),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("review_reference", sa.String(500), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("reference_id", "generation", name="uq_road_corridor_generation"))
    op.create_index("ix_road_corridor_maps_reference_id", "road_corridor_maps", ["reference_id"])
    op.create_index("ix_road_corridor_maps_topology_id", "road_corridor_maps", ["topology_id"])


def downgrade():
    op.drop_table("road_corridor_maps")
    op.drop_table("road_corridor_references")
    op.drop_table("road_topology_revisions")
