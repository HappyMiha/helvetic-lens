"""Explicit, bounded claim inputs and retained-answer access/freshness fences."""
import hashlib
import re

from sqlalchemy import case

from . import product_claim_review as reviews
from .product_investigation_models import DossierClaim, InvestigationSource

SCOPE = "claims_v1"
CANDIDATES = 12
CLAIMS = 2
QUOTES = 8
CHANGED = "Claim evidence or human review changed. Review a fresh preview and generate a new note."
UNAVAILABLE = "This research note is hidden because a supporting source is no longer available in this dossier."


def pin(session, claim, current=None):
    current = current or reviews.context(session, claim)
    state = reviews.projection(session, claim, current=current)
    return {"claim_id": claim.id, "fingerprint": reviews.digest(state),
        "sources": [value["id"] for value in current["basis"]["sources"]]}, current, state


def selection(session, parent, question):
    words = list(dict.fromkeys(re.findall(r"\w{4,}", question.lower())))[:20]
    rank = sum((case((DossierClaim.statement.icontains(word, autoescape=True), 1), else_=0) for word in words), 0)
    query = reviews.claims(parent.id).where(DossierClaim.organization_id == parent.organization_id)
    if words:
        query = query.order_by(rank.desc())
    candidates = list(session.scalars(query.order_by(DossierClaim.created_at.desc(), DossierClaim.id).limit(CANDIDATES)))
    groups = [pin(session, claim) for claim in candidates]
    # Stable lexical/recency order within each workflow category; never a truth score.
    groups.sort(key=lambda group: group[2]["human_status"] != "ACCEPTED")
    claims, sources, pins = [], {}, []
    omitted = 0
    for captured, context, state in groups:
        citations = {value["id"]: value for value in context["evidence"]}
        for comparison in context["comparisons"]:
            citations.update({value["id"]: value for value in comparison["evidence"]})
        if (len(claims) >= CLAIMS or not context["reviewable"]
                or any(len(value["quote"]) > 1800 for value in citations.values())
                or len(set(sources) | set(citations)) > QUOTES):
            omitted += 1
            continue
        pins.append(captured)
        claims.append({"id": context["claim"]["id"], "statement": context["claim"]["statement"],
            "machine_status": context["claim"]["evidence_status"],
            "human_review": {key: state[key] for key in ("revision", "decision", "stale", "human_status")},
            "citations": [value["id"] for value in context["evidence"]],
            "comparisons": [{"kind": value["kind"], "status": value["status"],
                "statement": value["claim"]["statement"], "machine_status": value["claim"]["evidence_status"],
                "citations": [item["id"] for item in value["evidence"]]} for value in context["comparisons"]]})
        for identifier, value in citations.items():
            source = value["source"]
            sources[identifier] = {"key": identifier, "kind": "investigation_quote", "title": source["title"],
                "text": value["quote"], "url": source["url"], "date": source["captured_at"],
                "claim_id": value["claim_id"], "relation": value["relation"], "locator": value["locator"],
                "source_record_id": source["id"], "capture_sha256": source["sha256"],
                "saved_version": source["saved_version"], "sha256": hashlib.sha256(value["quote"].encode()).hexdigest()}
    sources = [{**value, "id": f"S{index + 1}"} for index, value in enumerate(sources.values())]
    ids = {value["key"]: value["id"] for value in sources}
    for claim in claims:
        claim["citations"] = [ids[value] for value in claim["citations"]]
        for comparison in claim["comparisons"]:
            comparison["citations"] = [ids[value] for value in comparison["citations"]]
    return claims, sources, pins, {"claim_candidate_limit": CANDIDATES, "claim_limit": CLAIMS,
        "claim_quote_limit": QUOTES, "claim_candidates": len(candidates), "omitted_claim_groups": omitted}


def retained_state(session, entry):
    """No inference. Original pins are immutable, including after answer acceptance."""
    if not entry or entry.kind != "research" or entry.data_json.get("evidence_scope") != SCOPE:
        return None
    recorded = entry.data_json.get("claim_contexts")
    if not isinstance(recorded, list) or len(recorded) > CLAIMS:
        return {"status": "unavailable", "message": UNAVAILABLE, "fingerprint": reviews.digest(None)}
    states = []
    for value in recorded:
        claim = session.scalar(reviews.claims(entry.dossier_id).where(DossierClaim.id == value["claim_id"]))
        source_ids = set(value["sources"])
        visible = set(session.scalars(reviews.source_query(entry.dossier_id).with_only_columns(InvestigationSource.id)
            .where(InvestigationSource.id.in_(source_ids))))
        if not claim or visible != source_ids:
            states.append({"status": "unavailable"})
            continue
        current, _, _ = pin(session, claim)
        states.append({"status": "current" if current == value else "changed", "pin": current})
    status = "unavailable" if any(value["status"] == "unavailable" for value in states) else (
        "changed" if any(value["status"] == "changed" for value in states) else "current")
    return {"status": status, "message": UNAVAILABLE if status == "unavailable" else CHANGED if status == "changed" else "",
        "fingerprint": reviews.digest(states)}


def serialize(session, entry, result):
    if entry.kind == "action" and entry.data_json.get("action_id"):
        from .product_models import DossierAction

        action = session.get(DossierAction, entry.data_json["action_id"])
        if action and action_hidden(session, action):
            return {**result, "title": "Research follow-up unavailable", "body": UNAVAILABLE, "data": {}, "analysis": None}
    state = retained_state(session, entry)
    if state is None:
        return result
    result["data"] = {key: value for key, value in result["data"].items() if key != "claim_contexts"}
    result["data"]["claim_freshness"] = state
    if state["status"] == "unavailable":
        result.update(title="Research note unavailable", body=UNAVAILABLE, url="", analysis=None,
            data={"evidence_scope": SCOPE, "claim_freshness": state})
    return result


def action_hidden(session, action):
    from .product_models import DossierEntry

    origin = action.evidence_json.get("research", {})
    if origin.get("evidence_scope") != SCOPE:
        return False
    entry = session.get(DossierEntry, origin.get("entry_id"))
    state = retained_state(session, entry)
    return not state or state["status"] == "unavailable"
