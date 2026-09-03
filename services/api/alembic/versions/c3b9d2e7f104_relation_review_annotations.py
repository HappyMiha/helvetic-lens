"""Allow append-only annotations in relation review history.

Revision ID: c3b9d2e7f104
Revises: a1d8f63c2b74
"""

from alembic import op

revision = "c3b9d2e7f104"
down_revision = "a1d8f63c2b74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("organization_relation_reviews") as batch_op:
        batch_op.drop_constraint(
            "ck_organization_relation_review_decision", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_organization_relation_review_decision",
            "decision IN ('confirmed', 'rejected', 'annotated')",
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM organization_relation_reviews WHERE decision = 'annotated'"
    )
    with op.batch_alter_table("organization_relation_reviews") as batch_op:
        batch_op.drop_constraint(
            "ck_organization_relation_review_decision", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_organization_relation_review_decision",
            "decision IN ('confirmed', 'rejected')",
        )
