"""Complete fictional research through native jobs; no live provider calls."""
import json

import pytest
from sqlalchemy import select
from test_product_dossiers import signed as signed
from test_product_exploration import adapters, start
from test_product_iterative_research import complete

from helvetic_lens import product_investigation_worker as worker
from helvetic_lens import product_iterative_steps as steps
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, WebResearchPolicy


@pytest.mark.parametrize("product", ["legal", "pharma"])
@pytest.mark.parametrize("slow", [False, True])
def test_exploration_balances_meanings_deepens_and_delivers_brief_within_budget(signed, monkeypatch, product, slow):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client, product)
    clock, calls = [0.0], []
    original = steps.execute

    async def measured(service, work, seconds):
        calls.append((work["phase"], work["query"], seconds))
        result = await original(service, work, seconds)
        cost = {"plan": 5, "search": 15, "gate": 8, "read": 35,
                "extract": 20, "reflect": 10, "orient": 7, "brief": 25}.get(work["phase"], 5)
        clock[0] += min(seconds, cost if slow else 1)
        return result

    monkeypatch.setattr(steps, "execute", measured)
    monkeypatch.setattr(worker, "perf_counter", lambda: clock[0])
    result = complete(client, service, root + "/investigations", run)
    assert result["exploration"]["status"] == "ready", result["stop_reason"]
    assert result["question"] == "Alpin Foundation money — who receives it?"
    assert len(trace["queries"]) >= 2
    assert "legal identity" in trace["queries"][0] and "grants report" in trace["queries"][1]
    assert len(trace["reads"]) >= 2
    assert any(phase == "brief" and seconds >= 25 for phase, _, seconds in calls)
    assert clock[0] <= 360
    # Source analysis is delivered before another source read in that branch.
    read_positions = [i for i, (phase, _, _) in enumerate(calls) if phase == "read"]
    for first, second in zip(read_positions, read_positions[1:]):
        if calls[first][1] == calls[second][1]:
            assert any(phase == "extract" for phase, _, _ in calls[first + 1:second])
    if not slow:
        assert "recipient disclosure" in trace["queries"][2]
        assert result["claims"][0]["status"] == "CONTESTED"
        assert {f["basis"] for f in result["exploration"]["briefing"]["findings"]} == {"direct", "contradiction"}
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert saved.research_state["limits"]["active_seconds"] == 360
        assert saved.research_state["used"]["active_seconds"] <= 360
        assert session.scalar(select(WebResearchPolicy)) is None
        branches = session.scalars(select(InvestigationBranch).where(InvestigationBranch.investigation_id == saved.id)).all()
        assert all(step["deadline_seconds"] <= 90 for b in branches for step in b.checkpoint.get("steps", []))
    assert "private provider error" not in json.dumps(result)


def test_final_time_is_retained_after_a_slow_capture_and_old_runs_keep_original_budget(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    from helvetic_lens import product_research_pacing as pacing
    from helvetic_lens.product_investigation_models import InvestigationSource

    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        # Current admission intentionally has no legacy episode allowance.
        # Exercise the old metered contract explicitly, not a new mission.
        legacy = {key: value for key, value in saved.research_state.items() if key not in {"admission", "mission"}}
        saved.research_state = {**legacy, "limits": {**legacy["limits"], "active_seconds": 360},
            "used": {"active_seconds": 300, "model_calls": 1}}
        assert pacing.remaining_seconds(saved, "read") == 0
        assert pacing.remaining_seconds(saved, "brief") == 60
        old = {**saved.research_state["exploration"]}
        old.pop("pacing_version")
        saved.research_state = {**saved.research_state, "exploration": old}
        assert pacing.remaining_seconds(saved, "read") == 60
        saved.research_state = {**saved.research_state, "exploration": {**old, "pacing_version": 1}}
        # Retained evidence alone cannot authorize a fabricated final answer.
        session.add(InvestigationSource(dossier_id=saved.dossier_id, organization_id=saved.organization_id,
            investigation_id=saved.id, source_key="fixture", kind="public_source", title="Fixture record",
            url="https://example.org/fixture", sha256="a" * 64,
            snapshot={"excerpts": [{"text": "A fictional retained record remains available.", "passage": "p1"}]}))
        session.commit()
    result = complete(client, service, root + "/investigations", run)
    assert result["exploration"]["status"] == "ready"
    assert result["status"] == "paused"
    assert result["exploration"]["briefing"]["findings"][0]["quote"] == "A fictional retained record remains available."


def test_accepted_source_is_read_and_analysed_before_gating_the_whole_candidate_list(signed, monkeypatch):
    client, service, _, model = signed
    adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    original, calls = steps.execute, []

    async def source_first(service, work, seconds):
        calls.append((work['phase'], work['query'], work.get('item', {}).get('url')))
        result = await original(service, work, seconds)
        if work['phase'] == 'search' and 'legal identity' in work['query']:
            # A useful first candidate followed by another allowed source.
            result['items'] = [result['items'][1], {
                'id': 'second-candidate', 'title': 'Recipient disclosure', 'summary': 'Public fixture candidate',
                'url': 'https://example.org/recipient',
            }]
        return result

    monkeypatch.setattr(steps, 'execute', source_first)
    result = complete(client, service, root + '/investigations', run)
    identity = [(phase, url) for phase, query, url in calls if 'legal identity' in query]
    first_read = next(i for i, (phase, _) in enumerate(identity) if phase == 'read')
    next_gate = next(i for i, (phase, url) in enumerate(identity) if phase == 'gate' and url.endswith('/recipient'))
    assert first_read < next_gate
    assert any(phase == 'extract' for phase, _ in identity[first_read:next_gate])
    assert result['exploration']['status'] == 'ready'


def test_overlapping_initial_results_do_not_spend_fetch_budget_on_skipped_reads(signed, monkeypatch):
    client, service, _, model = signed
    trace = adapters(monkeypatch, service, model)
    root, run, _ = start(client)
    original = steps.execute

    async def overlapping(service, work, seconds):
        result = await original(service, work, seconds)
        if work['phase'] == 'search':
            result['items'] = [{'id': 'shared', 'title': 'Alpine Foundation identity',
                'summary': 'Public fixture registry', 'url': 'https://example.org/identity'}]
        return result

    monkeypatch.setattr(steps, 'execute', overlapping)
    result = complete(client, service, root + '/investigations', run)
    assert result['exploration']['status'] == 'ready'
    assert trace['reads'] == ['https://example.org/identity']
    with service.db.session() as session:
        saved = session.get(Investigation, run['id'])
        assert saved.research_state['used']['source_fetches'] == 1
        branches = session.scalars(select(InvestigationBranch).where(InvestigationBranch.investigation_id == saved.id)).all()
        assert sum(step['phase'] == 'read' and step['status'] == 'unavailable'
            for b in branches for step in b.checkpoint.get('steps', [])) == 1
