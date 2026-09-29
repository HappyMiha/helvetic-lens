"""Bounded current human review beside search, never embedded or sent to models."""
from . import product_claim_review as reviews
from .product_api import fail
from .product_evidence_search import BATCH_SIZE, capture_rows, fingerprint
from .product_investigation_models import DossierClaim
from .product_investigations import access


def snapshot(session, dossier_id, identifiers):
    ids = set(identifiers)
    if len(ids) > BATCH_SIZE:
        fail("Too many finding reviews requested.", 422)
    rows = list(session.scalars(reviews.claims(dossier_id).where(DossierClaim.id.in_(ids)))) if ids else []
    if {row.id for row in rows} != ids:
        fail("Saved findings or access changed. Search again.", 409, "evidence_changed")
    return {row.id: reviews.projection(session, row) for row in sorted(rows, key=lambda row: row.id)}


def read(service, identity, product, dossier_id, command, captured_fingerprint, identifiers):
    with service.db.session() as session:
        if session.get_bind().dialect.name == "postgresql":
            session.connection().exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
        row = access(session, identity, product, dossier_id)
        if fingerprint(capture_rows(session, row, command)) != captured_fingerprint:
            fail("Saved evidence or access changed. Search again.", 409, "evidence_changed")
        return snapshot(session, row.id, identifiers)


def decorate(service, identity, product, dossier_id, command, captured_fingerprint, result):
    identifiers = sorted({item["claim_id"] for item in result["items"] if item["kind"] == "claim"})
    current = read(service, identity, product, dossier_id, command, captured_fingerprint, identifiers)
    return {**result, "review_claim_ids": identifiers, "review_fingerprint": fingerprint(current),
        "items": [{**item, "human_review": current.get(item["claim_id"])} for item in result["items"]]}
