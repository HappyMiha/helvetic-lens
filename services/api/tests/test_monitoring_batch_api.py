"""Actual HTTP preview/apply, CSRF, native state and tenant boundaries."""

from datetime import UTC

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from test_auth import _csrf, _register
from test_business_item_api import seed
from test_tender_api import api as api

from helvetic_lens import business_item_work as work
from helvetic_lens import (
    business_monitor_api,
    monitoring_batch_api,
    monitoring_centre,
    monitoring_evidence_api,
)
from helvetic_lens.models import OrganizationMembership

PATH = "/api/monitoring-centre/review"


@pytest.mark.parametrize("domain,action", [("tenders", "no_bid"), ("ip", "reviewed"), ("auctions", "inspect")])
def test_http_native_decisions_from_real_queue_and_no_model(api, domain, action, monkeypatch):
    client, app, settings, identity = api
    monitor, item, _ = seed(api, domain, monkeypatch)
    monkeypatch.setattr(monitoring_batch_api, "datetime", business_monitor_api.datetime)
    monkeypatch.setattr(monitoring_evidence_api, "datetime", business_monitor_api.datetime)
    monkeypatch.setattr(monitoring_centre, "datetime", business_monitor_api.datetime)
    record = {"domain": domain, "monitor_id": monitor, "item_id": item, "sequence": None}
    payload = {"locale": "en-CH", "records": [record]}
    queue = client.get("/api/monitoring-centre/notifications", params={"domain": domain})
    assert queue.status_code == 200 and queue.json()["items"]
    assert queue.json()["items"][0]["record"] == record
    now = business_monitor_api.datetime.now(UTC)
    calls = len(app.state.service.model_client.calls)
    assert client.post(PATH+"/preview", json=payload).status_code == 403
    preview = client.post(PATH+"/preview", json=payload, headers=_csrf(client))
    assert preview.status_code == 200, preview.text
    assert preview.headers["cache-control"] == "no-store"
    value = preview.json()["items"][0]
    assert client.get(value["reference_url"]).status_code == 200
    for extra in ({"source": "trust me"}, {"records": []}, {"records": [record, record]}, {"locale": "unknown"}):
        assert client.post(PATH+"/preview", json={**payload, **extra}, headers=_csrf(client)).status_code == 422
    with TestClient(app) as peer:
        _register(peer, email=f"batch-peer-{domain}@example.test")
        assert peer.post(PATH+"/preview", json=payload, headers=_csrf(peer)).status_code == 404
    applied = {"locale": "en-CH", "selections": [{"record": record, "expected_binding": value["binding"], "action": action}]}
    assert client.post(PATH+"/apply", json=applied).status_code == 403
    result = client.post(PATH+"/apply", json=applied, headers=_csrf(client))
    assert result.status_code == 200 and result.json()["count"] == 1, result.text
    assert client.post(PATH+"/apply", json=applied, headers=_csrf(client)).status_code == 409
    with app.state.service.db.organization_context(identity["organization"]["id"]), app.state.service.db.session() as session:
        current = work.read(session, identity["user"]["id"], domain, monitor, item, now=now)
        assert current["decision"] == action and len(current["history"]) == 1
    assert len(app.state.service.model_client.calls) == calls


def test_viewer_cannot_preview_or_apply_batch(api, monkeypatch):
    client, app, _, identity = api
    monitor, item, _ = seed(api, "tenders", monkeypatch)
    record = {"domain": "tenders", "monitor_id": monitor, "item_id": item}
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"])
            .values(role="viewer"))
        session.commit()
    for operation, body in (("preview", {"records": [record]}), ("apply", {"selections": [{"record": record, "expected_binding": "a"*64, "action": "bid"}]})):
        assert client.post(PATH+"/"+operation, json={"locale": "en-CH", **body}, headers=_csrf(client)).status_code == 403
    with app.state.service.db.session(include_all_organizations=True) as session:
        from helvetic_lens.tender_models import TenderDossier
        assert session.scalar(select(TenderDossier.decision).where(TenderDossier.id == item)) is None
