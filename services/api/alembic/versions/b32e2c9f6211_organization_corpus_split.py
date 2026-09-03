"""Split the shared public corpus from organization-owned monitoring data."""

import sqlalchemy as sa

from alembic import op

revision = "b32e2c9f6211"
down_revision = "a21f8c4d9b10"
branch_labels = None
depends_on = None

LEGACY_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


def _add_owned_column(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(
            sa.Column(
                "organization_id",
                sa.String(length=36),
                nullable=False,
                server_default=LEGACY_ORGANIZATION_ID,
            )
        )
        batch.create_foreign_key(
            f"fk_{table}_organization_id", "organizations", ["organization_id"], ["id"]
        )
        batch.create_index(f"ix_{table}_organization_id", ["organization_id"])


def _drop_owned_column(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.drop_index(f"ix_{table}_organization_id")
        batch.drop_constraint(f"fk_{table}_organization_id", type_="foreignkey")
        batch.drop_column("organization_id")


def upgrade():
    dialect = op.get_bind().dialect.name
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, created_at) "
            "VALUES (:id, 'Legacy workspace', 'legacy-workspace', CURRENT_TIMESTAMP)"
        ).bindparams(id=LEGACY_ORGANIZATION_ID)
    )

    for table in (
        "sources",
        "observations",
        "identity_decisions",
        "scans",
        "scan_items",
        "profiles",
        "apertus_configuration",
        "prompt_configuration",
        "integration_logs",
        "analyses",
        "ask_records",
        "job_steps",
        "outbox_messages",
    ):
        _add_owned_column(table)

    op.execute(
        sa.text("UPDATE jobs SET organization_id = :id WHERE organization_id = 'default'").bindparams(
            id=LEGACY_ORGANIZATION_ID
        )
    )
    with op.batch_alter_table("jobs") as batch:
        batch.create_foreign_key(
            "fk_jobs_organization_id", "organizations", ["organization_id"], ["id"]
        )

    with op.batch_alter_table("profiles") as batch:
        batch.alter_column("id", type_=sa.String(length=80), existing_type=sa.String(length=30))
        batch.create_unique_constraint("uq_profiles_organization_id", ["organization_id"])
    with op.batch_alter_table("apertus_configuration") as batch:
        batch.alter_column("id", type_=sa.String(length=80), existing_type=sa.String(length=30))
        batch.create_unique_constraint("uq_apertus_configuration_organization_id", ["organization_id"])
    with op.batch_alter_table("prompt_configuration") as batch:
        batch.alter_column("id", type_=sa.String(length=80), existing_type=sa.String(length=30))
        batch.create_unique_constraint("uq_prompt_configuration_organization_id", ["organization_id"])

    with op.batch_alter_table("laws", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}) as batch:
        batch.add_column(sa.Column("owner_organization_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("canonical_identity", sa.String(length=500), nullable=True))
        batch.create_foreign_key(
            "fk_laws_owner_organization_id", "organizations", ["owner_organization_id"], ["id"]
        )
        batch.create_index("ix_laws_owner_organization_id", ["owner_organization_id"])
        batch.drop_constraint("laws_url_key" if dialect == "postgresql" else "uq_laws_url", type_="unique")
    op.execute("UPDATE laws SET canonical_identity = LOWER(url)")
    op.execute(
        sa.text(
            "UPDATE laws SET owner_organization_id = :id "
            "WHERE LOWER(url) NOT LIKE 'https://fedlex.admin.ch/%' "
            "AND LOWER(url) NOT LIKE 'https://fedlex.data.admin.ch/%'"
        ).bindparams(id=LEGACY_ORGANIZATION_ID)
    )
    with op.batch_alter_table("laws") as batch:
        batch.alter_column("canonical_identity", nullable=False)
    op.create_index(
        "uq_public_law_canonical_identity",
        "laws",
        ["canonical_identity"],
        unique=True,
        postgresql_where=sa.text("owner_organization_id IS NULL"),
        sqlite_where=sa.text("owner_organization_id IS NULL"),
    )
    op.create_index(
        "uq_private_law_canonical_identity",
        "laws",
        ["owner_organization_id", "canonical_identity"],
        unique=True,
        postgresql_where=sa.text("owner_organization_id IS NOT NULL"),
        sqlite_where=sa.text("owner_organization_id IS NOT NULL"),
    )

    with op.batch_alter_table("versions") as batch:
        batch.add_column(sa.Column("owner_organization_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_versions_owner_organization_id", "organizations", ["owner_organization_id"], ["id"]
        )
        batch.create_index("ix_versions_owner_organization_id", ["owner_organization_id"])
        batch.drop_constraint("uq_law_content", type_="unique")
    op.execute(
        sa.text(
            "UPDATE versions SET owner_organization_id = :id "
            "WHERE origin <> 'live' OR law_id IN "
            "(SELECT id FROM laws WHERE owner_organization_id IS NOT NULL)"
        ).bindparams(id=LEGACY_ORGANIZATION_ID)
    )
    op.create_index(
        "uq_public_version_content",
        "versions",
        ["law_id", "content_hash", "extractor"],
        unique=True,
        postgresql_where=sa.text("owner_organization_id IS NULL"),
        sqlite_where=sa.text("owner_organization_id IS NULL"),
    )
    op.create_index(
        "uq_private_version_content",
        "versions",
        ["owner_organization_id", "law_id", "content_hash", "extractor"],
        unique=True,
        postgresql_where=sa.text("owner_organization_id IS NOT NULL"),
        sqlite_where=sa.text("owner_organization_id IS NOT NULL"),
    )

    with op.batch_alter_table("comparisons") as batch:
        batch.add_column(sa.Column("owner_organization_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_comparisons_owner_organization_id",
            "organizations",
            ["owner_organization_id"],
            ["id"],
        )
        batch.create_index("ix_comparisons_owner_organization_id", ["owner_organization_id"])
    op.execute(
        sa.text(
            "UPDATE comparisons SET owner_organization_id = :id WHERE "
            "old_version_id IN (SELECT id FROM versions WHERE owner_organization_id IS NOT NULL) "
            "OR new_version_id IN (SELECT id FROM versions WHERE owner_organization_id IS NOT NULL)"
        ).bindparams(id=LEGACY_ORGANIZATION_ID)
    )

    op.create_table(
        "document_watches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("law_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=300), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("selected_baseline_version_id", sa.String(length=36), nullable=True),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.String(length=40), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["law_id"], ["laws.id"]),
        sa.ForeignKeyConstraint(["selected_baseline_version_id"], ["versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "law_id", name="uq_document_watch_organization_law"),
    )
    op.create_index("ix_document_watches_organization_id", "document_watches", ["organization_id"])
    op.create_index("ix_document_watches_law_id", "document_watches", ["law_id"])
    # SQLite and PostgreSQL both accept this deterministic UUID-shaped legacy watch key.
    op.execute(
        sa.text(
            "INSERT INTO document_watches "
            "(id, organization_id, law_id, display_name, active, selected_baseline_version_id, "
            "last_checked, last_result, last_error, created_at) "
            "SELECT SUBSTR(id || '-00000000-0000-0000-000000000000', 1, 36), :org, id, name, active, NULL, "
            "last_checked, last_result, last_error, created_at FROM laws"
        ).bindparams(org=LEGACY_ORGANIZATION_ID)
    )


def downgrade():
    op.drop_index("ix_document_watches_law_id", table_name="document_watches")
    op.drop_index("ix_document_watches_organization_id", table_name="document_watches")
    op.drop_table("document_watches")
    op.drop_index("uq_private_law_canonical_identity", table_name="laws")
    op.drop_index("uq_public_law_canonical_identity", table_name="laws")
    with op.batch_alter_table("comparisons") as batch:
        batch.drop_index("ix_comparisons_owner_organization_id")
        batch.drop_constraint("fk_comparisons_owner_organization_id", type_="foreignkey")
        batch.drop_column("owner_organization_id")
    op.drop_index("uq_private_version_content", table_name="versions")
    op.drop_index("uq_public_version_content", table_name="versions")
    with op.batch_alter_table("versions") as batch:
        batch.create_unique_constraint("uq_law_content", ["law_id", "content_hash", "extractor"])
        batch.drop_index("ix_versions_owner_organization_id")
        batch.drop_constraint("fk_versions_owner_organization_id", type_="foreignkey")
        batch.drop_column("owner_organization_id")
    with op.batch_alter_table("laws") as batch:
        batch.create_unique_constraint("uq_laws_url", ["url"])
        batch.drop_index("ix_laws_owner_organization_id")
        batch.drop_constraint("fk_laws_owner_organization_id", type_="foreignkey")
        batch.drop_column("canonical_identity")
        batch.drop_column("owner_organization_id")
    for table in ("prompt_configuration", "apertus_configuration", "profiles"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"uq_{table}_organization_id", type_="unique")
            batch.alter_column("id", type_=sa.String(length=30), existing_type=sa.String(length=80))
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("fk_jobs_organization_id", type_="foreignkey")
    op.execute("UPDATE jobs SET organization_id = 'default'")
    for table in reversed(
        (
            "sources", "observations", "identity_decisions", "scans", "scan_items", "profiles",
            "apertus_configuration", "prompt_configuration", "integration_logs", "analyses",
            "ask_records", "job_steps", "outbox_messages",
        )
    ):
        _drop_owned_column(table)
    op.drop_table("organizations")
