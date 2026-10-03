"""Cited pair suggestions and append-only human decisions, never entity merges."""
import hashlib
from itertools import combinations

from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from .product_api import iso
from .product_investigation_models import (
    DossierEntity,
    EntityIdentityReview,
    Investigation,
    InvestigationSource,
)
from .product_provenance import canonical
from .product_public_research import eligible, sources_visible
from .research_knowledge import captured_at

ENTITY_LIMIT = 120
SUGGESTION_LIMIT = 30
PAGE_SIZE = 20
BASIS = "Exact cited identifier, issuer, jurisdiction and kind. This is a suggestion, not a confirmed identity."
BOUNDARY = "Decisions apply only to these two retained mentions. Original records and claims are unchanged; no transitive merge or claim acceptance is implied."


def audience(run, publication):
    if publication:
        return and_(run.publication_id == publication.id, run.publication_revision == publication.revision, eligible(run))
    return and_(run.publication_id.is_(None), sources_visible(run))


def entities(dossier_id, publication=None):
    return select(DossierEntity).join(Investigation, Investigation.id == DossierEntity.investigation_id).where(
        DossierEntity.dossier_id == dossier_id, Investigation.status == "completed", audience(Investigation, publication))


def reviews(dossier_id, publication=None, *, latest=True):
    current, previous = aliased(Investigation), aliased(Investigation)
    result = select(EntityIdentityReview).join(current, current.id == EntityIdentityReview.investigation_id).join(
        previous, previous.id == EntityIdentityReview.previous_investigation_id).where(
            EntityIdentityReview.dossier_id == dossier_id, audience(current, publication), audience(previous, publication))
    if latest:
        newer = aliased(EntityIdentityReview)
        result = result.where(~select(newer.id).where(newer.entity_id == EntityIdentityReview.entity_id,
            newer.previous_entity_id == EntityIdentityReview.previous_entity_id,
            newer.revision > EntityIdentityReview.revision).exists())
    return result


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def mention(session, entity):
    """Revalidate the primary literal citation; never infer an identifier from a name."""
    evidence = entity.evidence or {}
    source = session.scalar(select(InvestigationSource).where(InvestigationSource.id == evidence.get("source_id"),
        InvestigationSource.investigation_id == entity.investigation_id,
        InvestigationSource.dossier_id == entity.dossier_id, InvestigationSource.organization_id == entity.organization_id))
    identifier, quote, locator = evidence.get("identifier"), evidence.get("quote"), evidence.get("locator")
    if not source or not isinstance(identifier, dict) or not isinstance(quote, str) or not quote.strip():
        return None
    if any(not isinstance(identifier.get(key), str) or not identifier[key].strip()
           for key in ("value", "issuer", "jurisdiction", "kind")):
        return None
    if identifier["kind"] != entity.kind or any(value not in quote for value in
            (entity.name, identifier["value"], identifier["issuer"], identifier["jurisdiction"])):
        return None
    if evidence.get("sha256") != source.sha256 or not any(
            part.get("passage") == locator and quote in part.get("text", "") for part in source.snapshot.get("excerpts", [])):
        return None
    return {"id": entity.id, "investigation_id": entity.investigation_id, "name": entity.name, "kind": entity.kind,
        "identifier": {key: identifier[key] for key in ("value", "issuer", "jurisdiction", "kind")},
        "quote": quote, "locator": locator,
        "source": {"id": source.id, "title": source.title, "url": source.url, "kind": source.kind,
            "sha256": source.sha256, "captured_at": captured_at(source)},
        "capture_fingerprint": digest(source.snapshot.get("excerpts", []))}


def pair(session, first, second):
    values = [mention(session, value) for value in (first, second)]
    valid = all(values)
    return {"id": first.id + ":" + second.id, "entity_id": first.id, "previous_entity_id": second.id,
        "first": values[0], "second": values[1], "evidence_fingerprint": digest(values) if valid else None,
        "exact_identifier_match": bool(valid and values[0]["identifier"] == values[1]["identifier"]),
        "basis": BASIS, "boundary": BOUNDARY}


def review_payload(session, value, publication=None):
    first, second = (session.get(DossierEntity, key) for key in (value.entity_id, value.previous_entity_id))
    result = pair(session, first, second)
    history = session.scalars(reviews(value.dossier_id, publication, latest=False).where(
        EntityIdentityReview.entity_id == value.entity_id, EntityIdentityReview.previous_entity_id == value.previous_entity_id)
        .order_by(EntityIdentityReview.revision).limit(100))
    return {**result, "revision": value.revision, "decision": value.decision,
        "stale": result["evidence_fingerprint"] != value.evidence_fingerprint,
        "history": [{"revision": row.revision, "decision": row.decision, "reason": row.reason,
            "at": iso(row.created_at), "reviewer": "Dossier editor" if row.reviewed_by_user_id else "Former dossier editor",
            "evidence_fingerprint": row.evidence_fingerprint} for row in history]}


def candidates(session, dossier_id, publication=None):
    values = list(session.scalars(entities(dossier_id, publication).order_by(
        DossierEntity.created_at.desc(), DossierEntity.id).limit(ENTITY_LIMIT + 1)))
    limited, values = len(values) > ENTITY_LIMIT, values[:ENTITY_LIMIT]
    ids = [value.id for value in values]
    decided = {(row.entity_id, row.previous_entity_id) for row in session.scalars(reviews(dossier_id, publication).where(
        EntityIdentityReview.entity_id.in_(ids), EntityIdentityReview.previous_entity_id.in_(ids)))}
    valid = {value.id: mention(session, value) for value in values}
    items = []
    for first, second in combinations(sorted(values, key=lambda value: value.id), 2):
        left, right = valid[first.id], valid[second.id]
        if (first.investigation_id == second.investigation_id or (first.id, second.id) in decided
                or not left or not right or left["identifier"] != right["identifier"]):
            continue
        items.append({"id": first.id + ":" + second.id, "entity_id": first.id, "previous_entity_id": second.id,
            "first": left, "second": right, "evidence_fingerprint": digest([left, right]), "exact_identifier_match": True,
            "basis": BASIS, "boundary": BOUNDARY, "revision": 0, "decision": "unreviewed", "stale": False, "history": []})
        if len(items) > SUGGESTION_LIMIT:
            break
    return {"items": items[:SUGGESTION_LIMIT], "entities_examined": len(values), "entity_limit": ENTITY_LIMIT,
        "entity_window_limited": limited, "suggestion_limit": SUGGESTION_LIMIT, "more_suggestions": len(items) > SUGGESTION_LIMIT}


def page(session, dossier_id, publication=None, *, offset=0):
    query = reviews(dossier_id, publication)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = list(session.scalars(query.order_by(EntityIdentityReview.created_at.desc(), EntityIdentityReview.id)
        .offset(offset).limit(PAGE_SIZE)))
    return {"items": [review_payload(session, value, publication) for value in items], "total": total,
        "offset": offset, "page_size": PAGE_SIZE, "publication_revision": publication.revision if publication else None,
        "suggestions": candidates(session, dossier_id, publication) if offset == 0 else None, "boundary": BOUNDARY}
