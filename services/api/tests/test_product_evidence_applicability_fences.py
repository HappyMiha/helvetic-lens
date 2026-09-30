"""Optional scope checks preserve valid evidence and existing execution boundaries."""
import json
from copy import deepcopy

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_clarification import pause
from test_product_evidence_applicability import setup, start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_selected_direction import choose

from helvetic_lens import product_evidence_applicability as applicability
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
from helvetic_lens.product_models import ProductDossier


@pytest.mark.parametrize("mode", ["missing", "shape", "quote", "source", "requested", "dimension", "source_detail", "unresolved"])
def test_unknown_or_invalid_optional_scope_does_not_discard_valid_extraction(signed, monkeypatch, mode):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model, mode=mode)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    assert len(final["claims"]) == 2 and "legal targeted" not in trace["queries"]
    supplied = next(r["input"] for r in reversed(trace["requests"]) if r["phase"] == "Briefing")
    readings = supplied["evidence_applicability"]["readings"]
    assert len(readings) == 2
    status = "unassessed" if mode == "missing" else "assessed" if mode == "unresolved" else "unavailable"
    assert {r["status"] for r in readings} == {status}
    assert all(c["relation"] == "unresolved" for r in readings for c in r["checks"])
    assert "PRIVATE" not in json.dumps(final) and "PRIVATE" not in json.dumps(supplied)
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]


@pytest.mark.parametrize("change,when", [("source", "during"), ("rights", "during"), ("title", "during"),
    ("question", "during"), ("policy", "during"), ("record", "after"), ("missing_reading", "after"), ("missing_policy", "after")])
def test_changed_policy_question_or_passage_fences_the_actual_work_and_answer(signed, monkeypatch, change, when):
    client, service, _, model = signed
    changed = False

    def mutate(source_id=None):
        nonlocal changed
        if changed:
            return
        changed = True
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            state = deepcopy(saved.research_state)
            if change in {"source", "rights", "title"}:
                source = session.get(InvestigationSource, source_id)
                if change == "source":
                    source.snapshot = {**source.snapshot, "excerpts": [{"passage": "p1", "text": "PRIVATE MUTATED SOURCE"}]}
                elif change == "rights":
                    source.snapshot = {**source.snapshot, "allow_discovery": False}
                else:
                    source.title = "PRIVATE MUTATED TITLE"
            elif change == "question":
                state["questions"][0]["question"] = "PRIVATE MUTATED QUESTION"
            elif change == "policy":
                state["exploration"]["applicability_policy"]["primary_policy"] = "unknown/v1"
            elif change == "record":
                state["exploration"]["applicability_readings"][0]["checks"][0]["reason"] = "PRIVATE MUTATED REASON"
            elif change == "missing_reading":
                state["exploration"].pop("applicability_readings")
            else:
                state["exploration"].pop("applicability_policy")
            saved.research_state = state
            session.commit()

    def during(data, phase):
        if when == "during" and phase == "ResearchExtraction":
            mutate(data["source"]["id"])

    trace = setup(monkeypatch, service, model, callback=during)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    if when == "after":
        assert final["exploration"]["status"] == "ready"
        mutate()
        final = client.get(root + "/investigations/" + run["id"]).json()
    else:
        assert final["status"] == "paused"
        assert "legal targeted" not in trace["queries"]
        with service.db.session() as session:
            assert applicability.state(session.get(Investigation, run["id"]))["applicability_inputs_invalid"]
    assert final["exploration"]["status"] == "evidence_changed"
    assert not final["exploration"].get("briefing")
    # A currently permitted source remains inspectable; derived stale output does not.
    derived = {k: v for k, v in final["exploration"].items() if k != "sources"}
    assert "PRIVATE MUTATED" not in json.dumps(derived)


def until_reading(service, run):
    for _ in range(35):
        tick(service, run["id"])
        with service.db.session() as session:
            state = applicability.state(session.get(Investigation, run["id"]))
            if state.get("applicability_readings"):
                return deepcopy(state)
    raise AssertionError("No saved scope reading")


def test_pause_resume_keeps_policy_and_private_subject_is_never_researched(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        dossier = session.get(ProductDossier, saved.dossier_id)
        dossier.domain_context_json = {"values": {"jurisdictions": ["PRIVATE SUBJECT CANARY"]}}
        session.commit()
    before = until_reading(service, run)
    stopped = pause(client, root, run)
    count = len(trace["requests"])
    tick(service, run["id"])
    assert len(trace["requests"]) == count
    response = post(client, root + "/investigations/" + run["id"] + "/control",
        {"action": "resume", "expected_revision": stopped["revision"]})
    assert response.status_code == 200
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready"
    with service.db.session() as session:
        after = applicability.state(session.get(Investigation, run["id"]))
        assert after["applicability_policy"] == before["applicability_policy"]
        assert after["applicability_readings"][:1] == before["applicability_readings"][:1]
    assert len(trace["reads"]) == len(set(trace["reads"])) == 3
    assert "PRIVATE SUBJECT" not in json.dumps(trace)


def test_source_budget_exhaustion_does_not_turn_a_contextual_source_into_direct_support(signed, monkeypatch):
    client, service, _, model = signed
    exhausted = False

    def during(data, phase):
        nonlocal exhausted
        if phase == "Reflection" and not exhausted:
            exhausted = True
            with service.db.session() as session:
                saved = session.get(Investigation, run["id"])
                state = deepcopy(saved.research_state)
                state["used"]["source_fetches"] = state["limits"]["source_fetches"]
                saved.research_state = state
                session.commit()

    trace = setup(monkeypatch, service, model, callback=during)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready"
    assert "source_fetches" in final["research"]["stops"]
    assert not any(url.endswith("/targeted") for url in trace["reads"])
    assert not any(f["basis"] == "direct" for f in final["exploration"]["briefing"]["findings"])
    assert final["research"]["used"]["source_fetches"] == final["research"]["limits"]["source_fetches"]


def test_legacy_episode_does_not_acquire_new_scope_metadata(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    root, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        state = deepcopy(saved.research_state)
        state["exploration"].pop("applicability_contract")
        saved.research_state = state
        session.commit()
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready"
    assert all("evidence_applicability" not in r["input"] for r in trace["requests"])
    assert len(trace["queries"]) == 2


def test_typed_descendant_cannot_keep_answer_after_parent_scope_changed(signed, monkeypatch):
    client, service, _, model = signed
    setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready"
    with service.db.session() as session:
        saved = session.get(Investigation, parent["id"])
        state = deepcopy(saved.research_state)
        state["exploration"]["applicability_policy"]["primary_policy"] = "changed-policy"
        saved.research_state = state
        session.commit()
    assert client.get(root + "/investigations/" + child["id"]).json()["exploration"]["status"] == "evidence_changed"
