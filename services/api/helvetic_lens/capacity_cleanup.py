from __future__ import annotations

import argparse
import os
import re

from sqlalchemy import delete, or_, select

from .config import Settings
from .db import Base, Database
from .models import Organization, OrganizationMembership, User, Version

DELETE_ACK = "delete-synthetic-capacity-data"


def cleanup_capacity(db: Database, settings: Settings, *, prefix: str) -> dict:
    if len(prefix) < 8 or not re.fullmatch(r"[a-z0-9][a-z0-9-]+", prefix):
        raise ValueError("Use the exact lowercase capacity prefix (at least eight characters).")
    with db.session(include_all_organizations=True) as session:
        organizations = list(
            session.scalars(select(Organization).where(Organization.slug.like(f"{prefix}-%")))
        )
        organization_ids = [item.id for item in organizations]
        if not organization_ids:
            return {"prefix": prefix, "organizations": 0, "users": 0, "rows": {}, "artifacts": 0}
        user_ids = list(
            session.scalars(
                select(User.id)
                .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
                .where(
                    OrganizationMembership.organization_id.in_(organization_ids),
                    User.email.like(f"{prefix}-%@capacity.invalid"),
                )
            )
        )
        artifact_keys = set(
            session.scalars(
                select(Version.artifact_key).where(
                    Version.owner_organization_id.in_(organization_ids)
                )
            )
        )
        row_counts = {}
        organization_columns = {
            "organization_id",
            "owner_organization_id",
            "requested_by_organization_id",
        }
        user_columns = {"user_id", "actor_user_id", "invited_by_user_id"}
        for table in reversed(Base.metadata.sorted_tables):
            conditions = [
                table.c[name].in_(organization_ids)
                for name in organization_columns
                if name in table.c
            ]
            conditions.extend(
                table.c[name].in_(user_ids) for name in user_columns if name in table.c
            )
            if table.name == "organizations":
                conditions.append(table.c.id.in_(organization_ids))
            if table.name == "users":
                conditions.append(table.c.id.in_(user_ids))
            if not conditions:
                continue
            result = session.execute(delete(table).where(or_(*conditions)))
            if result.rowcount:
                row_counts[table.name] = result.rowcount
        session.commit()

    with db.session(include_all_organizations=True) as session:
        retained_artifacts = set(
            session.scalars(select(Version.artifact_key).where(Version.artifact_key.in_(artifact_keys)))
        )
    removed_artifacts = 0
    for artifact_key in artifact_keys - retained_artifacts:
        path = settings.storage_path / "artifacts" / artifact_key
        if path.is_file():
            path.unlink()
            removed_artifacts += 1
    return {
        "prefix": prefix,
        "organizations": len(organization_ids),
        "users": len(user_ids),
        "rows": row_counts,
        "artifacts": removed_artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete one exact synthetic capacity prefix from an isolated deployment."
    )
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    if not arguments.execute or os.getenv("HELVETIC_LENS_CAPACITY_DELETE_ACK") != DELETE_ACK:
        parser.error(
            "Deletion requires --execute and "
            f"HELVETIC_LENS_CAPACITY_DELETE_ACK={DELETE_ACK}."
        )
    settings = Settings()
    result = cleanup_capacity(Database(settings), settings, prefix=arguments.prefix)
    print(
        f"Deleted {result['organizations']} synthetic organizations, {result['users']} users, "
        f"and {sum(result['rows'].values())} rows for prefix {arguments.prefix}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
