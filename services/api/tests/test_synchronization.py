import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from helvetic_lens import synchronization
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    ConnectorRun,
    ConnectorSchedule,
    DocumentWatch,
    FeedState,
    Job,
    Law,
    LegacyDocumentMapping,
    Organization,
    RegulatoryDocumentVersion,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryExpression,
    RegulatoryWork,
)


def test_default_schedules_are_persisted_and_visible(harness):
    client, _, service, _ = harness

    response = client.get("/api/admin/connectors")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 11
    assert {(item["connector"], item["stream"]) for item in payload["items"]} >= {
        ("fedlex", "rss-de"),
        ("swiss-parliament", "recent"),
        ("federal-supreme-court", "latest"),
    }
    assert payload["pressure"]["blocked"] is False
    with service.db.session(include_all_organizations=True) as session:
        assert synchronization.seed_schedules(session) == 0


def test_due_scheduler_is_bounded_jittered_and_restart_safe(harness):
    _, _, service, _ = harness
    now = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
    with service.db.session(include_all_organizations=True) as session:
        schedules = session.scalars(select(ConnectorSchedule)).all()
        selected = next(item for item in schedules if item.stream == "rss-de")
        for item in schedules:
            item.enabled = item.id == selected.id
        selected.interval_seconds = 600
        selected.jitter_seconds = 60
        selected.next_run_at = now - timedelta(seconds=1)
        session.commit()

        first = synchronization.enqueue_due(session, service.settings, now=now)
        session.commit()
        next_due = selected.next_run_at
        repeated = synchronization.enqueue_due(session, service.settings, now=now)
        session.commit()

        assert first["queued"] == 1
        assert repeated["queued"] == 0
        assert now + timedelta(seconds=600) <= next_due <= now + timedelta(seconds=660)
        assert session.scalar(
            select(func.count()).select_from(Job).where(Job.type == "connector_sync")
        ) == 1
        assert session.scalar(select(func.count()).select_from(ConnectorRun)) == 1


def test_manual_sync_reuses_active_lock_and_worker_records_run(harness, monkeypatch):
    _, _, service, _ = harness
    first = service.enqueue_connector_sync("fedlex", "rss-de")
    second = service.enqueue_connector_sync("fedlex", "rss-de")
    assert first["reused"] is False
    assert second["reused"] is True
    assert second["job"]["id"] == first["job"]["id"]

    async def completed(_stream):
        return {
            "connector": "fedlex",
            "stream": "rss-de",
            "status": "persisted",
            "page_id": None,
            "persisted": 0,
            "total": 0,
            "next_cursor": {"published": "2026-09-03T08:00:00Z"},
            "error": None,
        }

    monkeypatch.setattr(service, "sync_fedlex", completed)
    result = asyncio.run(service.execute_job(first["job"]["id"], worker="fixture-worker"))

    assert result["state"] == "succeeded"
    assert result["result"]["data"]["run"]["status"] == "persisted"
    assert result["result"]["data"]["run"]["output_cursor"] == {
        "published": "2026-09-03T08:00:00Z"
    }


def test_shared_event_fans_out_to_two_organizations_once(harness):
    _, _, service, _ = harness
    with service.db.session(include_all_organizations=True) as session:
        second_org = Organization(name="Second organization", slug="second-organization")
        law = Law(
            owner_organization_id=None,
            canonical_identity="https://fedlex.data.admin.ch/eli/cc/2026/42",
            name="Shared act",
            url="https://fedlex.data.admin.ch/eli/cc/2026/42",
            provider="fedlex",
        )
        work = RegulatoryWork(
            owner_organization_id=None,
            kind="act",
            authority="fedlex",
            canonical_key="eli_uri:https://fedlex.data.admin.ch/eli/cc/2026/42",
            title="Shared act",
            stable_official_url="https://fedlex.data.admin.ch/eli/cc/2026/42",
        )
        session.add_all([second_org, law, work])
        session.flush()
        expression = RegulatoryExpression(
            work_id=work.id,
            language="de",
            expression_key="shared-act-de",
            title="Shared act",
        )
        mapping = LegacyDocumentMapping(
            owner_organization_id=None,
            law_id=law.id,
            work_id=work.id,
            mapping_status="matched",
        )
        session.add_all([expression, mapping])
        session.flush()
        version = RegulatoryDocumentVersion(
            expression_id=expression.id,
            version_key="2026-09-03",
            content_hash="a" * 64,
            artifact_key="a" * 64 + ".html",
            extractor="html-v1",
            text="One shared immutable artifact.",
            passages=[{"id": "p1", "text": "One shared immutable artifact."}],
        )
        watches = [
            DocumentWatch(
                organization_id=service.organization_id,
                law_id=law.id,
                display_name="Shared act",
            ),
            DocumentWatch(
                organization_id=second_org.id,
                law_id=law.id,
                display_name="Shared act",
            ),
        ]
        schedule = session.scalar(
            select(ConnectorSchedule).where(
                ConnectorSchedule.connector == "fedlex",
                ConnectorSchedule.stream == "rss-de",
            )
        )
        started = datetime.now(UTC) - timedelta(seconds=1)
        run = ConnectorRun(
            schedule_id=schedule.id,
            connector="fedlex",
            stream="rss-de",
            trigger="scheduled",
            status="running",
            started_at=started,
        )
        event = RegulatoryEvent(
            work_id=work.id,
            expression_id=expression.id,
            document_version_id=version.id,
            authority="fedlex",
            event_type="new_version",
            dedupe_key="fixture-shared-event",
            detected_at=datetime.now(UTC),
            source_url=law.url,
            provenance_method="official_metadata",
            connector="fedlex",
            connector_health="healthy",
            evidence_json={"stream": "rss-de"},
        )
        session.add_all([version, *watches, run, event])
        session.flush()

        finished = synchronization.finish_run(
            session,
            run.id,
            {
                "status": "persisted",
                "page_id": None,
                "next_cursor": {"published": "2026-09-03T08:00:00Z"},
            },
        )
        session.commit()

        assert finished.changed_count == 1
        assert finished.fanout_count == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryEventState)) == 2
        assert session.scalar(select(func.count()).select_from(FeedState)) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryDocumentVersion)) == 1
        assert session.scalar(select(func.count()).select_from(RegulatoryEvent)) == 1

        first_started_at = finished.started_at
        synchronization.fail_run(
            session,
            run.id,
            "worker disappeared after persistence",
            now=datetime.now(UTC),
        )
        restarted = synchronization.start_run(
            session,
            run.id,
            now=datetime.now(UTC) + timedelta(seconds=1),
        )
        assert restarted.started_at == first_started_at
        assert restarted.finished_at is None
        assert restarted.error_detail is None

        repeated = synchronization.finish_run(
            session,
            run.id,
            {
                "status": "persisted",
                "page_id": None,
                "next_cursor": {"published": "2026-09-03T08:00:00Z"},
            },
        )
        session.commit()
        assert repeated.fanout_count == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryEventState)) == 2
        assert session.scalar(select(func.count()).select_from(FeedState)) == 2


def test_pause_window_validation_and_backpressure(harness):
    client, _, service, _ = harness
    changed = client.put(
        "/api/admin/connectors/fedlex/rss-de",
        json={
            "enabled": False,
            "interval_seconds": 900,
            "jitter_seconds": 30,
            "window_start": "22:00",
            "window_end": "05:00",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["enabled"] is False
    invalid = client.put(
        "/api/admin/connectors/fedlex/rss-de",
        json={
            "enabled": True,
            "interval_seconds": 900,
            "jitter_seconds": 700,
            "window_start": None,
            "window_end": None,
        },
    )
    assert invalid.status_code == 422

    service.enqueue_connector_sync("fedlex", "rss-it")
    constrained = service.settings.model_copy(update={"connector_max_active_jobs": 1})
    with service.db.session(include_all_organizations=True) as session:
        with pytest.raises(DomainError) as error:
            synchronization.enqueue_manual(
                session,
                constrained,
                "fedlex",
                "rss-fr",
                service.organization_id,
            )
        assert error.value.code == "connector_backpressure"
