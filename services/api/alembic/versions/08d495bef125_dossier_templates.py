"""Retain optional versioned template guidance on the existing dossier."""
import sqlalchemy as sa

from alembic import op

revision = '08d495bef125'
down_revision = '07d495bef125'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('product_dossiers', sa.Column('template_json', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    rows = op.get_bind().execute(sa.text('SELECT template_json FROM product_dossiers')).scalars()
    if any(value not in (None, '{}', {}) for value in rows):
        raise RuntimeError('Retain saved templates: roll back application code without removing the additive column.')
    with op.batch_alter_table('product_dossiers') as batch:
        batch.drop_column('template_json')
