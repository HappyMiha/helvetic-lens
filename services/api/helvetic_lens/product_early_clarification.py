"""Optional source-bound early choices; existing pause, reply and worker lifecycle."""
from copy import deepcopy

from . import product_informed_research as informed
from .product_api import fail
from .product_operations import fingerprint

CONTRACT = "early-clarification/v1"


def enabled(run):
    return (run.research_state or {}).get("exploration", {}).get("clarification_contract") == CONTRACT


def source_record(source):
    # Pin the source identity and actual supplied material. Later AI source_class
    # and analysis_completed annotations are not inputs to the early request.
    # Current discovery/duplicate/exclusion rights are checked by sources().
    return {"id": source.id, "sha256": source.sha256, "title": source.title,
        "url": source.url, "kind": source.kind,
        "excerpts": deepcopy(source.snapshot.get("excerpts")),
        "text_truncated": source.snapshot.get("text_truncated")}


def remember(session, run, supplied):
    from . import product_exploration as exploration

    available = exploration.sources(session, run)
    value = {"contract": CONTRACT, "original_question": run.question,
        "orientation_fingerprint": fingerprint(run.research_state["exploration"]["orientation"]),
        "sources": [source_record(available[s["id"]]) for s in supplied["sources"]],
        "claims": deepcopy(supplied.get("claims", [])),
        "read_context": deepcopy(supplied.get("read_context"))}
    exploration.update(run, orientation_context={**value, "fingerprint": fingerprint(value)})


def validate(session, run, supplied):
    from . import product_exploration as exploration

    available = exploration.sources(session, run)
    if supplied.get("original_question") != run.question or any(
            s["id"] not in available or s != source_record(available[s["id"]]) for s in supplied["sources"]):
        fail("The early source inputs changed during research.", 422, "invalid_evidence")


def local_current(session, run):
    """Check the saved early inputs, allowing independent later assessments to grow."""
    from . import product_exploration as exploration

    state = (run.research_state or {}).get("exploration", {})
    orientation = state.get("orientation") or {}
    if not enabled(run) or orientation.get("status") != "ready":
        return True
    saved = state.get("orientation_context")
    if (not isinstance(saved, dict) or saved.get("contract") != CONTRACT
            or saved.get("fingerprint") != fingerprint({k: v for k, v in saved.items() if k != "fingerprint"})
            or saved.get("original_question") != run.question
            or saved.get("orientation_fingerprint") != fingerprint(orientation)):
        return False
    available = exploration.sources(session, run)
    recorded = saved.get("sources")
    if not isinstance(recorded, list) or not recorded or any(
            s.get("id") not in available or source_record(available[s["id"]]) != s for s in recorded):
        return False
    ids = {s["id"] for s in recorded}
    claims = saved.get("claims")
    if not isinstance(claims, list) or claims != informed.public_claims(
            session, run, ids, selected={c["id"] for c in claims}):
        return False
    old = saved.get("read_context")
    if old:
        supplied = {"sources": [{"id": s["id"], "sha256": s["sha256"],
            "excerpts": s["excerpts"]} for s in recorded]}
        current = informed.context(session, run, supplied)
        if (old.get("reading_limits") != current["reading_limits"]
                or any(a not in current["assessments"] for a in old.get("assessments", []))):
            return False
    return True


def selected_context(session, run, index, revision):
    state = run.research_state.get("exploration", {})
    orientation = state.get("orientation") or {}
    brief = orientation.get("briefing") or {}
    choices = brief.get("directions", [])
    if (not enabled(run) or orientation.get("status") != "ready" or orientation.get("revision") != revision
            or not local_current(session, run) or not brief.get("clarification", "").strip()
            or not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(choices)):
        return None
    return {"original_question": run.question, "orientation_revision": revision,
        "early_direction": index, "direction": choices[index],
        "context_fingerprint": state["orientation_context"]["fingerprint"]}


def select(session, run, current, index, revision, question):
    orientation = current.get("orientation") or {}
    value = selected_context(session, run, index, revision)
    if (current.get("briefing") or current["status"] == "evidence_changed"
            or orientation.get("status") != "ready" or value is None
            or value["direction"]["question"] != question):
        fail("This early clarification or its evidence changed. Refresh before choosing.", 409)
    return {"early_direction": index, "orientation_revision": revision,
        "early_fingerprint": fingerprint(value)}
