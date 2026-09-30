"""Existing cross-branch candidate deduplication preserves an earlier scope check."""
from test_product_dossiers import signed as signed
from test_product_evidence_applicability import setup, start
from test_product_iterative_research import complete

from helvetic_lens import decision_search


def test_duplicate_candidate_does_not_repeat_read_or_invalidate_scope(signed, monkeypatch):
    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    original = decision_search.federated_retrieve

    async def repeat(settings, query, index, depth, product):
        result = await original(settings, query, index, depth, product)
        if query.endswith(" counter"):
            result["items"][0].update(url="https://example.org/legal/overview", title="Fictional legal overview")
        return result

    monkeypatch.setattr(decision_search, "federated_retrieve", repeat)
    root, run, _ = start(client)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["status"] == "ready", final["stop_reason"]
    assert trace["reads"].count("https://example.org/legal/overview") == 1
    assert "https://example.org/legal/targeted" in trace["reads"]
    assert "legal counter" in trace["queries"]
    assert len(final["sources"]) == 2
