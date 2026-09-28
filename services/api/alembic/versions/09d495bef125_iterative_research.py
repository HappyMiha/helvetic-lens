"""Add version-pinned iterative research state without rewriting saved evidence."""
import sqlalchemy as sa

from alembic import op

revision = '09d495bef125'
down_revision = '08d495bef125'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('product_investigations', sa.Column('research_state', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    rows = op.get_bind().execute(sa.text('SELECT research_state FROM product_investigations')).scalars()
    if any(value not in (None, '{}', {}) for value in rows):
        raise RuntimeError('Retain research checkpoints: roll back code without removing the additive column.')
    with op.batch_alter_table('product_investigations') as batch:
        batch.drop_column('research_state')
