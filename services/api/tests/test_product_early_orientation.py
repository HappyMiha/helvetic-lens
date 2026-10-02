"""Durable early checkpoints with fictional adapters, not a semantic benchmark."""
import json
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_exploration import QUESTION, adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import decision_sources, jobs
from helvetic_lens.db import utcnow
from helvetic_lens.product_investigation_models import (
    Investigation,
    InvestigationBranch,
    InvestigationSource,
    WebResearchPolicy,
)
from helvetic_lens.product_models import DossierEntry


def until(client, service, root, run, status="ready"):
    for _ in range(80):
        value = client.get(root + "/investigations/" + run["id"]).json()
        if value["exploration"].get("orientation", {}).get("status") == status:
            return value
        assert value["status"] in {"queued", "running"}, value
        tick(service, run["id"])
    raise AssertionError("No early checkpoint reached")


def exclude(service, identity, source_id):
    with service.db.session() as session:
        source = session.get(InvestigationSource, source_id)
        session.add(DossierEntry(dossier_id=source.dossier_id, organization_id=source.organization_id,
            request_key=str(uuid4()), kind="source_review", actor_user_id=identity["user"]["id"],
            url=source.url, body="PRIVATE EXCLUSION REASON", data_json={"decision": "exclude", "revision": 1}))
        session.commit()


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_orientation_precedes_more_research_and_is_retained_beside_the_final_brief(signed, monkeypatch, product):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client, product)
    early = until(client, service, root, run)
    orientation = deepcopy(early["exploration"]["orientation"])
    assert early["status"] == "running" and early["exploration"]["briefing"] is None
    assert early["question"] == QUESTION
    assert len(trace["reads"]) == 2 and len(trace["orientations"]) == 1
    assert orientation["revision"] == early["exploration"]["revision"] > 0
    assert len(orientation["briefing"]["source_dependencies"]) == 2
    assert post(client, root + "/web-research", {"request_key": str(uuid4()), "expected_revision": 0,
        "enabled": True, "question": QUESTION, "cadence_hours": 24,
        "standing_public_query_confirmed": True}).status_code == 409
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready"
    assert final["exploration"]["orientation"] == orientation
    assert len(trace["reads"]) == 3 and len(trace["orientations"]) == 1
    assert trace["briefings"][0]["early_orientation"] == orientation["briefing"]
    assert "contradiction" in {f["basis"] for f in final["exploration"]["briefing"]["findings"]}
    assert final["research"]["used"]["model_calls"] <= final["research"]["limits"]["model_calls"]
    with service.db.session() as session:
        assert session.scalar(select(WebResearchPolicy)) is None


@pytest.mark.parametrize("mode", ["invalid_quote", "provider_failure"])
def test_failed_early_orientation_does_not_stop_or_repeat_remaining_research(signed, monkeypatch, mode):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    base = model.complete
    async def response(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if kwargs["response_schema"]["title"] == "EarlyOrientation":
            assert kwargs["budget"].max_seconds <= 45
            if mode == "provider_failure":
                raise RuntimeError("PRIVATE PROVIDER DETAIL")
            value = json.loads(result)
            value["interpretations"][0]["quote"] = "Fabricated passage, not evidence"
            return json.dumps(value)
        return result
    monkeypatch.setattr(model, "complete", response)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["orientation"]["status"] == "unavailable"
    assert final["exploration"]["orientation"]["briefing"] is None
    assert final["exploration"]["status"] == "ready"
    assert len(trace["reads"]) == 3 and len(trace["orientations"]) == 1
    assert "PRIVATE PROVIDER" not in json.dumps(final) and "Fabricated passage" not in json.dumps(final)
    assert "early_orientation" not in trace["briefings"][0]
    branch = next(b for b in final["branches"] if b["phase"] == "orient")
    assert len(branch["model_routes"]) == 1 and branch["model_routes"][0]["phase"] == "orient"


@pytest.mark.parametrize("during_model", [False, True])
def test_all_inputs_not_just_quoted_inputs_remain_source_contained(signed, monkeypatch, during_model):
    client, service, identity, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        session.add(InvestigationSource(dossier_id=saved.dossier_id, organization_id=saved.organization_id,
            investigation_id=saved.id, source_key="private", kind="uploaded_file", title="PRIVATE TITLE",
            url="", sha256="f" * 64, snapshot={"excerpts": [{"passage": "p1", "text": "PRIVATE EVIDENCE"}]}))
        session.commit()
    base = model.complete
    async def response(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if kwargs["response_schema"]["title"] == "EarlyOrientation":
            assert "PRIVATE" not in user
            if during_model:
                data = json.loads(user)
                # The response quotes only the first input, but its prose may
                # also depend on the second. Excluding that input must hide all.
                exclude(service, identity, data["sources"][1]["id"])
        return result
    monkeypatch.setattr(model, "complete", response)
    value = until(client, service, root, run, "unavailable" if during_model else "ready")
    if not during_model:
        exclude(service, identity, trace["orientations"][0]["sources"][1]["id"])
        value = client.get(root + "/investigations/" + run["id"]).json()
        assert value["exploration"]["orientation"]["status"] == "evidence_changed"
    assert value["exploration"]["orientation"]["briefing"] is None
    assert "PRIVATE" not in json.dumps(value["exploration"])
    final = complete(client, service, root + "/investigations", run)
    if during_model:
        assert final["status"] == "paused", 'Withdrawn synthesis inputs must stop the active worker'
        assert not trace.get("briefings"), 'No final model call may use withdrawn evidence'
    else:
        assert "early_orientation" not in trace["briefings"][0]


@pytest.mark.parametrize("constraint", ["one_source", "time"])
def test_early_checkpoint_needs_evidence_but_unmetered_research_has_no_elapsed_budget(signed, monkeypatch, constraint):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    if constraint == "one_source":
        original = decision_sources.safe_inspect
        async def inspect(settings, query, item, mode, **kwargs):
            if not item["url"].endswith("identity"):
                return {"status": "unavailable"}
            return await original(settings, query, item, mode, **kwargs)
        monkeypatch.setattr(decision_sources, "safe_inspect", inspect)
    root, run, _ = start(client)
    if constraint == "time":
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            saved.research_state = {**saved.research_state,
                "used": {"active_seconds": 320}}
            session.commit()
    final = complete(client, service, root + "/investigations", run)
    assert bool(trace.get("orientations")) == (constraint == "time")
    assert final["exploration"]["status"] == "ready"


@pytest.mark.parametrize("early", [False, True])
def test_pause_and_correct_before_final_brief_preserves_the_old_episode_and_replays_once(signed, monkeypatch, early):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    url = root + "/investigations/" + run["id"]
    current = until(client, service, root, run) if early else client.get(url).json()
    paused = post(client, url + "/control", {"action": "pause", "expected_revision": current["revision"]})
    assert paused.status_code == 200, paused.text
    command = {"request_key": str(uuid4()), "expected_revision": paused.json()["exploration"]["revision"],
        "question": "Investigate a different foundation's identity.", "public_query_confirmed": True}
    assert command["expected_revision"] > current["exploration"]["revision"]
    assert post(client, url + "/exploration/reply", {**command,
        "expected_revision": current["exploration"]["revision"]}).status_code in {409, 422}
    new = post(client, url + "/exploration/reply", command)
    assert new.status_code == 202, new.text
    assert post(client, url + "/exploration/reply", command).json()["id"] == new.json()["id"]
    old = client.get(url).json()
    assert old["question"] == QUESTION and old["status"] == "paused"
    assert old["exploration"].get("orientation") == current["exploration"].get("orientation")
    complete(client, service, root + "/investigations", new.json())
    plan_input = [v["input"] for v in trace["models"] if v["phase"] == "ResearchPlan"][-1]
    assert plan_input["question"] == command["question"]
    # A corrected question is the authority for new planning. The unconfirmed
    # earlier interpretation is retained for reading, not promoted to intent.
    assert "previous_public_orientation" not in plan_input
    assert client.get(root + "/investigations").json()["total"] == 2
    assert post(client, url + "/control", {"action": "resume", "expected_revision": old["revision"]}).status_code == 409


def test_pause_during_early_model_fences_the_result_and_allows_correction(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    url = root + "/investigations/" + run["id"]
    base = model.complete
    async def response(system, user, **kwargs):
        result = await base(system, user, **kwargs)
        if kwargs["response_schema"]["title"] == "EarlyOrientation":
            current = client.get(url).json()
            assert post(client, url + "/control", {"action": "pause", "expected_revision": current["revision"]}).status_code == 200
        return result
    monkeypatch.setattr(model, "complete", response)
    value = complete(client, service, root + "/investigations", run)
    assert value["status"] == "paused"
    assert value["exploration"]["orientation"]["briefing"] is None
    assert post(client, url + "/exploration/reply", {"request_key": str(uuid4()),
        "expected_revision": value["exploration"]["revision"], "question": "Correct the intended organisation.",
        "public_query_confirmed": True}).status_code == 202


def test_interrupted_orientation_request_is_not_automatically_repeated(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    until(client, service, root, run, "scheduled")
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        job = jobs.claim(session, saved.job_id, "interrupted-early")
        job.heartbeat_at = utcnow() - timedelta(hours=1)
        branch = session.scalar(select(InvestigationBranch).where(InvestigationBranch.investigation_id == saved.id,
            InvestigationBranch.phase == "orient"))
        branch.checkpoint = {**branch.checkpoint, "iterative": True, "inflight": "reserved-before-crash",
            "steps": [{"id": "reserved-before-crash", "phase": "orient", "status": "running"}]}
        saved.research_state = {**saved.research_state, "used": {**saved.research_state["used"],
            "model_calls": saved.research_state["used"]["model_calls"] + 1}}
        session.commit()
    with service.db.session() as session:
        jobs.reconcile(session, 30)
        session.commit()
    value = complete(client, service, root + "/investigations", run)
    assert not trace.get("orientations")
    assert value["exploration"]["orientation"]["status"] == "unavailable"
    assert value["exploration"]["status"] == "ready"
    assert any(step["status"] == "interrupted" for b in value["branches"] for step in b["steps"])
