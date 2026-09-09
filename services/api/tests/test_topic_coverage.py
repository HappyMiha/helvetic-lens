"""Source previews expose saved evidence of readiness, never activate collection."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, event, func, select
from test_topic_matching import plan

from helvetic_lens.models import (
    ConnectorRun,
    ConnectorSchedule,
    ConnectorState,
    Job,
    MonitoringTopic,
    Organization,
    SourcePackDefinition,
    SourcePackSubscription,
)
from helvetic_lens.synchronization import seed_schedules
from helvetic_lens.topic_coverage import snapshot

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


def stream(result, name="rss-de"):
    return next(item for item in result["items"][0]["streams"] if item["stream"] == name)


def test_unscheduled_unsubscribed_preview_remains_read_only_without_inference(harness):
    client, _, service, model = harness
    with service.db.session() as session:
        # Startup seeds schedules; explicitly model an installation with no saved
        # Fedlex schedule in this isolated fixture database.
        session.execute(delete(ConnectorSchedule).where(ConnectorSchedule.connector == "fedlex"))
        session.commit()
        tables = (ConnectorSchedule, ConnectorState, ConnectorRun, SourcePackSubscription, Job, MonitoringTopic)
        before = [session.scalar(select(func.count()).select_from(table)) for table in tables]
    response = client.post("/api/monitoring-topics/preview", json=plan())
    assert response.status_code == 200, response.text
    result = response.json()["source_coverage"]
    assert result["enabled_pack_count"] == 0 and len(result["items"]) == 1
    assert result["scope"] == "selected_packs_saved_operational_state" and result["ai_calls"] == 0
    assert result["items"][0]["subscription_state"] == "inactive"
    for item in result["items"][0]["streams"]:
        assert not item["configured"] and not item["enabled"]
        assert item["last_success_at"] is None and item["next_run_at"] is None
        assert item["last_reported_health"] == "unknown"
        assert not item["next_attempt_past_due"]
    with service.db.session() as session:
        assert before == [session.scalar(select(func.count()).select_from(table)) for table in tables]
    assert model.calls == []


def prepare(service):
    with service.db.session() as session:
        seed_schedules(session)
        schedule = session.scalar(select(ConnectorSchedule).where(
            ConnectorSchedule.connector == "fedlex", ConnectorSchedule.stream == "rss-de"))
        schedule.interval_seconds, schedule.jitter_seconds = 7200, 120
        schedule.window_start, schedule.window_end = "07:00", "20:00"
        schedule.next_run_at = NOW - timedelta(minutes=1)
        session.add(ConnectorState(connector="fedlex", stream="rss-de", contract_version="qa",
            connector_version="qa", schema_version="qa", health="degraded",
            health_message="Do not expose diagnostic text", cursor_json={"private": "not-for-preview"},
            last_success_at=NOW - timedelta(days=2)))
        session.add(SourcePackSubscription(pack_id="fedlex-legislation", enabled=True, state="partial"))
        session.add(ConnectorRun(schedule_id=schedule.id, connector="fedlex", stream="rss-de", trigger="manual",
            status="failed", error_detail="Do not expose private errors", created_at=NOW - timedelta(hours=1)))
        session.add(ConnectorRun(schedule_id=schedule.id, connector="fedlex", stream="rss-de", trigger="scheduled",
            status="partial", created_at=NOW))
        session.commit()


def test_custom_schedule_partial_health_and_old_success_are_separate_saved_facts(harness):
    client, _, service, model = harness
    prepare(service)
    with service.db.session() as session:
        result = snapshot(session, ["fedlex-legislation"], now=NOW)
    assert result["captured_at"] == NOW.isoformat() and result["timezone"] == "Europe/Zurich"
    assert result["enabled_pack_count"] == 1 and result["items"][0]["subscription_state"] == "partial"
    item = stream(result)
    assert item["interval_seconds"] == 7200 and item["jitter_seconds"] == 120
    assert (item["window_start"], item["window_end"]) == ("07:00", "20:00")
    assert item["next_attempt_past_due"] and item["configured"] and item["enabled"]
    assert item["last_success_at"] == (NOW - timedelta(days=2)).isoformat()
    assert item["last_reported_health"] == "degraded" and item["last_run_status"] == "partial"
    assert "Do not expose" not in str(result) and "not-for-preview" not in str(result)
    assert set(item["localized_copy"]) == {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"}
    # Public preview uses the same persisted schedule, not the catalogue default.
    assert stream(client.post("/api/monitoring-topics/preview", json=plan()).json()["source_coverage"])["interval_seconds"] == 7200
    assert model.calls == []


def test_paused_schedule_preserves_old_success_without_claiming_next_delivery(harness):
    _, _, service, _ = harness
    prepare(service)
    with service.db.session() as session:
        schedule = session.scalar(select(ConnectorSchedule).where(ConnectorSchedule.stream == "rss-de"))
        schedule.enabled = False
        session.commit()
        item = stream(snapshot(session, ["fedlex-legislation"], now=NOW))
    assert item["configured"] and not item["enabled"] and not item["next_attempt_past_due"]
    assert item["last_success_at"]


def test_privileged_preview_does_not_borrow_other_organization_subscription(harness):
    _, _, service, _ = harness
    prepare(service)
    with service.db.session(include_all_organizations=True) as session:
        other = Organization(name="Separate coverage owner", slug="coverage-owner")
        session.add(other)
        session.flush()
        session.scalar(select(SourcePackSubscription)).organization_id = other.id
        session.commit()
        result = snapshot(session, ["fedlex-legislation"], now=NOW)
    assert result["enabled_pack_count"] == 0
    assert not result["items"][0]["subscription_enabled"]
    assert stream(result)["configured"]  # Shared operational state is separate from subscription.


def test_one_and_all_packs_use_four_scalar_queries_without_diagnostic_hydration(harness):
    _, _, service, model = harness
    prepare(service)
    with service.db.session() as session:
        ids = list(session.scalars(select(SourcePackDefinition.id).where(SourcePackDefinition.parent_id.is_not(None))))
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())
    event.listen(service.db.engine, "before_cursor_execute", capture)
    try:
        with service.db.session() as session:
            one = snapshot(session, ["fedlex-legislation"], now=NOW)
            assert len(statements) == 4
            statements.clear()
            all_packs = snapshot(session, ids, now=NOW)
            assert len(statements) == 4
        assert len(one["items"]) == 1 and len(all_packs["items"]) == 6
        for column in ("cursor_json", "source_contract_json", "policy_json", "error_detail", "health_message"):
            assert column not in " ".join(statements)
        assert sum(len(item["streams"]) for item in all_packs["items"]) == 26
    finally:
        event.remove(service.db.engine, "before_cursor_execute", capture)
    assert model.calls == []


def test_unknown_stream_is_disclosed_and_does_not_expand_operational_queries(harness):
    _, _, service, _ = harness
    with service.db.session() as session:
        definition = session.get(SourcePackDefinition, "fedlex-legislation")
        definition.filters_json = {"streams": [["unknown", "new-source"]]}
        session.commit()
        result = snapshot(session, [definition.id], now=NOW)
        assert result["items"][0]["unknown_stream_count"] == 1
        assert result["items"][0]["streams"] == []
        with pytest.raises(ValueError):
            snapshot(session, [definition.id] * 21, now=NOW)
