"""Fallible reading navigation, bound to unchanged authorized original passages."""
from copy import deepcopy

from . import research_source_context as source_context

CONTRACT = "source-scoped-reading-context/v1"
PROJECTION = "source-reading-original-pointers/v2"
SCOPE = ("Original pointers selected during fallible reading, not proof of an assertion. "
    "Only the supplied original passages are citable; preserve their qualifications.")
ROLES = {"support", "counterevidence", "context"}


def stamp(question, investigation_id):
    """Only called when an ordinary reading result passes its existing checks."""
    if not isinstance(question, str) or not question or not investigation_id:
        return {}
    return {"contract": CONTRACT, "question": question, "investigation_id": investigation_id}


def current_stamp(value, question, investigation_id):
    expected = stamp(question, investigation_id)
    return bool(expected and isinstance(value, dict)
        and all(value.get(key) == item for key, item in expected.items()))


def reading_note(point, sources, *, source_id=None, level):
    """Keep a validated observation's role/text apart from its original evidence."""
    if (not isinstance(point, dict) or point.get("role") not in ROLES
            or not isinstance(point.get("statement"), str) or not 5 <= len(point["statement"]) <= 700
            or level not in {"section", "document"}):
        raise ValueError("Invalid reading observation")
    original = source_context._binding(point, sources, source_id)
    from .research_reference_metadata import citation_use
    if citation_use(sources[original["source_id"]], original["locator"], original["quote"]) == "reference_metadata":
        raise ValueError("Reference metadata is not a reading finding")
    anchors = point.get("context_anchors", [])
    if not isinstance(anchors, list):
        raise ValueError("Invalid reading anchors")
    linked = source_context.association(point, anchors, sources, source_id=source_id)
    return {"interpretation": point["statement"], "role": point["role"], "level": level,
        "original": original, "anchors": linked["anchors"] if linked else []}


def validated_notes(sources, question, *, investigation_id=None):
    """Omit stale/legacy optional notes, retaining all original source material."""
    sources = {source["id"]: source for source in sources if source.get("id")}
    result = {}
    for identifier, source in sources.items():
        envelope = source.get("reading_context")
        if (not isinstance(envelope, dict) or not current_stamp(envelope, question, investigation_id)
                or not isinstance(envelope.get("notes"), list)):
            continue
        for note in envelope["notes"]:
            if (not isinstance(note, dict) or not isinstance(note.get("original"), dict)
                    or note["original"].get("source_id") != identifier
                    or not note["original"].get("sha256") or not isinstance(note.get("anchors"), list)
                    or any(not isinstance(anchor, dict) or not anchor.get("sha256") for anchor in note["anchors"])):
                continue
            try:
                bound = reading_note({**note["original"], "statement": note.get("interpretation"),
                    "role": note.get("role"), "context_anchors": note["anchors"]}, sources,
                    level=note.get("level"))
            except ValueError:
                continue
            if bound not in result.setdefault(identifier, []):
                result[identifier].append(bound)
    return result


def bind_notes(sources, passages, references, notes):
    """Resolve every literal note binding to complete canonical passage windows."""
    available = {source["id"] for source in sources if source.get("id")}

    def aliases(binding):
        identity = tuple(binding[key] for key in ("source_id", "sha256", "locator"))
        candidates = list(dict.fromkeys(ref for key, refs in passages.items()
            if key[:3] == identity and binding["quote"] in key[3] for ref in refs))
        if not candidates or any(ref not in references for ref in candidates):
            raise ValueError("Reading note no longer binds to an original")
        return [ref for ref in candidates if references[ref]["quote"] == binding["quote"]] or candidates

    result = {}
    for identifier, entries in notes.items():
        if identifier not in available:
            continue
        for note in entries:
            try:
                bound = {**deepcopy(note), "original_refs": aliases(note["original"]),
                    "anchors": [{"kind": anchor["kind"], "citation_refs": aliases(anchor)}
                        for anchor in note["anchors"]]}
            except (KeyError, ValueError):
                continue
            result.setdefault(identifier, []).append(bound)
    return result


def _unit_closure(wire):
    """One wire-local structural cache, exactly rebound before every reuse."""
    from .html_document_structure import HTML_STRUCTURE_VERSIONS
    from .product_operations import fingerprint
    from .research_original_context import POLICY, reference_units

    metadata = [{key: source.get(key) for key in ("id", "sha256", "url", "original_context")}
        | {"excerpts": [{"passage": passage.get("passage"), "text": passage.get("text"),
            "html_structure": passage.get("html_structure")}
            for passage in source.get("excerpts", [])]}
        for source in getattr(wire, "input", {}).get("sources", [])]
    binding = fingerprint({"references": wire.references, "sources": metadata,
        "source_context": getattr(wire, "source_context", []), "context_policy": POLICY,
        "html_versions": sorted(HTML_STRUCTURE_VERSIONS)})
    cached = getattr(wire, "_reading_unit_closure", None)
    if cached and cached["binding"] == binding:
        return cached["closure"]
    closure = {}
    for unit in reference_units(wire):
        for key in unit["primary"]:
            closure.setdefault(key, set()).update(unit["references"])
    wire._reading_unit_closure = {"binding": binding, "closure": closure}
    return closure


def provider_notes(wire, references, *, validated=None):
    """Emit original pointers only with all exact windows and governing context.

    `references` may use correction-local IDs. Text identities, never old numbers,
    bind the note back to the supplied original quotations. Generated reading
    interpretations and semantic evidence roles remain private model artifacts.
    """
    notes = getattr(wire, "reading_context", {}) if validated is None else validated
    if not notes:
        return {}
    identities = {}
    for key, reference in references.items():
        identity = tuple(reference.get(field) for field in ("source_id", "locator", "quote"))
        identities.setdefault(identity, []).append(key)
    local = {key: identities.get(tuple(reference.get(field) for field in ("source_id", "locator", "quote")), [])
        for key, reference in wire.references.items()}
    closure = _unit_closure(wire)
    result = {}
    for identifier, entries in notes.items():
        for note in entries:
            original = note["original_refs"]
            seeds = set(original) | {ref for anchor in note["anchors"] for ref in anchor["citation_refs"]}
            required = seeds | {ref for seed in seeds for ref in closure.get(seed, [])}
            if not original or any(not local.get(ref) for ref in required):
                continue

            def mapped(keys):
                return list(dict.fromkeys(ref for key in keys for ref in local[key]))

            pointer = {"level": note["level"], "original_citation_refs": mapped(original),
                "context_anchors": [{"kind": anchor["kind"], "citation_refs": mapped(anchor["citation_refs"])}
                    for anchor in note["anchors"]]}
            target = result.setdefault(identifier, [])
            if pointer not in target:
                target.append(pointer)
    return result
