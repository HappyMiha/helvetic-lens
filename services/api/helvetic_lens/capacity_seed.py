from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from argon2 import PasswordHasher
from argon2.low_level import Type
from sqlalchemy import select

from .config import Settings
from .db import Database, utcnow
from .diffing import compare_passages
from .identity import assess_comparison_identity, build_artifact_identity
from .models import (
    Comparison,
    DocumentWatch,
    Law,
    Organization,
    OrganizationMembership,
    OrganizationQuota,
    Profile,
    User,
    Version,
)

CAPACITY_ACK = "dedicated-capacity-environment"
LOCALES = ("de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH")
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def _passages(version: str) -> list[dict]:
    retention = "30" if version == "old" else "60"
    notification = "72" if version == "old" else "48"
    passages = [
        {"id": "p0001", "text": "Capacity Gate Data Governance Act", "page": 1},
        {
            "id": "p0002",
            "text": f"Art. 1 Retention. Audit records shall be retained for {retention} days.",
            "page": 1,
        },
        {
            "id": "p0003",
            "text": (
                "Art. 2 Notification. Material incidents shall be reported within "
                f"{notification} hours."
            ),
            "page": 1,
        },
    ]
    if version == "new":
        passages.append(
            {
                "id": "p0004",
                "text": "Art. 3 Register. The organization shall maintain an incident register.",
                "page": 1,
            }
        )
    return passages


def _version(
    *, organization_id: str, law: Law, kind: str, settings: Settings
) -> Version:
    passages = _passages(kind)
    text = "\n\n".join(item["text"] for item in passages)
    content = (
        "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>"
        + "".join(f"<p>{item['text']}</p>" for item in passages)
        + "</body></html>"
    ).encode()
    digest = hashlib.sha256(content).hexdigest()
    filename = f"capacity-{kind}.html"
    artifact_key = f"{digest}.html"
    source_url = law.url
    identity = build_artifact_identity(
        title=law.name,
        source_url=source_url,
        passages=passages,
        extractor="capacity-fixture-v1",
        content_type="text/html",
        filename=filename,
        declared_date="2026-01-01" if kind == "old" else "2026-08-01",
    )
    artifact_path = settings.storage_path / "artifacts" / artifact_key
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(content)
    return Version(
        owner_organization_id=organization_id,
        law_id=law.id,
        title=law.name,
        content_hash=digest,
        extractor="capacity-fixture-v1",
        text=text,
        passages=passages,
        content_type="text/html",
        artifact_key=artifact_key,
        filename=filename,
        source_url=source_url,
        origin="capacity_gate",
        declared_date="2026-01-01" if kind == "old" else "2026-08-01",
        date_provenance="capacity_fixture",
        synthetic=True,
        identity_json=identity,
    )


def seed_capacity(
    db: Database,
    settings: Settings,
    *,
    password: str,
    organizations: int = 10,
    users_per_organization: int = 10,
    prefix: str = "hl-capacity",
    source_url_template: str = "https://{organization}.capacity.invalid/data-governance-act",
) -> dict:
    if len(password) < 12:
        raise ValueError("The synthetic account password must contain at least 12 characters.")
    if organizations < 2 or users_per_organization < 2:
        raise ValueError("The capacity scenario requires at least two organizations and two users each.")
    password_hash = _PASSWORD_HASHER.hash(password)
    manifest = {
        "schema_version": "1",
        "synthetic": True,
        "prefix": prefix,
        "organizations": [],
    }
    with db.session(include_all_organizations=True) as session:
        for organization_index in range(organizations):
            slug = f"{prefix}-{organization_index:02d}"
            organization = session.scalar(select(Organization).where(Organization.slug == slug))
            if organization is None:
                organization = Organization(
                    name=f"Helvetic Lens capacity organization {organization_index:02d}",
                    slug=slug,
                )
                session.add(organization)
                session.flush()
            if session.get(Profile, organization.id) is None:
                session.add(
                    Profile(
                        id=organization.id,
                        organization_id=organization.id,
                        name=f"Capacity organization {organization_index:02d}",
                        description="Synthetic organization for the reproducible capacity gate.",
                    )
                )
            if session.scalar(
                select(OrganizationQuota).where(
                    OrganizationQuota.organization_id == organization.id
                )
            ) is None:
                session.add(OrganizationQuota(organization_id=organization.id, values={}))

            accounts = []
            for user_index in range(users_per_organization):
                email = f"{prefix}-o{organization_index:02d}-u{user_index:02d}@capacity.invalid"
                user = session.scalar(select(User).where(User.email == email))
                if user is None:
                    user = User(
                        email=email,
                        password_hash=password_hash,
                        name=f"Capacity user {organization_index:02d}-{user_index:02d}",
                        locale=LOCALES[(organization_index + user_index) % len(LOCALES)],
                        active=True,
                        platform_admin=organization_index == 0 and user_index == 0,
                        email_verified_at=utcnow(),
                    )
                    session.add(user)
                    session.flush()
                role = "organization_admin" if user_index < 2 else "viewer"
                membership = session.scalar(
                    select(OrganizationMembership).where(
                        OrganizationMembership.organization_id == organization.id,
                        OrganizationMembership.user_id == user.id,
                    )
                )
                if membership is None:
                    session.add(
                        OrganizationMembership(
                            organization_id=organization.id,
                            user_id=user.id,
                            role=role,
                        )
                    )
                accounts.append(
                    {
                        "email": email,
                        "role": role,
                        "locale": user.locale,
                    }
                )

            canonical_identity = f"capacity:{slug}:data-governance-act"
            law = session.scalar(
                select(Law).where(
                    Law.owner_organization_id == organization.id,
                    Law.canonical_identity == canonical_identity,
                )
            )
            if law is None:
                law = Law(
                    owner_organization_id=organization.id,
                    canonical_identity=canonical_identity,
                    name="Capacity Gate Data Governance Act",
                    url=source_url_template.format(organization=slug),
                    provider="capacity_fixture",
                    active=True,
                )
                session.add(law)
                session.flush()

            versions = []
            for kind in ("old", "new"):
                proposed = _version(
                    organization_id=organization.id,
                    law=law,
                    kind=kind,
                    settings=settings,
                )
                version = session.scalar(
                    select(Version).where(
                        Version.owner_organization_id == organization.id,
                        Version.law_id == law.id,
                        Version.content_hash == proposed.content_hash,
                        Version.extractor == proposed.extractor,
                    )
                )
                if version is None:
                    session.add(proposed)
                    session.flush()
                    version = proposed
                versions.append(version)
            old, new = versions
            law.current_version_id = new.id
            law.last_checked = utcnow()
            law.last_result = "changed"

            watch = session.scalar(
                select(DocumentWatch).where(
                    DocumentWatch.organization_id == organization.id,
                    DocumentWatch.law_id == law.id,
                )
            )
            if watch is None:
                watch = DocumentWatch(
                    organization_id=organization.id,
                    law_id=law.id,
                    display_name=law.name,
                    active=True,
                    selected_baseline_version_id=old.id,
                    last_checked=utcnow(),
                    last_result="changed",
                )
                session.add(watch)

            comparison = session.scalar(
                select(Comparison).where(
                    Comparison.old_version_id == old.id,
                    Comparison.new_version_id == new.id,
                    Comparison.mode == "saved_versions",
                )
            )
            if comparison is None:
                comparison = Comparison(
                    owner_organization_id=organization.id,
                    law_id=law.id,
                    old_version_id=old.id,
                    new_version_id=new.id,
                    mode="saved_versions",
                    diff=compare_passages(old.passages, new.passages),
                    identity_json={},
                )
                session.add(comparison)
                session.flush()
                comparison.identity_json = assess_comparison_identity(law, old, new)

            manifest["organizations"].append(
                {
                    "slug": slug,
                    "organization_id": organization.id,
                    "accounts": accounts,
                    "law_id": law.id,
                    "old_version_id": old.id,
                    "new_version_id": new.id,
                    "comparison_id": comparison.id,
                }
            )
        session.commit()
    manifest["account_count"] = organizations * users_per_organization
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed an isolated Helvetic Lens deployment for the capacity gate."
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--organizations", type=int, default=10)
    parser.add_argument("--users-per-organization", type=int, default=10)
    parser.add_argument("--prefix", default="hl-capacity")
    parser.add_argument(
        "--source-url-template",
        default="https://{organization}.capacity.invalid/data-governance-act",
        help="Optional controlled public fixture URL; {organization} is replaced with the test slug.",
    )
    arguments = parser.parse_args()
    if os.getenv("HELVETIC_LENS_CAPACITY_ACK") != CAPACITY_ACK:
        parser.error(
            f"Set HELVETIC_LENS_CAPACITY_ACK={CAPACITY_ACK} only on a dedicated test deployment."
        )
    password = os.getenv("CAPACITY_GATE_PASSWORD", "")
    if not password:
        parser.error("Set CAPACITY_GATE_PASSWORD; it is never written to the manifest.")
    settings = Settings()
    db = Database(settings)
    db.migrate()
    manifest = seed_capacity(
        db,
        settings,
        password=password,
        organizations=arguments.organizations,
        users_per_organization=arguments.users_per_organization,
        prefix=arguments.prefix,
        source_url_template=arguments.source_url_template,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"Seeded {manifest['account_count']} synthetic accounts across "
        f"{len(manifest['organizations'])} organizations."
    )
    print(f"Manifest: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
