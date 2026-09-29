"""Review retained findings without rewriting machine evidence assessments."""
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, StrictBool
from sqlalchemy import select

from .domain_packs import for_product
from .legal_profiles import Input
from .product_api import Product, fail
from .product_claim_evolution_api import editor
from .product_claim_interpretation import Interpretation, resolve
from .product_claim_review import claims, context, page, payload
from .product_community import participant, publication
from .product_entity_identity import digest
from .product_investigation_models import ClaimReview, DossierClaim, Investigation
from .product_investigations import access, event, scope
from .product_models import ProductDossier
from .product_public_research import public_identity


class Review(Input):
    claim_id: UUID
    request_key: UUID
    expected_revision: int = Field(ge=0, le=100)
    evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["accepted", "dismissed", "needs_more_evidence"]
    reason: str = Field(min_length=5, max_length=500)
    confirm_public: StrictBool = False
    interpretation: Interpretation | None = None


def apply_review(session, parent, identity, data, published=None):
    # Serialize first reviews as well as revisions. Native guards also recheck roles.
    session.scalar(select(ProductDossier).where(ProductDossier.id == parent.id).with_for_update())
    if not editor(session, parent, identity):
        fail("Only a current dossier owner or editor can review findings.", 403)
    if published and not data.confirm_public:
        fail("Confirm that this explanation may be published with the claim history.", 409)
    claim = session.scalar(claims(parent.id, published).where(DossierClaim.id == str(data.claim_id))
        .with_for_update(of=DossierClaim).execution_options(populate_existing=True))
    if not claim:
        fail("This finding is not available for review.", 404)
    current = context(session, claim, published)
    if not current["reviewable"] or current["evidence_fingerprint"] != data.evidence_fingerprint:
        fail("The evidence changed or cannot be fully reviewed. Reload the finding and its sources.", 409)
    request_data = data.model_dump(mode="json")
    if data.interpretation is None:
        request_data.pop("interpretation")  # Preserve historical retry fingerprints.
    fingerprint = digest([identity.user_id, request_data])
    previous = session.scalar(select(ClaimReview).where(ClaimReview.claim_id == claim.id)
        .order_by(ClaimReview.revision.desc()).limit(1))
    replay = session.scalar(select(ClaimReview).where(ClaimReview.dossier_id == parent.id,
        ClaimReview.request_key == str(data.request_key)))
    if replay:
        if replay.claim_id != claim.id or replay.request_fingerprint != fingerprint:
            fail("This request key belongs to a different review.", 409)
        return payload(session, claim, published, current=current)
    revision = previous.revision if previous else 0
    if revision != data.expected_revision or revision >= 100:
        fail("This finding changed or reached its review limit. Reload its history before reviewing.", 409)
    basis = dict(current["basis"])
    if data.interpretation is not None:
        basis["interpretation"] = resolve(for_product(parent.product), data.interpretation)
    elif previous and previous.basis.get("interpretation"):
        fail("Review the claim type explicitly before saving another decision.", 409)
    run = session.get(Investigation, claim.investigation_id)
    session.add(ClaimReview(**scope(run), claim_id=claim.id, decision=data.decision, reason=data.reason,
        revision=revision + 1, evidence_fingerprint=current["evidence_fingerprint"], basis=basis,
        reviewed_by_user_id=identity.user_id, request_key=str(data.request_key), request_fingerprint=fingerprint))
    event(session, run, "claim_reviewed", reason="A dossier editor reviewed a finding; source assessment and original evidence remain unchanged.")
    session.flush()
    result = payload(session, claim, published, current=current)
    session.commit()
    return result


def routes(router, service, actor):
    private = "/dossiers/{dossier_id}/claim-reviews"
    public = "/public-dossiers/{publication_id}/claim-reviews"

    @router.get(private)
    def read_private(product: Product, dossier_id: str, request: Request, offset: int = Query(default=0, ge=0, le=100000)):
        identity = actor(request)
        with service.db.session() as session:
            parent = access(session, identity, product, dossier_id)
            return {**page(session, parent.id, offset=offset), "can_review": editor(session, parent, identity)}

    @router.post(private + "/review")
    def review_private(product: Product, dossier_id: str, data: Review, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            return apply_review(session, access(session, identity, product, dossier_id, write=True), identity, data)

    @router.get(public)
    def read_public(product: Product, publication_id: UUID, offset: int = Query(default=0, ge=0, le=100000)):
        with service.db.session(include_all_organizations=True) as session:
            published = publication(session, product, publication_id)
            return page(session, published.dossier_id, published, offset=offset)

    @router.get(public + "/workspace")
    def public_controls(product: Product, publication_id: UUID, request: Request):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            published, _ = participant(session, identity, product, publication_id)
            public_identity(session, identity)
            return {"can_review": editor(session, session.get(ProductDossier, published.dossier_id), identity)}

    @router.post(public + "/review")
    def review_public(product: Product, publication_id: UUID, data: Review, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            published, _ = participant(session, identity, product, publication_id, write=True)
            public_identity(session, identity, lock=True)
            return apply_review(session, session.get(ProductDossier, published.dossier_id), identity, data, published)
