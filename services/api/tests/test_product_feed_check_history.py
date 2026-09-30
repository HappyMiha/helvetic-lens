"""Real local connector acquisition and current dossier access to shared history."""
import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_auth import _register
from test_connectors import MANIFEST, FixtureConnector
from test_private_dossier_monitoring import private, remove
from test_product_dossiers import active, create, post
from test_product_dossiers import signed as signed
from test_product_guests import accept, guest, invitation
from test_product_teams import switch

from helvetic_lens.db import utcnow
from helvetic_lens.models import (
    ConnectorRun,
    ConnectorSchedule,
    ConnectorState,
    Job,
    MonitoringTopicRevision,
    SourcePackDefinition,
    SourcePackSubscription,
)

PARAMS = {"pack_id": "fedlex-legislation", "connector": "fedlex", "stream": "rss-de"}


def setup(client, product="pharma", activate=True):
    _, request = create(client)
    doc = post(client, f"/api/products/{product}/dossiers", {**request, "creation_key": str(uuid4())}).json()
    if activate:
        active(client, doc)
    return doc, f"/api/products/{product}/dossiers/{doc['id']}"


def read(client, root, **query):
    response = client.get(root + "/coverage/history", params={**PARAMS, **query})
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    return response.json()


def run(service):
    start = service.enqueue_connector_sync("fedlex", "rss-de")
    result = asyncio.run(service.execute_job(start["job"]["id"], worker="local-feed-fixture"))
    assert result["state"] == "succeeded", result
    return start["run"]["id"]


@pytest.mark.parametrize("product", ["legal", "pharma"])
def test_real_partial_collection_retry_completed_empty_and_failed_source(signed, monkeypatch, product):
    client, service, _, model = signed
    _, root = setup(client, product)
    connector = FixtureConnector(manifest=replace(MANIFEST, name="fedlex"), fail_identity_once="law:b")
    async def acquire(stream):
        return asdict(await service.connector_runner.run_page(connector, stream=stream))
    monkeypatch.setattr(service, "sync_fedlex", acquire)
    assert read(client, root)["items"] == []
    first_id = run(service)
    partial = read(client, root)["items"][0]
    assert partial["id"] == first_id and partial["status"] == "partial"
    assert partial["started_at"] <= partial["finished_at"] and partial["reported_counts"]["failed"] == 1
    run(service)
    completed = read(client, root)["items"][0]
    assert completed["status"] == "persisted" and completed["reported_counts"]["failed"] == 1
    assert "earlier attempts" in completed["explanation"]
    run(service)
    no_new = read(client, root)["items"][0]
    assert no_new["status"] == "persisted"
    assert no_new["reported_counts"]["new"] == no_new["reported_counts"]["changed"] == 0
    assert "does not establish unchanged" in no_new["explanation"] or "earlier attempts" in no_new["explanation"]
    with service.db.session() as session:
        success = session.scalar(select(ConnectorState.last_success_at).where(ConnectorState.connector == "fedlex", ConnectorState.stream == "rss-de"))
    connector.empty = True  # Invalid empty discovery really degrades the connector.
    run(service)
    history = read(client, root)
    assert history["items"][0]["status"] == "degraded"
    assert len(history["items"]) == 4 and history["items"][-1]["id"] == first_id
    with service.db.session() as session:
        assert session.scalar(select(ConnectorState.last_success_at).where(ConnectorState.connector == "fedlex", ConnectorState.stream == "rss-de")) == success
        before = session.scalar(select(func.count()).select_from(Job))
        row = session.scalar(select(ConnectorRun).where(ConnectorRun.id == first_id))
        row.error_detail = "PRIVATE provider credential error"
        row.input_cursor_json = {"PRIVATE": "input cursor"}
        row.output_cursor_json = {"PRIVATE": "output cursor"}
        session.commit()
    requests = len(connector.calls)
    again = read(client, root)
    assert again["items"] == history["items"] and "PRIVATE" not in str(again)
    assert all(key not in str(again) for key in ("job_id", "requested_by_organization_id", "fanout", "cursor"))
    assert len(connector.calls) == requests and model.calls == [] and service.fetcher.calls == []
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == before


@pytest.mark.parametrize("case", ["removed_pack", "removed_stream", "unsupported", "different_product", "foreign"])
def test_history_authority_uses_current_selection_and_product(signed, case):
    client, service, _, _ = signed
    _, root = setup(client)
    assert read(client, root)["source"]["stream"] == "rss-de"
    with service.db.session() as session:
        if case == "removed_pack":
            for revision in session.scalars(select(MonitoringTopicRevision)):
                revision.source_pack_ids_json = []
        elif case in {"removed_stream", "unsupported"}:
            session.get(SourcePackDefinition, PARAMS["pack_id"]).filters_json = {"streams": [["fedlex", "rss-fr"]] if case == "removed_stream" else [["unverified", "custom"]]}
        session.commit()
    if case == "foreign":
        _register(client, "foreign-feed-history@example.ch")
    response = client.get(root.replace("pharma", "legal") + "/coverage/history" if case == "different_product" else root + "/coverage/history", params=PARAMS)
    assert response.status_code == 404 and "items" not in response.text


def test_draft_disconnected_and_paused_selection_does_not_claim_topic_checks(signed):
    client, service, _, _ = signed
    _, root = setup(client, activate=False)
    draft = read(client, root)
    assert draft["profile_status"] == "draft" and not draft["topics"]
    assert not draft["pack"]["subscription_enabled"] and "not a dossier-wide scan" in draft["scope"]
    with service.db.session() as session:
        session.get(SourcePackDefinition, PARAMS["pack_id"]).active = False
        schedule = session.scalar(select(ConnectorSchedule).where(ConnectorSchedule.connector == "fedlex", ConnectorSchedule.stream == "rss-de"))
        schedule.enabled = False
        session.commit()
    saved = read(client, root)
    assert saved["pack"]["definition_state"] == "inactive" and not saved["source"]["enabled"]


def test_guest_grant_and_revocation_control_shared_history(signed):
    client, service, _, _ = signed
    owner = dict(client.cookies)
    account, cookies = guest(client, service)
    _, root, _ = private(client)
    invite = invitation(client, root, account, "VIEWER")
    switch(client, cookies)
    assert client.get(root + "/coverage/history", params=PARAMS).status_code == 404
    accept(client, root, invite)
    assert read(client, root)["pack"]["subscription_enabled"]
    switch(client, owner)
    remove(client, root, account["user"]["id"])
    switch(client, cookies)
    assert client.get(root + "/coverage/history", params=PARAMS).status_code == 404
    client.cookies.clear()
    assert client.get(root + "/coverage/history", params=PARAMS).status_code == 401


def test_pagination_cutoff_and_unknown_timestamps_and_statuses(signed):
    client, service, _, _ = signed
    _, root = setup(client)
    with service.db.session() as session:
        schedule = session.scalar(select(ConnectorSchedule).where(ConnectorSchedule.connector == "fedlex", ConnectorSchedule.stream == "rss-de"))
        for i in range(24):
            session.add(ConnectorRun(schedule_id=schedule.id, connector="fedlex", stream="rss-de", status=["queued", "running", "unknown_new", "interrupted", "cancelled", "failed"][i % 6]))
        session.commit()
    first = read(client, root)
    seen = first["items"]
    cursor = first["next_offset"]
    while cursor is not None:
        value = read(client, root, offset=cursor, as_of=first["as_of"])
        seen.extend(value["items"])
        cursor = value["next_offset"]
    assert len(seen) == len({r["id"] for r in seen}) == 24
    assert all(r["started_at"] is None and r["finished_at"] is None for r in seen)
    assert all(r["reported_counts"] is None for r in seen if r["status"] != "failed")
    assert {r["status"] for r in seen} == {"queued", "running", "unknown", "interrupted", "cancelled", "failed"}
    service.enqueue_connector_sync("fedlex", "rss-de")
    assert read(client, root, as_of=first["as_of"])["total"] == 24
    assert read(client, root)["total"] == 25
    for query in ({"offset": 10}, {"offset": -1}, {"as_of": "2026-01-01T00:00:00"}, {"as_of": (utcnow()+timedelta(days=1)).isoformat()}):
        assert client.get(root + "/coverage/history", params={**PARAMS, **query}).status_code == 422
    with service.db.session() as session:
        for sub in session.scalars(select(SourcePackSubscription)):
            sub.enabled = False
        session.commit()
    assert read(client, root)["total"] == 25 and not read(client, root)["pack"]["subscription_enabled"]
