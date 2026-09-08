"""Actual read/write HTTP boundary, tenant access and inspectable saved evidence."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_interest_admission import setup
from test_native_comparisons import baseline, choose

from helvetic_lens.models import (
    NativeDocumentComparison,
    NativeEventComparisonSelection,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
)


def paths(event_id):
    return f"/api/registry/events/{event_id}/comparison", f"/api/registry/events/{event_id}/baselines"


def test_http_save_complete_pair_page_exact_changes_and_clear(harness):
    client, _, service, model = harness
    _, event_id, _, _ = setup(harness, units=400)
    old, after = baseline(service, event_id)
    comparison_url, choices_url = paths(event_id)
    empty = client.get(comparison_url).json()
    assert empty["status"] == "unselected" and empty["revision"] == 0
    choices = client.get(choices_url).json()
    assert [row["id"] for row in choices["items"]] == [old]
    assert "text" not in choices["items"][0] and "passages" not in choices["items"][0]
    response = client.put(comparison_url, json={"before_version_id": old, "after_version_id": after, "expected_revision": 0})
    assert response.status_code == 200, response.text
    result = client.get(comparison_url).json()
    assert result["status"] == "ready" and result["material_count"] == 1
    assert result["before"]["id"] == old and result["after"]["id"] == after and result["language"] == "en"
    assert len(result["items"]) == 1 and result["items"][0]["old"]["text"].endswith("Earlier synthetic wording.")
    assert result["items"][0]["new"]["text"] != result["items"][0]["old"]["text"]
    complete = client.get(comparison_url, params={"material_only": False, "limit": 7}).json()
    assert len(complete["items"]) == 7 and complete["pagination"]["total"] == 400
    next_page = client.get(comparison_url, params={"material_only": False, "limit": 7, "offset": 7,
                                                 "comparison_id": result["comparison_id"]}).json()
    assert len({row["id"] for row in complete["items"] + next_page["items"]}) == 14
    assert next_page["pagination"]["previous_offset"] == 0
    assert client.put(comparison_url, json={"before_version_id": None, "after_version_id": after, "expected_revision": 1}).status_code == 200
    assert client.get(comparison_url).json()["status"] == "unselected"
    assert client.get(comparison_url, params={"comparison_id": result["comparison_id"]}).status_code == 409
    assert not model.calls


def test_oversized_ai_dossier_still_has_complete_paged_comparison(harness):
    client, _, service, model = harness
    _, event_id, _, _ = setup(harness, units=70)
    old, after = baseline(service, event_id)
    with service.db.session() as session:
        version = session.get(RegulatoryDocumentVersion, old)
        version.passages = [{**row, "text": row["text"] + " Old duty."} for row in version.passages]
        session.commit()
    comparison_url, _ = paths(event_id)
    assert client.put(comparison_url, json={"before_version_id": old, "after_version_id": after, "expected_revision": 0}).status_code == 200
    collected, offset, pinned = [], 0, ""
    while True:
        response = client.get(comparison_url, params={"offset": offset, "limit": 11, "comparison_id": pinned})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "ready"
        pinned = data["comparison_id"]
        collected.extend(data["items"])
        offset = data["pagination"]["next_offset"]
        if offset is None:
            break
    assert len(collected) == len({row["id"] for row in collected}) == 70
    assert not model.calls


def test_candidates_paginate_without_private_or_other_language_versions(harness):
    client, _, service, _ = harness
    _, event_id, _, _ = setup(harness)
    expected = {baseline(service, event_id)[0] for _ in range(8)}
    hidden, _ = baseline(service, event_id, grant=False)
    different_language, _ = baseline(service, event_id)
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        expression = RegulatoryExpression(work_id=event.work_id, language="fr", expression_key="native-ui-fr")
        session.add(expression)
        session.flush()
        session.get(RegulatoryDocumentVersion, different_language).expression_id = expression.id
        session.commit()
    url = paths(event_id)[1]
    seen, cursor = [], ""
    while True:
        response = client.get(url, params={"after": cursor, "limit": 3})
        assert response.status_code == 200, response.text
        result = response.json()
        seen.extend(row["id"] for row in result["items"])
        cursor = result["next_after"]
        if not cursor:
            break
    assert set(seen) == expected and len(seen) == len(expected) and hidden not in seen and different_language not in seen


@pytest.mark.parametrize("change", ["text", "grant", "diff"])
def test_stale_comparison_returns_recoverable_state_without_old_passages(harness, change):
    client, _, service, _ = harness
    _, event_id, _, _ = setup(harness)
    old, after = baseline(service, event_id)
    chosen = choose(service, event_id, old, after)
    with service.db.session() as session:
        if change == "text":
            session.get(RegulatoryDocumentVersion, old).text += " Changed."
        elif change == "grant":
            event = session.scalar(select(RegulatoryEvent.id).where(RegulatoryEvent.document_version_id == old))
            session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event))
        else:
            session.get(NativeDocumentComparison, chosen.comparison_id).diff = {"items": []}
        session.commit()
    response = client.get(paths(event_id)[0])
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stale" and data["items"] == [] and data["before"] is None
    assert data["revision"] == 1 and "Earlier synthetic wording" not in response.text


@pytest.mark.parametrize("values", [{"expected_revision": True}, {"expected_revision": -1},
                                      {"before_version_id": ""}, {"after_version_id": ""}])
def test_invalid_selection_body_does_not_write(harness, values):
    client, _, service, _ = harness
    _, event_id, _, _ = setup(harness)
    old, after = baseline(service, event_id)
    payload = {"before_version_id": old, "after_version_id": after, "expected_revision": 0, **values}
    assert client.put(paths(event_id)[0], json=payload).status_code == 422
    with service.db.session() as session:
        assert not list(session.scalars(select(NativeEventComparisonSelection)))


def test_omitted_baseline_is_not_an_implicit_clear_and_stale_edit_is_conflict(harness):
    client, _, service, _ = harness
    _, event_id, _, _ = setup(harness)
    old, after = baseline(service, event_id)
    choose(service, event_id, old, after)
    url, _ = paths(event_id)
    assert client.put(url, json={"after_version_id": after, "expected_revision": 1}).status_code == 422
    assert client.put(url, json={"before_version_id": None, "after_version_id": after, "expected_revision": 0}).status_code == 409
    assert client.get(url).json()["status"] == "ready"
    assert client.get(url, params={"comparison_id": str(uuid4())}).status_code == 409
    assert client.get(url, params={"limit": 500}).status_code == 422


def test_unknown_and_revoked_events_do_not_disclose_comparisons(harness):
    client, _, service, _ = harness
    _, event_id, _, _ = setup(harness)
    old, after = baseline(service, event_id)
    choose(service, event_id, old, after)
    with service.db.session() as session:
        session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        session.commit()
    for target in (event_id, str(uuid4())):
        for url in paths(target):
            response = client.get(url)
            assert response.status_code == 404 and old not in response.text


def test_authentication_csrf_and_viewer_policy_are_enforced(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_organization_access import csrf, register, settings

    from helvetic_lens.main import create_app
    from helvetic_lens.models import OrganizationMembership
    fetcher, model = FakeFetcher(), ScriptedModel()
    app = create_app(settings(tmp_path), fetcher=fetcher, model_client=model)
    with TestClient(app) as client:
        for path in paths(str(uuid4())):
            assert client.get(path).status_code == 401
        registered = register(client, "native-editor@example.ch").json()
        client.headers.update(csrf(client))
        service = app.state.service
        with service.db.organization_context(registered["organization"]["id"]):
            test_harness = (client, fetcher, service, model)
            _, event_id, _, _ = setup(test_harness)
            old, after = baseline(service, event_id)
            url, _ = paths(event_id)
            body = {"before_version_id": old, "after_version_id": after, "expected_revision": 0}
            assert client.put(url, json=body, headers={"X-CSRF-Token": "wrong"}).status_code == 403
            assert client.put(url, json=body).status_code == 200
            with service.db.session() as session:
                member = session.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == registered["user"]["id"]))
                member.role = "viewer"
                session.commit()
            assert client.get(url).status_code == 200
            blocked = client.put(url, json={**body, "before_version_id": None, "expected_revision": 1})
            assert blocked.status_code == 403 and blocked.json()["code"] == "viewer_read_only"
            assert client.get(url).json()["status"] == "ready"
        assert not model.calls and "Earlier synthetic wording" not in json.dumps(client.get(paths(str(uuid4()))[0]).json())
