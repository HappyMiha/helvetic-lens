"""Enabled private HTTP journey against an isolated source policy and database."""

from datetime import UTC, datetime, timedelta

import pytest

from test_auth import _csrf
from test_monitoring_subject_api import URL, create, grant
from test_monitoring_subject_api import api as api

from helvetic_lens.pollen_sources import PollenSourcePolicy


def enable(settings, identity):
    grant(settings, identity["organization"]["id"], mode="enabled")
    now = datetime.now(UTC)
    settings.pollen_source_policy = PollenSourcePolicy.model_validate({"channels": [{
        "version": "synthetic-http-review", "review_sha256": "a" * 64, "source_id": "meteoswiss:ogd-pollen",
        "method_version": "meteoswiss-automatic-hourly-v1", "period": "observation_hourly", "stations": ["PBS"],
        "allergens": ["birch", "grasses"], "status": "approved", "valid_from": now - timedelta(days=1),
        "valid_until": now + timedelta(days=1), "freshness_seconds": 10800, "poll_seconds": 1200, "retention_days": 30}]})


@pytest.mark.parametrize("instance", ["main", "monitoring-v2"])
def test_live_http_start_lost_response_pause_edit_export_delete(api, instance):
    client, app, settings, identity = api
    settings.deployment_instance = instance
    enable(settings, identity)
    subject = create(client)
    base = URL + "/" + subject["id"]
    preview = client.post(URL + "/preview", json={"configuration": subject["configuration"]}, headers=_csrf(client)).json()
    assert preview["preview_kind"] == "source_coverage" and preview["start_available"]
    assert client.get(base + "/state").json()["runtime"]["version"] == 0
    body = {"action": "start", "expected_revision": 1, "expected_version": 0, "request_key": "synthetic-start"}
    first = client.post(base + "/commands", json=body, headers=_csrf(client))
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "active" and first.json()["runtime"]["health"] == "waiting"
    assert client.post(base + "/commands", json=body, headers=_csrf(client)).json() == first.json()
    assert client.get(URL + "/today").json() == {"items": [], "next_cursor": None}
    paused = client.post(base + "/commands", json={**body, "action": "pause", "expected_version": 1,
        "request_key": "synthetic-pause"}, headers=_csrf(client))
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
    config = subject["configuration"]
    config["delivery"] = {"email": "daily_digest", "digest_at": "08:00"}
    edited = client.patch(base, json={"expected_revision": 1, "configuration": config}, headers=_csrf(client))
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    exported = client.get(base + "/export")
    assert exported.status_code == 200 and '"complete":true' in exported.text
    assert "private" in exported.headers["cache-control"]
    assert client.request("DELETE", base, json={"expected_revision": 2, "expected_version": 2}, headers=_csrf(client)).status_code == 409
    assert client.request("DELETE", base, json={"expected_revision": 2, "expected_version": 3}, headers=_csrf(client)).status_code == 204
    assert client.get(base + "/export").status_code == 404
    assert client.get(base + "/state").status_code == 404


def test_category_rule_requires_reviewed_matching_scale_and_no_browser_approval(api):
    client, _, settings, identity = api
    enable(settings, identity)
    config = {"station_id": "PBS", "selections": [{"allergen": "birch", "rules": [{
        "period": "observation_hourly", "category_change": True}]}]}
    preview = client.post(URL + "/preview", json={"configuration": config}, headers=_csrf(client))
    assert preview.status_code == 200 and preview.json()["blocking_reasons"] == ["pollen_category_not_ready"]
    response = client.post(URL, json={"request_key": "category", "configuration": config}, headers=_csrf(client))
    base = URL + "/" + response.json()["id"]
    denied = client.post(base + "/start", json={"expected_revision": 1, "request_key": "start"}, headers=_csrf(client))
    assert denied.status_code == 409 and denied.json()["code"] == "pollen_category_not_ready"
    assert client.post(base + "/commands", json={"action": "start", "expected_revision": 1, "expected_version": 0,
        "request_key": "start", "source_ready": True}, headers=_csrf(client)).status_code == 422


def test_private_monitor_job_list_detail_cancel_and_retry_exclude_workspace_peer(api):
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from test_auth import _register

    from helvetic_lens.models import Job, OrganizationMembership

    owner_client, app, settings, owner = api
    enable(settings, owner)
    subject = create(owner_client)
    response = owner_client.post(URL + "/" + subject["id"] + "/start",
        json={"expected_revision": 1, "request_key": "private-job"}, headers=_csrf(owner_client))
    assert response.status_code == 200
    with app.state.service.db.session(include_all_organizations=True) as session:
        job_id = session.scalar(select(Job.id).where(Job.target_id == subject["id"]))
    assert owner_client.get("/api/jobs/" + job_id).status_code == 200
    with TestClient(app) as peer_client:
        peer = _register(peer_client, "private-peer@example.test", "Peer workspace").json()
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=owner["organization"]["id"],
                user_id=peer["user"]["id"], role="organization_admin"))
            session.commit()
        assert peer_client.post("/api/auth/session/organization", json={"organization_id": owner["organization"]["id"]},
            headers=_csrf(peer_client)).status_code == 200
        assert job_id not in peer_client.get("/api/jobs").text
        assert peer_client.get("/api/jobs/" + job_id).status_code == 404
        for action in ("cancel", "retry"):
            assert peer_client.post(f"/api/jobs/{job_id}/{action}", headers=_csrf(peer_client)).status_code == 404
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert not session.get(Job, job_id).cancel_requested
