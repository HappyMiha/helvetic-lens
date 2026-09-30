"""Recovery cannot bypass current evidence, access or request binding."""

import json
from copy import deepcopy

import pytest
from test_product_briefing_recovery import CANARY, response_adapter
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_iterative_research import complete
from test_product_question_renewal import configured
from test_product_question_renewal_context import change

from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource


def alter(service, identity, data, kind):
    if kind not in {"read", "contract", "original"}:
        change(service, identity, data, kind)
        return
    with service.db.session() as session:
        if kind == "read":
            source = session.get(InvestigationSource, data["sources"][0]["id"])
            source.snapshot = {**source.snapshot, "text_truncated": True}
        else:
            branch = session.get(InvestigationBranch, data["question_renewal_targets"][0]["branch_id"])
            run = session.get(Investigation, branch.investigation_id)
            if kind == "contract":
                state = deepcopy(run.research_state)
                state["exploration"].pop("renewal_recovery_contract")
                run.research_state = state
            else:
                run.question = "Changed initial public question"
        session.commit()


@pytest.mark.parametrize(
    "kind",
    ["source", "hash", "claim_status", "claim_text", "mixed", "question", "read", "contract", "original"],
)
def test_bad_optional_shape_does_not_hide_shared_inflight_changes(signed, monkeypatch, kind):
    client, service, identity, model = signed
    root, run, _, observed, _ = configured(
        signed, monkeypatch, callback=lambda data: alter(service, identity, data, kind)
    )

    def transform(title, data, value):
        if title == "Briefing":
            value["question_renewals"] = CANARY

    calls = response_adapter(monkeypatch, model, transform)
    final = complete(client, service, root + "/investigations", run)
    assert observed and calls.count("Briefing") == 1
    assert final["exploration"]["briefing"] is None
    assert final["exploration"]["next_check"] is None
    assert CANARY not in json.dumps(final)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert not any(q.get("branch_assessment_history") for q in saved.research_state["questions"])
        assert "renewal_context" not in saved.research_state["exploration"]


@pytest.mark.parametrize("kind", ["source", "read", "claim_status"])
def test_recovered_summary_keeps_unquoted_context_dependencies(signed, monkeypatch, kind):
    client, service, identity, model = signed
    root, run, _, observed, _ = configured(signed, monkeypatch)

    def transform(title, data, value):
        if title == "Briefing":
            value["question_renewals"] = CANARY

    response_adapter(monkeypatch, model, transform)
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["briefing"]["question_updates"] == {"status": "unavailable"}
    alter(service, identity, observed[0], kind)
    changed = client.get(root + "/investigations/" + run["id"]).json()
    assert changed["exploration"]["status"] == "evidence_changed"
    assert changed["exploration"]["briefing"] is None
    assert changed["exploration"]["next_check"] is None
    assert "question_updates" not in json.dumps(changed["exploration"])


@pytest.mark.parametrize("action", ["pause", "cancel"])
def test_control_during_final_request_discards_recoverable_result(signed, monkeypatch, action):
    client, service, _, model = signed
    controls = []

    def control(data):
        detail = root + "/investigations/" + run["id"]
        current = client.get(detail).json()
        result = post(
            client, detail + "/control", {"expected_revision": current["revision"], "action": action}
        )
        assert result.status_code == 200, result.text
        controls.append(result.json()["status"])

    root, run, _, observed, _ = configured(signed, monkeypatch, callback=control)

    def transform(title, data, value):
        if title == "Briefing":
            value["question_renewals"] = CANARY

    response_adapter(monkeypatch, model, transform)
    final = complete(client, service, root + "/investigations", run)
    assert observed and controls == ["paused" if action == "pause" else "cancelled"]
    assert final["status"] == controls[0] and final["exploration"]["briefing"] is None
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert "renewal_context" not in saved.research_state["exploration"]
