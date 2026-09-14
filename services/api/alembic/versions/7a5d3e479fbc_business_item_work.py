"""Native item assignees and immutable evidence-bound work history."""

import sqlalchemy as sa

from alembic import op

revision = "7a5d3e479fbc"
down_revision = "6f4c2d368eab"
branch_labels = None
depends_on = None

TARGETS = {"tender_dossier": "tender_dossiers", "trademark_candidate": "trademark_candidates", "auction_item": "auction_items"}


def upgrade():
    for kind, table in TARGETS.items():
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("assigned_user_id", sa.String(36)))
            batch.create_foreign_key(f"fk_{kind}_assigned_user", "users", ["assigned_user_id"], ["id"], ondelete="SET NULL")
            batch.create_index(f"ix_{table}_assigned_user_id", ["assigned_user_id"])
    op.create_table("business_item_work_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        *(sa.Column(f"{kind}_id", sa.String(36)) for kind in TARGETS),
        sa.Column("item_version", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assigned_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decision", sa.String(20)), sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("evidence_binding", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *(sa.ForeignKeyConstraint([f"{kind}_id", "organization_id"], [f"{table}.id", f"{table}.organization_id"], ondelete="CASCADE") for kind, table in TARGETS.items()),
        sa.CheckConstraint("(CASE WHEN tender_dossier_id IS NULL THEN 0 ELSE 1 END + CASE WHEN trademark_candidate_id IS NULL THEN 0 ELSE 1 END + CASE WHEN auction_item_id IS NULL THEN 0 ELSE 1 END) = 1", name="ck_business_item_target"),
        sa.CheckConstraint("item_version >= 1 AND length(comment) <= 4000", name="ck_business_item_values"),
        *(sa.UniqueConstraint(f"{kind}_id", "item_version", name=f"uq_business_item_{kind.split('_')[0]}_version") for kind in TARGETS))
    for column in ("organization_id", *(f"{kind}_id" for kind in TARGETS)):
        op.create_index(f"ix_business_item_work_events_{column}", "business_item_work_events", [column])


def downgrade():
    op.drop_table("business_item_work_events")
    for kind, table in reversed(list(TARGETS.items())):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_assigned_user_id")
            batch.drop_constraint(f"fk_{kind}_assigned_user", type_="foreignkey")
            batch.drop_column("assigned_user_id")
