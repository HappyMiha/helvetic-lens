"""AC-B8-12: synthetic normalized adapters, real journal/worker/private HTTP.

These are adapter-output conformance fixtures, not implementations or captured
responses of a Zurich publisher. Native Ticino parsing is tested separately.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_auction_api import ROOT
from test_auction_api import api as _api_fixture
from test_auction_rules import NOW, facts, price, profile
from test_auction_sources import grant
from test_auth import _csrf, _register

from helvetic_lens import auction_api, auction_jobs, auction_reminders, auction_sources
from helvetic_lens.auction_contracts import AuctionFacts
from helvetic_lens.auction_source_models import AuctionSourceRecordRevision
from helvetic_lens.auction_workflow_models import AuctionDecision, AuctionItemEvent, AuctionReminder
from helvetic_lens.config import DomainError
from helvetic_lens.models import OrganizationMembership

api = _api_fixture


@dataclass(frozen=True)
class AdapterOutputFixture:
    canton: str

    @property
    def key(self):
        return "conformance-" + self.canton.lower()

    @property
    def endpoint(self):
        return f"https://{self.key}.example.invalid/auctions/"

    def permission(self, database):
        return grant(database, source_key=self.key, cantons=(self.canton,), endpoint=self.endpoint,
            attribution=f"Synthetic {self.canton} conformance fixture; no live coverage",
            private_decisions_allowed=True, notifications_allowed=True)

    def output(self, now, **changes):
        # The synthetic transport contains exactly the fields handed to the
        # normalized contract. No live publisher format is inferred here.
        value = facts(canton=self.canton, source_key=self.key, asset_location="Test location",
            source_url=self.endpoint + "12", observed_at=now,
            documents={"state": "complete", "items": [{"official_id": "terms", "title": "Terms", "sha256": "a" * 64}]},
            conditions_sha256="a" * 64).model_dump(mode="json", exclude={"raw_sha256"})
        value.update(changes)
        raw = json.dumps(value, sort_keys=True).encode()
        normalized = AuctionFacts.model_validate({**json.loads(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()})
        return raw, normalized

    def admit(self, database, permission, now, *, cursor=0, request_key=None, **changes):
        raw, normalized = self.output(now, **changes)
        with database.session() as session:
            admitted = auction_sources.accept_record(session, permission, raw, normalized,
                request_key=request_key or str(uuid4()), request_url=self.endpoint + "12",
                expected_generation=1, expected_cursor_version=cursor, received_at=now, now=now)
            session.commit()
        return admitted


@pytest.fixture(params=["TI", "ZH"])
def adapter(request):
    return AdapterOutputFixture(request.param)


def read(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def post(client, path, body=None, *, status=200):
    response = client.post(path, headers=_csrf(client), json=body)
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def start(client, cantons):
    config = profile(cantons=cantons, notify={**profile().notify.model_dump(), "ending_soon_hours": 24}).model_dump(mode="json")
    preview = post(client, ROOT + "/preview", {"configuration": config})
    assert preview["start_available"] and not preview["coverage_verified"]
    assert preview["available_cantons"] == sorted(cantons) and preview["unverified_cantons"] == []
    saved = post(client, ROOT + "/monitors", {"configuration": config, "request_key": str(uuid4())}, status=201)
    path = ROOT + "/monitors/" + saved["id"]
    post(client, path + "/start", {"expected_version": 1})
    return path


def item(client, path):
    row, = read(client, path + "/items")["items"]
    return row


def decide(client, path, row, decision="inspect"):
    return post(client, path + f"/items/{row['id']}/decision", {
        "expected_version": row["version"], "expected_state_hash": row["state_hash"], "decision": decision})


def follow(client, path, row):
    return post(client, path + f"/items/{row['id']}/follow", {
        "expected_version": row["version"], "expected_state_hash": row["state_hash"], "following": True})


def project(database, settings, now):
    assert auction_jobs.refresh_due(database, settings, now=now) == {"refreshed": 1, "unavailable": 0}
    assert auction_jobs.refresh_due(database, settings, now=now) == {"refreshed": 0, "unavailable": 0}


def test_adapter_to_private_review_history_reminder_and_cancellation(api, adapter, monkeypatch):
    client, app, settings = api
    database, now = app.state.service.db, NOW
    monkeypatch.setattr(auction_api, "_now", lambda: now)
    permission = adapter.permission(database)
    initial = adapter.admit(database, permission, now, request_key="initial")
    assert adapter.admit(database, permission, now, request_key="initial") == initial
    path = start(client, [adapter.canton])
    project(database, settings, now)
    row = item(client, path)
    item_path = path + f"/items/{row['id']}"
    assert row["facts"]["source_key"] == adapter.key and row["facts"]["canton"] == adapter.canton
    assert row["source_revision_id"] == initial["revision_id"] and row["assessment"]["status"] == "match"
    row = decide(client, path, follow(client, path, row))
    assert row["decision"] == "inspect" and not row["needs_review"]
    assert auction_reminders.activate_due(database, settings, now=now)["ready"] == 1
    old, = read(client, path + "/reminders")["items"]
    assert old["eligible"]

    now += timedelta(seconds=61)
    changed = adapter.admit(database, permission, now, cursor=1, prices=[price(1270000)],
        ends_at=(NOW + timedelta(hours=21)).isoformat(), conditions_sha256="b" * 64,
        documents={"state": "complete", "items": [{"official_id": "terms", "title": "Terms", "sha256": "b" * 64}]})
    project(database, settings, now)
    row = item(client, path)
    assert row["following"] and row["decision"] == "inspect" and row["needs_review"]
    assert row["assessment"]["status"] == "excluded" and row["deadline_generation"] == 2
    assert row["source_revision_id"] == changed["revision_id"]
    feed = read(client, ROOT + "/inbox")["items"]
    crossing = next(value for value in feed if "price_above_limit" in value.get("change_codes", []))
    assert {"price_above_limit", "deadline_changed", "conditions_changed", "document_changed"} <= set(crossing["change_codes"])
    exact = read(client, path + "/events/" + crossing["id"])
    assert exact["previous"]["facts"]["prices"][0]["amount_minor"] == 850000
    assert exact["previous"]["facts"]["conditions_sha256"] == "a" * 64
    assert read(client, path + "/reminders/" + old["id"])["state"] == "invalidated"
    assert auction_reminders.activate_due(database, settings, now=now)["ready"] == 1
    replacement, = read(client, ROOT + "/reminders")["items"]
    assert replacement["id"] != old["id"] and replacement["eligible"]
    row = decide(client, path, row, "no_bid")
    reviewed_version = row["version"]
    # Reading and replaying a worker cannot create a new user decision.
    assert item(client, path)["version"] == reviewed_version

    now += timedelta(seconds=61)
    adapter.admit(database, permission, now, cursor=2, prices=[price(1290000)],
        ends_at=(NOW + timedelta(hours=21)).isoformat(), conditions_sha256="b" * 64,
        documents={"state": "complete", "items": [{"official_id": "terms", "title": "Terms", "sha256": "b" * 64}]})
    project(database, settings, now)
    assert not item(client, path)["needs_review"]
    assert auction_reminders.activate_due(database, settings, now=now)["ready"] == 0
    same, = read(client, ROOT + "/reminders")["items"]
    assert same["id"] == replacement["id"]
    with database.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(AuctionItemEvent)) == 2

    now += timedelta(seconds=61)
    adapter.admit(database, permission, now, cursor=3, status="cancelled", prices=[price(1290000)],
        ends_at=(NOW + timedelta(hours=21)).isoformat(), conditions_sha256="b" * 64,
        documents={"state": "complete", "items": [{"official_id": "terms", "title": "Terms", "sha256": "b" * 64}]})
    project(database, settings, now)
    row = item(client, path)
    assert row["facts"]["status"] == "cancelled" and row["decision"] == "no_bid" and row["needs_review"]
    assert read(client, ROOT + "/reminders")["items"] == []
    assert all(value["state"] == "invalidated" and not value["eligible"]
        for value in read(client, path + "/reminders")["items"])
    assert auction_reminders.activate_due(database, settings, now=now)["ready"] == 0
    first_page = read(client, item_path + "/history?limit=1")
    second_page = read(client, item_path + f"/history?limit=10&before={first_page['next_cursor']}")
    history = first_page["items"] + second_page["items"]
    assert len(history) == 4
    assert {entry["facts"]["source_key"] for entry in history} == {adapter.key}
    assert history[-1]["facts"]["prices"][0]["amount_minor"] == 850000
    with database.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(AuctionSourceRecordRevision)) == 4
        assert session.scalar(select(func.count()).select_from(AuctionDecision)) == 3  # follow, inspect, no-bid
        assert session.scalar(select(func.count()).select_from(AuctionItemEvent)) == 3
        assert all(value.state == "invalidated" for value in session.scalars(select(AuctionReminder)))
    assert read(client, ROOT + "/source-status")["coverage_verified"] is False


def test_unknown_adapter_fields_do_not_invent_budget_match_or_deadline(api, adapter, monkeypatch):
    client, app, settings = api
    database = app.state.service.db
    monkeypatch.setattr(auction_api, "_now", lambda: NOW)
    permission = adapter.permission(database)
    adapter.admit(database, permission, NOW, prices=[], ends_at=None, asset_location=None)
    path = start(client, [adapter.canton])
    project(database, settings, NOW)
    row = item(client, path)
    assert row["assessment"]["status"] == "unknown" and row["facts"]["prices"] == []
    assert row["facts"]["ends_at"] is None and row["facts"]["asset_location"] is None
    follow(client, path, row)
    assert auction_reminders.activate_due(database, settings, now=NOW)["ready"] == 0
    assert read(client, path + "/reminders")["items"] == []
    with database.session(include_all_organizations=True) as session:
        event, = session.scalars(select(AuctionItemEvent))
        assert event.change_codes == ["candidate_unknown"] and not event.notify
        assert session.scalar(select(func.count()).select_from(AuctionReminder)) == 0


def test_adapter_permissions_and_owner_access_still_gate_every_private_reader(api, adapter, monkeypatch):
    client, app, settings = api
    database = app.state.service.db
    monkeypatch.setattr(auction_api, "_now", lambda: NOW)
    permission = adapter.permission(database)
    # A valid normalized shape cannot widen the reviewed canton or source URL.
    with pytest.raises(DomainError):
        adapter.admit(database, permission, NOW, canton="BE")
    with pytest.raises(DomainError):
        adapter.admit(database, permission, NOW, source_url="https://other.example.invalid/auctions/12")
    adapter.admit(database, permission, NOW)
    path = start(client, [adapter.canton])
    project(database, settings, NOW)
    event, = read(client, ROOT + "/today")["items"]
    assert event["change_codes"] == ["new_match"]
    row = decide(client, path, follow(client, path, item(client, path)))
    auction_reminders.activate_due(database, settings, now=NOW)
    reminder, = read(client, path + "/reminders")["items"]
    private_paths = (path + "/items", path + f"/items/{row['id']}/history",
        path + "/events/" + event["id"], path + "/reminders/" + reminder["id"])
    owner = client.get("/api/auth/session").json()
    with TestClient(app) as peer:
        identity = _register(peer, email="adapter-peer@example.test").json()
        with database.session(include_all_organizations=True) as session:
            session.add(OrganizationMembership(organization_id=owner["organization"]["id"],
                user_id=identity["user"]["id"], role="organization_admin"))
            session.commit()
        switched = peer.post("/api/auth/session/organization", headers=_csrf(peer),
            json={"organization_id": owner["organization"]["id"]})
        assert switched.status_code == 200
        for endpoint in private_paths:
            assert peer.get(endpoint).status_code == 404
        assert read(peer, ROOT + "/today")["items"] == []
        assert read(peer, ROOT + "/reminders")["items"] == []
    with database.session() as session:
        auction_sources.revoke_permission(session, permission, now=NOW)
        session.commit()
    redacted = item(client, path)
    assert redacted["facts"] is None and redacted["assessment"] is None and not redacted["can_review"]
    assert read(client, ROOT + "/today")["items"] == []
    assert read(client, ROOT + "/reminders")["items"] == []
    retained, = read(client, path + "/reminders")["items"]
    assert retained["current"]["facts"] is None and retained["ends_at"] is None
    assert client.get(private_paths[1]).status_code == 409
    assert not read(client, private_paths[3])["eligible"]


def test_two_adapters_with_identical_publisher_ids_never_merge_or_transfer_review(api, monkeypatch):
    client, app, settings = api
    database, now = app.state.service.db, NOW
    monkeypatch.setattr(auction_api, "_now", lambda: now)
    ti, zh = AdapterOutputFixture("TI"), AdapterOutputFixture("ZH")
    permissions = {adapter.key: adapter.permission(database) for adapter in (ti, zh)}
    for adapter in (ti, zh):
        adapter.admit(database, permissions[adapter.key], now)
    path = start(client, ["TI", "ZH"])
    project(database, settings, now)
    rows = read(client, path + "/items")["items"]
    assert len(rows) == 2 and len({row["id"] for row in rows}) == 2
    assert len({(row["facts"]["auction_id"], row["facts"]["lot_id"]) for row in rows}) == 1
    by_source = {row["facts"]["source_key"]: row for row in rows}
    inspected = decide(client, path, by_source[ti.key])
    assert inspected["decision"] == "inspect" and not inspected["needs_review"]
    now += timedelta(seconds=61)
    zh.admit(database, permissions[zh.key], now, cursor=1, prices=[price(1270000)])
    project(database, settings, now)
    rows = read(client, path + "/items")["items"]
    by_source = {row["facts"]["source_key"]: row for row in rows}
    assert by_source[ti.key]["version"] == inspected["version"] and not by_source[ti.key]["needs_review"]
    assert by_source[zh.key]["needs_review"] and by_source[zh.key]["decision"] is None
    for adapter in (ti, zh):
        history = read(client, path + f"/items/{by_source[adapter.key]['id']}/history")["items"]
        assert {entry["facts"]["source_key"] for entry in history} == {adapter.key}
        assert {entry["facts"]["canton"] for entry in history} == {adapter.canton}
