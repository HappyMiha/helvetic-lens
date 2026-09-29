"""Actual continued worker episodes; scripted captures, not a semantic benchmark."""

import hashlib
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_adaptive_orientation import PASSAGE, QUERY
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import start
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_saved_check import command, prepared, url

from helvetic_lens import decision_search, decision_sources
from helvetic_lens import product_exploration_progress as progress
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
from helvetic_lens.product_investigations import snapshot


def child_adapters(monkeypatch, model, trace, capture, *, callback=None, unavailable=False):
    retrieve, base = decision_search.federated_retrieve, model.complete
    requests = []

    async def search(settings, query, *args):
        result = await retrieve(settings, query, *args)
        assert query == QUERY
        result["items"] = [
            {
                "id": "selected",
                "url": capture["url"],
                "title": "Current public capture",
                "summary": "Public fixture",
            }
        ]
        return result

    async def read(*args, **kwargs):
        trace["reads"].append(capture["url"])
        return {"status": "unavailable"} if unavailable else {"status": "complete", **capture}

    async def respond(system, user, **kwargs):
        data, phase = json.loads(user), kwargs["response_schema"]["title"]
        requests.append({"phase": phase, "input": data, "system": system})
        if phase == "ResearchExtraction":
            quote = data["source"]["excerpts"][0]["text"]
            return json.dumps(
                {"claims": [{"statement": quote, "relation": "CONTEXT", "quote": quote, "locator": "p1"}]}
            )
        if phase == "Reflection":
            return json.dumps(
                {
                    "outcome": "The capture was read; the broader payment question remains unresolved.",
                    "gaps": [],
                }
            )
        result = await base(system, user, **kwargs)
        if callback:
            callback(phase, data)
        return result

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", read)
    monkeypatch.setattr(model, "complete", respond)
    return requests


def capture_for(value, mode):
    source = value["sources"][0]
    text = source["snapshot"]["excerpts"][0]["text"] if mode in {"repeat", "mirror"} else PASSAGE
    address = source["url"] if mode in {"repeat", "changed"} else "https://example.org/current-check"
    return {
        "url": address,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "excerpts": [{"text": text, "passage": "p1"}],
    }


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize(
    "mode,expected",
    [("repeat", "repeated"), ("changed", "changed_capture"), ("mirror", "repeated"), ("new", "unmatched")],
)
def test_real_continuation_compares_captures_and_informs_each_model_phase(
    signed, monkeypatch, product, mode, expected
):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch, product)
    old_copy = deepcopy(old["sources"])
    requests = child_adapters(monkeypatch, model, trace, capture_for(old, mode))
    body = command(old)
    child = post(client, url(root, old), body).json()
    assert post(client, url(root, old), body).json()["id"] == child["id"]
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["status"] == "ready"
    view = final["exploration"]["capture_progress"]
    assert view["status"] == "ready" and view["counts"][expected] == 1
    assert sum(view["counts"].values()) == 1
    assert view["scope"]["previous_captures"] == len(old_copy) and not view["scope"]["truncated"]
    item = view["items"][0]
    assert item["classification"] == expected
    assert item["current"]["investigation_id"] == child["id"]
    assert item["comparison"]["source_independence"] == "not_established"
    assert item["comparison"]["publication_and_effective_dates"] == "not_established_by_capture_metadata"
    if mode == "mirror":
        assert item["comparison"]["same_recorded_address"] is False
    if mode == "changed":
        assert item["comparison"]["content_hash_match"] is False
    if expected != "unmatched":
        assert item["previous"]["investigation_id"] == old["id"]
    assert {r["phase"] for r in requests} == {"ResearchExtraction", "Reflection", "Briefing"}
    for request in requests:
        assert request["input"]["capture_progress"]["counts"][expected] == 1
        assert "not proof of new facts or independent" in request["system"]
    assert final["exploration"]["briefing"]["uncertainties"]
    assert (
        final["research"]["questions"][0]["status"] == "evidence_found"
    )  # This is not an answered/accepted claim.
    assert trace["queries"].count(QUERY) == 1
    prior = client.get(root + "/investigations/" + old["id"]).json()
    assert prior["sources"] == old_copy and prior["exploration"]["capture_progress"] is None


def extra_source(session, run, *, private=False):
    text = (
        "PRIVATE CANARY"
        if private
        else "An additional public baseline capture not used by the earlier model."
    )
    item = {
        "title": text,
        "url": "https://example.org/private" if private else "https://example.org/extra-baseline",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "excerpts": [{"text": text, "passage": "p1"}],
        "kind": "uploaded_file",
        "allow_discovery": not private,
    }
    return snapshot(session, run, item, public=not private, captured=private)[0]


@pytest.mark.parametrize("when", ["queued", "during_brief", "after", "rights", "hash"])
def test_new_comparison_dependencies_fence_work_and_derived_text(signed, monkeypatch, when):
    client, service, identity, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    with service.db.session() as session:
        parent = session.get(Investigation, old["id"])
        extra = extra_source(session, parent)
        extra_id = extra.id
        assert extra_id not in {
            d["source_id"] for d in parent.research_state["exploration"]["adaptive_dependencies"]
        }
        session.commit()

    def callback(phase, data):
        if when == "during_brief" and phase == "Briefing":
            exclude(service, identity, extra_id)

    requests = child_adapters(monkeypatch, model, trace, capture_for(old, "new"), callback=callback)
    child = post(client, url(root, old), command(old)).json()
    tick(service, child["id"])  # Seed pins the comparison baseline before queued provider work.
    if when == "queued":
        exclude(service, identity, extra_id)
    final = complete(client, service, root + "/investigations", child)
    if when in {"after", "rights", "hash"}:
        assert final["exploration"]["briefing"]
        if when == "after":
            exclude(service, identity, extra_id)
        else:
            with service.db.session() as session:
                extra = session.get(InvestigationSource, extra_id)
                if when == "hash":
                    extra.sha256 = "f" * 64
                else:
                    extra.snapshot = {**extra.snapshot, "allow_discovery": False}
                session.commit()
        final = client.get(root + "/investigations/" + child["id"]).json()
    assert final["exploration"]["capture_progress"] == {"status": "evidence_changed"}
    assert final["exploration"]["briefing"] is None and final["research"] is None
    assert final["branches"] == final["plans"] == []
    if when in {"queued", "during_brief"}:
        assert final["status"] == "paused"
    if when == "queued":
        assert not requests and QUERY not in trace["queries"]


def test_no_successful_read_is_not_progress_or_an_answer(signed, monkeypatch):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    requests = child_adapters(monkeypatch, model, trace, capture_for(old, "new"), unavailable=True)
    child = post(client, url(root, old), command(old)).json()
    final = complete(client, service, root + "/investigations", child)
    assert final["exploration"]["capture_progress"]["scope"]["current_captures"] == 0
    assert not requests and final["exploration"]["briefing"] is None
    assert final["research"]["questions"][0]["status"] == "unresolved"


def test_comparison_limits_private_isolation_and_current_input_revocation(signed, monkeypatch):
    client, service, _, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    other_root, other, _ = start(client)
    with service.db.session() as session:
        parent = session.get(Investigation, old["id"])
        private = extra_source(session, parent, private=True)
        private_id = private.id
        unrelated = session.get(Investigation, other["id"])
        snapshot(
            session,
            unrelated,
            {**capture_for(old, "new"), "title": "Unrelated matching material"},
            public=True,
        )
        session.commit()
    monkeypatch.setattr(progress, "MAX_PREVIOUS", 1)
    requests = child_adapters(monkeypatch, model, trace, capture_for(old, "new"))
    child = post(client, url(root, old), command(old)).json()
    final = complete(client, service, root + "/investigations", child)
    view = final["exploration"]["capture_progress"]
    assert view["scope"]["truncated"] and view["scope"]["previous_captures"] == 1
    assert view["counts"]["unmatched"] == 1
    assert "PRIVATE CANARY" not in json.dumps(requests) and private_id not in json.dumps(view)
    assert other["id"] not in json.dumps(requests)
    with service.db.session() as session:
        saved = session.get(Investigation, child["id"])
        source = session.get(InvestigationSource, view["items"][0]["current"]["id"])
        assert source.id in {s["id"] for s in progress.state(saved)["input_dependencies"]}
        source.snapshot = {**source.snapshot, "allow_discovery": False}
        session.commit()
    final = client.get(root + "/investigations/" + child["id"]).json()
    assert final["exploration"]["capture_progress"] == {"status": "evidence_changed"}
    assert final["exploration"]["briefing"] is None
    assert client.get(other_root + "/investigations/" + other["id"]).status_code == 200


def test_unknown_capture_metadata_does_not_establish_novelty():
    current = {
        "id": str(uuid4()),
        "kind": "public_source",
        "url": "https://example.org/current",
        "sha256": "a" * 64,
        "captured_at": "2026-09-29",
    }
    old = {**current, "id": str(uuid4()), "url": "https://example.org/old", "sha256": None}
    assert progress.match(current, [old])["classification"] == "unestablished"
    assert progress.match({**current, "sha256": None}, [current])["classification"] == "unestablished"


def test_unquoted_current_capture_revoked_during_briefing_discards_output(signed, monkeypatch):
    from test_product_iterative_research import GRANT

    client, service, identity, model = signed
    root, old, trace = prepared(client, service, model, monkeypatch)
    original = next(s for s in old["sources"] if s["snapshot"]["excerpts"][0]["text"] == GRANT)
    first = {
        "url": original["url"],
        "sha256": original["sha256"],
        "excerpts": [{"text": GRANT, "passage": "p1"}],
    }
    second = capture_for(old, "new")
    requests = child_adapters(monkeypatch, model, trace, first)
    base_search, base_model = decision_search.federated_retrieve, model.complete
    observed = []

    async def search(*args):
        result = await base_search(*args)
        result["items"].append(
            {
                "id": "second",
                "title": "Unquoted later capture",
                "url": second["url"],
                "summary": "Another public fixture",
            }
        )
        return result

    async def read(settings, query, item, *args, **kwargs):
        trace["reads"].append(item["url"])
        return {"status": "complete", **(first if item["url"] == first["url"] else second)}

    async def respond(system, user, **kwargs):
        result = json.loads(await base_model(system, user, **kwargs))
        if kwargs["response_schema"]["title"] == "Briefing":
            data = json.loads(user)
            result["findings"] = result["findings"][:1]
            cited = {r["source_id"] for r in result["findings"] + result["directions"]}
            unquoted = next(s for s in data["sources"] if s["id"] not in cited)
            assert len(data["capture_progress"]["items"]) == 2
            observed.append(unquoted["id"])
            exclude(service, identity, unquoted["id"])
        return json.dumps(result)

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(decision_sources, "safe_inspect", read)
    monkeypatch.setattr(model, "complete", respond)
    child = post(client, url(root, old), command(old)).json()
    final = complete(client, service, root + "/investigations", child)
    early = [r for r in requests if r["phase"] == "EarlyOrientation"]
    assert len(early) == 1 and early[0]["input"]["capture_progress"]["scope"]["current_captures"] == 2
    assert "not proof of new facts or independent" in early[0]["system"]
    assert observed and final["status"] == "paused"
    assert final["exploration"]["capture_progress"] == {"status": "evidence_changed"}
    assert final["exploration"]["briefing"] is None
    assert final["exploration"]["orientation"]["briefing"] is None
    assert final["research"] is None
