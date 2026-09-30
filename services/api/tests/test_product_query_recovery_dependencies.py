"""Reformulation must not reuse queries derived from revoked public evidence."""

import json

import pytest
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import adapters, start
from test_product_investigations import tick
from test_product_iterative_research import complete

from helvetic_lens import decision_search
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import rows


@pytest.mark.parametrize("when", ["before", "during", "changed_before"])
def test_revoked_previous_query_dependency_never_launches_reformulated_search(signed, monkeypatch, when):
    client, service, identity, model = signed
    trace = adapters(monkeypatch, service, model)
    retrieve, base = decision_search.federated_retrieve, model.complete
    proposals = []
    source_id = None

    async def search(*args):
        result = await retrieve(*args)
        if "recipient disclosure" in args[1]:
            result["items"] = []
        return result

    async def model_call(system, user, **kwargs):
        if kwargs["response_schema"]["title"] != "QueryReformulation":
            return await base(system, user, **kwargs)
        proposals.append(json.loads(user))
        if when == "during":
            exclude(service, identity, source_id)
        return json.dumps({"query": "A distinct recipient record search"})

    monkeypatch.setattr(decision_search, "federated_retrieve", search)
    monkeypatch.setattr(model, "complete", model_call)
    root, run, _ = start(client)
    for _ in range(45):
        tick(service, run["id"])
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            branch = next(
                (b for b in rows(session, InvestigationBranch, saved) if b.phase == "reformulate"), None
            )
            if branch:
                assert branch.checkpoint["trigger"]
                source_id = branch.checkpoint["trigger"]["source_id"]
                break
    assert source_id, "A real evidence-derived query must reach the recovery checkpoint"
    if when == "before":
        exclude(service, identity, source_id)
    if when == "changed_before":
        with service.db.session() as session:
            session.get(InvestigationSource, source_id).sha256 = "0" * 64
            session.commit()
    value = complete(client, service, root + "/investigations", run)
    assert len(proposals) == int(when == "during")
    assert "A distinct recipient record search" not in trace["queries"]
    assert value["exploration"]["research_scope"]["status"] == "evidence_changed"
