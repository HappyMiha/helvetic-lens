"""Actual saved reflection progress, distinct from ongoing work and final conclusions."""

import json
from copy import deepcopy
from datetime import datetime

import pytest
from sqlalchemy import select
from test_product_branch_assessment import configured
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import product_exploration as exploration
from helvetic_lens.product_investigation_models import (
    DossierClaim,
    Investigation,
    InvestigationEvent,
    InvestigationSource,
)


def setup(signed, monkeypatch, product="legal"):
    root, run, trace, requests = configured(signed, monkeypatch, product)
    model = signed[3]
    base = model.complete

    async def respond(system, user, **kwargs):
        value = json.loads(await base(system, user, **kwargs))
        data = json.loads(user)
        if kwargs["response_schema"]["title"] == "Reflection" and not value.get("assessment"):
            target = data["branch_assessment_question"]
            source = data["sources"][0]
            value["assessment"] = {
                "question_id": target["question_id"], "status": "partial",
                "points": [{"statement": "The fictional registry identifies a possible entity, not the full answer.",
                    "evidence": [{"source_id": source["id"], "quote": source["excerpts"][0]["text"],
                        "locator": "p1", "role": "support"}]}],
                "limitations": ["Only this branch's retained passages were considered."],
            }
        return json.dumps(value)

    monkeypatch.setattr(model, "complete", respond)
    return root, run, trace, requests


def advance(service, run, after=0):
    for _ in range(70):
        tick(service, run["id"])
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            value = exploration.projection(session, saved)
            update = value.get("research_update")
            if update and update["event_sequence"] > after:
                assert value["briefing"] is None
                return value
            assert saved.status not in {"completed", "failed", "cancelled"}, value
    pytest.fail("No actual assessment checkpoint was produced")


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_saved_events_order_successive_updates_and_final_brief_takes_over(signed, monkeypatch, product):
    client, service, _, _ = signed
    root, run, trace, requests = setup(signed, monkeypatch, product)
    first = advance(service, run)["research_update"]
    second_view = advance(service, run, first["event_sequence"])
    second = second_view["research_update"]
    assert second["question_id"] != first["question_id"]
    assert datetime.fromisoformat(second["saved_at"]) >= datetime.fromisoformat(first["saved_at"])
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        records = list(session.scalars(select(InvestigationEvent).where(
            InvestigationEvent.investigation_id == saved.id,
            InvestigationEvent.kind == "question_assessment_saved").order_by(InvestigationEvent.sequence)))
        assert [r.sequence for r in records] == [first["event_sequence"], second["event_sequence"]]
        assert [r.detail["question_id"] for r in records] == [first["question_id"], second["question_id"]]
        assert all("claims" not in r.detail and "assessment" not in r.detail for r in records)
        data = deepcopy(saved.research_state)
        data["questions"].reverse()
        saved.research_state = data
        session.commit()
        assert exploration.projection(session, saved)["research_update"] == second
        stored = deepcopy(saved.research_state)
        revision, sequence = saved.revision, saved.event_sequence
    url = root + "/investigations/" + run["id"]
    for _ in range(2):
        read = client.get(url).json()
        assert read["exploration"]["research_update"] == second
        assert "research_update_contract" not in json.dumps(read)
        assert "research_update" not in json.dumps(read["research"])
        assert "research_update" not in json.dumps(read["plans"])
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert saved.research_state == stored and (saved.revision, saved.event_sequence) == (revision, sequence)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready"
    assert final["exploration"]["research_update"] is None
    assert len(requests) == 2 and len(trace["queries"]) == 2
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert [q["branch_assessment"]["research_update"] for q in saved.research_state["questions"]] == [
            {k: v for k, v in item.items() if k != "question_id"} for item in (second, first)]


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("action", ["pause", "cancel"])
def test_saved_result_survives_controls_without_claiming_work_is_running(signed, monkeypatch, product, action):
    client, service, _, _ = signed
    root, run, trace, requests = setup(signed, monkeypatch, product)
    update = advance(service, run)["research_update"]
    url = root + "/investigations/" + run["id"]
    before = client.get(url).json()
    response = post(client, url + "/control", {"action": action, "expected_revision": before["revision"]})
    assert response.status_code == 200, response.text
    value = response.json()["exploration"]
    assert value["research_update"] == update
    assert value["current_activity"]["status"] == ("paused" if action == "pause" else "finished")
    counts = (len(trace["queries"]), len(requests))
    assert client.get(url).json()["exploration"]["research_update"] == update
    assert (len(trace["queries"]), len(requests)) == counts
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
    client.cookies.clear()
    denied = client.get(url)
    assert denied.status_code == 401 and update["question_id"] not in denied.text


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("change", ["rights", "hash", "claim_status", "claim_text"])
def test_changed_evidence_hides_the_promoted_assessment(signed, monkeypatch, product, change):
    client, service, identity, _ = signed
    root, run, _, _ = setup(signed, monkeypatch, product)
    first = advance(service, run)["research_update"]
    update = advance(service, run, first["event_sequence"])["research_update"] if change.startswith("claim") else first
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        q = next(q for q in saved.research_state["questions"] if q["id"] == update["question_id"])
        receipt = q["branch_assessment"]
        source_id = receipt["source_dependencies"][0]["source_id"]
        if change == "hash":
            session.get(InvestigationSource, source_id).sha256 = "b" * 64
        elif change.startswith("claim"):
            claim = session.get(DossierClaim, receipt["claims"][0]["id"])
            if change == "claim_status":
                claim.status = "SUPPORTED" if claim.status != "SUPPORTED" else "CONTESTED"
            else:
                claim.statement = "PRIVATE changed statement"
        session.commit()
    if change == "rights":
        exclude(service, identity, source_id)
    value = client.get(root + "/investigations/" + run["id"]).json()["exploration"]
    if change == "claim_status":
        assert value["research_update"] == first
        assert [a["question_id"] for a in value["question_assessments"]["assessments"]] == [first["question_id"]]
        assert value["question_assessments"]["outdated"] == 1
    else:
        assert value["research_update"] is None
        assert not value["question_assessments"].get("assessments")
    assert "PRIVATE changed" not in json.dumps(value)


@pytest.mark.parametrize("case", ["legacy", "missing", "invalid"])
def test_no_event_or_time_is_invented_for_legacy_or_rejected_output(signed, monkeypatch, case):
    client, service, _, _ = signed
    root, run, _, _ = configured(signed, monkeypatch, invalid={"missing": "missing", "invalid": "quote"}.get(case))
    if case == "legacy":
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            data = deepcopy(saved.research_state)
            data["exploration"].pop("research_update_contract")
            saved.research_state = data
            session.commit()
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["research_update"] is None
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert not any(q.get("branch_assessment", {}).get("research_update") for q in saved.research_state["questions"])
        assert not list(session.scalars(select(InvestigationEvent).where(
            InvestigationEvent.investigation_id == saved.id,
            InvestigationEvent.kind == "question_assessment_saved")))
