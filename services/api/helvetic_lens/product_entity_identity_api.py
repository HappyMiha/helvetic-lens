"""Review exact cited entity pairs using current dossier and publication authority."""
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field, StrictBool
from sqlalchemy import select

from .legal_profiles import Input
from .product_api import Product, fail
from .product_claim_evolution_api import editor
from .product_community import participant, publication
from .product_entity_identity import digest, entities, page, pair, review_payload, reviews
from .product_investigation_models import DossierEntity, EntityIdentityReview, Investigation
from .product_investigations import access, event, scope
from .product_models import ProductDossier
from .product_public_research import public_identity


class Review(Input):
    entity_id: UUID
    previous_entity_id: UUID
    request_key: UUID
    expected_revision: int = Field(ge=0, le=100)
    evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["same", "different", "unresolved"]
    reason: str = Field(min_length=5, max_length=500)
    confirm_public: StrictBool = False


def apply_review(session, parent, identity, data, published=None):
    # Serialize first revisions too; locking a nonexistent pair cannot do that.
    session.scalar(select(ProductDossier).where(ProductDossier.id == parent.id).with_for_update())
    if not editor(session, parent, identity):
        fail("Only a current dossier owner or editor can review entity identities.", 403)
    if published and not data.confirm_public:
        fail("Confirm that this review note may be published with the entity history.", 409)
    identifiers = sorted((str(data.entity_id), str(data.previous_entity_id)))
    values = list(session.scalars(entities(parent.id, published).where(DossierEntity.id.in_(identifiers))
        .order_by(DossierEntity.id).execution_options(populate_existing=True)))
    if len(values) != 2 or values[0].investigation_id == values[1].investigation_id:
        fail("This pair of entity mentions is not available.", 404)
    current = pair(session, *values)
    if not current["evidence_fingerprint"] or current["evidence_fingerprint"] != data.evidence_fingerprint:
        fail("The cited evidence changed. Reload the mentions before reviewing them.", 409)
    fingerprint = digest([identity.user_id, data.model_dump(mode="json")])
    replay = session.scalar(reviews(parent.id, published, latest=False).where(EntityIdentityReview.request_key == str(data.request_key)))
    if replay:
        if replay.request_fingerprint != fingerprint:
            fail("This request key belongs to a different review.", 409)
        latest = session.scalar(reviews(parent.id, published).where(EntityIdentityReview.entity_id == identifiers[0],
            EntityIdentityReview.previous_entity_id == identifiers[1]))
        return review_payload(session, latest, published)
    # Do not reveal an existing request in another audience.
    if session.scalar(select(EntityIdentityReview.id).where(EntityIdentityReview.dossier_id == parent.id,
            EntityIdentityReview.request_key == str(data.request_key))):
        fail("This request key cannot be reused. Reload before reviewing.", 409)
    previous = session.scalar(reviews(parent.id, published).where(EntityIdentityReview.entity_id == identifiers[0],
        EntityIdentityReview.previous_entity_id == identifiers[1]))
    revision = previous.revision if previous else 0
    if revision != data.expected_revision or revision >= 100:
        fail("This pair changed or reached its review limit. Reload its history before reviewing.", 409)
    if not previous and not current["exact_identifier_match"]:
        fail("A first review requires an exact cited identifier, issuer, jurisdiction and kind match.", 409)
    run = session.get(Investigation, values[0].investigation_id)
    value = EntityIdentityReview(**scope(run), entity_id=values[0].id, previous_entity_id=values[1].id,
        previous_investigation_id=values[1].investigation_id, source_id=current["first"]["source"]["id"],
        previous_source_id=current["second"]["source"]["id"], decision=data.decision, reason=data.reason,
        revision=revision + 1, evidence_fingerprint=current["evidence_fingerprint"],
        reviewed_by_user_id=identity.user_id, request_key=str(data.request_key), request_fingerprint=fingerprint)
    session.add(value)
    event(session, run, "entity_identity_reviewed", reason="A dossier editor reviewed two cited entity mentions; originals remain separate.")
    session.flush()
    result = review_payload(session, value, published)
    session.commit()
    return result


def routes(router, service, actor):
    private = "/dossiers/{dossier_id}/entity-identities"
    public = "/public-dossiers/{publication_id}/entity-identities"

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
