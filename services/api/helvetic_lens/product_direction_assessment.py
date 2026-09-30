"""A selected early goal assessed in the existing final request and reader."""
from copy import deepcopy

from pydantic import Field, PrivateAttr

from . import legal_profiles
from . import product_early_clarification as clarification
from . import product_exploration as exploration
from . import product_informed_research as informed
from . import product_question_renewal as renewal
from .config import DomainError
from .product_api import fail
from .product_operations import fingerprint

CONTRACT = "selected-direction-assessment/v1"
SYSTEM = """direction_assessment_target identifies the exact early research goal
the user chose. In this SAME briefing optionally return direction_assessment with
its selection unchanged. It has no saved-question ID. Assess the chosen question,
not merely the user's possible intent. Its earlier_context is historical untrusted
wording, AI rationale and an earlier passage, not confirmation of identity or a
new source. Cite ONLY this episode's supplied READ sources/excerpts for the answer.
Use possible_answer, partial, conflicting or not_found IN THE MATERIAL READ.
Every substantive point needs exact support/counterevidence/context citations.
A possible answer needs support. Conflict needs distinct supporting and contrary
passages. Tangential material may justify not_found with cited context, never proof
of absence. Preserve limitations, ambiguity, jurisdiction, analogy and contrary
evidence. Do not infer an answer from counts, completed work or the earlier quote.
These are tentative AI assessments, not truth or human acceptance. The assessment
is the concise primary conclusion; keep background in findings. If no assessment
can be made, return null and retain a valid cited briefing, without inventing facts
or requesting more work. No hidden reasoning or assumed monitoring consent.
"""


class Selection(legal_profiles.Input):
    investigation_id: str = Field(min_length=36, max_length=36)
    orientation_revision: int = Field(ge=1, strict=True)
    direction_index: int = Field(ge=0, le=2, strict=True)


class DirectionAssessment(exploration.AssessmentOutcome):
    selection: Selection


class DirectionBriefing(exploration.Briefing):
    model_config = {**exploration.Briefing.model_config, "title": "Briefing"}
    direction_assessment: DirectionAssessment | None = None
    _direction_unavailable: bool = PrivateAttr(default=False)


class RenewedDirectionBriefing(renewal.RenewalBriefing):
    direction_assessment: DirectionAssessment | None = None
    _direction_unavailable: bool = PrivateAttr(default=False)


def enabled(run):
    state = (run.research_state or {}).get("exploration", {})
    return state.get("direction_assessment_contract") == CONTRACT and "early_direction" in (state.get("previous") or {})


def target(session, run):
    context = clarification.context(session, run)
    if not enabled(run) or not context or context.get("status") != "ready":
        fail("The selected direction is no longer available.", 422, "invalid_evidence")
    return {"contract": CONTRACT, "selection": {k: context[k] for k in
        ("investigation_id", "orientation_revision", "direction_index")},
        "question": run.question, "earlier_context": context}


def prepare(session, run, supplied):
    if not enabled(run):
        return
    supplied["direction_assessment_target"] = target(session, run)
    available = exploration.sources(session, run)
    supplied["sources"] = [clarification.source_record(available[s["id"]]) for s in supplied["sources"]]
    supplied["claims"] = []
    informed.prepare(session, run, supplied)
    validate_inputs(session, run, supplied)


def validate_inputs(session, run, supplied):
    if supplied.get("direction_assessment_target") != target(session, run) or not informed.enabled(run):
        fail("The selected direction context changed.", 422, "invalid_evidence")
    clarification.validate(session, run, supplied)
    informed.validate(session, run, supplied)
    if supplied.get("claims") != informed.public_claims(session, run, {s["id"] for s in supplied["sources"]}):
        fail("The direction assessment claim context changed.", 422, "invalid_evidence")


def input_current(session, run, supplied):
    if "direction_assessment_target" not in supplied:
        return True
    try:
        validate_inputs(session, run, supplied)
    except DomainError:
        return False
    return True


def apply(session, run, supplied, result, value):
    if "direction_assessment_target" not in supplied:
        return
    validate_inputs(session, run, supplied)
    selected = supplied["direction_assessment_target"]
    draft = getattr(result, "direction_assessment", None)
    bound = None
    if draft is not None and not getattr(result, "_direction_unavailable", False):
        try:
            if draft.selection.model_dump() != selected["selection"]:
                fail("Assessment does not match the chosen direction.", 422, "invalid_evidence")
            bound = exploration.validated_question_points(session, run, supplied, draft)
        except DomainError:
            # Optional output errors are recoverable; changed shared inputs are not.
            validate_inputs(session, run, supplied)
    if bound is not None:
        value["assessment"] = {**bound, "contract": CONTRACT,
            "question": selected["question"], "investigation_id": run.id,
            "selected_from_investigation_id": selected["selection"]["investigation_id"]}
    else:
        value["selected_direction_assessment"] = {"status": "unavailable"}
    # The whole briefing saw these inputs even when its optional answer failed.
    context = {k: deepcopy(supplied[k]) for k in
        ("original_question", "direction_assessment_target", "sources", "claims", "read_context")}
    exploration.update(run, direction_assessment_context={**context, "fingerprint": fingerprint(context)})


def current(session, run):
    state = (run.research_state or {}).get("exploration", {})
    context = state.get("direction_assessment_context")
    if context is None:
        return not (enabled(run) and state.get("briefing"))
    if context.get("fingerprint") != fingerprint({k: v for k, v in context.items() if k != "fingerprint"}):
        return False
    return input_current(session, run, context)
