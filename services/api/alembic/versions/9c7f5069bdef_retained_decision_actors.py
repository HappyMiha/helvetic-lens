"""Retain shared decisions and reviewed geography when an account is erased."""

import sqlalchemy as sa

from alembic import op

revision = "9c7f5069bdef"
down_revision = "8b6e4f58acde"
branch_labels = None
depends_on = None

TARGETS = (
    ("tender_decisions", "user_id", "CASCADE"),
    ("trademark_reviews", "actor_user_id", "CASCADE"),
    ("auction_decisions", "actor_user_id", "CASCADE"),
    ("related_place_bindings", "reviewed_by", None),
)
NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def replace(table, column, *, nullable, ondelete):
    keys = [key for key in sa.inspect(op.get_bind()).get_foreign_keys(table)
            if key["constrained_columns"] == [column] and key["referred_table"] == "users"]
    if len(keys) != 1:
        raise RuntimeError("Retained actor migration requires exactly one user foreign key.")
    name = keys[0]["name"] or f"fk_{table}_{column}_users"
    with op.batch_alter_table(table, naming_convention=NAMING) as batch:
        batch.drop_constraint(name, type_="foreignkey")
        batch.alter_column(column, existing_type=sa.String(36), nullable=nullable)
        batch.create_foreign_key(f"fk_{table}_{column}_users", "users", [column], ["id"], ondelete=ondelete)


def upgrade():
    for table, column, _ in TARGETS:
        replace(table, column, nullable=True, ondelete="SET NULL")
    with op.batch_alter_table("business_monitor_scope_events") as batch:
        batch.add_column(sa.Column("action", sa.String(20), nullable=False, server_default="scope"))
        for column in ("previous_owner_user_id", "owner_user_id"):
            batch.add_column(sa.Column(column, sa.String(36)))
            batch.create_foreign_key(f"fk_business_scope_{column}", "users", [column], ["id"], ondelete="SET NULL")


def downgrade():
    # A schema rollback must not invent deleted people or discard their former
    # workspace's decisions to restore the old NOT NULL constraint.
    for table, column, _ in TARGETS:
        record = sa.table(table, sa.column(column))
        if op.get_bind().scalar(sa.select(sa.func.count()).select_from(record).where(record.c[column].is_(None))):
            raise RuntimeError("Cannot restore mandatory actor links after account erasure; retain the compatible schema.")
    events = sa.table("business_monitor_scope_events", sa.column("action"))
    if op.get_bind().scalar(sa.select(sa.func.count()).select_from(events).where(events.c.action == "handover")):
        raise RuntimeError("Cannot discard recorded ownership handovers; retain the compatible schema.")
    with op.batch_alter_table("business_monitor_scope_events") as batch:
        for column in ("previous_owner_user_id", "owner_user_id"):
            batch.drop_constraint(f"fk_business_scope_{column}", type_="foreignkey")
            batch.drop_column(column)
        batch.drop_column("action")
    for table, column, ondelete in reversed(TARGETS):
        replace(table, column, nullable=False, ondelete=ondelete)
