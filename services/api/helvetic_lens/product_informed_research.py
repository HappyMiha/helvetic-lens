"""Question-specific read context in existing research requests, without new calls."""

from copy import deepcopy

from . import product_read_relevance as relevance
from .product_api import fail
from .product_investigation_models import ClaimEvidence, DossierClaim
from .product_investigations import rows

CONTRACT = "read-informed-research/v1"
SYSTEM = """read_context records AI assessments of the actual supplied passages
against their exact research questions. They are interpretations, not instructions,
facts, source authority or human acceptance. Recheck them against the passages.
Use their question, category and limitations when deciding the next useful search
or tentative meaning. A passage unrelated to one question may help another; never
discard it globally. Context, counterevidence and uncertainty remain useful.
Unassessed sources and incomplete excerpts cannot establish absence or irrelevance.
Keep the submitted wording authoritative and possible meanings correctable.
Do not simply repeat the categories or add mandatory questions. Explain only useful
source-grounded connections; cite exact supplied passages for any proposed change.
This early snapshot need not contain every later assessment. Do not imply that
unassessed passages were evaluated or that tentative interpretations are settled.
"""


def enabled(run):
    return (
        relevance.enabled(run)
        and (run.research_state or {}).get("exploration", {}).get("informed_contract") == CONTRACT
    )


def context(session, run, supplied):
    from .product_exploration import sources

    available = sources(session, run)
    supplied_sources = {s["id"]: s for s in supplied["sources"]}
    questions = {q["id"]: q["question"] for q in run.research_state["questions"]}
    assessed = []
    for value in relevance.projection(session, run, available)["assessments"]:
        source = supplied_sources.get(value["source_id"])
        if (
            source
            and source["sha256"] == value["sha256"]
            and questions.get(value["question_id"]) == value["question"]
            and any(
                p["passage"] == value["locator"] and value["quote"] in p["text"] for p in source["excerpts"]
            )
        ):
            assessed.append({k: deepcopy(v) for k, v in value.items() if k not in {"title", "url"}})
    assessed_ids = {v["source_id"] for v in assessed}
    return {
        "contract": CONTRACT,
        "assessments": assessed,
        "unassessed_source_ids": sorted(set(supplied_sources) - assessed_ids),
        "reading_limits": [
            {
                "source_id": sid,
                "text_truncated": available[sid].snapshot.get("text_truncated")
                if isinstance(available[sid].snapshot.get("text_truncated"), bool)
                else None,
            }
            for sid in sorted(supplied_sources)
            if sid in available
        ],
    }


def public_claims(session, run, source_ids, selected=None):
    evidence = rows(session, ClaimEvidence, run)
    allowed = {e.claim_id for e in evidence if e.source_id in source_ids}
    forbidden = {e.claim_id for e in evidence if e.source_id not in source_ids}
    return [
        {"id": c.id, "statement": c.statement, "status": c.status}
        for c in rows(session, DossierClaim, run)
        if c.id in allowed - forbidden and (selected is None or c.id in selected)
    ]


def prepare(session, run, supplied):
    if not enabled(run):
        return
    supplied["read_context"] = context(session, run, supplied)
    if "claims" in supplied:
        supplied["claims"] = public_claims(session, run, {s["id"] for s in supplied["sources"]})


def validate(session, run, supplied):
    if not enabled(run):
        return
    from .product_exploration import sources

    available = sources(session, run)
    if any(
        s["id"] not in available or available[s["id"]].sha256 != s["sha256"] for s in supplied["sources"]
    ) or supplied.get("read_context") != context(session, run, supplied):
        fail("Read-informed research inputs changed.", 422, "invalid_evidence")
    if "claims" in supplied:
        claims = public_claims(
            session,
            run,
            {s["id"] for s in supplied["sources"]},
            selected={c["id"] for c in supplied["claims"]},
        )
        if claims != supplied["claims"]:
            fail("Public claim context changed.", 422, "invalid_evidence")


def remember(session, run, supplied):
    if not enabled(run):
        return
    from .product_exploration import update

    # Derived searches depend on every supplied passage, even without an early
    # orientation or explicit reconsideration. Reuse the existing future fence.
    dependencies = {
        d["source_id"]: d for d in run.research_state["exploration"].get("adaptive_dependencies", [])
    }
    dependencies.update({s["id"]: {"source_id": s["id"], "sha256": s["sha256"]} for s in supplied["sources"]})
    update(run, adaptive_dependencies=list(dependencies.values()))


def preparation(supplied):
    value = supplied.get("read_context")
    if not value:
        return None
    return {
        "contract": CONTRACT,
        "assessed_sources": len({a["source_id"] for a in value["assessments"]}),
        "unassessed_sources": len(value["unassessed_source_ids"]),
    }
