"""Current-audience evidence changes and explicit, revisioned editor review."""
import hashlib
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, StrictBool

from .db import utcnow
from .legal_profile_models import LegalMonitoringProfile
from .legal_profiles import Input
from .product_access import RANK, role
from .product_api import Product, fail, iso
from .product_claim_evolution import page, payload, query
from .product_community import participant, publication
from .product_investigation_models import ClaimChange, Investigation
from .product_investigations import access, event
from .product_models import ProductDossier
from .product_provenance import canonical
from .product_public_research import public_identity


class Review(Input):
    request_key: UUID
    expected_revision: int = Field(ge=1)
    status: Literal["active", "dismissed"]
    reason: str = Field(min_length=5, max_length=500)
    confirm_public: StrictBool = False


def editor(session, parent, identity):
    profile = session.get(LegalMonitoringProfile, parent.profile_id)
    return RANK.get(role(session, parent, profile, identity.user_id), -1) >= 2


def apply_review(session, parent, identifier, identity, data, published=None):
    if not editor(session, parent, identity):
        fail("Only a current dossier owner or editor can review evidence relationships.", 403)
    if published and not data.confirm_public:
        fail("Confirm that this review note may be published with the evidence history.", 409)
    value = session.scalar(query(parent.id, published).where(ClaimChange.id == str(identifier))
        .with_for_update(of=ClaimChange).execution_options(populate_existing=True))
    if not value:
        fail("This evidence relationship is not available.", 404)
    fingerprint = hashlib.sha256(canonical([identity.user_id, data.model_dump(mode="json")]).encode()).hexdigest()
    if value.last_request_key == str(data.request_key):
        if value.last_request_fingerprint != fingerprint:
            fail("This request key belongs to a different review.", 409)
        return payload(session, value)
    if value.revision != data.expected_revision or value.status == data.status:
        fail("This relationship changed. Refresh before applying the review.", 409)
    if len(value.history) >= 100:
        fail("This comparison has reached its review-history limit. Add a new correction with evidence.", 409)
    previous = value.status
    value.status, value.revision, value.updated_at = data.status, value.revision + 1, utcnow()
    value.reviewed_by_user_id = identity.user_id
    value.last_request_key, value.last_request_fingerprint = str(data.request_key), fingerprint
    value.history = [*value.history, {"revision": value.revision, "from": previous, "to": value.status,
        "reason": data.reason, "at": iso(value.updated_at)}]
    event(session, session.get(Investigation, value.investigation_id), "evidence_reviewed",
        reason="A dossier editor reviewed a source comparison. Current evidence history retains the decision.")
    session.commit()
    return payload(session, value)


def routes(router, service, actor):
    private = "/dossiers/{dossier_id}/evidence-changes"
    public = "/public-dossiers/{publication_id}/evidence-changes"

    @router.get(private)
    def read_private(product: Product, dossier_id: str, request: Request,
                     offset: int = Query(default=0, ge=0, le=100000), status: Literal["active", "dismissed", "all"] = "active"):
        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            return {**page(session, parent.id, offset=offset, status=status), "can_review": editor(session, parent, identity)}

    @router.post(private + "/{identifier}/review")
    def review_private(product: Product, dossier_id: str, identifier: UUID, data: Review, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            parent = access(session, identity, product, dossier_id, write=True)
            return apply_review(session, parent, identifier, identity, data)

    @router.get(public)
    def read_public(product: Product, publication_id: UUID,
                    offset: int = Query(default=0, ge=0, le=100000), status: Literal["active", "dismissed", "all"] = "active"):
        with service.db.session(include_all_organizations=True) as session:
            published = publication(session, product, publication_id)
            return page(session, published.dossier_id, published, offset=offset, status=status)

    @router.get(public + "/workspace")
    def public_controls(product: Product, publication_id: UUID, request: Request):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            published, _ = participant(session, identity, product, publication_id)
            public_identity(session, identity)
            return {"can_review": editor(session, session.get(ProductDossier, published.dossier_id), identity)}

    @router.post(public + "/{identifier}/review")
    def review_public(product: Product, publication_id: UUID, identifier: UUID, data: Review, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            published, _ = participant(session, identity, product, publication_id, write=True)
            public_identity(session, identity, lock=True)
            return apply_review(session, session.get(ProductDossier, published.dossier_id), identifier, identity, data, published)
