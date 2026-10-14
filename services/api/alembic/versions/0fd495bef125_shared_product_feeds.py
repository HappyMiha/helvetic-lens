"""Independent feeds, immutable material history and reusable dossier links."""
import sqlalchemy as sa

from alembic import op

revision = "0fd495bef125"
down_revision = "0ed495bef125"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_feeds',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('owner_user_id', sa.String(length=36), nullable=False),
    sa.Column('product', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('query', sa.String(length=300), nullable=False),
    sa.Column('sources_json', sa.JSON(), nullable=False),
    sa.Column('config_json', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', sa.String(length=500), nullable=True),
    sa.Column('job_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("product IN ('loyer','pharma')"),
    sa.CheckConstraint("status IN ('active','paused')"),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organization_id')
    )
    op.create_index(op.f('ix_product_feeds_next_check_at'), 'product_feeds', ['next_check_at'], unique=False)
    op.create_index(op.f('ix_product_feeds_organization_id'), 'product_feeds', ['organization_id'], unique=False)
    op.create_index(op.f('ix_product_feeds_owner_user_id'), 'product_feeds', ['owner_user_id'], unique=False)
    op.create_index(op.f('ix_product_feeds_status'), 'product_feeds', ['status'], unique=False)
    op.create_table('product_feed_updates',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('feed_id', sa.String(length=36), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('source_key', sa.String(length=2048), nullable=False),
    sa.Column('title', sa.String(length=700), nullable=False),
    sa.Column('url', sa.String(length=2048), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('source_text', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('snapshot_json', sa.JSON(), nullable=False),
    sa.Column('published_at', sa.String(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['feed_id', 'organization_id'], ['product_feeds.id', 'product_feeds.organization_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_id', 'sequence'),
    sa.UniqueConstraint('id', 'organization_id')
    )
    op.create_index(op.f('ix_product_feed_updates_feed_id'), 'product_feed_updates', ['feed_id'], unique=False)
    op.create_index(op.f('ix_product_feed_updates_organization_id'), 'product_feed_updates', ['organization_id'], unique=False)
    op.create_index(op.f('ix_product_feed_updates_source_key'), 'product_feed_updates', ['source_key'], unique=False)
    op.create_table('product_feed_assessments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('feed_id', sa.String(length=36), nullable=False),
    sa.Column('update_id', sa.String(length=36), nullable=False),
    sa.Column('spec_binding', sa.String(length=64), nullable=False),
    sa.Column('plan_binding', sa.String(length=64), nullable=False),
    sa.Column('decision_key', sa.String(length=64), nullable=False),
    sa.Column('verdict', sa.String(length=16), nullable=False),
    sa.Column('decision_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("verdict IN ('relevant','uncertain','unrelated','unavailable')"),
    sa.ForeignKeyConstraint(['feed_id', 'organization_id'], ['product_feeds.id', 'product_feeds.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['update_id', 'organization_id'], ['product_feed_updates.id', 'product_feed_updates.organization_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('update_id', 'spec_binding', 'decision_key')
    )
    for column in ('organization_id', 'feed_id', 'update_id', 'spec_binding', 'verdict', 'created_at'):
        op.create_index(op.f(f'ix_product_feed_assessments_{column}'), 'product_feed_assessments', [column], unique=False)
    op.create_table('product_feed_links',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('feed_id', sa.String(length=36), nullable=False),
    sa.Column('dossier_id', sa.String(length=36), nullable=False),
    sa.Column('public_question', sa.String(length=300), nullable=False),
    sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('cursor_sequence', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('active','detached')"),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['dossier_id', 'organization_id'], ['product_dossiers.id', 'product_dossiers.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['feed_id', 'organization_id'], ['product_feeds.id', 'product_feeds.organization_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_id', 'dossier_id'),
    sa.UniqueConstraint('id', 'organization_id')
    )
    op.create_index(op.f('ix_product_feed_links_dossier_id'), 'product_feed_links', ['dossier_id'], unique=False)
    op.create_index(op.f('ix_product_feed_links_feed_id'), 'product_feed_links', ['feed_id'], unique=False)
    op.create_index(op.f('ix_product_feed_links_organization_id'), 'product_feed_links', ['organization_id'], unique=False)
    op.create_table('product_feed_imports',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('link_id', sa.String(length=36), nullable=False),
    sa.Column('update_id', sa.String(length=36), nullable=False),
    sa.Column('investigation_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('pending','seeded')"),
    sa.ForeignKeyConstraint(['investigation_id'], ['product_investigations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['link_id', 'organization_id'], ['product_feed_links.id', 'product_feed_links.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['update_id', 'organization_id'], ['product_feed_updates.id', 'product_feed_updates.organization_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('link_id', 'update_id')
    )
    op.create_index(op.f('ix_product_feed_imports_investigation_id'), 'product_feed_imports', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_product_feed_imports_link_id'), 'product_feed_imports', ['link_id'], unique=False)
    op.create_index(op.f('ix_product_feed_imports_organization_id'), 'product_feed_imports', ['organization_id'], unique=False)
    op.create_index(op.f('ix_product_feed_imports_update_id'), 'product_feed_imports', ['update_id'], unique=False)
    op.create_table('product_feed_receipts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('owner_user_id', sa.String(length=36), nullable=False),
    sa.Column('request_key', sa.String(length=36), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('result_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_user_id', 'request_key')
    )
    op.create_index(op.f('ix_product_feed_receipts_organization_id'), 'product_feed_receipts', ['organization_id'], unique=False)
    op.create_index(op.f('ix_product_feed_receipts_owner_user_id'), 'product_feed_receipts', ['owner_user_id'], unique=False)
    op.create_table('product_feed_checks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('feed_id', sa.String(length=36), nullable=False),
    sa.Column('job_id', sa.String(length=36), nullable=True),
    sa.Column('feed_revision', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('receipts_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('queued','running','completed','partial','failed','cancelled')"),
    sa.ForeignKeyConstraint(['feed_id', 'organization_id'], ['product_feeds.id', 'product_feeds.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id')
    )
    op.create_index(op.f('ix_product_feed_checks_feed_id'), 'product_feed_checks', ['feed_id'], unique=False)
    op.create_index(op.f('ix_product_feed_checks_organization_id'), 'product_feed_checks', ['organization_id'], unique=False)
    op.create_table('product_feed_follows',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('feed_id', sa.String(length=36), nullable=False),
    sa.Column('owner_user_id', sa.String(length=36), nullable=False),
    sa.Column('following', sa.Boolean(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('seen_sequence', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('seen_sequence >= 0 AND revision >= 1'),
    sa.ForeignKeyConstraint(['feed_id', 'organization_id'], ['product_feeds.id', 'product_feeds.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feed_id', 'owner_user_id')
    )
    op.create_index(op.f('ix_product_feed_follows_feed_id'), 'product_feed_follows', ['feed_id'], unique=False)
    op.create_index(op.f('ix_product_feed_follows_organization_id'), 'product_feed_follows', ['organization_id'], unique=False)
    op.create_index(op.f('ix_product_feed_follows_owner_user_id'), 'product_feed_follows', ['owner_user_id'], unique=False)

def downgrade():
    names = ['product_feed_follows', 'product_feed_checks', 'product_feed_receipts', 'product_feed_imports', 'product_feed_links', 'product_feed_assessments', 'product_feed_updates', 'product_feeds']
    for name in names:
        if op.get_bind().scalar(sa.select(sa.func.count()).select_from(sa.table(name))):
            raise RuntimeError("Retained feed materials, links and notification preferences cannot be discarded.")
    for name in names:
        op.drop_table(name)
