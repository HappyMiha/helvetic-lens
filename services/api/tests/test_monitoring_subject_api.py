"""C01b1 HTTP authorization/transaction checks; source Start stays unavailable."""

from uuid import uuid4

import pytest
from conftest import FakeFetcher, ScriptedModel
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from test_auth import _csrf, _register, _settings

from helvetic_lens.main import create_app
from helvetic_lens.models import Job, MonitoringSubject, OrganizationMembership
from helvetic_lens.monitoring_contracts import MonitoringRollout, RolloutGrant

URL = "/api/monitoring-subjects"


def config(station="PBS"):
    return {"station_id": station, "selections": [{"allergen": "birch"}, {"allergen": "grasses"}]}


def grant(settings, *organizations, mode="shadow"):
    settings.monitoring_rollout = MonitoringRollout(enabled=True, grants=tuple(
        RolloutGrant(workspace_id=organization, template_id="pollen-watch", template_version=1, mode=mode)
        for organization in organizations
    ))


@pytest.fixture
def api(tmp_path):
    settings = _settings(tmp_path, deployment_instance="monitoring-v2")
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        response = _register(client)
        assert response.status_code == 201, response.text
        identity = response.json()
        grant(settings, identity["organization"]["id"])
        yield client, app, settings, identity


def create(client, key="first", station="PBS"):
    response = client.post(URL, json={"request_key": key, "configuration": config(station)}, headers=_csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_http_draft_journey_revision_history_preview_and_blocked_start(api):
    client, app, _, _ = api
    preview = client.post(URL + "/preview", json={"configuration": config()}, headers=_csrf(client))
    assert preview.status_code == 200
    assert preview.json()["preview_kind"] == "configuration_only"
    assert preview.json()["observations"] == preview.json()["forecasts"] == []
    assert preview.json()["start_available"] is False
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(MonitoringSubject)) == 0
        jobs_before = session.scalar(select(func.count()).select_from(Job))
    first = create(client)
    assert create(client) == first
    conflict = client.post(URL, json={"request_key": "first", "configuration": config("PZH")}, headers=_csrf(client))
    assert conflict.status_code == 409
    edited = client.patch(URL + "/" + first["id"], json={"expected_revision": 1, "configuration": config("PZH")}, headers=_csrf(client))
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    stale = client.patch(URL + "/" + first["id"], json={"expected_revision": 1, "configuration": config()}, headers=_csrf(client))
    assert stale.status_code == 409
    history = client.get(URL + "/" + first["id"] + "/history?limit=1").json()
    assert history["items"][0]["configuration"]["station_id"] == "PZH"
    older = client.get(URL + "/" + first["id"] + "/history", params={"before_revision": history["next_before_revision"]}).json()
    assert older["items"][0]["configuration"]["station_id"] == "PBS"
    assert older["next_before_revision"] is None
    start = client.post(URL + "/" + first["id"] + "/start", json={"expected_revision": 2}, headers=_csrf(client))
    assert start.status_code == 409 and start.json()["code"] == "pollen_source_not_ready"
    assert client.get(URL + "/" + first["id"]).json()["status"] == "draft"
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(Job)) == jobs_before
    removed = client.request("DELETE", URL + "/" + first["id"], json={"expected_revision": 2}, headers=_csrf(client))
    assert removed.status_code == 204
    assert client.get(URL + "/" + first["id"]).status_code == 404


def test_pagination_has_no_duplicates_and_preserves_owner_scope(api):
    client, _, _, _ = api
    expected = {create(client, key=str(index))["id"] for index in range(3)}
    seen, cursor = [], None
    while True:
        page = client.get(URL, params={"limit": 1, **({"cursor": cursor} if cursor else {})}).json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 3
    assert set(seen) == expected
    assert client.get(URL, params={"cursor": str(uuid4())}).status_code == 404
    assert client.get(URL, params={"limit": 101}).status_code == 422


def test_csrf_and_input_errors_do_not_mutate_drafts_or_echo_private_values(api):
    client, app, _, _ = api
    blocked = client.post(URL, json={"request_key": "csrf", "configuration": config()})
    assert blocked.status_code == 403 and blocked.json()["code"] == "csrf_failed"
    invalid = client.post(URL, json={"request_key": "bad", "configuration": {
        **config(), "home_address": "PRIVATE ADDRESS VALUE",
    }}, headers=_csrf(client))
    assert invalid.status_code == 422
    assert "PRIVATE ADDRESS VALUE" not in invalid.text
    spoofed = client.post(URL, json={"request_key": "spoof", "configuration": config(), "owner_user_id": str(uuid4())}, headers=_csrf(client))
    assert spoofed.status_code == 422
    for response in (blocked, invalid, spoofed):
        assert response.headers["cache-control"] == "private, no-store"
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(MonitoringSubject)) == 0


def test_rollout_defaults_off_and_only_exact_shadow_grant_allows_drafts(api):
    client, _, settings, identity = api
    assert client.get(URL).status_code == 200
    settings.monitoring_rollout = MonitoringRollout()
    assert client.get(URL).status_code == 404
    grant(settings, str(uuid4()))
    assert client.get(URL).status_code == 404
    grant(settings, identity["organization"]["id"], mode="enabled")
    assert client.get(URL).status_code == 404  # No verified source gate for enabled mode.
    grant(settings, identity["organization"]["id"])
    settings.deployment_instance = "main"
    assert client.get(URL).status_code == 404


def test_cross_workspace_and_same_workspace_other_owner_are_denied(api):
    first, app, settings, owner = api
    record = create(first)
    with TestClient(app) as second:
        peer = _register(second, "peer@example.test", "Other workspace").json()
        grant(settings, owner["organization"]["id"], peer["organization"]["id"])
        assert second.get(URL).json()["items"] == []
        assert second.get(URL + "/" + record["id"]).status_code == 404
        assert second.get(URL, params={"cursor": record["id"]}).status_code == 404
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=owner["organization"]["id"],
                                                user_id=peer["user"]["id"], role="organization_admin"))
            session.commit()
        switched = second.post("/api/auth/session/organization", json={"organization_id": owner["organization"]["id"]}, headers=_csrf(second))
        assert switched.status_code == 200, switched.text
        for suffix in ("", "/history"):
            assert second.get(URL + "/" + record["id"] + suffix).status_code == 404
        for method, suffix, body in (("PATCH", "", {"expected_revision": 1, "configuration": config()}),
                                      ("DELETE", "", {"expected_revision": 1}),
                                      ("POST", "/start", {"expected_revision": 1})):
            response = second.request(method, URL + "/" + record["id"] + suffix, json=body, headers=_csrf(second))
            assert response.status_code == 404


def test_role_downgrade_takes_effect_on_next_http_request(api):
    client, app, _, owner = api
    record = create(client)
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.execute(update(OrganizationMembership).where(
            OrganizationMembership.organization_id == owner["organization"]["id"],
            OrganizationMembership.user_id == owner["user"]["id"],
        ).values(role="viewer"))
        session.commit()
    assert client.get(URL + "/" + record["id"]).status_code == 200
    assert client.patch(URL + "/" + record["id"], json={"expected_revision": 1, "configuration": config("PZH")}, headers=_csrf(client)).status_code == 403


def test_anonymous_development_still_requires_a_personal_session(tmp_path):
    settings = _settings(tmp_path, deployment_instance="monitoring-v2")
    settings.allow_anonymous_dev = True
    app = create_app(settings, fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        response = client.get(URL)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "private, no-store"


def test_rate_limit_is_shared_across_subject_paths(api):
    client, _, _, _ = api
    for _ in range(60):
        assert client.get(URL + "/" + str(uuid4())).status_code == 404
    limited = client.get(URL)
    assert limited.status_code == 429
    assert limited.headers["cache-control"] == "private, no-store"
