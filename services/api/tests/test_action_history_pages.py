"""Complete bounded action history, current decisions and legacy compatibility."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, event, insert, select
from sqlalchemy.orm import Session
from test_analysis_selection import seed

from helvetic_lens import action_history
from helvetic_lens.db import utcnow
from helvetic_lens.models import ActionDecision, Analysis, Comparison, Law, Organization


def prepare(harness, count=151):
    _, _, service, _ = harness
    law, comparison, report, calls = seed(harness, 1)
    action = report["result"]["actions"][0]["action_key"]
    stamp = utcnow() - timedelta(days=1)
    with service.db.session() as session:
        session.execute(
            insert(ActionDecision),
            [
                dict(
                    id=f"77000000-0000-0000-0000-{i:012}",
                    organization_id=service.organization_id,
                    comparison_id=comparison["id"],
                    analysis_id=report["id"],
                    action_key=action,
                    decision="accepted",
                    actor_label=f"Reviewer {i}",
                    rationale="Saved rationale " * 100,
                    created_at=stamp,
                )
                for i in range(count)
            ],
        )
        session.commit()
    url = f"/api/comparisons/{comparison['id']}/analyses/{report['id']}/actions/{action}/decisions"
    return law, comparison, report, action, calls, url


def test_complete_action_history_pages_and_compact_summary(harness):
    client, _, service, model = harness
    _, cmp, report, action, calls, url = prepare(harness)
    loaded = []

    def load(_session, value):
        if isinstance(value, ActionDecision):
            loaded.append(value.id)

    event.listen(Session, "loaded_as_persistent", load)
    try:
        response = client.get(f"/api/comparisons/{cmp['id']}?paged_actions=true")
        assert response.status_code == 200, response.text
        summary = response.json()["analysis"]["action_decisions"]
        assert summary["history"] == [] and summary["history_mode"] == "per_action"
        assert summary["counts"] == {action: 151}
        assert summary["current"][action]["actor_label"] == "Reviewer 150"
        cursor, ids, first = "", [], None
        while True:
            response = client.get(url, params={"cursor": cursor})
            assert response.status_code == 200, response.text
            page = response.json()
            assert len(page["items"]) <= 20 and page["total"] == 151
            first = first or page["first_cursor"]
            ids.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert ids == [f"77000000-0000-0000-0000-{i:012}" for i in reversed(range(151))]
        assert client.get(url, params={"cursor": first}).json()["items"][0]["id"] == ids[0]
        assert loaded == []
    finally:
        event.remove(Session, "loaded_as_persistent", load)
    legacy = client.get(f"/api/comparisons/{cmp['id']}").json()["analysis"]["action_decisions"]
    assert len(legacy["history"]) == 151
    assert legacy["current"][action]["id"] == summary["current"][action]["id"]
    assert len(model.calls) == calls


def test_action_history_new_decision_and_deleted_boundary(harness):
    (
        client,
        _,
        service,
        _,
    ) = harness
    _, _, _, action, _, url = prepare(harness, 41)
    first = client.get(url).json()
    saved = client.post(url + "?paged_actions=true", json={"decision": "accepted"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["history"] == [] and saved.json()["counts"][action] == 42
    with service.db.session() as session:
        session.execute(delete(ActionDecision).where(ActionDecision.id == first["items"][-1]["id"]))
        session.commit()
    rest = client.get(url, params={"cursor": first["next_cursor"]}).json()
    assert rest["items"][0]["actor_label"] == "Reviewer 20"
    assert rest["total"] == 40
    assert client.get(url).json()["total"] == 41


@pytest.mark.parametrize("fault", ["garbage", "action", "limit", "analysis"])
def test_action_history_cursor_scope_cannot_be_reused(harness, fault):
    client, _, _, _ = harness
    _, _, _, _, _, url = prepare(harness, 21)
    cursor = client.get(url).json()["next_cursor"]
    params = {"cursor": cursor}
    if fault == "garbage":
        params["cursor"] = "not-a-cursor"
    elif fault == "action":
        url = url.replace("/actions/", "/actions/other-")
    elif fault == "limit":
        params["limit"] = 50
    else:
        url = url.replace("/analyses/", "/analyses/missing-")
    assert client.get(url, params=params).status_code == (404 if fault == "analysis" else 422)


@pytest.mark.parametrize("hidden", ["decision", "analysis", "comparison", "law"])
def test_action_history_explicit_scope(harness, hidden):
    _, _, service, _ = harness
    law, cmp, report, action, _, _ = prepare(harness, 1)
    with service.db.session(include_all_organizations=True) as session:
        foreign = Organization(name="Foreign decisions", slug="foreign-action-history")
        session.add(foreign)
        session.flush()
        if hidden == "decision":
            session.scalar(select(ActionDecision)).organization_id = foreign.id
        elif hidden == "analysis":
            session.get(Analysis, report["id"]).organization_id = foreign.id
        else:
            model, id_ = (Comparison, cmp["id"]) if hidden == "comparison" else (Law, law["id"])
            session.get(model, id_).owner_organization_id = foreign.id
        session.commit()
        summary = action_history.summary(session, service.organization_id, cmp["id"], report["id"])
        assert summary["current"] == {} and summary["counts"] == {}
        if hidden == "decision":
            assert (
                action_history.page(session, service.organization_id, cmp["id"], report["id"], action)[
                    "items"
                ]
                == []
            )
        else:
            from helvetic_lens.config import DomainError

            with pytest.raises(DomainError):
                action_history.page(session, service.organization_id, cmp["id"], report["id"], action)
