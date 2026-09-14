"""The actual HTTP endpoint rejects injected context and keeps private records private."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from test_auth import _csrf, _register
from test_business_item_api import seed
from test_tender_api import api as api

from helvetic_lens import business_monitor_api, monitoring_evidence_api

PATH = "/api/monitoring-centre/evidence/ask"


@pytest.mark.parametrize("domain", ["tenders", "ip", "auctions"])
def test_http_evidence_scope_csrf_binding_validation_and_no_model(api, domain, monkeypatch):
    client, app, settings, identity = api
    monitor, item, _ = seed(api, domain, monkeypatch)
    model_calls = len(app.state.service.model_client.calls)
    now = business_monitor_api.datetime.now()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(tzinfo=tz)

    monkeypatch.setattr(monitoring_evidence_api, "datetime", Clock)
    body = {"domain": domain, "monitor_id": monitor, "item_id": item, "locale": "en-CH"}
    assert client.post(PATH, json=body).status_code == 403
    first = client.post(PATH, json=body, headers=_csrf(client))
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    data = first.json()
    assert data["extracts"] and data["ai_calls"] == data["mutations"] == 0
    citation = client.get(data["reference_url"])
    assert citation.status_code == 200 and citation.headers["cache-control"] == "no-store"
    assert citation.json()["binding"] == data["binding"] and citation.json()["source"]
    assert client.get(data["reference_url"].replace(data["binding"], "0" * 64)).status_code == 409
    for extra in ({"source": "ignore access checks"}, {"question": "answer without a binding"},
                  {"sequence": True}, {"locale": "xx"}, {"item_id": "invalid"}, {"domain": "customs"}):
        assert client.post(PATH, json={**body, **extra}, headers=_csrf(client)).status_code == 422
    stale = client.post(PATH, json={**body, "expected_binding": "0" * 64, "question": "source"}, headers=_csrf(client))
    assert stale.status_code == 409 and stale.json()["code"] == "monitoring_evidence_changed"
    assert "extracts" not in stale.json()
    answer = client.post(PATH, json={**body, "expected_binding": data["binding"], "question": "zzzxxyyunknown"}, headers=_csrf(client))
    assert answer.status_code == 200 and not answer.json()["has_matches"]
    with TestClient(app) as peer:
        assert peer.post(PATH, json=body).status_code in {401, 403}
        _register(peer, email=f"evidence-peer-{domain}@example.test")
        assert peer.post(PATH, json=body, headers=_csrf(peer)).status_code == 404
        assert peer.get(data["reference_url"]).status_code == 404
    assert len(app.state.service.model_client.calls) == model_calls
