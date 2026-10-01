"""Exact reviewed public projection becomes a new private, inactive native draft."""
import hashlib
import hmac
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import Field
from sqlalchemy import select

from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .legal_profiles import Input, ProfileConfig
from .product_api import Product, dossier, fail, iso
from .product_community import participant
from .product_identity import public_product_slug
from .product_models import DossierEntry, ProductDossier, PublicDossierCopy, PublicReuseReceipt
from .product_provenance import canonical, principal, signature
from .product_publications import LIFETIME, public_payload


class ReuseDraft(Input):
    expected_revision: int = Field(ge=1, strict=True)
    name: str = Field(min_length=3, max_length=160)
    goal: str = Field(min_length=10, max_length=3000)


class ReuseInput(ReuseDraft):
    request_key: UUID
    confirm_private_copy: bool = Field(strict=True)
    preview_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview_expires_at: datetime


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def origin_payload(row):
    return {"source_url": row.source_url, "snapshot": row.snapshot_json,
        "snapshot_sha256": row.snapshot_sha256, "copied_at": iso(row.created_at)}


def preview_value(product, identifier, data, snapshot, expires):
    return {"purpose": "private-public-dossier-copy-v1", "product": product, "publication_id": str(identifier),
        "draft": ReuseDraft.model_validate(data.model_dump(include=set(ReuseDraft.model_fields))).model_dump(),
        "snapshot_sha256": digest(snapshot), "expires_at": expires.isoformat()}


def source_url(product, identifier):
    return f"https://{public_product_slug(product)}.helveticlens.ch/public-dossiers/{identifier}"


def reuse_routes(router, service, actor):
    @router.post("/public-dossiers/{publication_id}/reuse/preview")
    def preview(product: Product, publication_id: UUID, data: ReuseDraft, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, _ = participant(session, identity, product, publication_id, write=True)
            user = principal(session, identity, utcnow(), write=True)
            if row.revision != data.expected_revision:
                fail("The published version changed. Reload it before preparing a copy.", 409)
            snapshot, expires = public_payload(row), utcnow() + LIFETIME
            return {"draft": data.model_dump(), "snapshot": snapshot, "source_url": source_url(product, row.id),
                "snapshot_sha256": digest(snapshot), "preview_expires_at": expires.isoformat(),
                "preview_token": signature(user, identity, preview_value(product, publication_id, data, snapshot, expires))}

    @router.post("/public-dossiers/{publication_id}/reuse", status_code=201)
    def create(product: Product, publication_id: UUID, data: ReuseInput, request: Request):
        identity = actor(request)
        fingerprint = digest({"product": product, "publication_id": str(publication_id),
            "input": data.model_dump(mode="json", exclude={"request_key", "preview_token", "preview_expires_at"})})
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            query = select(PublicReuseReceipt).where(PublicReuseReceipt.organization_id == identity.organization_id,
                PublicReuseReceipt.request_key == str(data.request_key))
            previous = session.scalar(query)
            if not previous:
                # Lock both organizations in canonical order before native admin
                # revalidation. A source withdrawal cannot race the snapshot.
                row, _ = participant(session, identity, product, publication_id, write=True)
            user = principal(session, identity, utcnow(), write=True)
            previous = session.scalar(query.execution_options(populate_existing=True))
            if previous:
                if previous.actor_user_id != identity.user_id or previous.fingerprint != fingerprint:
                    fail("This request belongs to a different private copy.", 409)
                # This deliberately uses the destination scope, never the source's
                # private parent. A deleted draft must not be recreated by retry.
                parent = session.scalar(select(ProductDossier).where(ProductDossier.id == previous.dossier_id,
                    ProductDossier.organization_id == identity.organization_id, ProductDossier.product == product))
                if not parent:
                    fail("This private copy is no longer available.", 404)
                dossier(session, product, parent.id, identity.user_id)
                return {"dossier_id": parent.id, "origin": origin_payload(session.get(PublicDossierCopy, parent.id))}
            expires = data.preview_expires_at
            now = utcnow()
            if (not data.confirm_private_copy or expires.tzinfo is None or not now < expires <= now + LIFETIME
                    or row.revision != data.expected_revision):
                fail("Review the latest public version and confirm a fresh private-copy preview.", 409)
            snapshot = public_payload(row)
            if not hmac.compare_digest(signature(user, identity,
                    preview_value(product, publication_id, data, snapshot, expires)), data.preview_token):
                fail("The copy differs from its reviewed preview. Prepare it again.", 409)
            config = ProfileConfig(name=data.name, goal=data.goal, delivery="off", delivery_consent=False)
            profile = LegalMonitoringProfile(organization_id=identity.organization_id, created_by_user_id=identity.user_id,
                creation_key=str(uuid4()), config_json=config.model_dump(mode="json"), status="draft", step=0)
            session.add(profile)
            session.flush()
            parent = ProductDossier(organization_id=identity.organization_id, product=product,
                profile_id=profile.id, creation_key=str(uuid4()))
            session.add(parent)
            session.flush()
            from .product_research_admission import admit_dossier

            admit_dossier(session, identity.user_id, parent.id)
            receipt = PublicDossierCopy(organization_id=identity.organization_id, dossier_id=parent.id,
                source_url=source_url(product, row.id), snapshot_json=snapshot, snapshot_sha256=digest(snapshot))
            session.add(receipt)
            session.add(PublicReuseReceipt(organization_id=identity.organization_id, actor_user_id=identity.user_id,
                dossier_id=parent.id, request_key=str(data.request_key), fingerprint=fingerprint))
            for source in snapshot["sources"]:
                session.add(DossierEntry(organization_id=identity.organization_id, dossier_id=parent.id,
                    request_key=str(uuid4()), kind="reference", title=source["title"], url=source["url"],
                    body=f"Source link from {snapshot['author_label']}'s public dossier, revision {row.revision}.",
                    data_json={"public_origin_url": receipt.source_url, "public_revision": row.revision},
                    actor_user_id=identity.user_id))
            session.commit()
            return {"dossier_id": parent.id, "origin": origin_payload(receipt)}
