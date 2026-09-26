"""Add accountable product review and action workflows."""

import sqlalchemy as sa

from alembic import op

revision = "f4c495bef124"
down_revision = "f3c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("product_dossiers") as batch:
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("context_json", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("priority", sa.String(12), nullable=False, server_default="normal"))
        batch.add_column(sa.Column("owner_user_id", sa.String(36)))
        batch.add_column(sa.Column("next_review_on", sa.Date()))
        batch.add_column(sa.Column("last_reviewed_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key("fk_product_dossier_owner", "users", ["owner_user_id"], ["id"], ondelete="SET NULL")
    op.create_table("product_dossier_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("creation_key", sa.String(36), nullable=False),
        sa.Column("creation_fingerprint", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(12), nullable=False),
        sa.Column("assignee_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("due_on", sa.Date()),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"], ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dossier_id", "creation_key", name="uq_product_action_creation"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'done', 'cancelled')", name="ck_product_action_status"),
        sa.CheckConstraint("priority IN ('normal', 'high', 'urgent')", name="ck_product_action_priority"))
    for name in ("organization_id", "dossier_id", "status", "due_on"):
        op.create_index("ix_product_dossier_actions_" + name, "product_dossier_actions", [name])
    op.create_table("product_research_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("creation_key", sa.String(36), nullable=False),
        sa.Column("creation_fingerprint", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("accepted_entry_id", sa.String(36)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id", "organization_id"], ["product_dossiers.id", "product_dossiers.organization_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dossier_id", "creation_key", name="uq_research_thread_creation"))
    for name in ("organization_id", "dossier_id"):
        op.create_index("ix_product_research_threads_" + name, "product_research_threads", [name])
    with op.batch_alter_table("product_dossier_entries") as batch:
        batch.add_column(sa.Column("thread_id", sa.String(36)))
        batch.create_foreign_key("fk_dossier_entry_thread", "product_research_threads", ["thread_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_product_dossier_entries_thread_id", ["thread_id"])


def downgrade():
    with op.batch_alter_table("product_dossier_entries") as batch:
        batch.drop_constraint("fk_dossier_entry_thread", type_="foreignkey")
        batch.drop_index("ix_product_dossier_entries_thread_id")
        batch.drop_column("thread_id")
    op.drop_table("product_research_threads")
    op.drop_table("product_dossier_actions")
    with op.batch_alter_table("product_dossiers") as batch:
        batch.drop_constraint("fk_product_dossier_owner", type_="foreignkey")
        for name in ("last_reviewed_at", "next_review_on", "owner_user_id", "priority", "context_json", "revision"):
            batch.drop_column(name)
