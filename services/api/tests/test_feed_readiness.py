"""An empty feed needs bounded saved facts, not an invented quiet-period verdict."""

from datetime import timedelta

import pytest
from sqlalchemy import event, func, select
from test_topic_coverage import prepare
from test_topic_matching import create_topic
from test_workflow import add_law

from helvetic_lens.db import utcnow
from helvetic_lens.feed_readiness import read
from helvetic_lens.models import (
    Job,
    Law,
    MonitoringTopic,
    MonitoringTopicRevision,
    Organization,
    SourcePackDefinition,
    SourcePackSubscription,
)
from helvetic_lens.monitoring_topics import _history_key


def test_readiness_is_passive_and_source_failure_does_not_become_quiet(harness):
    client, fetcher, service, model = harness
    initial = client.get("/api/interest-feed/readiness")
    assert initial.status_code == 200, initial.text
    assert initial.json()["topics"] == [] and not initial.json()["active_document_watch"]
    prepare(service)
    law = add_law(client)
    with service.db.session() as session:
        before = session.scalar(select(func.count()).select_from(Job))
    calls = (len(fetcher.calls), len(model.calls))
    value = client.get("/api/interest-feed/readiness").json()
    assert value["sources_need_attention"] and value["enabled_pack_count_shown"] == 1
    assert (
        value["active_document_watch"]
        and not value["quiet_period_verified"]
        and not value["source_freshness_verified"]
    )
    assert "Do not expose" not in str(value) and "not-for-preview" not in str(value)
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == before
        # A watch cannot make a now foreign-owned document visible.
        session.add(Organization(id="private-owner", name="Private owner", slug="private-owner"))
        session.flush()
        session.get(Law, law["id"]).owner_organization_id = "private-owner"
        session.commit()
    assert not client.get("/api/interest-feed/readiness").json()["active_document_watch"]
    assert (len(fetcher.calls), len(model.calls)) == calls
    with service.db.session() as session:
        subscription = session.scalar(select(SourcePackSubscription))
        subscription.state = "backfilling"
        session.commit()
    assert client.get("/api/interest-feed/readiness").json()["sources_pending"]


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("queued", "queued"),
        ("failed", "failed"),
        ("complete", "complete"),
        ("legacy", "unverified"),
        ("old_evaluator", "superseded"),
        ("old_revision", "not_started"),
    ],
)
def test_history_only_reports_current_revision_and_checkpoint(harness, mode, expected):
    client, _, service, _ = harness
    topic = create_topic(client)
    with service.db.session() as session:
        record = session.get(MonitoringTopic, topic["id"])
        job = session.scalar(
            select(Job).where(Job.type == "topic_match_backfill", Job.target_id == record.id)
        )
        stamp = utcnow().isoformat()
        job.state = mode if mode in {"queued", "failed"} else "succeeded"
        job.payload = {
            "revision": record.current_revision,
            "secret": "must-not-leak",
            "checkpoint": {
                "captured_at": stamp,
                "cursor": {"created_at": stamp, "id": "private-cursor-id"},
                "processed": 500,
                "remaining": 0 if mode == "complete" else 4,
            },
        }
        job.result_json = {"status": "complete", "has_more": False, "large_private_data": "must-not-leak"}
        job.idempotency_key = _history_key(record)
        if mode == "legacy":
            job.payload = {"revision": record.current_revision}
        if mode == "old_evaluator":
            job.idempotency_key = "old-evaluation"
        if mode == "old_revision":
            job.payload = {"revision": record.current_revision - 1}
        session.commit()
    value = client.get("/api/interest-feed/readiness").json()
    row = value["topics"][0]
    assert row["history_status"] == expected
    assert row["name"] == topic["plan"]["name"]
    assert row["url"] == f"/topics#topic-{topic['id']}"
    assert not value["quiet_period_verified"]
    assert "must-not-leak" not in str(value) and "private-cursor-id" not in str(value)
    if mode == "complete":
        assert row["processed"] == 500 and row["remaining"] == 0
        assert row["captured_at"] == stamp and row["processed_through"] == stamp
    if mode in {"old_evaluator", "old_revision"}:
        assert row["processed"] is None and row["captured_at"] is None


def test_readiness_bounds_topics_and_isolates_even_privileged_sessions(harness):
    client, _, service, _ = harness
    original = create_topic(client)
    now = utcnow()
    with service.db.session(include_all_organizations=True) as session:
        session.add(Organization(id="foreign-readiness", name="Other", slug="foreign-readiness"))
        session.flush()
        for index in range(24):
            organization = service.organization_id if index < 23 else "foreign-readiness"
            topic = MonitoringTopic(
                organization_id=organization,
                idempotency_key=f"readiness-{index}",
                status="active",
                current_revision=1,
                created_at=now + timedelta(seconds=index),
            )
            session.add(topic)
            session.flush()
            session.add(
                MonitoringTopicRevision(
                    organization_id=organization,
                    topic_id=topic.id,
                    revision=1,
                    status="active",
                    name=f"topic {index}",
                    goal="do not load goal",
                )
            )
        session.add(
            SourcePackSubscription(
                organization_id="foreign-readiness",
                pack_id="fedlex-legislation",
                enabled=True,
                state="backfilling",
            )
        )
        session.commit()
    loaded, queries = [], []

    def on_load(_session, instance):
        loaded.append(type(instance).__name__)

    def on_query(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    with service.db.session(include_all_organizations=True) as session:
        event.listen(session, "loaded_as_persistent", on_load)
        event.listen(service.db.engine, "before_cursor_execute", on_query)
        try:
            value = read(session, service.organization_id, now=now)
        finally:
            event.remove(service.db.engine, "before_cursor_execute", on_query)
    assert len(value["topics"]) == 20 and value["more_topics"]
    assert original["id"] not in {row["id"] for row in value["topics"]}
    assert "topic 23" not in str(value) and value["enabled_pack_count_shown"] == 0
    assert not loaded and len(queries) <= 8
    assert "do not load goal" not in str(value)

    with service.db.session(include_all_organizations=True) as session:
        foreign = read(session, "foreign-readiness", now=now)
        assert foreign["sources_pending"] and foreign["enabled_pack_count_shown"] == 1
        assert [row["name"] for row in foreign["topics"]] == ["topic 23"]
        for index in range(21):
            pack_id = f"bounded-source-{index:02}"
            session.add(
                SourcePackDefinition(
                    id=pack_id, revision="qa", active=True, filters_json={"streams": [["unknown", "stream"]]}
                )
            )
            session.flush()
            session.add(
                SourcePackSubscription(organization_id=service.organization_id, pack_id=pack_id, enabled=True)
            )
        session.commit()
        value = read(session, service.organization_id, now=now)
        assert value["more_packs"] and value["enabled_pack_count_shown"] == 20
        assert value["sources_need_attention"] and not value["sources_pending"]
