"""Typed saved-check continuation through actual worker turns and source fences."""
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_adaptive_orientation import PASSAGE, QUERY, adaptive
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import QUESTION, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import product_exploration_followups as followups
from helvetic_lens import product_iterative_research as research
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource, WebResearchPolicy
from helvetic_lens.product_operations import fingerprint


def prepared(client, service, model, monkeypatch, product="legal"):
    trace = adaptive(monkeypatch, service, model)
    root, run, _ = start(client, product)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        saved.research_state = {**saved.research_state, "limits": {**saved.research_state["limits"], "depth": 1}}
        session.commit()
    value = complete(client, service, root + "/investigations", run)
    check = value["exploration"]["next_check"]
    assert check and check["quote"] and QUERY not in trace["queries"]
    return root, value, trace


def command(value):
    check = value["exploration"]["next_check"]
    return {"request_key": str(uuid4()), "expected_revision": value["exploration"]["revision"],
        "question": check["question"], "follow_up_id": check["question_id"], "public_query_confirmed": True}


def url(root, value):
    return root + "/investigations/" + value["id"] + "/exploration/reply"


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_selected_saved_query_is_searched_without_replanning_and_keeps_history(signed, monkeypatch, product):
    client, service, _, model = signed
    root, value, trace = prepared(client, service, model, monkeypatch, product)
    body = command(value)
    response = post(client, url(root, value), body)
    assert response.status_code == 202, response.text
    new = response.json()
    assert post(client, url(root, value), body).json()["id"] == new["id"]
    assert new["exploration"]["continuation"]["question_id"] == body["follow_up_id"]
    assert new["exploration"]["continuation"]["original_question"] == QUESTION
    plans_before = len([v for v in trace["models"] if v["phase"] == "ResearchPlan"])
    final = complete(client, service, root + "/investigations", new)
    assert final["exploration"]["status"] == "ready"
    assert trace["queries"].count(QUERY) == 1 and trace["queries"][-1] == QUERY
    assert trace["reads"][-1] == "https://example.org/reconciliation"
    assert final["sources"][0]["snapshot"]["excerpts"][0]["text"] == PASSAGE
    assert len([v for v in trace["models"] if v["phase"] == "ResearchPlan"]) == plans_before
    assert trace["briefings"][-1]["selected_public_check"]["question_id"] == body["follow_up_id"]
    assert final["research"]["objective"] == body["question"]
    assert len(final["research"]["questions"]) == 1
    old = client.get(root + "/investigations/" + value["id"]).json()
    assert old["question"] == QUESTION and old["sources"] == value["sources"]
    assert old["exploration"]["briefing"] == value["exploration"]["briefing"]
    assert old["exploration"]["next_check"] is None
    assert post(client, url(root, value), {**body, "request_key": str(uuid4())}).status_code == 409
    assert client.get(root + "/investigations").json()["total"] == 2
    with service.db.session() as session:
        assert session.scalar(select(WebResearchPolicy)) is None


def test_selection_is_exact_exclusive_current_and_edit_authorized(signed, monkeypatch):
    client, service, _, model = signed
    root, value, _ = prepared(client, service, model, monkeypatch)
    body = command(value)
    for changes, status in [({"direction": 0}, 422), ({"follow_up_id": str(uuid4())}, 409),
            ({"question": "A hidden replacement public query"}, 409), ({"expected_revision": 1}, 409),
            ({"public_query_confirmed": False}, 422), ({"follow_up_id": "not-a-uuid"}, 422)]:
        result = post(client, url(root, value), {**body, **changes})
        assert result.status_code == status, result.text
    assert client.get(root + "/investigations").json()["total"] == 1
    client.cookies.clear()
    assert client.post(url(root, value), json=body).status_code in {401, 403}


@pytest.mark.parametrize("when", ["before_selection", "queued", "during_search", "after_completion"])
def test_unquoted_source_dependency_stays_current_across_episodes(signed, monkeypatch, when):
    client, service, identity, model = signed
    root, value, trace = prepared(client, service, model, monkeypatch)
    body = command(value)
    source_id = value["exploration"]["orientation"]["briefing"]["source_dependencies"][0]["source_id"]
    assert source_id != value["exploration"]["next_check"]["source"]["id"]
    if when == "before_selection":
        exclude(service, identity, source_id)
        assert post(client, url(root, value), body).status_code == 409
        assert client.get(root + "/investigations/" + value["id"]).json()["exploration"]["next_check"] is None
        return
    response = post(client, url(root, value), body)
    assert response.status_code == 202, response.text
    new = response.json()
    if when == "during_search":
        from helvetic_lens import decision_search
        base = decision_search.federated_retrieve
        async def retrieve(*args, **kwargs):
            result = await base(*args, **kwargs)
            exclude(service, identity, source_id)
            return result
        monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
    elif when == "after_completion":
        complete(client, service, root + "/investigations", new)
        exclude(service, identity, source_id)
    else:
        exclude(service, identity, source_id)
    result = complete(client, service, root + "/investigations", new)
    assert result["exploration"]["continuation"] == {"status": "evidence_changed"}
    assert result["exploration"]["briefing"] is None and result["research"] is None
    assert result["branches"] == result["plans"] == []
    if when == "queued":
        assert QUERY not in trace["queries"]
    if when != "after_completion":
        assert result["status"] == "paused" and "https://example.org/reconciliation" not in trace["reads"]
    # A lost response replays the same saved episode even after source revocation;
    # it neither starts another job nor restores withheld derived context.
    replay = post(client, url(root, value), body)
    assert replay.status_code == 202 and replay.json()["id"] == new["id"]
    assert replay.json()["exploration"]["continuation"]["status"] == "evidence_changed"


@pytest.mark.parametrize("change", ["hash", "rights", "selection", "finished", "legacy_context"])
def test_saved_check_disappears_when_its_contract_is_no_longer_valid(signed, monkeypatch, change):
    client, service, _, model = signed
    root, value, _ = prepared(client, service, model, monkeypatch)
    body = command(value)
    with service.db.session() as session:
        saved = session.get(Investigation, value["id"])
        state = deepcopy(saved.research_state)
        q = next(q for q in state["questions"] if q["id"] == body["follow_up_id"])
        if change in {"hash", "rights"}:
            source = session.get(InvestigationSource, q["trigger"]["source_id"])
            if change == "hash":
                source.sha256 = "e" * 64
            else:
                source.snapshot = {**source.snapshot, "allow_discovery": False}
        elif change == "selection":
            q["question"] = "A later changed question, not the one selected."
        elif change == "finished":
            q["status"] = "evidence_found"
        else:
            state["exploration"]["previous"] = {"investigation_id": str(uuid4()), "briefing_revision": 1}
        saved.research_state = state
        session.commit()
    assert post(client, url(root, value), body).status_code == 409
    assert client.get(root + "/investigations").json()["total"] == 1


def test_typed_ancestry_revocation_and_legacy_reply_fingerprint(signed, monkeypatch):
    client, service, identity, model = signed
    root, old, _ = prepared(client, service, model, monkeypatch)
    response = post(client, url(root, old), command(old))
    new = complete(client, service, root + "/investigations", response.json())
    # Build a stored second-generation unresolved check from its actual new
    # capture. This exercises the ancestry contract, not another model benchmark.
    with service.db.session() as session:
        saved = session.get(Investigation, new["id"])
        source = session.scalar(select(InvestigationSource).where(InvestigationSource.investigation_id == saved.id))
        state = deepcopy(saved.research_state)
        q = deepcopy(next(q for q in old["research"]["questions"] if q.get("reconsideration")))
        q.update(id=str(uuid4()), query="River Trust later payment record", query_key=research.query_key("River Trust later payment record"),
            question="Was the later instalment paid?", branch_id=None, status="open",
            trigger={"source_id":source.id,"sha256":source.sha256,"quote":PASSAGE,"locator":"p1"})
        state["questions"].append(q)
        state["exploration"]["adaptive_dependencies"]=[{"source_id":source.id,"sha256":source.sha256}]
        saved.research_state = state
        session.commit()
    new = client.get(root + "/investigations/" + new["id"]).json()
    third = post(client, url(root, new), command(new))
    assert third.status_code == 202, third.text
    third = third.json()
    exclude(service, identity, old["exploration"]["next_check"]["source"]["id"])
    tick(service, third["id"])
    last = client.get(root + "/investigations/" + third["id"]).json()
    assert last["status"] == "paused" and last["exploration"]["continuation"]["status"] == "evidence_changed"
    # Existing free-text correction remains a separate explicit authority. The
    # new optional selector must not alter old idempotency fingerprints.
    body = {"request_key":str(uuid4()),"expected_revision":last["exploration"]["revision"],
        "question":"A corrected public question with independent authority.","public_query_confirmed":True}
    correction = post(client, url(root, last), body)
    assert correction.status_code == 202, correction.text
    with service.db.session() as session:
        saved = session.get(Investigation, last["id"])
        assert saved.research_state["exploration"]["reply_fingerprint"] == fingerprint({**body,"direction":None,"actor":identity["user"]["id"]})
        assert followups.reference(session.get(Investigation, correction.json()["id"])).get("follow_up_id") is None
    assert post(client, url(root, last), body).json()["id"] == correction.json()["id"]


def test_a_running_episode_cannot_be_forked_through_saved_check_selection(signed, monkeypatch):
    from test_product_adaptive_orientation import until_change
    client, service, _, model = signed
    adaptive(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        saved.research_state = {**saved.research_state, "limits": {**saved.research_state["limits"], "depth": 1}}
        session.commit()
    value = until_change(client, service, root, run)
    assert value["status"] == "running" and value["exploration"]["next_check"] is None
    q = next(q for q in value["research"]["questions"] if q.get("reconsideration"))
    response = post(client, url(root, value), {"request_key":str(uuid4()),
        "expected_revision":value["exploration"]["revision"],"question":q["question"],
        "follow_up_id":q["id"],"public_query_confirmed":True})
    assert response.status_code == 409
    assert client.get(root + "/investigations").json()["total"] == 1


def test_withdrawn_ancestor_hides_a_child_early_interpretation_too(signed, monkeypatch):
    client, service, identity, model = signed
    root, value, _ = prepared(client, service, model, monkeypatch)
    child = post(client, url(root, value), command(value)).json()
    child = complete(client, service, root + "/investigations", child)
    # Exercise the persisted early-view gate with this child's genuine capture;
    # scripted storage is not an additional generated/model quality result.
    with service.db.session() as session:
        saved = session.get(Investigation, child["id"])
        source = session.scalar(select(InvestigationSource).where(InvestigationSource.investigation_id == saved.id))
        state = deepcopy(saved.research_state)
        state["exploration"]["orientation"]={"status":"ready","briefing":{
            "interpretations":[{"source_id":source.id,"sha256":source.sha256,"quote":PASSAGE,"locator":"p1",
                "meaning":"A tentative view informed by the earlier selected context.","why":"A later source mentions instalments.","signal":"possible"}],
            "uncertainties":["The explanation remains tentative."],
            "source_dependencies":[{"source_id":source.id,"sha256":source.sha256}]}}
        saved.research_state=state
        session.commit()
    assert client.get(root + "/investigations/" + child["id"]).json()["exploration"]["orientation"]["briefing"]
    exclude(service, identity, value["exploration"]["next_check"]["source"]["id"])
    result=client.get(root + "/investigations/" + child["id"]).json()
    assert result["exploration"]["orientation"]["status"]=="evidence_changed"
    assert result["exploration"]["orientation"]["briefing"] is None
