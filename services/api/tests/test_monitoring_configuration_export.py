"""Real authenticated exports of owned settings across all nine native models."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from test_auth import _csrf, _register
from test_monitoring_configuration_drafts import example
from test_tender_api import api as api

from helvetic_lens.models import Job, OrganizationMembership, OutboxMessage, User
from helvetic_lens.monitoring_configuration_export import DOMAINS, MODELS, POLICIES
from helvetic_lens.monitoring_live_models import MonitoringRuntime
from helvetic_lens.monitoring_subjects import create_draft

URL = "/api/monitoring-centre/configuration/export"


def seed(app, identity, domain, **values):
    db = app.state.service.db
    organization, user = identity["organization"]["id"], identity["user"]["id"]
    with db.organization_context(organization), db.session() as session:
        if domain == "pollen":
            item = create_draft(session, user_id=user, request_key=str(uuid4()), configuration=example(domain))
            identifier = item["id"]
            row = session.get(MODELS[domain], identifier)
            for key, value in values.items():
                setattr(row, key, value)
        else:
            identifier = str(uuid4())
            row = MODELS[domain](id=identifier, organization_id=organization, owner_user_id=user,
                request_key="private-request-key-" + identifier, request_hash="a" * 64,
                configuration=example(domain), **values)
            session.add(row)
        session.commit()
    return identifier


def bindings(items):
    return {"items": [{key: item[key] for key in ("domain", "id", "sha256")} for item in items]}


def test_all_nine_disabled_sources_export_own_current_values_and_email_without_work(api):
    client, app, settings, identity = api
    for flag in ("pollen_watch_enabled", "air_watch_enabled", "river_watch_enabled", "hazard_watch_enabled",
                 "commute_watch_enabled", "road_watch_enabled", "tender_watch_enabled", "trademark_watch_enabled", "auction_watch_enabled"):
        if hasattr(settings, flag):
            setattr(settings, flag, False)
    ids = {domain: seed(app, identity, domain, status="archived") for domain in DOMAINS}
    with app.state.service.db.session(include_all_organizations=True) as session:
        for domain, model in POLICIES.items():
            row = session.get(MODELS[domain], ids[domain])
            row.email_revision = 1
            session.add(model(monitor_id=row.id, organization_id=row.organization_id, revision=1,
                configuration={"timezone": "Europe/Zurich", "delivery": {"email": "off"}},
                recipient_email="owner@example.ch"))
        row = session.get(MODELS["air"], ids["air"])
        row.state = {"source_document": "PRIVATE_SOURCE_NOT_CONFIGURATION"}
        now = datetime.now(UTC)
        session.add(MonitoringRuntime(subject_id=ids["pollen"], organization_id=identity["organization"]["id"],
            version=1, run_id=str(uuid4()), configuration_revision=1, email_consent=True,
            muted=True, started_at=now, next_poll_at=now))
        session.commit()
        before = [session.scalar(select(func.count()).select_from(model)) for model in (Job, OutboxMessage)]
    response = client.get(URL)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["scope"] == [identity["organization"]["id"], identity["user"]["id"], None]
    assert body["next_cursor"] is None and len(body["items"]) == 9
    assert {item["domain"] for item in body["items"]} == set(DOMAINS)
    assert "PRIVATE_SOURCE_NOT_CONFIGURATION" not in response.text and "private-request-key" not in response.text
    for item in body["items"]:
        if item["domain"] not in {"traffic", "commute"}:
            assert item["configuration"] == example(item["domain"])
        else:
            assert item["configuration"]["name"]
        assert item["status"] == "archived" and item["configuration_revision"] == 1
        assert hashlib.sha256(item["canonical_json"].encode()).hexdigest() == item["sha256"]
        assert json.loads(item["canonical_json"])["configuration"] == item["configuration"]
        if item["domain"] != "pollen":
            assert item["email_preferences"]["revision"] == 1
            assert item["email_preferences"]["recipient_email"] == "owner@example.ch"
        else:
            assert item["email_preferences"]["consent_recorded"] and item["email_preferences"]["muted"]
    checked = client.post(URL + "/verify", json=bindings(body["items"]), headers=_csrf(client))
    assert checked.status_code == 200 and checked.json()["verified"] == 9
    with app.state.service.db.session(include_all_organizations=True) as session:
        assert before == [session.scalar(select(func.count()).select_from(model)) for model in (Job, OutboxMessage)]
    assert not app.state.service.fetcher.calls


def test_pagination_crosses_categories_ties_and_ignores_later_creation(api):
    client, app, _, identity = api
    clock = datetime.now(UTC) - timedelta(days=1)
    expected = {seed(app, identity, domain, created_at=clock) for domain in DOMAINS for _ in range(2)}
    page = client.get(URL + "?limit=3").json()
    late = seed(app, identity, "air", created_at=datetime.now(UTC) + timedelta(seconds=1))
    seen, started = [], page["started_at"]
    while True:
        assert page["started_at"] == started
        seen.extend(item["id"] for item in page["items"])
        if not page["next_cursor"]:
            break
        response = client.get(URL, params={"limit": 3, "cursor": page["next_cursor"]})
        assert response.status_code == 200, response.text
        page = response.json()
    assert len(seen) == 18 and set(seen) == expected and late not in seen
    filtered = client.get(URL + "?domain=ip").json()
    assert len(filtered["items"]) == 2 and all(row["domain"] == "ip" for row in filtered["items"])


def test_colleague_shared_monitors_foreign_workspace_and_transferred_cursor_do_not_leak(api):
    client, app, _, owner = api
    own = seed(app, owner, "tenders", visibility="workspace")
    seed(app, owner, "air")
    first = client.get(URL + "?limit=1").json()
    colleague = _register(client, "colleague@example.ch", "Other workspace").json()
    seed(app, colleague, "tenders", visibility="workspace")
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.add(OrganizationMembership(user_id=colleague["user"]["id"], organization_id=owner["organization"]["id"], role="viewer"))
        session.commit()
    foreign_cursor = client.get(URL, params={"cursor": first["next_cursor"]})
    assert foreign_cursor.status_code == 422
    switched = client.post("/api/auth/session/organization", json={"organization_id": owner["organization"]["id"]}, headers=_csrf(client))
    assert switched.status_code == 200, switched.text
    assert client.get(URL).json()["items"] == []
    assert client.post(URL + "/verify", json={"items": [{"domain": "tenders", "id": own, "sha256": "0" * 64}]}, headers=_csrf(client)).status_code == 409
    assert client.post(URL + "/verify", json={"items": []}, headers=_csrf(client)).status_code == 200


@pytest.mark.parametrize("change", ["configuration", "email", "deleted", "revoked", "inactive", "visibility"])
def test_final_verification_rejects_changed_or_revoked_records(api, change):
    client, app, _, identity = api
    identifier = seed(app, identity, "tenders")
    body = bindings(client.get(URL).json()["items"])
    with app.state.service.db.session(include_all_organizations=True) as session:
        row = session.get(MODELS["tenders"], identifier)
        if change == "configuration":
            row.configuration = {**row.configuration, "name": "Changed private settings"}
        elif change == "email":
            row.email_revision = 1
            session.add(POLICIES["tenders"](monitor_id=row.id, organization_id=row.organization_id,
                revision=1, configuration={"delivery": {"email": "off"}}))
        elif change == "deleted":
            session.delete(row)
        elif change == "revoked":
            session.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
        elif change == "inactive":
            session.execute(update(User).where(User.id == identity["user"]["id"]).values(active=False))
        else:
            row.visibility = "workspace"
        session.commit()
    expected = {"revoked": 401, "inactive": 403}.get(change, 409)
    assert client.post(URL + "/verify", json=body, headers=_csrf(client)).status_code == expected


def test_revocation_during_page_assembly_refuses_entire_response(api, monkeypatch):
    from helvetic_lens import monitoring_configuration_export as exports
    client, app, _, identity = api
    seed(app, identity, "air")
    original = exports.record

    def revoke(session, domain, row):
        result = original(session, domain, row)
        with app.state.service.db.session(include_all_organizations=True) as changed:
            changed.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]))
            changed.commit()
        return result

    monkeypatch.setattr(exports, "record", revoke)
    response = client.get(URL)
    assert response.status_code == 403 and "configuration" not in response.json()


def test_cursor_input_limits_email_gap_csrf_and_viewer_read_access(api):
    client, app, _, identity = api
    seed(app, identity, "air")
    seed(app, identity, "air")
    page = client.get(URL + "?limit=1").json()
    cursor = json.loads(base64.urlsafe_b64decode(page["next_cursor"]))
    for changes in ({"scope": ["foreign", "foreign", None]}, {"position": True}, {"after": "not-a-uuid"},
                    {"started": "2020-01-01T00:00:00+00:00"}, {"v": 2}):
        token = base64.urlsafe_b64encode(json.dumps({**cursor, **changes}).encode()).decode()
        assert client.get(URL, params={"cursor": token}).status_code == 422
    for params in ({"cursor": "!"}, {"limit": 0}, {"limit": 51}, {"domain": "customs"}, {"cursor": page["next_cursor"], "domain": "air"}):
        assert client.get(URL, params=params).status_code == 422
    body = bindings(page["items"])
    assert client.post(URL + "/verify", json=body).status_code == 403
    with app.state.service.db.session(include_all_organizations=True) as session:
        session.execute(update(OrganizationMembership).where(OrganizationMembership.user_id == identity["user"]["id"]).values(role="viewer"))
        session.commit()
    assert client.get(URL).status_code == 200
    assert client.post(URL + "/verify", json=body, headers=_csrf(client)).status_code == 200
    with app.state.service.db.session(include_all_organizations=True) as session:
        row = session.get(MODELS["air"], page["items"][0]["id"])
        row.email_revision = 9
        session.commit()
    missing = client.get(URL)
    assert missing.status_code == 503 and missing.json()["code"] == "configuration_export_incomplete"
    client.cookies.clear()
    assert client.get(URL).status_code == 401
