"""Source-bound selected-question assessments through real durable episodes."""

import hashlib
import json
from copy import deepcopy

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import capture_for, child_adapters, extra_source
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_saved_check import command, prepared, url

from helvetic_lens import decision_search, decision_sources
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource


def assessment_adapters(
    monkeypatch, model, trace, old, status, *, invalid=None, callback=None, unavailable=False
):
    capture = capture_for(old, "repeat" if status == "possible_answer" else "new")
    requests = child_adapters(monkeypatch, model, trace, capture, unavailable=unavailable)
    search, base = decision_search.federated_retrieve, model.complete
    other_text = "The fictional recipient record reports a different payment amount for the same period."
    other = {
        "url": "https://example.org/counterevidence",
        "sha256": hashlib.sha256(other_text.encode()).hexdigest(),
        "excerpts": [{"text": other_text, "passage": "p1"}],
    }

    async def search_two(*args):
        result = await search(*args)
        if status == "conflicting":
            result["items"].append(
                {
                    "id": "counter",
                    "title": "Recipient record",
                    "summary": "Public fixture",
                    "url": other["url"],
                }
            )
        return result

    async def read(*args, **kwargs):
        item = other if args[2]["url"] == other["url"] else capture
        trace["reads"].append(item["url"])
        return {"status": "unavailable"} if unavailable else {"status": "complete", **item}

    async def respond(system, user, **kwargs):
        raw = await base(system, user, **kwargs)
        data = json.loads(user)
        if not data.get("assessment_question"):
            return raw
        result = json.loads(raw)
        sources = data["sources"]

        def ref(s, role):
            return {"source_id": s["id"], "quote": s["excerpts"][0]["text"], "locator": "p1", "role": role}

        roles = (
            ["support", "counterevidence"]
            if status == "conflicting"
            else ["context" if status == "not_found" else "support"]
        )
        points = [
            {"statement": s["excerpts"][0]["text"], "evidence": [ref(s, role)]}
            for s, role in zip(sources, roles)
        ]
        result["assessment"] = {
            "question_id": data["assessment_question"]["question_id"],
            "status": status,
            "points": points,
            "limitations": [
                "The scripted records cannot establish complete coverage or settle other periods."
            ],
        }
        a = result["assessment"]
        if invalid == "question":
            a["question_id"] = "another-question"
        if invalid == "source":
            a["points"][0]["evidence"][0]["source_id"] = "unsupplied-source"
        if invalid == "quote":
            a["points"][0]["evidence"][0]["quote"] = "This fabricated quotation must not survive."
        if invalid == "uncited":
            a["points"][0]["evidence"] = []
        if invalid == "conflict":
            a["status"] = "conflicting"
        if invalid == "missing":
            result.pop("assessment")
        if callback:
            callback(data)
        return json.dumps(result)

    monkeypatch.setattr(decision_search, "federated_retrieve", search_two)
    monkeypatch.setattr(decision_sources, "safe_inspect", read)
    monkeypatch.setattr(model, "complete", respond)
    return requests


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("status", ["possible_answer", "partial", "conflicting", "not_found"])
def test_selected_question_has_cited_assessment_and_retained_history(signed, monkeypatch, product, status):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch, product)
    original = deepcopy(old["exploration"]["briefing"])
    requests = assessment_adapters(monkeypatch, model, trace, old, status)
    body = command(old)
    child = post(client, url(root, old), body).json()
    assert post(client, url(root, old), body).json()["id"] == child["id"]
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    assessment = final["exploration"]["briefing"]["assessment"]
    assert assessment["contract"] == "selected-question-assessment/v1"
    assert assessment["question_id"] == body["follow_up_id"] and assessment["question"] == body["question"]
    assert (
        assessment["investigation_id"] == child["id"]
        and assessment["selected_from_investigation_id"] == old["id"]
    )
    assert assessment["status"] == status and assessment["limitations"]
    request = next(r for r in requests if r["phase"] == "Briefing")
    assert request["input"]["assessment_question"]["question"] == body["question"]
    assert request["input"]["selected_public_check"]["question_id"] == body["follow_up_id"]
    assert "not merely the user" in request["system"]
    actual = {s["id"]: s for s in final["sources"]}
    for point in assessment["points"]:
        for ref in point["evidence"]:
            assert ref["sha256"] == actual[ref["source_id"]]["sha256"]
            assert ref["quote"] in [e["text"] for e in actual[ref["source_id"]]["snapshot"]["excerpts"]]
    if status == "possible_answer":
        assert final["exploration"]["capture_progress"]["counts"]["repeated"] == 1
    if status == "conflicting":
        assert {r["role"] for p in assessment["points"] for r in p["evidence"]} == {
            "support",
            "counterevidence",
        }
    assert client.get(root + "/investigations/" + old["id"]).json()["exploration"]["briefing"] == original
    assert (
        client.get(root + "/investigations/" + child["id"]).json()["exploration"]["briefing"]["assessment"]
        == assessment
    )
    assert post(client, url(root, old), body).json()["id"] == child["id"]
    assert client.get(root + "/web-research").json()["policy"]["enabled"] is False


@pytest.mark.parametrize("invalid", ["question", "source", "quote", "uncited", "conflict", "missing"])
def test_invalid_assessment_never_becomes_a_briefing(signed, monkeypatch, invalid):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    assessment_adapters(monkeypatch, model, trace, old, "partial", invalid=invalid)
    child = post(client, url(root, old), command(old)).json()
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["briefing"] is None
    assert final["exploration"]["status"] == "unavailable"
    assert final["sources"]  # Preserved primary material is still readable.


@pytest.mark.parametrize("when", ["during", "after", "hash", "unquoted"])
def test_current_inputs_fence_assessment_and_private_material_is_excluded(signed, monkeypatch, when):
    client, service, identity, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)

    def callback(data):
        if when == "during":
            exclude(service, identity, data["sources"][0]["id"])

    requests = assessment_adapters(monkeypatch, model, trace, old, "partial", callback=callback)
    child = post(client, url(root, old), command(old)).json()
    tick(service, child["id"])
    with service.db.session() as session:
        saved = session.get(Investigation, child["id"])
        extra_source(session, saved, private=True)
        unquoted = extra_source(session, saved)
        unquoted_id = unquoted.id
        session.commit()
    final = complete(client, service, root + "/investigations", child)
    assert "PRIVATE CANARY" not in json.dumps(requests)
    if when != "during":
        assessment = final["exploration"]["briefing"]["assessment"]
        ids = {r["source_id"] for p in assessment["points"] for r in p["evidence"]}
        # Earliest supplied extra source is quoted; revoke the other supplied input.
        target = (
            next(s["id"] for s in final["sources"] if s["kind"] == "public_source" and s["id"] not in ids)
            if when == "unquoted"
            else next(iter(ids))
        )
        if when == "hash":
            with service.db.session() as session:
                source = session.get(InvestigationSource, target)
                source.sha256 = "f" * 64
                session.commit()
        else:
            exclude(service, identity, target)
        final = client.get(root + "/investigations/" + child["id"]).json()
    assert final["exploration"]["briefing"] is None
    assert final["exploration"]["status"] == "evidence_changed"
    assert "assessment" not in json.dumps(final["exploration"])
    assert unquoted_id


def test_no_read_and_preexisting_typed_episode_keep_honest_contracts(signed, monkeypatch):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    requests = assessment_adapters(monkeypatch, model, trace, old, "not_found", unavailable=True)
    child = post(client, url(root, old), command(old)).json()
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "no_evidence" and final["exploration"]["briefing"] is None
    assert not requests


def test_legacy_typed_briefing_does_not_acquire_an_assessment(signed, monkeypatch):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    requests = child_adapters(monkeypatch, model, trace, capture_for(old, "new"))
    child = post(client, url(root, old), command(old)).json()
    tick(service, child["id"])
    with service.db.session() as session:
        run = session.get(Investigation, child["id"])
        state = deepcopy(run.research_state)
        state["exploration"].pop("assessment_contract")
        run.research_state = state
        session.commit()
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready"
    assert "assessment" not in final["exploration"]["briefing"]
    assert all("assessment_question" not in r["input"] for r in requests)
