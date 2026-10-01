"""One-hop retrieval over cited relationships and claim evidence, never name merges."""
import re

from sqlalchemy import select

from .product_investigation_models import DossierEntity, DossierRelationship

LIMIT = 2000


def project(session, parent, items, query):
    by_source = {}
    for item in items:
        by_source.setdefault(item["source_id"], []).append(item)
    sources = set(by_source)
    if not sources:
        return {"ranked_ids": [], "links": {}, "truncated": False}
    # Items already come from the current permitted ledger. An edge and both
    # endpoints must have exact quotations within those same authorized records.
    def records(evidence):
        source_id, quote = evidence.get("source_id"), evidence.get("quote", "")
        return [r["id"] for r in by_source.get(source_id, []) if quote.strip()
            and r["sha256"] == evidence.get("sha256") and r["locator"] == evidence.get("locator") and quote in r["quote"]]
    rows = list(session.scalars(select(DossierRelationship).where(
        DossierRelationship.dossier_id == parent.id, DossierRelationship.organization_id == parent.organization_id,
        DossierRelationship.evidence["source_id"].as_string().in_(sources))
        .order_by(DossierRelationship.created_at.desc(), DossierRelationship.id).limit(LIMIT + 1)))
    entity_ids = {key for row in rows[:LIMIT] for key in (row.subject_id, row.object_id)}
    entities = {entity.id: entity for entity in session.scalars(select(DossierEntity).where(
        DossierEntity.dossier_id == parent.id, DossierEntity.organization_id == parent.organization_id,
        DossierEntity.id.in_(entity_ids)))} if entity_ids else {}
    terms = set(re.findall(r"\w+", query.casefold()))
    scores, links = {}, {}
    for row in rows[:LIMIT]:
        left, right = entities.get(row.subject_id), entities.get(row.object_id)
        if not left or not right or left.investigation_id != row.investigation_id or right.investigation_id != row.investigation_id:
            continue
        edge_records, left_records, right_records = records(row.evidence), records(left.evidence), records(right.evidence)
        if not edge_records or not left_records or not right_records:
            continue
        ids = list(dict.fromkeys([*edge_records, *left_records, *right_records]))
        overlap = len(terms.intersection(re.findall(r"\w+", f"{left.name} {row.predicate} {right.name}".casefold())))
        for key in ids:
            links.setdefault(key, set()).update(other for other in ids if other != key)
            if overlap:
                scores[key] = scores.get(key, 0) + overlap
    # A finding's supporting and contrary quotations form the same evidence
    # neighbourhood. Never suppress contradictions or rejected machine matches.
    claims = {}
    for item in items:
        if item.get("claim_id"):
            claims.setdefault(item["claim_id"], []).append(item["id"])
    for identifiers in claims.values():
        for key in identifiers:
            links.setdefault(key, set()).update(other for other in identifiers if other != key)
    return {"ranked_ids": sorted(scores, key=lambda key: (-scores[key], key)),
        "links": {key: sorted(values) for key, values in links.items()}, "truncated": len(rows) > LIMIT}


def fuse(ranked, graph):
    if not graph:
        return ranked
    neighbours = list(dict.fromkeys(key for item in ranked[:8] for key in graph["links"].get(item["id"], [])))
    order = list(dict.fromkeys([*graph["ranked_ids"], *neighbours]))
    positions = {key: number for number, key in enumerate(order, 1)}
    result = [{**item, "graph_related": item["id"] in positions,
        "rank_score": item["rank_score"] + (1 / (60 + positions[item["id"]]) if item["id"] in positions else 0)} for item in ranked]
    return sorted(result, key=lambda item: (-item["rank_score"], item["id"]))
