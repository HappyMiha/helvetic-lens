"""Optional bad model output never replaces the earlier cited checkpoint."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_adaptive_orientation import QUERY
from test_product_dossiers import signed as signed
from test_product_iterative_research import complete
from test_product_question_renewal import configured

from helvetic_lens.product_investigation_models import Investigation

CANARY = "PRIVATE INVALID OPTIONAL OUTPUT"


def response_adapter(monkeypatch, model, transform):
    base = model.complete
    calls = []

    async def respond(system, user, **kwargs):
        title = kwargs["response_schema"]["title"]
        calls.append(title)
        raw = await base(system, user, **kwargs)
        data = json.loads(user)
        value = json.loads(raw)
        changed = transform(title, data, value)
        return changed if isinstance(changed, str) else json.dumps(value)

    monkeypatch.setattr(model, "complete", respond)
    return calls


def unchanged(service, run, before):
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        questions = saved.research_state["questions"]
        assert [q["branch_assessment"] for q in questions if q.get("branch_assessment")] == before
        assert not any(q.get("branch_assessment_history") for q in questions)
        assert CANARY not in json.dumps(saved.research_state)
        assert saved.research_state["exploration"].get("renewal_context")


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("invalid", ["shape", "target", "quote", "query"])
def test_bad_optional_update_preserves_cited_summary_without_more_work(signed, monkeypatch, product, invalid):
    client, service, _, model = signed
    root, run, trace, observed, before = configured(signed, monkeypatch, product, invalid=invalid)

    def transform(title, data, value):
        if title == "Briefing" and invalid == "shape":
            value["question_renewals"] = {"unexpected": CANARY}

    calls = response_adapter(monkeypatch, model, transform)
    final = complete(client, service, root + "/investigations", run)
    brief = final["exploration"]["briefing"]
    assert final["exploration"]["status"] == "ready" and brief["findings"]
    assert brief["question_updates"] == {"status": "unavailable"}
    assert observed and before and calls.count("Briefing") == 1
    assert final["research"]["used"]["model_calls"] == len(calls)
    assert len(trace["queries"]) == 3 and QUERY not in trace["queries"]
    assert final["exploration"]["next_check"] is None
    assert CANARY not in json.dumps(final)
    assert "_renewal_unavailable" not in json.dumps(final)
    assert "renewal_recovery_contract" not in json.dumps(final["exploration"])
    assert client.get(root + "/investigations").json()["total"] == 1
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
    unchanged(service, run, before)


def test_two_valid_updates_then_wrong_target_apply_none(signed, monkeypatch):
    client, service, _, model = signed
    root, run, _, observed, _ = configured(signed, monkeypatch)
    before = []

    def transform(title, data, value):
        if title == "Reflection" and data.get("branch_assessment_question") and not value.get("assessment"):
            s = data["sources"][0]
            value["assessment"] = {
                "question_id": data["branch_assessment_question"]["question_id"],
                "status": "partial",
                "points": [
                    {
                        "statement": "A read passage leaves the question open.",
                        "evidence": [
                            {
                                "source_id": s["id"],
                                "quote": s["excerpts"][0]["text"],
                                "locator": "p1",
                                "role": "context",
                            }
                        ],
                    }
                ],
                "limitations": ["Later context remains unchecked."],
            }
        if title == "Briefing":
            targets = data["question_renewal_targets"]
            assert len(targets) >= 2
            draft = value["question_renewals"][0]
            draft.pop("further_check", None)
            value["question_renewals"] = [
                {**deepcopy(draft), "question_id": t["question_id"]} for t in targets[:2]
            ]
            value["question_renewals"].append({**deepcopy(draft), "question_id": str(uuid4())})
            with service.db.session() as session:
                saved = session.get(Investigation, run["id"])
                before.extend(
                    deepcopy(q["branch_assessment"])
                    for q in saved.research_state["questions"]
                    if q.get("branch_assessment")
                )

    response_adapter(monkeypatch, model, transform)
    final = complete(client, service, root + "/investigations", run)
    assert observed and before
    assert final["exploration"]["briefing"]["question_updates"] == {"status": "unavailable"}
    unchanged(service, run, before)


@pytest.mark.parametrize("kind", ["quote", "shape"])
def test_pre_recovery_episode_keeps_original_failure_semantics(signed, monkeypatch, kind):
    client, service, _, model = signed
    root, run, _, observed, _ = configured(signed, monkeypatch, invalid="quote")
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        state = deepcopy(saved.research_state)
        state["exploration"].pop("renewal_recovery_contract")
        saved.research_state = state
        session.commit()

    def transform(title, data, value):
        if title == "Briefing" and kind == "shape":
            value["question_renewals"] = CANARY

    response_adapter(monkeypatch, model, transform)
    final = complete(client, service, root + "/investigations", run)
    assert observed and "question_renewal_recovery" not in observed[0]
    assert final["exploration"]["status"] == "unavailable"
    assert final["exploration"]["briefing"] is None


def test_invalid_base_citation_is_not_rescued_by_rejected_optional_output(signed, monkeypatch):
    client, service, _, model = signed
    root, run, _, observed, _ = configured(signed, monkeypatch)

    def transform(title, data, value):
        if title == "Briefing":
            value["question_renewals"] = CANARY
            value["findings"][0]["quote"] = "An invented main finding quotation"

    response_adapter(monkeypatch, model, transform)
    final = complete(client, service, root + "/investigations", run)
    assert observed and final["exploration"]["briefing"] is None
    assert final["exploration"]["status"] == "unavailable"
    assert CANARY not in json.dumps(final)
