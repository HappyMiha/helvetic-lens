"""Add shared relation candidates and organization delivery state."""

import sqlalchemy as sa

from alembic import op

revision = "e92f4b63c7d1"
down_revision = "d81e7a42bc10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "relation_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("regulatory_events.id"), nullable=False),
        sa.Column("source_work_id", sa.String(36), sa.ForeignKey("regulatory_works.id"), nullable=False),
        sa.Column("target_work_id", sa.String(36), sa.ForeignKey("regulatory_works.id"), nullable=False),
        sa.Column("relation_id", sa.String(36), sa.ForeignKey("regulatory_relations.id"), nullable=True),
        sa.Column("source_version_id", sa.String(36), sa.ForeignKey("regulatory_document_versions.id"), nullable=True),
        sa.Column("target_version_id", sa.String(36), sa.ForeignKey("regulatory_document_versions.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("score_components_json", sa.JSON(), nullable=False),
        sa.Column("why_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("rule_revision", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "target_work_id", name="uq_relation_candidate_event_target"),
        sa.CheckConstraint("status IN ('active', 'expired', 'promoted', 'rejected')", name="ck_relation_candidate_status"),
    )
    for column in ("event_id", "source_work_id", "target_work_id", "relation_id", "status", "expires_at"):
        op.create_index(f"ix_relation_candidates_{column}", "relation_candidates", [column])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_regulatory_works_title_fts ON regulatory_works "
            "USING gin (to_tsvector('simple', coalesce(title, '')))"
        )
    op.create_table(
        "organization_relation_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("relation_candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("watch_id", sa.String(36), sa.ForeignKey("document_watches.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "candidate_id", name="uq_org_relation_candidate"),
        sa.CheckConstraint("status IN ('pending', 'queued', 'analysed', 'dismissed', 'expired')", name="ck_org_relation_candidate_status"),
    )
    for column in ("organization_id", "candidate_id", "watch_id", "status"):
        op.create_index(
            f"ix_organization_relation_candidates_{column}",
            "organization_relation_candidates",
            [column],
        )


def downgrade():
    op.drop_table("organization_relation_candidates")
    op.drop_table("relation_candidates")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_regulatory_works_title_fts")
