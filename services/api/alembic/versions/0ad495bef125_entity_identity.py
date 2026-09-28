"""Retain explicit cross-run entity reviews without merging original mentions."""
import sqlalchemy as sa

from alembic import op

revision = "0ad495bef125"
down_revision = "09d495bef125"
branch_labels = None
depends_on = None


def upgrade():
    # Frozen additive schema, independent of future ORM changes.
    columns = [sa.Column(name, sa.String(36), nullable=False) for name in (
        "organization_id", "dossier_id", "investigation_id", "entity_id", "previous_entity_id",
        "previous_investigation_id", "source_id", "previous_source_id", "request_key")]
    constraints = [sa.ForeignKeyConstraint(["investigation_id", "dossier_id", "organization_id"],
        ["product_investigations.id", "product_investigations.dossier_id", "product_investigations.organization_id"], ondelete="CASCADE")]
    for table, pairs in (
        ("product_dossier_entities", (("entity_id", "investigation_id"), ("previous_entity_id", "previous_investigation_id"))),
        ("product_investigation_sources", (("source_id", "investigation_id"), ("previous_source_id", "previous_investigation_id"))),
    ):
        for identifier, run in pairs:
            constraints.append(sa.ForeignKeyConstraint([identifier, run, "dossier_id", "organization_id"],
                [f"{table}.{key}" for key in ("id", "investigation_id", "dossier_id", "organization_id")], ondelete="CASCADE"))
    op.create_table("product_entity_identity_reviews",
        sa.Column("id", sa.String(36), primary_key=True), *columns,
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), *constraints,
        sa.UniqueConstraint("entity_id", "previous_entity_id", "revision", name="uq_entity_identity_revision"),
        sa.UniqueConstraint("dossier_id", "request_key", name="uq_entity_identity_request"),
        sa.CheckConstraint("entity_id < previous_entity_id", name="ck_entity_identity_order"),
        sa.CheckConstraint("investigation_id <> previous_investigation_id", name="ck_entity_identity_other_run"),
        sa.CheckConstraint("decision IN ('same','different','unresolved')", name="ck_entity_identity_decision"),
        sa.CheckConstraint("revision BETWEEN 1 AND 100", name="ck_entity_identity_revision"))
    for name in ("organization_id", "dossier_id", "investigation_id", "entity_id", "previous_entity_id"):
        op.create_index("ix_product_entity_identity_reviews_" + name, "product_entity_identity_reviews", [name])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM product_entity_identity_reviews")):
        raise RuntimeError("Retain entity reviews: roll back code without dropping their history.")
    op.drop_table("product_entity_identity_reviews")
