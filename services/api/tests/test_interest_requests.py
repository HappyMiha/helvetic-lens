"""Explicit requests must remain cheap, scoped, coalesced and worker-validated."""
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_interest_admission import setup
from test_interest_automation import enable, second_event
from test_interest_execution import artifacts, execution
from test_interest_policy import save
from test_topic_history import execute

from helvetic_lens import interest_requests
from helvetic_lens.config import DomainError
from helvetic_lens.models import Job

__all__ = ["artifacts", "execution"]


def request(service, event, locale="en", nonce=None):
    return service.request_interest_brief(event, locale, nonce or uuid4())


def test_request_is_cheap_coalesces_and_runs_through_durable_worker(execution):
    service = enable(execution)
    nonce = uuid4()
    created = request(service, execution[2], nonce=nonce)
    again = request(service, execution[2])
    assert again["reused"] and again["job"]["id"] == created["job"]["id"]
    assert created["ai_calls"] == 0 and not execution[4]["requests"]
    admission = execute(service, created["job"]["id"])
    outcome = admission["result"]["data"]["outcomes"][0]
    assert execute(service, outcome["job_id"])["state"] == "succeeded"
    assert asyncio.run(service.read_interest_brief(execution[2]))["status"] == "available"
    assert len(execution[4]["generated"]) == 1
    assert request(service, execution[2], nonce=nonce)["job"]["id"] == created["job"]["id"]
    # A fresh explicit request checks/reuses the exact successful assessment.
    repeat = execute(service, request(service, execution[2])["job"]["id"])
    assert repeat["result"]["data"]["outcomes"][0]["cached"]
    assert len(execution[4]["generated"]) == 1


def test_language_request_does_not_require_organization_fallback_locale(execution):
    service = enable(execution)
    save(service, locale="it", enabled=True)
    first = request(service, execution[2], "en")
    french = request(service, execution[2], "fr")
    assert first["job"]["id"] != french["job"]["id"]
    with service.db.session() as session:
        assert session.get(Job, first["job"]["id"]).payload["locale"] == "en"
        assert session.get(Job, french["job"]["id"]).payload["locale"] == "fr"
    assert not execution[4]["requests"]


@pytest.mark.parametrize("limit", ["MAX_PENDING", "MAX_DAILY"])
def test_request_limits_are_org_wide_and_preserve_pending_reuse(execution, monkeypatch, limit):
    service = enable(execution)
    monkeypatch.setattr(interest_requests, limit, 1)
    created = request(service, execution[2])
    assert request(service, execution[2])["job"]["id"] == created["job"]["id"]
    with pytest.raises(DomainError) as error:
        request(service, second_event(execution))
    assert error.value.code == "interest_request_limit"
    assert not execution[4]["requests"]


def test_disabled_unknown_and_revoked_requests_never_enqueue(execution):
    from sqlalchemy import delete

    from helvetic_lens.models import RegulatoryEventState
    service = enable(execution)
    save(service, enabled=False)
    with pytest.raises(DomainError) as error:
        request(service, execution[2])
    assert error.value.code == "interest_auto_disabled"
    with pytest.raises(DomainError) as error:
        request(service, "missing")
    assert error.value.status == 404
    save(service, enabled=True)
    created = request(service, execution[2])
    with service.db.session() as session:
        session.execute(delete(RegulatoryEventState).where(RegulatoryEventState.event_id == execution[2]))
        session.commit()
    with pytest.raises(DomainError) as error:
        request(service, execution[2])
    assert error.value.status == 404
    outcome = execute(service, created["job"]["id"])
    assert outcome["result"]["data"]["outcomes"][0]["status"] == "limited"
    assert not execution[4]["generated"]


def test_http_request_defaults_to_browser_language_without_provider_calls(harness):
    client, _, service, model = harness
    _, event, *_ = setup(harness)
    save(service, enabled=True)
    path = f"/api/interest-feed/events/{event}/brief/requests"
    response = client.post(path, json={"request_id": str(uuid4())}, headers={"Accept-Language": "fr-CH"})
    assert response.status_code == 202, response.text
    with service.db.session() as session:
        assert session.get(Job, response.json()["job"]["id"]).payload["locale"] == "fr"
    assert client.post(path, json={"request_id": "not-a-uuid"}).status_code == 422
    assert client.post(path, json={"request_id": str(uuid4()), "locale": "uk"}).status_code == 422
    assert not model.calls


def test_postgres_concurrent_requests_coalesce(harness):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    service = harness[2]
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL concurrent admission")
    _, event, *_ = setup(harness)
    save(service, enabled=True)
    barrier = Barrier(2)
    def submit(_):
        barrier.wait(timeout=10)
        return request(service, event)["job"]["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids[0] == ids[1]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.target_type == interest_requests.TARGET)) == 1


def test_viewer_requests_obey_csrf_policy_and_tenant_scope(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_organization_access import csrf, register, settings
    from test_topic_matching import add_event

    from helvetic_lens.main import create_app
    app = create_app(settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    service = app.state.service
    with TestClient(app) as owner, TestClient(app) as viewer, TestClient(app) as foreign:
        anonymous = viewer.post("/api/interest-feed/events/missing/brief/requests", json={"request_id": str(uuid4())})
        assert anonymous.status_code == 401
        organization = register(owner, "brief-owner@example.invalid").json()["organization"]["id"]
        with service.db.organization_context(organization):
            event = add_event(service)
        path = f"/api/interest-feed/events/{event}/brief/requests"
        invite = owner.post("/api/organization/invitations", headers=csrf(owner),
            json={"email": "brief-viewer@example.invalid", "role": "viewer"}).json()
        register(viewer, "brief-viewer@example.invalid", invitation_token=invite["token"])
        body = {"request_id": str(uuid4()), "locale": "de"}
        assert viewer.post(path, json=body).status_code == 403
        assert viewer.post(path, json=body, headers=csrf(viewer)).json()["code"] == "interest_auto_disabled"
        assert owner.patch("/api/settings/interest-briefs", json={"revision": 0, "enabled": True}, headers=csrf(owner)).status_code == 200
        created = viewer.post(path, json=body, headers=csrf(viewer))
        assert created.status_code == 202, created.text
        assert viewer.get("/api/jobs/" + created.json()["job"]["id"]).status_code == 200
        assert viewer.patch("/api/settings/interest-briefs", json={"revision": 1, "enabled": False}, headers=csrf(viewer)).status_code == 403
        register(foreign, "brief-foreign@example.invalid")
        assert foreign.post(path, json=body, headers=csrf(foreign)).status_code == 404
        assert foreign.get("/api/jobs/" + created.json()["job"]["id"]).status_code == 404
