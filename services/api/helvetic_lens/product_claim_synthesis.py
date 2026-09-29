"""Explicit, bounded claim inputs and retained-answer access/freshness fences."""
import hashlib
import re
from html import escape

from sqlalchemy import case

from . import product_claim_review as reviews
from .product_investigation_models import DossierClaim, InvestigationSource

SCOPE = "claims_v1"
TYPED_SCOPE = "claims_typed_v1"
SCOPES = (SCOPE, TYPED_SCOPE)
TYPED_CONTEXTS = 42
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


def editor_context(state, citations):
    """Only current editorial values; no reasons, identities or historical values."""
    current = bool(state["revision"] and not state["stale"] and state["reviewable"])
    status = "current" if current else "stale" if state["revision"] else "unreviewed"
    assessed = state.get("source_assessments", {}) if current else {}
    roles = {item["source_id"]: item for item in assessed.get("items", [])}
    return {"schema_version": 1, "status": status,
        "interpretation": state.get("interpretation") if current else None,
        "source_assessments": {key: assessed.get(key) for key in ("domain_pack", "domain_pack_version")} | {
            "items": [{"citation_id": value["id"], "source_record_id": value["source"]["id"],
                "category": roles.get(value["source"]["id"], {}).get("category", "UNASSESSED"),
                "label": roles.get(value["source"]["id"], {}).get("label", "Not assessed"),
                "status": status if not current else "current" if value["source"]["id"] in roles else "unassessed"}
                for value in citations]}}


def editor_brief(node):
    """Render the immutable supplied input, never current metadata or raw HTML."""
    value = node.get("editor_context")
    if not value:
        return ""
    interpretation = value.get("interpretation") or {}
    label = " · ".join(str(interpretation[key]) for key in ("kind_label", "label") if interpretation.get(key)) or "Not classified"
    roles = value["source_assessments"]
    items = "".join(f'<li>{escape(item["citation_id"])}: {escape(item["label"])} ({escape(item["status"])})</li>' for item in roles["items"])
    return (f'<p>Editor context ({escape(value["status"])}): {escape(label)}. '
        'Editorial assessment does not establish truth or applicability.</p>'
        f'<p>Source role registry: {escape(str(roles.get("domain_pack") or "Unknown"))} '
        f'{escape(str(roles.get("domain_pack_version") or ""))}</p><ul>{items}</ul>')


def selection(session, parent, question, *, typed=False):
    words = list(dict.fromkeys(re.findall(r"\w{4,}", question.lower())))[:20]
    rank = sum((case((DossierClaim.statement.icontains(word, autoescape=True), 1), else_=0) for word in words), 0)
    query = reviews.claims(parent.id).where(DossierClaim.organization_id == parent.organization_id)
    if words:
        query = query.order_by(rank.desc())
    candidates = list(session.scalars(query.order_by(DossierClaim.created_at.desc(), DossierClaim.id).limit(CANDIDATES)))
    groups = [pin(session, claim) for claim in candidates]
    # Stable lexical/recency order within each workflow category; never a truth score.
    groups.sort(key=lambda group: group[2]["human_status"] != "ACCEPTED")
    cache = {group[0]["claim_id"]: group for group in groups}
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
        if typed:
            selected = claims[-1]
            selected["editor_context"] = editor_context(state, citations.values())
            for original, comparison in zip(context["comparisons"], selected["comparisons"], strict=True):
                identifier = original["claim"]["id"]
                if identifier not in cache:
                    cache[identifier] = pin(session, session.get(DossierClaim, identifier))
                dependency, _, reviewed = cache[identifier]
                pins.append(dependency)
                comparison.update(id=identifier,
                    human_review={key: reviewed[key] for key in ("revision", "decision", "stale", "human_status")},
                    editor_context=editor_context(reviewed, original["evidence"]))
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
        if typed:
            for node in (claim, *claim["comparisons"]):
                for role in node["editor_context"]["source_assessments"]["items"]:
                    role["citation_id"] = ids[role["citation_id"]]
        claim["citations"] = [ids[value] for value in claim["citations"]]
        for comparison in claim["comparisons"]:
            comparison["citations"] = [ids[value] for value in comparison["citations"]]
    pins = list({value["claim_id"]: value for value in pins}.values())
    return claims, sources, pins, {"claim_candidate_limit": CANDIDATES, "claim_limit": CLAIMS,
        "claim_quote_limit": QUOTES, "claim_candidates": len(candidates), "omitted_claim_groups": omitted}


def retained_state(session, entry):
    """No inference. Original pins are immutable, including after answer acceptance."""
    if not entry or entry.kind != "research" or entry.data_json.get("evidence_scope") not in SCOPES:
        return None
    recorded = entry.data_json.get("claim_contexts")
    limit = TYPED_CONTEXTS if entry.data_json.get("evidence_scope") == TYPED_SCOPE else CLAIMS
    if not isinstance(recorded, list) or len(recorded) > limit:
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
            data={"evidence_scope": entry.data_json["evidence_scope"], "claim_freshness": state})
    return result


def action_hidden(session, action):
    from .product_models import DossierEntry

    origin = action.evidence_json.get("research", {})
    if origin.get("evidence_scope") not in SCOPES:
        return False
    entry = session.get(DossierEntry, origin.get("entry_id"))
    state = retained_state(session, entry)
    return not state or state["status"] == "unavailable"
