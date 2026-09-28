"""Personal research read positions and private dossier following."""
import sqlalchemy as sa

from alembic import op

revision = "05d495bef125"
down_revision = "04d495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_public_follows", sa.Column("research_seen_at", sa.DateTime(timezone=True)))
    op.create_table("product_private_follows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("following", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("seen_marker", sa.String(64), nullable=False),
        sa.Column("research_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"],
            ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_user_id", "dossier_id", name="uq_private_follow_owner"))
    for column in ("organization_id", "dossier_id", "owner_user_id"):
        op.create_index("ix_product_private_follows_" + column, "product_private_follows", [column])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_private_follows")):
        raise RuntimeError("Retained personal follows must be handled before downgrading.")
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_public_follows WHERE research_seen_at IS NOT NULL")):
        raise RuntimeError("Retained personal research read positions must be handled before downgrading.")
    op.drop_table("product_private_follows")
    op.drop_column("product_public_follows", "research_seen_at")
