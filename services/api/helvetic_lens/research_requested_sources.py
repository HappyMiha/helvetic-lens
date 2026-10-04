"""Quoted, fallible matches to a user's requested sources; selection only."""
from copy import deepcopy

from .research_reference_metadata import citation_use

# Reading grammar has its own request/schema fingerprint. The persisted match
# format and selection semantics stay compatible with completed source work.
CONTRACT = "requested-source-preference/v1"
CATEGORIES = {"primary", "official_secondary", "independent_secondary", "commentary"}
INSTRUCTIONS = """Return source_class as a cited classification or null when unknown.
In a classification, requested_source is the exact distinguishing source requirement
copied from the complete user question, with a citation identifying THIS document.
Use an empty string when no requested-source match is established. Do not copy the
document title instead of the user's words. A topic word or publisher hostname alone
is not a source match. Source category and this match are fallible reading notes,
not authority, applicability or truth. Other relevant or contrary evidence remains useful.
"""


def match(value, source, question):
    """Validate literal identity and question binding, never semantic authority."""
    if not isinstance(value, dict):
        return None
    if "identity" in value:
        if value.get("contract") != CONTRACT or "category" in value:
            return None
    elif not isinstance(value.get("category"), str) or value["category"] not in CATEGORIES:
        return None
    requested = value.get("requested_source")
    identity = value.get("identity", value)
    if (not isinstance(question, str) or not isinstance(requested, str)
            or len(requested.strip()) < 3 or requested != requested.strip() or requested not in question
            or value.get("original_question") != question or not isinstance(identity, dict)
            or identity.get("source_id") != source.get("id") or not source.get("sha256")
            or identity.get("sha256") != source["sha256"] or not source.get("url")
            or not isinstance(identity.get("quote"), str) or not identity["quote"]
            or not any(p.get("passage") == identity.get("locator") and identity["quote"] in p.get("text", "")
                for p in source.get("excerpts", []))):
        return None
    if citation_use(source, identity["locator"], identity["quote"]) == "reference_metadata":
        return None
    return {"contract": CONTRACT, "original_question": question, "requested_source": requested,
        "identity": {key: identity[key] for key in ("source_id", "sha256", "locator", "quote")}}


def validated_matches(sources, question):
    """Use current supplied identities; share only across the same URL and SHA.

    Retained copies do not inherit an old source ID or a different question.
    Missing identity portions and stale optional notes lose the preference.
    """
    sources = {source["id"]: source for source in sources}
    originals = {}
    for source in sources.values():
        for value in (source.get("source_class"), source.get("requested_source_basis")):
            if not isinstance(value, dict):
                continue
            identity = value.get("identity", value)
            identifier = identity.get("source_id") if isinstance(identity, dict) else None
            origin = sources.get(identifier) if isinstance(identifier, str) else None
            if not origin or (origin.get("url"), origin.get("sha256")) != (source.get("url"), source.get("sha256")):
                continue
            bound = match(value, origin, question)
            if bound:
                originals.setdefault((source["url"], source["sha256"]), bound)
    return {source["id"]: deepcopy(originals[source["url"], source["sha256"]])
        for source in sources.values() if (source.get("url"), source.get("sha256")) in originals}


def source_classes(session, run, sources):
    """Rebind new recalled notes only through the existing revocable origin pin."""
    values = {source.id: deepcopy(source.snapshot.get("source_class")) for source in sources}
    if session is None or run is None:
        return values
    pins = {source.id: source.snapshot.get("retained_origin") for source in sources}
    identifiers = {pin["source_id"] for pin in pins.values() if isinstance(pin, dict)
        and isinstance(pin.get("source_id"), str)}
    if not any(pin is not None for pin in pins.values()):
        return values
    from .product_investigation_models import InvestigationSource
    from .research_knowledge import eligible_sources, origin_pin

    allowed = {source.id: source for source in session.scalars(eligible_sources(run).where(
        InvestigationSource.id.in_(identifiers)))} if identifiers else {}
    for source in sources:
        pin = pins[source.id]
        if pin is None:
            continue
        recorded = values[source.id]
        values[source.id] = None
        identifier = pin.get("source_id") if isinstance(pin, dict) else None
        origin = allowed.get(identifier) if isinstance(identifier, str) else None
        if (origin is None or source.kind != "public_source" or source.snapshot.get("allow_discovery") is False
                or pin != origin_pin(origin) or source.url != origin.url or source.sha256 != origin.sha256
                or source.snapshot.get("excerpts") != origin.snapshot.get("excerpts")):
            continue
        current = {"id": source.id, "url": source.url, "sha256": source.sha256,
            "excerpts": source.snapshot.get("excerpts", [])}
        if match(recorded, current, run.question):
            values[source.id] = recorded  # Current-question analysis of a retained read.
            continue
        value = origin.snapshot.get("source_class")
        view = {"id": origin.id, "url": origin.url, "sha256": origin.sha256,
            "excerpts": origin.snapshot.get("excerpts", [])}
        if recorded == value and match(value, view, run.question):
            values[source.id] = {**deepcopy(value), "source_id": source.id}
    return values


def wire_matches(wire):
    return validated_matches(wire.input.get("sources", []),
        wire.input.get("original_question", wire.input.get("question", "")))


def provider_basis(wire, source_id, *, matches=None):
    """Expose a validated wire note without adding citation permission."""
    value = (wire_matches(wire) if matches is None else matches).get(source_id)
    if value is None:
        return {}
    return {"requested_source_basis": {"requested_source": value["requested_source"],
        "identity": deepcopy(value["identity"]),
        "scope": "Fallible match to the user's requested source; selection preference, not authority or factual support."}}
