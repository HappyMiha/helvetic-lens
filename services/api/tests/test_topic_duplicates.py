"""Warn about matching rules without changing shared monitoring or leaking another owner."""

import pytest
from sqlalchemy import event, func, select
from test_topic_matching import create_topic, plan

from helvetic_lens.models import Job, MonitoringTopic, MonitoringTopicRevision, Organization
from helvetic_lens.monitoring_topics import matching_rule_topics


def preview(client, **changes):
    response = client.post("/api/monitoring-topics/preview", json=plan(**changes))
    assert response.status_code == 200, response.text
    return response.json()["matching_topics"]


def test_rule_warning_is_read_only_case_order_insensitive_and_excludes_self(harness):
    client, _, service, model = harness
    original = create_topic(client)
    with service.db.session() as session:
        before = [session.scalar(select(func.count()).select_from(table))
                  for table in (MonitoringTopic, MonitoringTopicRevision, Job)]
    result = preview(client, name="Different title", goal="Different intended purpose",
                     concepts=["sr 141.0", "NATURALISATION"], languages=list(reversed(plan()["languages"])))
    assert result["items"] == [{"id": original["id"], "name": plan()["name"],
                                "status": "active", "current_revision": 1}]
    assert result["count_is_complete"] and result["match_count"] == 1
    assert preview(client, exclude_topic_id=original["id"])["items"] == []
    assert preview(client, exclude_topic_id="not-a-visible-topic")["match_count"] == 1
    with service.db.session() as session:
        assert before == [session.scalar(select(func.count()).select_from(table))
                          for table in (MonitoringTopic, MonitoringTopicRevision, Job)]
    assert model.calls == []


@pytest.mark.parametrize("change", [
    {"concepts": ["citizenship"]}, {"synonyms": ["immigration"]}, {"exclusions": []},
    {"jurisdictions": ["GE"]}, {"languages": ["de"]}, {"source_pack_ids": ["swiss-parliament"]},
    {"document_kinds": ["bill"]}, {"event_kinds": ["repealed"]}, {"importance_floor": "high"},
    {"concepts": plan()["synonyms"], "synonyms": plan()["concepts"]},
])
def test_different_rule_or_concept_synonym_role_is_not_called_identical(harness, change):
    client, _, _, _ = harness
    create_topic(client)
    assert preview(client, **change)["items"] == []


def test_only_current_rules_and_active_or_paused_topics_are_compared(harness):
    client, _, _, _ = harness
    topic = create_topic(client)
    updated = client.put(f"/api/monitoring-topics/{topic['id']}",
                         json={**plan(concepts=["new subject"]), "expected_revision": 1})
    assert updated.status_code == 200, updated.text
    assert preview(client)["items"] == []
    paused = client.patch(f"/api/monitoring-topics/{topic['id']}/status",
                         json={"status": "paused", "expected_revision": 2})
    assert paused.status_code == 200, paused.text
    match = preview(client, concepts=["new subject"])["items"][0]
    assert match["status"] == "paused" and match["current_revision"] == 3
    archived = client.patch(f"/api/monitoring-topics/{topic['id']}/status",
                           json={"status": "archived", "expected_revision": 3})
    assert archived.status_code == 200, archived.text
    assert preview(client, concepts=["new subject"])["items"] == []


def test_privileged_query_still_checks_both_topic_and_revision_owners(harness):
    client, _, service, _ = harness
    topic = create_topic(client)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Private other owner", slug="duplicate-other")
        session.add(other)
        session.flush()
        revision = session.scalar(select(MonitoringTopicRevision).where(MonitoringTopicRevision.topic_id == topic["id"]))
        revision.organization_id = other.id
        session.commit()
        assert matching_rule_topics(session, plan())["items"] == []
        revision.organization_id = session.info["organization_id"]
        session.get(MonitoringTopic, topic["id"]).organization_id = other.id
        session.commit()
        assert matching_rule_topics(session, plan())["items"] == []
    assert preview(client)["items"] == []


def test_warning_reads_at_most_501_current_scalar_rules_and_discloses_both_limits(harness):
    client, _, service, model = harness
    # Actual database-sized boundary, not a monkeypatched smaller limit.
    with service.db.session() as session:
        for index in range(501):
            topic = MonitoringTopic(id=f"duplicate-{index:04}", idempotency_key=f"duplicate-{index:04}",
                                    status="active", current_revision=1)
            session.add(topic)
            session.flush()
            session.add(MonitoringTopicRevision(topic_id=topic.id, revision=1, status="active",
                name=f"Topic {index}", goal="Must not hydrate this description", importance_floor="low",
                **{f"{key}_json": value for key, value in plan().items() if isinstance(value, list)}))
        session.commit()
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if "monitoring_topic_revisions" in statement.lower():
            statements.append(statement.lower())
    event.listen(service.db.engine, "before_cursor_execute", capture)
    try:
        result = preview(client)
    finally:
        event.remove(service.db.engine, "before_cursor_execute", capture)
    assert result["scanned_count"] == result["scan_limit"] == result["match_count"] == 500
    assert not result["count_is_complete"] and result["display_truncated"]
    assert len(result["items"]) == 10
    assert len(statements) == 1 and "limit" in statements[0]
    assert "monitoring_topic_revisions.goal" not in statements[0]
    assert model.calls == []


def test_viewer_can_review_existing_rules_but_cannot_activate_a_duplicate(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_monitoring_topics import auth_settings

    from helvetic_lens.auth import CSRF_COOKIE
    from helvetic_lens.main import create_app
    from helvetic_lens.models import OrganizationMembership

    app = create_app(auth_settings(tmp_path), fetcher=FakeFetcher(), model_client=ScriptedModel())
    with TestClient(app) as client:
        registered = client.post("/api/auth/register", json={
            "email": "duplicate-viewer@example.invalid", "password": "correct horse battery staple",
            "name": "Reader", "organization_name": "Duplicate QA",
        })
        assert registered.status_code == 201, registered.text
        headers = {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}
        created = client.post("/api/monitoring-topics", json={**plan(), "idempotency_key": "qa-duplicate-original"}, headers=headers)
        assert created.status_code == 201, created.text
        with app.state.service.db.session(include_all_organizations=True) as session:
            membership = session.scalar(select(OrganizationMembership))
            membership.role = "viewer"
            session.commit()
        checked = client.post("/api/monitoring-topics/preview", json=plan(), headers=headers)
        assert checked.status_code == 200, checked.text
        assert checked.json()["matching_topics"]["items"][0]["id"] == created.json()["id"]
        denied = client.post("/api/monitoring-topics", json={**plan(), "idempotency_key": "qa-duplicate-new-one"}, headers=headers)
        assert denied.status_code == 403
        with app.state.service.db.session(include_all_organizations=True) as session:
            assert session.scalar(select(func.count()).select_from(MonitoringTopic)) == 1
