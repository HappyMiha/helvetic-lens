"""Explain saved-evidence changes and retain explicit human review acknowledgements."""
from sqlalchemy import func, select

from .corpus_access import visible
from .models import DocumentWatch, Law, RegulatoryEventState, TopicEventMatch, Version
from .product_api import iso
from .product_models import DossierEntry
from .product_operations import fingerprint

MESSAGES = {
    "new_contributions": "New saved material or source decisions appeared after the last answer review.",
    "new_page_versions": "New saved page versions appeared after the last answer review.",
    "new_monitoring_matches": "New current monitoring matches appeared after the last answer review.",
    "source_changed": "Saved evidence behind this AI answer changed since it was reviewed.",
    "source_unavailable": "Saved evidence behind this AI answer is no longer accessible from this dossier.",
    "source_revision_unknown": "An older AI source has no recorded revision; inspect it before reconfirming.",
}


def page_states(session, parent, post, organization_id):
    if not post or post.kind != "research":
        return []
    sources = post.data_json.get("sources", [])
    sources = sources if isinstance(sources, list) else []
    states = []
    for source in sources:
        if not isinstance(source, dict) or source.get("kind") != "saved_page_extract":
            continue
        key = source.get("key")
        recorded = source.get("evidence_revision")
        recorded = recorded if type(recorded) is int and recorded > 0 else None
        document_id = source.get("document_id")
        monitored = select(DossierEntry.id).where(DossierEntry.dossier_id == parent.id,
            DossierEntry.kind == "monitor", DossierEntry.data_json["law_id"].as_string() == Version.law_id).exists()
        version = session.execute(select(Version.law_id, Version.evidence_revision, Version.synthetic)
            .join(Law, Law.id == Version.law_id).join(DocumentWatch, DocumentWatch.law_id == Law.id)
            .where(Version.id == key, visible(Version, organization_id), visible(Law, organization_id),
                   DocumentWatch.organization_id == organization_id, monitored)).mappings().first() if isinstance(key, str) else None
        available = version is not None and (document_id is None or document_id == version["law_id"])
        states.append({"source_id": source.get("id"), "version_id": key,
            "recorded_document_id": document_id, "recorded_revision": recorded,
            "status": "available" if available else "unavailable",
            "document_id": version["law_id"] if available else None,
            "revision": version["evidence_revision"] if available else None,
            "synthetic": bool(version["synthetic"]) if available else None})
    return states


def marker(session, query, model, stamp):
    count, latest, identifier = session.execute(query.with_only_columns(
        func.count(model.id), func.max(stamp), func.max(model.id))).one()
    return {"count": count, "latest_at": iso(latest) if latest else None, "id": identifier}


def review_state(session, parent, profile, row, organization_id, *, accepted=None):
    reasons = []
    current = []
    markers = {}
    baseline = None
    claim_state = None
    if row.accepted_entry_id and row.accepted_at:
        accepted = accepted or session.get(DossierEntry, row.accepted_entry_id)
        if not accepted or accepted.dossier_id != parent.id or accepted.thread_id != row.id:
            accepted = None
        from .product_claim_synthesis import retained_state

        claim_state = retained_state(session, accepted)
        if claim_state and claim_state["status"] != "current":
            reasons.append({"code": "claim_" + claim_state["status"], "message": claim_state["message"], "source_ids": []})
        current = page_states(session, parent, accepted, organization_id)
        audit = session.execute(select(DossierEntry.id, DossierEntry.data_json).where(
            DossierEntry.dossier_id == parent.id, DossierEntry.kind == "review",
            DossierEntry.data_json["thread_id"].as_string() == row.id,
            DossierEntry.data_json["accepted_entry_id"].as_string() == row.accepted_entry_id,
            DossierEntry.data_json["revision"].as_integer() <= row.revision)
            .order_by(DossierEntry.data_json["revision"].as_integer().desc(), DossierEntry.id.desc()).limit(1)).first()
        if audit:
            stored = audit.data_json.get("answer_evidence")
            if isinstance(stored, dict) and stored.get("schema_version") == 1 and isinstance(stored.get("sources"), list):
                baseline = stored["sources"]
        grouped = {}
        for state in current:
            previous = next((item for item in baseline or [] if isinstance(item, dict)
                and item.get("source_id") == state["source_id"] and item.get("version_id") == state["version_id"]), None)
            code = None
            if baseline is not None and previous == state:
                continue
            if state["status"] == "unavailable":
                code = "source_unavailable"
            elif baseline is not None or state["revision"] != state["recorded_revision"] or state["synthetic"]:
                code = "source_revision_unknown" if baseline is None and state["recorded_revision"] is None else "source_changed"
            if code:
                grouped.setdefault(code, []).append(state["source_id"])
        if baseline is not None and any(item not in current for item in baseline if isinstance(item, dict)):
            # Current states already identify corrections; also cover removed snapshot identities.
            missing = [item.get("source_id") for item in baseline if isinstance(item, dict)
                and not any(value["source_id"] == item.get("source_id") and value["version_id"] == item.get("version_id") for value in current)]
            if missing:
                grouped.setdefault("source_changed", []).extend(missing)
        reasons.extend({"code": code, "message": MESSAGES[code], "source_ids": list(dict.fromkeys(value for value in ids if isinstance(value, str)))} for code, ids in grouped.items())
        contributions = select(DossierEntry.id).where(DossierEntry.dossier_id == parent.id,
            DossierEntry.kind.in_(("reference", "note", "discussion", "research", "feedback", "source_review")),
            DossierEntry.created_at > row.accepted_at)
        watched = select(DossierEntry.data_json["law_id"].as_string()).where(DossierEntry.dossier_id == parent.id, DossierEntry.kind == "monitor")
        versions = select(Version.id).join(Law, Law.id == Version.law_id).join(DocumentWatch, DocumentWatch.law_id == Law.id).where(
            Version.law_id.in_(watched), visible(Version, organization_id), visible(Law, organization_id),
            DocumentWatch.organization_id == organization_id, Version.synthetic.is_(False), Version.created_at > row.accepted_at)
        matches = select(TopicEventMatch.id).join(RegulatoryEventState,
            (RegulatoryEventState.event_id == TopicEventMatch.event_id)
            & (RegulatoryEventState.organization_id == TopicEventMatch.organization_id)).where(
            TopicEventMatch.topic_id.in_(profile.topic_ids_json), TopicEventMatch.matched_at > row.accepted_at)
        for code, query, model, stamp in (
            ("new_contributions", contributions, DossierEntry, DossierEntry.created_at),
            ("new_page_versions", versions, Version, Version.created_at),
            ("new_monitoring_matches", matches, TopicEventMatch, TopicEventMatch.matched_at)):
            marks = marker(session, query, model, stamp)
            markers[code] = marks
            if marks["count"]:
                reasons.append({"code": code, "message": MESSAGES[code], "source_ids": []})
    token = fingerprint({"organization_id": organization_id, "product": parent.product, "dossier_id": parent.id,
        "thread_id": row.id, "revision": row.revision, "accepted_entry_id": row.accepted_entry_id,
        "accepted_at": iso(row.accepted_at) if row.accepted_at else None,
        "sources": current, "baseline": baseline, "markers": markers,
        **({"claim_state": claim_state} if claim_state else {})})
    return {"fingerprint": token, "reasons": reasons, "reviewed_at": iso(row.accepted_at) if row.accepted_at else None}
