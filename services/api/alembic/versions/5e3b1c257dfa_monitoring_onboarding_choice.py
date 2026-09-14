"""Persist a personal Monitoring choice without changing legacy intent values."""

import sqlalchemy as sa

from alembic import op

revision = "5e3b1c257dfa"
down_revision = "4d2a0b146cef"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_onboarding") as batch:
        batch.add_column(sa.Column("monitoring_template", sa.String(20), nullable=True))
        batch.create_check_constraint("ck_onboarding_monitoring_template",
            "monitoring_template IS NULL OR monitoring_template IN ('pollen','river','air','warnings','commute','traffic','tenders','ip','auctions')")


def downgrade():
    with op.batch_alter_table("user_onboarding") as batch:
        batch.drop_constraint("ck_onboarding_monitoring_template", type_="check")
        batch.drop_column("monitoring_template")
