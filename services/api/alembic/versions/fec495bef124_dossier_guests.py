"""Dossier-only guest grants without native organization membership."""
import sqlalchemy as sa

from alembic import op

revision = "fec495bef124"
down_revision = "fdc495bef124"
branch_labels = None
depends_on = None

TABLES = [("product_dossier_members", "user_id", "member"),
          ("product_dossier_invitations", "recipient_user_id", "invitation")]
NAMES = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def upgrade():
    for table, user, label in TABLES:
        old = next(fk for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)
                   if fk["referred_table"] == "organization_memberships")
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("membership_organization_id", sa.String(36), nullable=True))
            batch.add_column(sa.Column("is_guest", sa.Boolean(), nullable=False, server_default="0"))
        op.execute(sa.text(f"UPDATE {table} SET membership_organization_id = organization_id"))
        with op.batch_alter_table(table, naming_convention=NAMES) as batch:
            batch.drop_constraint(old["name"] or f"fk_{table}_organization_id_organization_memberships", type_="foreignkey")
            batch.create_foreign_key(f"fk_dossier_{label}_native_membership", "organization_memberships",
                ["membership_organization_id", user], ["organization_id", "user_id"], ondelete="CASCADE")
            owner = " AND role <> 'OWNER'" if label == "member" else ""
            batch.create_check_constraint(f"ck_dossier_{label}_membership_scope",
                f"(is_guest AND membership_organization_id IS NULL{owner}) OR "
                "(NOT is_guest AND membership_organization_id IS NOT NULL AND membership_organization_id = organization_id)")
    op.create_index("ix_product_dossier_members_user_id", "product_dossier_members", ["user_id"])
    with op.batch_alter_table("product_investigations") as batch:
        batch.add_column(sa.Column("session_organization_id", sa.String(36), nullable=True))


def downgrade():
    connection = op.get_bind()
    if any(connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table} WHERE is_guest")) for table, _, _ in TABLES):
        raise RuntimeError("Remove retained guest grants and invitations explicitly before downgrading their access schema.")
    with op.batch_alter_table("product_investigations") as batch:
        batch.drop_column("session_organization_id")
    op.drop_index("ix_product_dossier_members_user_id", table_name="product_dossier_members")
    for table, user, label in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"ck_dossier_{label}_membership_scope", type_="check")
            batch.drop_constraint(f"fk_dossier_{label}_native_membership", type_="foreignkey")
            batch.create_foreign_key(f"fk_{table}_organization_memberships", "organization_memberships",
                ["organization_id", user], ["organization_id", "user_id"], ondelete="CASCADE")
            batch.drop_column("is_guest")
            batch.drop_column("membership_organization_id")
