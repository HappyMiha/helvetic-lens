"""Transitive read context stays fenced even without an early interpretation."""

import json

import pytest
from test_product_branch_assessment import configured
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_iterative_research import complete
from test_product_question_assessment import assessment_adapters
from test_product_saved_check import command, url

from helvetic_lens import decision_search
from helvetic_lens.product_investigation_models import Investigation


@pytest.mark.parametrize("when", ["before_selection", "during_child_search"])
def test_unquoted_read_context_is_sealed_and_checked_through_ancestry(signed, monkeypatch, when):
    client, service, identity, model = signed
    root, run, trace, requests = configured(signed, monkeypatch)
    base = model.complete

    async def respond(system, user, **kwargs):
        if kwargs["response_schema"]["title"] == "EarlyOrientation":
            return "{}"
        return await base(system, user, **kwargs)

    monkeypatch.setattr(model, "complete", respond)
    with service.db.session() as session:
        extra = extra_source(session, session.get(Investigation, run["id"]))
        extra_id = extra.id
        session.commit()
    old = complete(client, service, root + "/investigations", run)
    assert old["exploration"]["next_check"]
    assert all(extra_id not in {s["id"] for s in request["sources"]} for request in requests)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        receipt = next(
            q["branch_assessment"] for q in saved.research_state["questions"] if q.get("branch_assessment")
        )
        assert extra_id in {d["source_id"] for d in receipt["source_dependencies"]}
        assert extra_id not in receipt["supplied_source_ids"]
    body = command(old)
    if when == "before_selection":
        exclude(service, identity, extra_id)
        assert post(client, url(root, old), body).status_code == 409
        assert client.get(root + "/investigations/" + old["id"]).json()["exploration"]["next_check"] is None
    else:
        assessment_adapters(monkeypatch, model, trace, old, "partial")
        child = post(client, url(root, old), body).json()
        search = decision_search.federated_retrieve

        async def retrieve(*args, **kwargs):
            value = await search(*args, **kwargs)
            exclude(service, identity, extra_id)
            return value

        monkeypatch.setattr(decision_search, "federated_retrieve", retrieve)
        final = complete(client, service, root + "/investigations", child)
        assert final["status"] == "paused" and not final["sources"]
        assert final["exploration"]["continuation"]["status"] == "evidence_changed"
        assert post(client, url(root, old), body).json()["id"] == child["id"]
    assert "branch_assessment" not in json.dumps(old["plans"])
