"""add consultation regulatory work kind

Revision ID: a14c50d3e9b2
Revises: f03a9d21e6b4
"""

from alembic import op

revision = "a14c50d3e9b2"
down_revision = "f03a9d21e6b4"
branch_labels = None
depends_on = None

OLD = "kind IN ('act', 'ordinance', 'parliamentary_business', 'initiative', 'bill', 'court_decision', 'official_notice', 'unclassified_document')"
NEW = "kind IN ('act', 'ordinance', 'parliamentary_business', 'initiative', 'bill', 'court_decision', 'official_notice', 'consultation', 'unclassified_document')"


def _replace(expression: str) -> None:
    with op.batch_alter_table("regulatory_works") as batch:
        batch.drop_constraint("ck_regulatory_work_kind", type_="check")
        batch.create_check_constraint("ck_regulatory_work_kind", expression)


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    _replace(OLD)
