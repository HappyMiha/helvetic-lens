"""Deliver a balanced exploration and retain time to explain what was found."""
from . import product_source_recovery as recovery


def enabled(run):
    return (run.research_state or {}).get("exploration", {}).get("pacing_version") == 1


def operation_seconds(run, phase, settings):
    from .product_research_admission import unmetered
    from .research_contracts import SKILLS

    skill = SKILLS.get(phase)
    if unmetered(run) and skill is not None and skill.provider == "synthesis":
        return settings.apertus_timeout_seconds
    return 90


def remaining_seconds(run, phase, *, operation_seconds=90):
    from .product_research_admission import unmetered

    if unmetered(run):
        return operation_seconds
    data = run.research_state
    remaining = data["limits"]["active_seconds"] - data["used"].get("active_seconds", 0)
    if enabled(run) and phase != "brief":
        remaining -= min(60, data["limits"]["active_seconds"] / 4)
    return max(0, remaining)


def order(branch):
    state = branch.checkpoint
    # Control steps already derive from retained evidence. Ordinary directions
    # share turns before deeper branches consume their remaining capacity.
    # Explain a captured source before spending another turn retrieving more.
    # Once two sources exist, the early update can use the first assessment.
    control = {"brief": -4, "plan": -3, "orient": -2, "extract": -1}.get(branch.phase, 0)
    return (control, state.get("depth", 0), len(state.get("steps", [])),
            -state.get("priority", 6), branch.created_at, branch.id)


def settle(branch, state):
    if not state.get("read_as_found") or branch.phase not in {"gate", "read", "extract"}:
        return False
    from .product_document_reading import pending_read

    if pending_read(state):
        branch.phase = "read"
    elif state.get("extract_index", 0) < len(state.get("source_ids", [])):
        branch.phase = "extract"
    elif state.get("read_index", 0) < len(state.get("items", [])):
        branch.phase = "read"
    elif (len(state.get("items", [])) < recovery.selection_limit(state)
            and state.get("gate_index", 0) < len(state.get("candidates", []))):
        branch.phase = "gate"
    else:
        return False
    return True
