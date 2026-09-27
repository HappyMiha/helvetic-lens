"""Durable dossier investigations, evidence, claims and observable activity."""
import sqlalchemy as sa

from alembic import op

revision = "fac495bef124"
down_revision = "f9c495bef124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_investigations',
        sa.Column('request_key', sa.String(length=36), nullable=False),
        sa.Column('question', sa.String(length=300), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('actor_user_id', sa.String(length=36), nullable=True),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('plan_version', sa.Integer(), nullable=False),
        sa.Column('event_sequence', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=True),
        sa.Column('stop_reason', sa.String(length=500), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('queued','running','paused','completed','failed','cancelled')"),
        sa.ForeignKeyConstraint(['session_id'], ['user_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['dossier_id', 'organization_id'], ['product_dossiers.id', 'product_dossiers.organization_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('dossier_id', 'request_key'),
        sa.UniqueConstraint('id', 'dossier_id', 'organization_id'))
    op.create_index('ix_product_investigations_dossier_id', 'product_investigations', ['dossier_id'])
    op.create_index('ix_product_investigations_organization_id', 'product_investigations', ['organization_id'])
    op.create_table('product_investigation_plans',
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=700), nullable=False),
        sa.Column('document', sa.JSON(), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('investigation_id', 'version'))
    op.create_index('ix_product_investigation_plans_dossier_id', 'product_investigation_plans', ['dossier_id'])
    op.create_index('ix_product_investigation_plans_investigation_id', 'product_investigation_plans', ['investigation_id'])
    op.create_index('ix_product_investigation_plans_organization_id', 'product_investigation_plans', ['organization_id'])
    op.create_table('product_investigation_branches',
        sa.Column('query', sa.String(length=300), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('phase', sa.String(length=24), nullable=False),
        sa.Column('checkpoint', sa.JSON(), nullable=False),
        sa.Column('reason', sa.String(length=700), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('investigation_id', 'query'))
    op.create_index('ix_product_investigation_branches_dossier_id', 'product_investigation_branches', ['dossier_id'])
    op.create_index('ix_product_investigation_branches_investigation_id', 'product_investigation_branches', ['investigation_id'])
    op.create_index('ix_product_investigation_branches_organization_id', 'product_investigation_branches', ['organization_id'])
    op.create_table('product_investigation_sources',
        sa.Column('source_key', sa.String(length=64), nullable=False),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('title', sa.String(length=700), nullable=False),
        sa.Column('url', sa.String(length=2000), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('id', 'investigation_id', 'dossier_id', 'organization_id'),
        sa.UniqueConstraint('investigation_id', 'source_key'))
    op.create_index('ix_product_investigation_sources_dossier_id', 'product_investigation_sources', ['dossier_id'])
    op.create_index('ix_product_investigation_sources_investigation_id', 'product_investigation_sources', ['investigation_id'])
    op.create_index('ix_product_investigation_sources_organization_id', 'product_investigation_sources', ['organization_id'])
    op.create_table('product_dossier_claims',
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('history', sa.JSON(), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('UNVERIFIED','SUPPORTED','CONTESTED','HYPOTHESIS','DISPROVED','SUPERSEDED')"),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('id', 'investigation_id', 'dossier_id', 'organization_id'))
    op.create_index('ix_product_dossier_claims_dossier_id', 'product_dossier_claims', ['dossier_id'])
    op.create_index('ix_product_dossier_claims_investigation_id', 'product_dossier_claims', ['investigation_id'])
    op.create_index('ix_product_dossier_claims_organization_id', 'product_dossier_claims', ['organization_id'])
    op.create_table('product_claim_evidence',
        sa.Column('claim_id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('relation', sa.String(length=16), nullable=False),
        sa.Column('quote', sa.Text(), nullable=False),
        sa.Column('locator', sa.String(length=100), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("relation IN ('SUPPORTS','CONTRADICTS','CONTEXT')"),
        sa.ForeignKeyConstraint(['claim_id', 'investigation_id', 'dossier_id', 'organization_id'], ['product_dossier_claims.id', 'product_dossier_claims.investigation_id', 'product_dossier_claims.dossier_id', 'product_dossier_claims.organization_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id', 'investigation_id', 'dossier_id', 'organization_id'], ['product_investigation_sources.id', 'product_investigation_sources.investigation_id', 'product_investigation_sources.dossier_id', 'product_investigation_sources.organization_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'))
    op.create_index('ix_product_claim_evidence_claim_id', 'product_claim_evidence', ['claim_id'])
    op.create_index('ix_product_claim_evidence_dossier_id', 'product_claim_evidence', ['dossier_id'])
    op.create_index('ix_product_claim_evidence_investigation_id', 'product_claim_evidence', ['investigation_id'])
    op.create_index('ix_product_claim_evidence_organization_id', 'product_claim_evidence', ['organization_id'])
    op.create_table('product_dossier_entities',
        sa.Column('name', sa.String(length=240), nullable=False),
        sa.Column('kind', sa.String(length=80), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('id', 'investigation_id', 'dossier_id', 'organization_id'))
    op.create_index('ix_product_dossier_entities_dossier_id', 'product_dossier_entities', ['dossier_id'])
    op.create_index('ix_product_dossier_entities_investigation_id', 'product_dossier_entities', ['investigation_id'])
    op.create_index('ix_product_dossier_entities_organization_id', 'product_dossier_entities', ['organization_id'])
    op.create_table('product_dossier_relationships',
        sa.Column('subject_id', sa.String(length=36), nullable=False),
        sa.Column('object_id', sa.String(length=36), nullable=False),
        sa.Column('predicate', sa.String(length=120), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['subject_id', 'investigation_id', 'dossier_id', 'organization_id'], ['product_dossier_entities.id', 'product_dossier_entities.investigation_id', 'product_dossier_entities.dossier_id', 'product_dossier_entities.organization_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['object_id', 'investigation_id', 'dossier_id', 'organization_id'], ['product_dossier_entities.id', 'product_dossier_entities.investigation_id', 'product_dossier_entities.dossier_id', 'product_dossier_entities.organization_id'], ondelete='CASCADE'))
    op.create_index('ix_product_dossier_relationships_dossier_id', 'product_dossier_relationships', ['dossier_id'])
    op.create_index('ix_product_dossier_relationships_investigation_id', 'product_dossier_relationships', ['investigation_id'])
    op.create_index('ix_product_dossier_relationships_organization_id', 'product_dossier_relationships', ['organization_id'])
    op.create_table('product_investigation_events',
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('dossier_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id', 'dossier_id', 'organization_id'], ['product_investigations.id', 'product_investigations.dossier_id', 'product_investigations.organization_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('investigation_id', 'sequence'))
    op.create_index('ix_product_investigation_events_dossier_id', 'product_investigation_events', ['dossier_id'])
    op.create_index('ix_product_investigation_events_investigation_id', 'product_investigation_events', ['investigation_id'])
    op.create_index('ix_product_investigation_events_organization_id', 'product_investigation_events', ['organization_id'])


def downgrade():
    op.drop_table('product_investigation_events')
    op.drop_table('product_dossier_relationships')
    op.drop_table('product_dossier_entities')
    op.drop_table('product_claim_evidence')
    op.drop_table('product_dossier_claims')
    op.drop_table('product_investigation_sources')
    op.drop_table('product_investigation_branches')
    op.drop_table('product_investigation_plans')
    op.drop_table('product_investigations')
