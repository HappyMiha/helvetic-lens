"""Real durable worker with scripted public sources; not a live-domain evaluation."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import tick
from test_product_iterative_research import GRANT, RECIPIENT, complete, pipeline
from test_product_web_research import enable

from helvetic_lens import decision_sources
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource, WebResearchPolicy
from helvetic_lens.product_models import DossierEntry

QUESTION = "Alpin Foundation money — who receives it?"


def start(client, product="pharma"):
    command = {"request_key": str(uuid4()), "question": QUESTION, "public_query_confirmed": True}
    response = post(client, f"/api/products/{product}/explore", command)
    assert response.status_code == 202, response.text
    saved = response.json()
    return f'/api/products/{product}/dossiers/{saved["dossier_id"]}', saved["investigation"], command


def adapters(monkeypatch, service, model, *, invalid=False, unavailable=False):
    trace = pipeline(monkeypatch, service, model)
    base = model.complete

    async def complete_model(system, user, **kwargs):
        data = json.loads(user)
        title = kwargs["response_schema"]["title"]
        if title == "EarlyOrientation":
            trace.setdefault("orientations", []).append(data)
            source = data["sources"][0]
            return json.dumps({"interpretations": [{"source_id": source["id"],
                "quote": source["excerpts"][0]["text"], "locator": "p1",
                "meaning": "Alpin may refer to Alpine Foundation; the intended identity is unconfirmed.",
                "why": "The captured registry describes a similarly named foundation, which may explain the submitted words.",
                "signal": "possible"}], "uncertainties": ["Does the user mean this foundation and its grant recipients?"]})
        if title != "Briefing":
            value = json.loads(await base(system, user, **kwargs))
            if title == "ResearchPlan" and data["question"].startswith("Check River Trust"):
                assert "previous_public_briefing" in data
                for branch in value["branches"]:
                    branch["query"] = "River Trust recipient disclosure " + branch["query"]
            return json.dumps(value)
        trace["briefings"] = trace.get("briefings", []) + [data]
        if unavailable:
            raise RuntimeError("private provider error must not reach the user")
        sources = {s["excerpts"][0]["text"]: s for s in data["sources"]}
        def cite(text):
            return {"source_id": sources[text]["id"], "quote": text, "locator": "p1"}
        first = next(iter(sources))
        value = {"understanding": "Alpin may mean Alpine Foundation; this is a tentative interpretation you can correct.",
            "findings": [{**cite(text), "statement": text,
                "basis": "contradiction" if text == RECIPIENT else "direct"}
                for text in sources],
            "uncertainties": ["The identity intended by the user is not confirmed; reported amounts need reconciliation."],
            "clarification": "Should the next episode verify the recipient or the foundation's identity?",
            "directions": [{**cite(GRANT if GRANT in sources else first), "quote": "This quote is invented and must be rejected" if invalid else (GRANT if GRANT in sources else first),
                "question": "Check River Trust recipient disclosure for the reported grant.", "why": "Verify the recipient side of the captured record."},
                {**cite(first), "question": "Is Alpine Foundation the intended entity?", "why": "Check the tentative interpretation against registry records."}]}
        if data.get("assessment_question"):
            value["assessment"] = {"question_id": data["assessment_question"]["question_id"],
                "status": "partial", "points": [{"statement": first,
                    "evidence": [{**cite(first), "role": "context"}]}],
                "limitations": ["The scripted capture does not settle the full selected question."]}
        return json.dumps(value)

    monkeypatch.setattr(model, "complete", complete_model)
    return trace


def reply(value, **changes):
    return {"request_key": str(uuid4()), "expected_revision": value["exploration"]["revision"],
        "question": value["exploration"]["briefing"]["directions"][0]["question"],
        "direction": 0, "public_query_confirmed": True, **changes}


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_explore_read_brief_choose_and_explicit_monitoring(signed, monkeypatch, product):
    client, service, _, model = signed
    # This journey exercises two complete episodes; quota behavior is tested separately.
    service.environment_settings.decision_search_daily_limit = 100
    trace = adapters(monkeypatch, service, model)
    root, run, command = start(client, product)
    assert client.get(root).json()["exploration"]["investigation_id"] == run["id"]
    assert "research_monitoring" not in client.get(root).json()
    assert post(client, f"/api/products/{product}/explore", command).json()["investigation"]["id"] == run["id"]
    before = post(client, root + "/web-research", {"request_key": str(uuid4()), "expected_revision": 0,
        "enabled": True, "question": QUESTION, "cadence_hours": 24, "standing_public_query_confirmed": True})
    assert before.status_code == 409
    value = complete(client, service, root + "/investigations", run)
    assert value["question"] == QUESTION
    assert value["status"] == "completed", value["stop_reason"]
    brief = value["exploration"]
    assert brief["status"] == "ready", value
    assert len(trace["queries"]) == 3 and len(trace["reads"]) == 3
    assert "Alpin may mean Alpine" in brief["briefing"]["understanding"]
    assert {f["basis"] for f in brief["briefing"]["findings"]} == {"direct", "contradiction"}
    assert value["claims"][0]["status"] == "CONTESTED"
    assert "exploration" not in value["research"]
    with service.db.session() as session:
        assert session.scalar(select(WebResearchPolicy)) is None
        receipt = session.scalar(select(DossierEntry).where(DossierEntry.kind == "question_start"))
        assert not receipt.data_json["daily_public_research_confirmed"]
    # Absence of a reply creates no further episode or monitoring authority.
    assert client.get(root + "/investigations").json()["total"] == 1
    policy, _ = enable(client, root, question="Check the disclosed Alpine Foundation grant.")
    assert policy["policy"]["enabled"]
    url = root + "/investigations/" + run["id"] + "/exploration/reply"
    response = reply(value)
    assert post(client, url, {**response, "expected_revision": brief["revision"] + 1}).status_code == 409
    assert post(client, url, {**response, "question": "An altered invisible search question"}).status_code == 409
    chosen = post(client, url, response)
    assert chosen.status_code == 202, chosen.text
    new = chosen.json()
    assert post(client, url, response).json()["id"] == new["id"]
    assert post(client, url, {**response, "request_key": str(uuid4())}).status_code == 409
    assert post(client, url, {**response, "question": "Changed retry question"}).status_code == 409
    # A newer exploration must not revoke previously understood recurring scope.
    enable(client, root, enabled=False, question="Check the disclosed Alpine Foundation grant.")
    resumed, _ = enable(client, root, question="Check the disclosed Alpine Foundation grant.")
    assert resumed["policy"]["enabled"]
    continued = complete(client, service, root + "/investigations", new)
    assert continued["status"] == "completed", continued
    assert trace["queries"][3:].count("River Trust recipient disclosure Alpine Foundation legal identity") == 1, continued
    assert client.get(root + "/investigations").json()["total"] == 2
    assert client.get(root + "/investigations/" + run["id"]).json()["exploration"]["briefing"] == brief["briefing"]
    client.cookies.clear()
    assert client.post(url, json=response).status_code in {401, 403}
    assert client.get(root + "/investigations/" + run["id"]).status_code == 401


@pytest.mark.parametrize("mode", ["invalid", "unavailable", "no_sources"])
def test_no_fabricated_brief_and_corrected_question_recovers(signed, monkeypatch, mode):
    client, service, _, model = signed
    adapters(monkeypatch, service, model, invalid=mode == "invalid", unavailable=mode == "unavailable")
    if mode == "no_sources":
        async def unavailable(*args, **kwargs):
            return {"status": "unavailable"}
        monkeypatch.setattr(decision_sources, "safe_inspect", unavailable)
    root, run, _ = start(client)
    value = complete(client, service, root + "/investigations", run)
    assert value["exploration"]["briefing"] is None
    assert value["exploration"]["status"] in {"unavailable", "no_evidence"}
    assert "private provider error" not in json.dumps(value)
    assert "invented and must" not in json.dumps(value)
    result = post(client, root + "/investigations/" + run["id"] + "/exploration/reply", {
        "request_key": str(uuid4()), "question": "I meant another foundation in Geneva.",
        "expected_revision": value["exploration"]["revision"], "public_query_confirmed": True})
    assert result.status_code == 202, result.text


def test_pause_resume_and_new_public_consent_are_required(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    for consent in (False, "true", 1):
        assert post(client, "/api/products/legal/explore", {"request_key": str(uuid4()),
            "question": QUESTION, "public_query_confirmed": consent}).status_code == 422
    root, run, _ = start(client)
    url = root + "/investigations/" + run["id"]
    tick(service, run["id"])
    current = client.get(url).json()
    paused = post(client, url + "/control", {"action": "pause", "expected_revision": current["revision"]}).json()
    assert paused["status"] == "paused" and not trace["queries"]
    resumed = post(client, url + "/control", {"action": "resume", "expected_revision": paused["revision"]})
    assert resumed.status_code == 200, resumed.text
    value = complete(client, service, root + "/investigations", run)
    assert value["exploration"]["status"] == "ready"
    with service.db.session() as session:
        assert session.scalar(select(WebResearchPolicy)) is None
        assert session.scalar(select(Investigation)).question == QUESTION


@pytest.mark.parametrize("during_model", [False, True])
def test_private_evidence_and_current_exclusions_fence_the_briefing(signed, monkeypatch, during_model):
    client, service, identity, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        session.add(InvestigationSource(dossier_id=saved.dossier_id, organization_id=saved.organization_id,
            investigation_id=saved.id, source_key="private", kind="uploaded_file", title="PRIVATE TITLE",
            url="", sha256="a" * 64, snapshot={"excerpts": [{"passage": "p1", "text": "PRIVATE EVIDENCE"}]}))
        session.commit()

    def exclude():
        with service.db.session() as session:
            source = session.scalar(select(InvestigationSource).where(InvestigationSource.investigation_id == run["id"],
                InvestigationSource.kind == "public_source"))
            session.add(DossierEntry(dossier_id=source.dossier_id, organization_id=source.organization_id,
                request_key=str(uuid4()), kind="source_review", actor_user_id=identity["user"]["id"],
                url=source.url, body="PRIVATE REVIEW REASON", data_json={"decision": "exclude", "revision": 1}))
            session.commit()

    base = model.complete
    async def guarded(system, user, **kwargs):
        if kwargs["response_schema"]["title"] == "Briefing":
            assert "PRIVATE" not in user
            result = await base(system, user, **kwargs)
            if during_model:
                exclude()
            return result
        return await base(system, user, **kwargs)
    monkeypatch.setattr(model, "complete", guarded)
    value = complete(client, service, root + "/investigations", run)
    if during_model:
        # The early-informed reflection now pins the complete source context.
        # Its revocation is explicit and also withholds derived plans/questions.
        assert value["exploration"]["status"] == "evidence_changed"
        assert value["exploration"]["changes_unavailable"]
        assert value["research"] is None and value["plans"] == value["branches"] == []
    else:
        assert value["exploration"]["status"] == "ready"
        exclude()
        value = client.get(root + "/investigations/" + run["id"]).json()
        assert value["exploration"]["status"] == "evidence_changed"
    assert value["exploration"]["briefing"] is None
    assert "PRIVATE" not in json.dumps(value["exploration"])


def test_analysis_budget_keeps_one_request_for_an_honest_partial_briefing(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        saved.research_state = {**saved.research_state,
            "limits": {**saved.research_state["limits"], "model_calls": 3}}
        session.commit()
    value = complete(client, service, root + "/investigations", run)
    assert value["status"] == "paused"
    assert value["research"]["used"]["model_calls"] == 3
    assert "model_calls" in value["research"]["stops"]
    assert value["exploration"]["status"] == "ready", value
    assert value["sources"] and value["exploration"]["briefing"]["uncertainties"]
    assert not trace.get("orientations")
