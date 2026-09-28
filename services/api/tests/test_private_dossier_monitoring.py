"""Private activation across native readers, recipient projections and retained mail."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from test_auth import _csrf
from test_legal_profiles import config
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_teams import colleague, switch
from test_topic_matching import add_event
from test_topic_validity import evaluate

from helvetic_lens import digests, interest_admission
from helvetic_lens.auth_mail import AuthMailer
from helvetic_lens.db import utcnow
from helvetic_lens.models import (
    DigestDelivery,
    Job,
    MonitoringTopic,
    MonitoringTopicRevision,
    TopicEventMatch,
)
from helvetic_lens.product_access import request_context


def private(client, product="pharma"):
    root = f"/api/products/{product}/dossiers"
    created = post(client, root, {"creation_key": str(uuid4()), "config": config(name="Private naturalisation project")})
    assert created.status_code == 201, created.text
    doc = created.json()
    root += "/" + doc["id"]
    assert post(client, root + "/team/enable", {"expected_revision": 1}).status_code == 200
    activated = post(client, "/api/monitoring-profiles/" + doc["profile"]["id"] + "/activate",
        {"expected_revision": 1, "monitoring_audience": "team"})
    assert activated.status_code == 200, activated.text
    return doc, root, activated.json()["topics"][0]


def invite(client, root, user_id, role, recipient):
    owner = dict(client.cookies)
    result = post(client, root + "/team/invitations", {"expected_revision": client.get(root + "/team").json()["revision"],
        "request_key": str(uuid4()), "user_id": user_id, "role": role})
    assert result.status_code == 201, result.text
    switch(client, recipient)
    route = root.split("/dossiers/")[0] + "/dossier-invitations/" + result.json()["invitation"]["id"] + "/accept"
    assert post(client, route, {}).status_code == 200
    switch(client, owner)


def remove(client, root, user_id):
    result = post(client, root + "/team/members/" + user_id + "/remove",
        {"expected_revision": client.get(root + "/team").json()["revision"]})
    assert result.status_code == 200, result.text


def matches(service, topic):
    event = add_event(service)
    evaluate(service, topic, event, "history")
    with service.db.session() as session:
        rows = list(session.scalars(select(TopicEventMatch).where(TopicEventMatch.topic_id == topic["id"])))
        assert rows
        for row in rows:
            row.matched_at = utcnow() - timedelta(seconds=1)
        session.commit()
        return event, rows[0].id


@pytest.mark.parametrize("product", ["pharma", "loyer"])
def test_private_activation_hides_every_native_reader_and_keeps_invited_access(signed, product):
    client, service, identity, _ = signed
    owner = dict(client.cookies)
    colleague_id, cookies = colleague(client, service, identity, role="organization_admin")
    doc, root, topic = private(client, product)
    event, match = matches(service, topic)
    original = client.post(root + "/files", headers=_csrf(client), files={"file": ("private.txt", b"Team original", "text/plain")}).json()
    access = client.get(root).json()["access"]
    assert access["audience"] == "team" and access["can_watch_pages"] is False
    with service.db.session() as session:
        job = session.scalar(select(Job).where(Job.target_type == "monitoring_topic", Job.target_id == topic["id"]))
        job_id = job.id
    routes = [root, root + "/export", root + "/entries", root + "/team", root + "/files/" + original["id"],
        "/api/monitoring-profiles/" + doc["profile"]["id"], "/api/monitoring-topics/" + topic["id"],
        "/api/monitoring-topics/" + topic["id"] + "/matches", "/api/monitoring-topics/" + topic["id"] + "/matches/page",
        "/api/topic-matches/" + match + "/reviews", "/api/jobs/" + job_id]
    for route in routes:
        assert client.get(route).status_code == 200, route
    switch(client, cookies)
    for route in routes:
        response = client.get(route)
        assert response.status_code == 404, (route, response.text)
    for route in [root.split("/dossiers/")[0] + "/dossiers", "/api/monitoring-profiles", "/api/monitoring-topics",
            "/api/jobs", "/api/interest-feed", "/api/interest-feed/readiness", "/api/onboarding",
            f"/api/products/{product}/workbench", f"/api/products/{product}/discover?provider=workspace&q=Private"]:
        response = client.get(route)
        assert response.status_code == 200, response.text
        assert topic["id"] not in response.text and "Private naturalisation project" not in response.text
    assert client.get("/api/interest-feed?event=" + event).json()["items"] == []
    assert post(client, "/api/jobs/" + job_id + "/cancel", {}).status_code == 404
    switch(client, owner)
    invite(client, root, colleague_id, "VIEWER", cookies)
    switch(client, cookies)
    for route in routes:
        assert client.get(route).status_code == 200, route
    assert client.get(root).json()["access"]["role"] == "VIEWER"
    assert client.get("/api/interest-feed?event=" + event).json()["items"][0]["topic_matches"][0]["topic_id"] == topic["id"]
    assert post(client, "/api/jobs/" + job_id + "/cancel", {}).status_code == 403
    switch(client, owner)
    remove(client, root, colleague_id)
    switch(client, cookies)
    for route in routes:
        assert client.get(route).status_code == 404, route


def test_shared_brief_context_excludes_private_interests_and_sql_alias_counts_are_scoped(signed):
    client, service, identity, _ = signed
    other_id, _ = colleague(client, service, identity)
    _, _, topic = private(client)
    event, _ = matches(service, topic)
    with service.db.session() as session:
        assert interest_admission._topics(session, service.organization_id, event) == []
    for user_id, count in [(identity["user"]["id"], 1), (other_id, 0), (identity["user"]["id"], 1)]:
        actor = SimpleNamespace(user_id=user_id)
        with request_context("/api/monitoring-topics", "GET", actor), service.db.session() as session:
            model = aliased(MonitoringTopic)
            revision = aliased(MonitoringTopicRevision)
            assert session.scalar(select(func.count()).select_from(model)) == count
            assert len(session.execute(select(model.id, revision.name).join(revision, revision.topic_id == model.id)).all()) == count


def test_prepared_digest_and_saved_history_recheck_team_after_revocation(signed, monkeypatch):
    client, service, identity, _ = signed
    owner = dict(client.cookies)
    user_id, cookies = colleague(client, service, identity)
    _, root, topic = private(client)
    invite(client, root, user_id, "VIEWER", cookies)
    event, _ = matches(service, topic)
    service.save_digest_preference(user_id, enabled=True, frequency="weekly", sources=[], severities=[])
    job = service.enqueue_digest_now(user_id)
    with service.db.session() as session:
        selection = digests.prepare_batch(session, job["target_id"], settings=service.settings)
        assert selection["event_ids"] == [event]
    sent = []
    monkeypatch.setattr(AuthMailer, "send_message", lambda *args, **kwargs: sent.append(args) or "development")
    delivered = digests.deliver(service.db, service.environment_settings, job["target_id"], selection=selection)
    assert delivered["status"] == "succeeded" and len(sent) == 1
    with service.db.session() as session:
        saved_job = session.get(Job, job["id"])
        saved_job.result_json = delivered
        saved_job.result_type = "digest_delivery"
        session.commit()
    switch(client, cookies)
    assert topic["id"] in client.get("/api/digests").text
    assert topic["id"] in client.get("/api/jobs/" + job["id"]).text
    switch(client, owner)
    assert client.get("/api/jobs/" + job["id"]).status_code == 404
    with service.db.session() as session:
        original = session.get(DigestDelivery, job["target_id"])
        # Prepare another period before revocation, then recheck it at delivery.
        pending = DigestDelivery(organization_id=original.organization_id, user_id=user_id,
            preference_id=original.preference_id, frequency=original.frequency,
            period_start=original.period_start - timedelta(seconds=1), period_end=original.period_end + timedelta(microseconds=1),
            status="queued")
        session.add(pending)
        session.commit()
        pending_id = pending.id
        pending_selection = digests.prepare_batch(session, pending_id, settings=service.settings)
        assert pending_selection["event_ids"] == [event]
    remove(client, root, user_id)
    switch(client, cookies)
    assert client.get("/api/interest-feed").json()["items"] == []
    for route in ["/api/digests", "/api/jobs/" + job["id"]]:
        result = client.get(route)
        assert result.status_code == 200, result.text
        assert topic["id"] not in result.text and topic["plan"]["name"] not in result.text
    with service.db.session() as session:
        original = session.get(DigestDelivery, job["target_id"])
        assert original.summary["events"][0]["topics"][0]["topic_id"] == topic["id"]
    sent.clear()
    result = digests.deliver(service.db, service.environment_settings, pending_id, selection=pending_selection)
    assert result["status"] == "skipped" and not sent


def test_private_activation_requires_team_and_never_starts_a_workspace_page_watch(signed, monkeypatch):
    from test_product_dossiers import create

    client, service, _, _ = signed
    doc, _ = create(client)
    route = "/api/monitoring-profiles/" + doc["profile"]["id"] + "/activate"
    result = post(client, route, {"expected_revision": 1, "monitoring_audience": "team"})
    assert result.status_code == 409
    assert client.get(route.removesuffix("/activate")).json()["status"] == "draft"
    _, root, _ = private(client)
    reference = post(client, root + "/entries", {"request_key": str(uuid4()), "kind": "reference",
        "title": "Private source selection", "body": "Research reference", "url": "https://example.org/evidence"})
    assert reference.status_code == 201
    async def forbidden(*args, **kwargs):
        pytest.fail("Private page-watch rejection must happen before any fetch or library write")
    monkeypatch.setattr(service, "add_law", forbidden)
    result = post(client, root + "/sources/" + reference.json()["id"] + "/monitor", {})
    assert result.status_code == 409 and "shared workspace library" in result.text
    assert client.get(root).json()["documents"] == []


def test_migration_preserves_existing_workspace_monitoring_and_refuses_privacy_downgrade(signed):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from test_account_deletion_migration import config as migration_config
    from test_product_dossiers import active, create

    from alembic import command
    from helvetic_lens.db import Base

    client, service, _, _ = signed
    doc, _ = create(client)
    old = active(client, doc)
    tables = {"product_dossiers", "monitoring_topics"}
    with service.db.engine.connect() as connection:
        command.downgrade(migration_config(connection), "fcc495bef124")
        command.upgrade(migration_config(connection), "head")
        context = MigrationContext.configure(connection, opts={"include_object":
            lambda obj, name, kind, reflected, other: kind != "table" or name in tables})
        assert compare_metadata(context, Base.metadata) == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    current = client.get("/api/products/pharma/dossiers/" + doc["id"]).json()
    assert current["access"]["audience"] == "workspace"
    assert current["profile"]["topic_ids"] == old["topic_ids"]
    _, _, topic = private(client)
    with service.db.engine.connect() as connection:
        with pytest.raises(RuntimeError, match="private dossier monitoring"):
            command.downgrade(migration_config(connection), "fcc495bef124")
        from alembic.script import ScriptDirectory

        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == ScriptDirectory.from_config(migration_config(connection)).get_current_head()
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert client.get("/api/monitoring-topics/" + topic["id"]).status_code == 200


def test_private_topic_cannot_point_to_a_dossier_from_another_workspace(signed):
    from sqlalchemy.exc import IntegrityError
    from test_auth import _register

    client, service, _, _ = signed
    _, _, topic = private(client)
    owner = dict(client.cookies)
    client.cookies.clear()
    assert _register(client, "foreign@example.ch", "Foreign workspace").status_code == 201
    foreign, _, _ = private(client)
    switch(client, owner)
    with service.db.session() as session:
        row = session.get(MonitoringTopic, topic["id"])
        row.dossier_id = foreign["id"]
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    assert client.get("/api/monitoring-topics/" + topic["id"]).status_code == 200


def test_active_private_contribution_runs_then_revocation_pauses_queued_research(signed, monkeypatch):
    from test_product_contributions import model_output, no_discovery, submit
    from test_product_investigations import complete, tick

    client, service, identity, model = signed
    owner = dict(client.cookies)
    user_id, cookies = colleague(client, service, identity)
    _, root, _ = private(client)
    invite(client, root, user_id, "CONTRIBUTOR", cookies)
    switch(client, cookies)
    model_output(monkeypatch, model)
    calls = no_discovery(monkeypatch)
    entry, _ = submit(client, root)
    done = complete(client, service, root + "/investigations", entry["analysis"])
    assert done["status"] == "completed" and done["evidence"] and not calls
    pending, _ = submit(client, root, body="Private queued contribution after the first completed review.")
    switch(client, owner)
    remove(client, root, user_id)
    tick(service, pending["analysis"]["id"])
    state = client.get(root + "/investigations/" + pending["analysis"]["id"]).json()
    assert state["status"] == "paused" and not state["claims"]
    switch(client, cookies)
    assert client.get(root + "/investigations").status_code == 404
    assert not calls


def test_event_wide_matching_job_never_exposes_private_cursor_or_topic_totals(signed):
    from test_topic_history import execute
    from test_topic_live import enqueue

    client, service, identity, _ = signed
    _, cookies = colleague(client, service, identity, role="organization_admin")
    _, _, topic = private(client)
    event = add_event(service)
    job_id, _ = enqueue(service, event)
    completed = execute(service, job_id)
    assert completed["state"] == "succeeded"
    assert completed["result"]["data"]["cursor"] == topic["id"]
    assert completed["result"]["data"]["eligible_topics"] == 1
    switch(client, cookies)
    for route in ["/api/jobs/" + job_id, "/api/jobs"]:
        response = client.get(route)
        assert response.status_code == 200
        assert topic["id"] not in response.text and "eligible_topics" not in response.text
    public = client.get("/api/jobs/" + job_id).json()
    assert public["result"]["data"] == {"status": "complete", "details_redacted": True}
    assert public["progress"] == {"current": 1, "total": 1, "unit": "job"}
    with service.db.session() as session:
        saved = session.get(Job, job_id)
        assert saved.result_json["checkpoint"]["cursor"] == topic["id"]
