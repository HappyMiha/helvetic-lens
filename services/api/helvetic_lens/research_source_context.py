"""Literal, current-original associations recorded while reading a source."""
from copy import deepcopy

KINDS = {"scope", "condition", "time", "category"}
QUALIFICATION_INSTRUCTIONS = """\nPreserve material exceptions in the answer itself.
An original saying 'X except Y' does not establish unqualified 'X', even when X
is the usual rule. In particular, 'no general permission' and 'no permission at
all' are different claims. Check absolute words such as any, all, never and only
against the full original. A quotation containing an exception does not repair
an answer that omits it. Do not silently read a narrower claim into its wording.
"""
INSTRUCTIONS = """Source context anchors retain original scope, condition or exception,
time, and category passages associated with an observation. Preserve applicable
qualifications in the finding; an association label is a fallible reading aid, not
proof. The linked quotations remain original evidence. No recorded anchors does not
mean all qualifications are known."""
READING_INSTRUCTIONS = INSTRUCTIONS + """ When a supplied observation depends on such
a passage, record its kind and exact citation in context_anchors. Use only supplied
passages of the same original, never generated explanations. Preserve applicable
anchors when merging observations."""


def _value(value):
    return value.model_dump() if hasattr(value, "model_dump") else value


def _binding(value, sources, default_source=None):
    value = _value(value)
    if not isinstance(value, dict):
        raise ValueError("Invalid source context citation")
    identifier = value.get("source_id", default_source)
    source = sources.get(identifier)
    quote, locator = value.get("quote"), value.get("locator")
    if (not source or not source.get("sha256") or not isinstance(quote, str) or not quote
            or not isinstance(locator, str) or not locator
            or ("sha256" in value and value["sha256"] != source["sha256"])
            or not any(p.get("passage") == locator and quote in p.get("text", "")
                for p in source.get("excerpts", []))):
        raise ValueError("Source context requires a current original citation")
    return {"source_id": identifier, "sha256": source["sha256"], "locator": locator, "quote": quote}


def association(observation, anchors, sources, *, source_id=None, supplied=None):
    """Bind a reading note to original text, optionally limited to a review's input."""
    if not anchors:
        return None
    primary = _binding(observation, sources, source_id)
    if supplied is not None and not any(p["source_id"] == primary["source_id"]
            and p["locator"] == primary["locator"] and primary["quote"] in p["quote"] for p in supplied):
        raise ValueError("Source context must use a supplied observation quotation")
    origin = sources[primary["source_id"]]
    result = []
    for raw in anchors:
        raw = _value(raw)
        if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
            raise ValueError("Invalid source context kind")
        anchor = _binding(raw, sources, primary["source_id"])
        other = sources[anchor["source_id"]]
        if (other["id"] != origin["id"] and (not origin.get("url")
                or origin["url"] != other.get("url") or origin["sha256"] != other["sha256"])):
            raise ValueError("Source context must refer to the same original")
        if supplied is not None and not any(p["source_id"] == anchor["source_id"]
                and p["locator"] == anchor["locator"] and anchor["quote"] in p["quote"] for p in supplied):
            raise ValueError("Source context must use a supplied original passage")
        item = {"kind": raw["kind"], **anchor}
        if item not in result:
            result.append(item)
    return {"observation": primary, "anchors": result}


def validated_context(sources):
    """Revalidate explicit associations against only the authorized current views.

    No inferred annotations or generated summaries are added to legacy sources.
    A supplied stale association rejects the transport instead of leaking its text.
    """
    sources = {s["id"]: s for s in sources}
    result = {}
    for identifier, source in sources.items():
        entries = source.get("source_context", [])
        if not isinstance(entries, list):
            raise ValueError("Invalid source context associations")
        bound = []
        for entry in entries:
            if (not isinstance(entry, dict) or not isinstance(entry.get("observation"), dict)
                    or entry["observation"].get("source_id") != identifier
                    or not isinstance(entry.get("anchors"), list)):
                raise ValueError("Invalid source context association")
            value = association(entry["observation"], entry["anchors"], sources)
            if value and value not in bound:
                bound.append(value)
        if bound:
            result[identifier] = deepcopy(bound)
    return result


def supplied_originals(value):
    """Only cited original text in a document-review input, including prior anchors."""
    def point(raw, source_id=None):
        identifier = raw.get("source_id", source_id)
        if identifier and raw.get("locator") and raw.get("quote"):
            yield {"source_id": identifier, "locator": raw["locator"], "quote": raw["quote"]}
        for anchor in raw.get("context_anchors", []):
            yield from point(anchor, identifier)

    for section in value.get("sections", []):
        for raw in [*section.get("observations", []), *section.get("cross_references", [])]:
            yield from point(raw, section["source_id"])
    for node in value.get("nodes", []):
        for raw in node.get("findings", []):
            yield from point(raw)
    for reference in value.get("cross_references", []):
        yield from point(reference)
        for passage in reference.get("target_passages", []):
            yield {"source_id": passage["source_id"], "locator": passage["passage"], "quote": passage["text"]}
