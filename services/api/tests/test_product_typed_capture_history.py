"""Actual early/saved research ancestry; fictional public captures, no live probe."""
import hashlib
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from test_product_answer_next_check import setup as next_setup
from test_product_direction_assessment import setup as direction_setup
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_exploration import start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_saved_check import command, url
from test_product_selected_direction import choose

from helvetic_lens import decision_search, decision_sources
from helvetic_lens import product_exploration_progress as progress
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource


def observe(monkeypatch, model, *, callback=None):
    base = model.complete
    requests = []

    async def response(system, user, **kwargs):
        data = json.loads(user)
        result = await base(system, user, **kwargs)
        requests.append({"phase": kwargs["response_schema"]["title"], "input": deepcopy(data), "system": system})
        if callback:
            callback(requests[-1])
        return result

    monkeypatch.setattr(model, "complete", response)
    return requests


def change_reads(monkeypatch, mode):
    retrieve, inspect = decision_search.federated_retrieve, decision_sources.safe_inspect

    async def search(*args):
        result = await retrieve(*args)
        if mode in {"mirror", "new"}:
            for item in result["items"]:
                if not item["url"].endswith("/road"):
                    item["url"] = item["url"].replace("example.org/", "example.org/later-")
        return result

    async def read(settings, query, item, *args, **kwargs):
        original = {**item, "url": item["url"].replace("example.org/later-", "example.org/")}
        result = await inspect(settings, query, original, *args, **kwargs)
        result["url"] = item["url"]
        if mode in {"changed", "new"}:
            text = result["excerpts"][0]["text"] + " An additional public appendix was captured."
            result.update(sha256=hashlib.sha256(text.encode()).hexdigest(), excerpts=[{"text": text, "passage": "p1"}])
        return result

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", read)


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("mode,expected", [("repeat", "repeated"), ("changed", "changed_capture"), ("mirror", "repeated"), ("new", "unmatched")])
def test_early_choice_retains_comparison_in_actual_requests_and_reader(signed, monkeypatch, tmp_path, product, mode, expected):
    client, service, _, model = signed
    trace = direction_setup(monkeypatch, service, model)
    root, parent, _ = start(client, product)
    early, _, child, body = choose(client, service, root, parent)
    assert child["exploration"]["capture_progress"] is None
    before = len(trace["queries"]), len(trace["reads"])
    requests = observe(monkeypatch, model)
    change_reads(monkeypatch, mode)
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    view = final["exploration"]["capture_progress"]
    assert view["status"] == "ready" and view["contract"] == progress.CONTRACT
    assert view["scope"]["previous_episodes"] == 1
    assert view["scope"]["previous_captures"] == len(early["sources"])
    assert view["counts"][expected] >= 1 and not view["scope"]["truncated"]
    assert len(trace["queries"]) > before[0] and len(trace["reads"]) > before[1]
    phases = {r["phase"] for r in requests if r["input"].get("capture_progress")}
    assert {"ResearchExtraction", "Reflection", "EarlyOrientation", "Briefing"}.issubset(phases)
    assert sum(r["phase"] == "ResearchPlan" for r in requests) == 1
    assert sum(r["phase"] == "Briefing" for r in requests) == 1
    assert all(progress.SYSTEM in r["system"] for r in requests if r["input"].get("capture_progress"))
    assert requests[-1]["input"]["capture_progress"]["counts"][expected] >= 1
    old_ids = {s["id"] for s in early["sources"]}
    assert not old_ids.intersection(s["id"] for s in final["sources"])
    assert all(ref["source_id"] not in old_ids for point in final["exploration"]["briefing"]["assessment"]["points"] for ref in point["evidence"])
    assert final["exploration"]["briefing"]["assessment"]["limitations"]
    assert view["question_resolution"] == "not_established_by_capture_comparison"
    assert "capture_history_contract" not in json.dumps(final) and '"history"' not in json.dumps(view)
    with service.db.session() as session:
        run = session.get(Investigation, child["id"])
        saved = deepcopy(run.research_state), run.revision, run.event_sequence
        assert progress.state(run)["episodes"] == [parent["id"]]
    assert client.get(root + "/investigations/" + child["id"]).json()["exploration"]["capture_progress"] == view
    with service.db.session() as session:
        run = session.get(Investigation, child["id"])
        assert (run.research_state, run.revision, run.event_sequence) == saved
    assert post(client, url(root, parent), body).json()["id"] == child["id"]
    old = client.get(root + "/investigations/" + parent["id"]).json()
    assert old["exploration"]["orientation"] == early["exploration"]["orientation"]
    assert old["exploration"]["capture_progress"] is None
    assert not client.get(root + "/web-research").json()["policy"]["enabled"]
    (tmp_path / "typed-capture-reader.json").write_text(json.dumps(final))


@pytest.mark.parametrize("change,when", [("exclude", "queued"), ("title", "plan"), ("rights", "brief"), ("hash", "after"), ("capture_time", "after"), ("contract", "after"), ("baseline", "after"), ("ancestry", "after")])
def test_unquoted_history_dependencies_fence_inflight_and_saved_output(signed, monkeypatch, change, when):
    client, service, identity, model = signed
    trace = direction_setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    with service.db.session() as session:
        extra = extra_source(session, session.get(Investigation, parent["id"]))
        extra_id = extra.id
        session.commit()

    def mutate():
        if change == "exclude":
            exclude(service, identity, extra_id)
            return
        with service.db.session() as session:
            source = session.get(InvestigationSource, extra_id)
            if change == "title":
                source.title = "Changed earlier metadata"
            elif change == "rights":
                source.snapshot = {**source.snapshot, "allow_discovery": False}
            elif change == "hash":
                source.sha256 = "f" * 64
            elif change == "capture_time":
                source.created_at += timedelta(days=1)
            else:
                run = session.get(Investigation, child["id"])
                state = deepcopy(run.research_state)
                if change == "ancestry":
                    state["exploration"]["previous"].pop("early_direction")
                else:
                    state["exploration"].pop("capture_history_contract" if change == "contract" else "capture_comparison")
                run.research_state = state
            session.commit()

    def callback(request):
        if (when == "plan" and request["phase"] == "ResearchPlan") or (when == "brief" and request["phase"] == "Briefing"):
            mutate()

    requests = observe(monkeypatch, model, callback=callback)
    before = len(trace["queries"])
    tick(service, child["id"])
    with service.db.session() as session:
        assert extra_id in {s["id"] for s in progress.state(session.get(Investigation, child["id"]))["previous"]}
    if when == "queued":
        mutate()
    final = complete(client, service, root + "/investigations", child)
    if when == "after":
        assert final["exploration"]["briefing"]
        mutate()
        final = client.get(root + "/investigations/" + child["id"]).json()
    else:
        assert final["status"] == "paused"
    assert final["exploration"]["status"] == "evidence_changed"
    assert final["exploration"]["briefing"] is None and final["exploration"]["next_check"] is None
    assert final["research"] is None and final["plans"] == final["branches"] == []
    assert final["exploration"]["capture_progress"] in (None, {"status": "evidence_changed"})
    if when in {"queued", "plan"}:
        assert len(trace["queries"]) == before
        assert len(requests) == int(when == "plan")
    assert "PRIVATE EXCLUSION" not in json.dumps(final)
    client.cookies.clear()
    assert client.get(root + "/investigations/" + child["id"]).status_code == 401


@pytest.mark.parametrize("bounded", [False, True])
def test_mixed_typed_ancestry_keeps_limits_and_excludes_private_unrelated_material(signed, monkeypatch, bounded):
    client, service, _, model = signed
    next_setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent)
    with service.db.session() as session:
        extra_source(session, session.get(Investigation, parent["id"]), private=True)
        session.commit()
    _, _, grandchild, _ = choose(client, service, root, child)
    final = complete(client, service, root + "/investigations", grandchild)
    assert final["exploration"]["next_check"]["answer_link"]
    other_root, other, _ = start(client)
    with service.db.session() as session:
        unrelated = extra_source(session, session.get(Investigation, other["id"]))
        unrelated_id = unrelated.id
        session.commit()
    if bounded:
        monkeypatch.setattr(progress, "MAX_EPISODES", 1)
        monkeypatch.setattr(progress, "MAX_PREVIOUS", 1)
    requests = observe(monkeypatch, model)
    response = post(client, url(root, final), command(final))
    assert response.status_code == 202, response.text
    continued = complete(client, service, root + "/investigations", response.json())
    view = continued["exploration"]["capture_progress"]
    assert view["status"] == "ready"
    assert view["scope"]["previous_episodes"] == (1 if bounded else 3)
    assert view["scope"]["truncated"] is bounded
    if bounded:
        assert view["scope"]["previous_captures"] == 1
        monkeypatch.setattr(progress, "MAX_EPISODES", 8)
        assert client.get(root + "/investigations/" + continued["id"]).json()["exploration"]["capture_progress"] == view
    with service.db.session() as session:
        baseline = progress.state(session.get(Investigation, continued["id"]))
        assert baseline["episodes"] == ([grandchild["id"]] if bounded else [grandchild["id"], child["id"], parent["id"]])
    assert requests and all(r["phase"] != "ResearchPlan" for r in requests)
    assert "PRIVATE CANARY" not in json.dumps(requests) and unrelated_id not in json.dumps(requests)
    assert other["id"] not in json.dumps(view)
    assert client.get(other_root + "/investigations/" + other["id"]).status_code == 200


@pytest.mark.parametrize("mode", ["free_text", "legacy"])
def test_untyped_or_legacy_early_choice_does_not_acquire_a_baseline(signed, monkeypatch, mode):
    client, service, _, model = signed
    direction_setup(monkeypatch, service, model)
    root, parent, _ = start(client)
    _, _, child, _ = choose(client, service, root, parent, free_text=mode == "free_text")
    if mode == "legacy":
        with service.db.session() as session:
            run = session.get(Investigation, child["id"])
            state = deepcopy(run.research_state)
            state["exploration"].pop("capture_history_contract")
            run.research_state = state
            session.commit()
    requests = observe(monkeypatch, model)
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready"
    assert final["exploration"]["capture_progress"] is None
    assert all("capture_progress" not in r["input"] for r in requests)
