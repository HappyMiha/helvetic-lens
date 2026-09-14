"""Private IP candidates, retained calibration provenance and internal review."""

import sqlalchemy as sa

from alembic import op

revision = "b4f17235d3b6"
down_revision = "a3e06124c2a5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('trademark_calibrations',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('configuration', sa.JSON(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('trademark_calibration_selections',
    sa.Column('language', sa.String(length=2), nullable=False),
    sa.Column('calibration_id', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['calibration_id'], ['trademark_calibrations.id'], ),
    sa.PrimaryKeyConstraint('language')
    )
    op.create_table('trademark_candidates',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('monitor_id', sa.String(length=36), nullable=False),
    sa.Column('source_key', sa.String(length=80), nullable=False),
    sa.Column('record_key', sa.String(length=64), nullable=False),
    sa.Column('brand_key', sa.String(length=64), nullable=False),
    sa.Column('permission_id', sa.String(length=36), nullable=False),
    sa.Column('source_generation', sa.Integer(), nullable=False),
    sa.Column('source_revision_id', sa.String(length=36), nullable=False),
    sa.Column('profile_revision', sa.Integer(), nullable=False),
    sa.Column('evaluation_hash', sa.String(length=64), nullable=False),
    sa.Column('calibration_ids', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('reviewed_sequence', sa.Integer(), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('version >= 1 AND sequence >= 1 AND reviewed_sequence >= 0 AND reviewed_sequence <= sequence', name='ck_trademark_candidate_version'),
    sa.ForeignKeyConstraint(['monitor_id', 'organization_id'], ['trademark_monitors.id', 'trademark_monitors.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['permission_id'], ['trademark_source_permissions.id'], ),
    sa.ForeignKeyConstraint(['source_revision_id'], ['trademark_register_revisions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organization_id', name='uq_trademark_candidate_scope'),
    sa.UniqueConstraint('monitor_id', 'source_key', 'record_key', 'brand_key', name='uq_trademark_candidate_identity')
    )
    op.create_index(op.f('ix_trademark_candidates_monitor_id'), 'trademark_candidates', ['monitor_id'], unique=False)
    op.create_index(op.f('ix_trademark_candidates_organization_id'), 'trademark_candidates', ['organization_id'], unique=False)
    op.create_table('trademark_projection_cursors',
    sa.Column('monitor_id', sa.String(length=36), nullable=False),
    sa.Column('source_key', sa.String(length=80), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('permission_id', sa.String(length=36), nullable=False),
    sa.Column('generation', sa.Integer(), nullable=False),
    sa.Column('after_key', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['monitor_id', 'organization_id'], ['trademark_monitors.id', 'trademark_monitors.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['permission_id'], ['trademark_source_permissions.id'], ),
    sa.PrimaryKeyConstraint('monitor_id', 'source_key')
    )
    op.create_index(op.f('ix_trademark_projection_cursors_organization_id'), 'trademark_projection_cursors', ['organization_id'], unique=False)
    op.create_table('trademark_runtimes',
    sa.Column('monitor_id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('health', sa.String(length=24), nullable=False),
    sa.Column('last_check_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('unavailable_count', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['monitor_id', 'organization_id'], ['trademark_monitors.id', 'trademark_monitors.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('monitor_id')
    )
    op.create_index(op.f('ix_trademark_runtimes_next_check_at'), 'trademark_runtimes', ['next_check_at'], unique=False)
    op.create_index(op.f('ix_trademark_runtimes_organization_id'), 'trademark_runtimes', ['organization_id'], unique=False)
    op.create_table('trademark_candidate_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('candidate_id', sa.String(length=36), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('source_revision_id', sa.String(length=36), nullable=False),
    sa.Column('previous_revision_id', sa.String(length=36), nullable=True),
    sa.Column('profile_revision', sa.Integer(), nullable=False),
    sa.Column('calibration_ids', sa.JSON(), nullable=False),
    sa.Column('evaluation_hash', sa.String(length=64), nullable=False),
    sa.Column('change_codes', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id', 'organization_id'], ['trademark_candidates.id', 'trademark_candidates.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['previous_revision_id'], ['trademark_register_revisions.id'], ),
    sa.ForeignKeyConstraint(['source_revision_id'], ['trademark_register_revisions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('candidate_id', 'sequence', name='uq_trademark_candidate_event')
    )
    op.create_index(op.f('ix_trademark_candidate_events_candidate_id'), 'trademark_candidate_events', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_trademark_candidate_events_organization_id'), 'trademark_candidate_events', ['organization_id'], unique=False)
    op.create_table('trademark_reviews',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('candidate_id', sa.String(length=36), nullable=False),
    sa.Column('candidate_version', sa.Integer(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('source_revision_id', sa.String(length=36), nullable=False),
    sa.Column('profile_revision', sa.Integer(), nullable=False),
    sa.Column('evaluation_hash', sa.String(length=64), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('actor_user_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("decision IN ('reviewed','relevant','not_relevant','monitor','counsel')", name='ck_trademark_review_decision'),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['candidate_id', 'organization_id'], ['trademark_candidates.id', 'trademark_candidates.organization_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_revision_id'], ['trademark_register_revisions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('candidate_id', 'candidate_version', name='uq_trademark_review_version')
    )
    op.create_index(op.f('ix_trademark_reviews_candidate_id'), 'trademark_reviews', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_trademark_reviews_organization_id'), 'trademark_reviews', ['organization_id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    op.drop_index(op.f('ix_trademark_reviews_organization_id'), table_name='trademark_reviews')
    op.drop_index(op.f('ix_trademark_reviews_candidate_id'), table_name='trademark_reviews')
    op.drop_table('trademark_reviews')
    op.drop_index(op.f('ix_trademark_candidate_events_organization_id'), table_name='trademark_candidate_events')
    op.drop_index(op.f('ix_trademark_candidate_events_candidate_id'), table_name='trademark_candidate_events')
    op.drop_table('trademark_candidate_events')
    op.drop_index(op.f('ix_trademark_runtimes_organization_id'), table_name='trademark_runtimes')
    op.drop_index(op.f('ix_trademark_runtimes_next_check_at'), table_name='trademark_runtimes')
    op.drop_table('trademark_runtimes')
    op.drop_index(op.f('ix_trademark_projection_cursors_organization_id'), table_name='trademark_projection_cursors')
    op.drop_table('trademark_projection_cursors')
    op.drop_index(op.f('ix_trademark_candidates_organization_id'), table_name='trademark_candidates')
    op.drop_index(op.f('ix_trademark_candidates_monitor_id'), table_name='trademark_candidates')
    op.drop_table('trademark_candidates')
    op.drop_table('trademark_calibration_selections')
    op.drop_table('trademark_calibrations')
    # ### end Alembic commands ###
