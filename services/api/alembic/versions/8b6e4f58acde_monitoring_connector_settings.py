"""Encrypted, versioned platform Monitoring connector configuration."""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "8b6e4f58acde"
down_revision = "7a5d3e479fbc"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table("monitoring_connector_configurations",
        sa.Column("domain", sa.String(16), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True)),
        sa.Column("check_revision", sa.Integer()),
        sa.Column("check_result", sa.JSON()))
    op.bulk_insert(table, [{"domain": domain, "revision": 0, "values": {}, "updated_at": datetime.now(UTC)}
        for domain in ("pollen", "river", "air", "warnings", "commute", "traffic", "tenders", "ip", "auctions")])


def downgrade():
    op.drop_table("monitoring_connector_configurations")
