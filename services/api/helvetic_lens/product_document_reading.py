"""Complete immutable originals, then analyse all sections and reconcile them."""
from copy import deepcopy

from . import product_research_mission as mission
from .product_investigations import event

BATCH_CHARACTERS = 64000


def prepare(run, state, work):
    if not (mission.enabled(run) or state.get("contribution_entry_id") or state.get("public_file_id")):
        return
    saved = state.get("document_reads", {}).get(str(state.get("read_index", 0)), {})
    work["document_cursor"] = saved.get("next_cursor") or {"page": 0, "offset": 0}
    work["document_sha256"] = saved.get("sha256")
    if saved.get("retained_document"):
        work["retained_document"] = deepcopy(saved["retained_document"])


def valid(work, result):
    if not isinstance(result, dict):
        return False
    reading = result.get("reading")
    if not reading:
        return not work.get("document_sha256")
    return (reading.get("contract") == "document-reading/v1"
        and reading.get("cursor") == work.get("document_cursor")
        and (not work.get("document_sha256") or result.get("sha256") == work["document_sha256"])
        and (not reading.get("next_cursor") or
            (reading["next_cursor"].get("page", -1), reading["next_cursor"].get("offset", -1))
            > (reading["cursor"]["page"], reading["cursor"]["offset"])))


def remember(session, run, state, work, result):
    """Commit every extraction portion; emit full-text analysis batches, no ranking."""
    reading = result.get("reading")
    if not reading:
        state["read_index"] = state.get("read_index", 0) + 1
        return result
    key = str(state.get("read_index", 0))
    previous = state.setdefault("document_reads", {}).get(key, {})
    warnings = list(dict.fromkeys([*previous.get("warnings", []), *result.get("warnings", [])]))
    saved = {**previous, **reading, "sha256": result["sha256"], "portions": previous.get("portions", 0) + 1,
        "url": work["item"]["url"], "title": work["item"]["title"], "warnings": warnings,
        "complete": False, "read_complete": not reading["next_cursor"] and not warnings,
        "analysis_complete": False, "characters_read": previous.get("characters_read", 0) + reading["characters_read"],
        "pages_read": (reading["pages"][1] if not reading["next_cursor"] or reading["next_cursor"]["offset"] == 0
            else reading["pages"][0] - 1) if reading.get("pages") else None,
        "unread_reason": reading.get("unread_reason") or ("Some pages could not be read." if warnings else "Section analysis and whole-document review are pending.")}
    if result.get("_retained_document"):
        saved["retained_document"] = result["_retained_document"]
    buffer = previous.get("buffer", {"cursor": reading["cursor"], "excerpts": [], "pages": reading.get("pages")})
    buffer["excerpts"].extend(result.get("excerpts", []))
    if buffer.get("pages"):
        buffer["pages"][1] = reading["pages"][1]
    saved["buffer"] = buffer
    state["document_reads"][key] = saved
    event(session, run, "document_portion_read", pages=reading["pages"],
        further_reading=bool(reading["next_cursor"]), warnings=bool(warnings))
    if not reading["next_cursor"] and not buffer["excerpts"] and not saved.get("source_ids"):
        saved["error"] = "No readable text was found in this document."
        state["error"] = saved["error"]
    if not reading["next_cursor"]:
        state["read_index"] = state.get("read_index", 0) + 1
    if reading["next_cursor"] and sum(len(p["text"]) for p in buffer["excerpts"]) < BATCH_CHARACTERS:
        return None
    saved.pop("buffer", None)
    return {**{k: v for k, v in result.items() if k != "_retained_document"},
        "excerpts": buffer["excerpts"], "document_index": key,
        "reading": {**reading, "cursor": buffer["cursor"], "pages": buffer["pages"], "complete": saved["read_complete"]},
        "scope": "Every extracted passage in this sequential section batch. Whole-document reading and reconciliation are tracked separately."}


def captured(state, result, source_id):
    if "document_index" in result:
        reading = state["document_reads"][result["document_index"]]
        reading.setdefault("source_ids", []).append(source_id)


def pending_read(state):
    reading = state.get("document_reads", {}).get(str(state.get("read_index", 0)))
    return bool(reading and reading.get("next_cursor") and not reading.get("error"))


def failure(state, phase, *, interrupted=False):
    if phase == "read":
        key = str(state.get("read_index", 0))
        reading = state.get("document_reads", {}).get(key)
        if reading:
            reading.update(complete=False, read_complete=False,
                error="Reading was interrupted; the original and next position are saved." if interrupted else "A document portion could not be read.")
    elif phase == "document_review":
        key = state.pop("review_document_index", None)
        if key is None:
            # Compatibility for a request dispatched by the preceding worker.
            from .product_document_analysis import next_document
            selected = next_document(state)
            key = selected[0] if selected else None
        reading = state.get("document_reads", {}).get(key)
        if reading and not reading.get("complete"):
            reading["review_failed"] = True


def failed_analysis(state):
    return bool(state.get("failed_extract_indices") or any(
        doc.get("review_failed") or doc.get("error") or doc.get("read_complete") is False
        for doc in state.get("document_reads", {}).values()))


def projection(state):
    # Parser buffers and storage keys are internal, never model or reader input.
    return [{k: v for k, v in reading.items() if k not in {"retained_document", "buffer", "source_ids", "review_tree"}}
        for reading in state.get("document_reads", {}).values()]


def incomplete(branches):
    return [r for b in branches for r in projection(b.checkpoint) if not r.get("complete")]


def model_projection(doc):
    value = deepcopy(doc)
    review = value.get("reconciliation", {})
    if review.get("contract") == "document-review-tree/v1":
        value["reconciliation"] = {k: review[k] for k in ("contract", "synopsis", "review_nodes")}
        value["reconciliation"]["reference_checks"] = len(review["cross_reference_checks"])
        value["reconciliation"]["scope"] = "The cited synthesis and its named gaps are supplied in whole_document_review."
    return value
