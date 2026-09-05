"""Eligibility is machine state; confirmation/rejection belongs to its evidence."""

from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from test_topic_history import execute
from test_topic_live import enqueue
from test_topic_matching import add_event, create_topic, plan

from alembic import command
from helvetic_lens import topic_matching
from helvetic_lens.config import DomainError
from helvetic_lens.db import utcnow
from helvetic_lens.models import (
    Job,
    Organization,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    SourcePackDefinition,
    TopicEventMatch,
)


def evaluate(service, topic, event_id, path):
    if path == "live":
        job_id, _ = enqueue(service, event_id)
        result = execute(service, job_id)
        assert result["state"] == "succeeded"
        return result["result"]["data"]
    with service.db.session() as session:
        result = topic_matching.run_backfill(session, topic["id"], 1, service.settings)
        session.commit()
        return result


@pytest.mark.parametrize("decision", ["confirmed", "rejected", "muted"])
@pytest.mark.parametrize("path", ["history", "live"])
def test_nonmatch_and_changed_positive_preserve_reviewed_evidence(harness, decision, path):
    client, _, service, model = harness
    event_id = add_event(service)
    topic = create_topic(client)
    evaluate(service, topic, event_id, path)
    endpoint = f"/api/monitoring-topics/{topic['id']}/matches"
    with service.db.session() as session:
        record = session.scalar(select(TopicEventMatch))
        record.decision_status = decision  # Existing scripted review: no invented UI/actor.
        original = deepcopy(record.evidence_references_json)
        original_fingerprint = record.evaluation_fingerprint
        session.commit()
    assert client.get(endpoint).json()[0]["decision_is_current"] is True
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        event.evidence_json = {**event.evidence_json, "correction": "sport"}
        session.commit()
    waiting = client.get(endpoint).json()[0]
    assert waiting["validity"] == "evidence_changed" and waiting["confidence"] is None
    assert waiting["decision_is_current"] is False
    result = evaluate(service, topic, event_id, path)
    assert result["invalidated"] == 1 and result["excluded"] == 1
    invalid = client.get(endpoint).json()[0]
    assert invalid["validity"] == "not_matching" and invalid["is_current"] is False
    assert invalid["decision"] == decision and invalid["decision_is_current"] is False
    assert invalid["evidence"] == invalid["review_evidence"]["evidence"] == original
    assert invalid["review_evidence"]["evaluation_fingerprint"] == original_fingerprint
    with service.db.session() as session:
        record = session.scalar(select(TopicEventMatch))
        checked_at = record.evaluated_at
        topic_matching.generate_for_events(session, [session.get(RegulatoryEvent, event_id)], service.settings, topic_id=topic["id"])
        session.commit()
        assert record.evaluated_at == checked_at  # Duplicate negative is not a new result.
        event = session.get(RegulatoryEvent, event_id)
        event.evidence_json = {**original["source_evidence"], "correction": "a new official reference"}
        session.commit()
    evaluate(service, topic, event_id, path)
    updated = client.get(endpoint).json()[0]
    assert updated["validity"] == "matching" and updated["confidence"] == "high"
    assert updated["decision"] == decision and updated["decision_is_current"] is False
    assert updated["review_evidence"] == invalid["review_evidence"]
    assert updated["evidence"] != original
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 1
    assert model.calls == []


@pytest.mark.parametrize("change", ["title", "pack", "rule", "plan", "paused"])
def test_reads_never_certify_stale_inputs_or_obsolete_plans(harness, monkeypatch, change):
    client, _, service, _ = harness
    event_id = add_event(service)
    topic = create_topic(client)
    evaluate(service, topic, event_id, "history")
    with service.db.session() as session:
        if change == "title":
            work = session.get(RegulatoryWork, session.get(RegulatoryEvent, event_id).work_id)
            work.title = "Corrected official title, same reference"
        elif change == "pack":
            session.get(SourcePackDefinition, "fedlex-legislation").active = False
        session.commit()
    if change == "rule":
        monkeypatch.setattr(topic_matching, "RULE_REVISION", "future-test-rule")
    elif change == "plan":
        assert client.put(f"/api/monitoring-topics/{topic['id']}", json={**plan(synonyms=["new citizenship synonym"]), "expected_revision": 1}).status_code == 200
    elif change == "paused":
        assert client.patch(f"/api/monitoring-topics/{topic['id']}/status", json={"status": "paused", "expected_revision": 1}).status_code == 200
    result = client.get(f"/api/monitoring-topics/{topic['id']}/matches").json()[0]
    assert result["validity"] == {"title": "evidence_changed", "pack": "evidence_changed", "rule": "rule_changed", "plan": "plan_changed", "paused": "plan_changed"}[change]
    assert result["is_current"] is False and result["confidence"] is None


def test_revoked_admission_and_foreign_owner_cannot_read_retained_match(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    topic = create_topic(client)
    evaluate(service, topic, event_id, "history")
    with service.db.session() as session:
        foreign = Organization(name="Unrelated", slug="validity-foreign")
        session.add(foreign)
        session.flush()
        foreign_id = foreign.id
        session.add(RegulatoryEventState(event_id=event_id, organization_id=foreign.id))
        state = session.scalar(select(RegulatoryEventState).where(RegulatoryEventState.event_id == event_id))
        session.delete(state)
        session.commit()
    assert client.get(f"/api/monitoring-topics/{topic['id']}/matches").json() == []
    with service.db.organization_context(foreign_id), service.db.session() as session:
        with pytest.raises(DomainError) as error:
            topic_matching.list_matches(session, topic["id"])
        assert error.value.code == "monitoring_topic_not_found"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 1


def test_failed_invalidation_rolls_back_review_and_machine_state(harness, monkeypatch):
    client, _, service, _ = harness
    event_id = add_event(service)
    topic = create_topic(client)
    evaluate(service, topic, event_id, "history")
    with service.db.session() as session:
        session.scalar(select(TopicEventMatch)).decision_status = "confirmed"
        event = session.get(RegulatoryEvent, event_id)
        event.evidence_json = {**event.evidence_json, "correction": "sport"}
        session.commit()
    job_id, _ = enqueue(service, event_id)
    original = topic_matching._persist_evaluation

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        args[0].flush()
        raise RuntimeError("test-only interruption after invalidating")

    monkeypatch.setattr(topic_matching, "_persist_evaluation", fail)
    assert execute(service, job_id)["state"] == "retrying"
    with service.db.session() as session:
        record = session.scalar(select(TopicEventMatch))
        assert record.match_status == "matching" and record.review_snapshot_json is None
        assert record.decision_status == "confirmed"
        session.get(Job, job_id).next_attempt_at = utcnow() - timedelta(seconds=1)
        session.commit()
    monkeypatch.setattr(topic_matching, "_persist_evaluation", original)
    assert execute(service, job_id)["state"] == "succeeded"
    with service.db.session() as session:
        record = session.scalar(select(TopicEventMatch))
        assert record.match_status == "not_matching" and record.review_snapshot_json["decision"] == "confirmed"


def test_legacy_complete_history_is_rechecked_without_forging_review(harness):
    client, _, service, _ = harness
    add_event(service)
    topic = create_topic(client)
    job_id = topic["backfill_job"]["id"]
    assert execute(service, job_id)["state"] == "succeeded"
    with service.db.session() as session:
        record = session.scalar(select(TopicEventMatch))
        record.match_status, record.evaluation_fingerprint, record.evaluated_at = "unchecked", None, None
        record.decision_status = "confirmed"
        session.get(Job, job_id).idempotency_key = "pre-validity-evaluator"
        session.commit()
    before = client.get(f"/api/monitoring-topics/{topic['id']}/matches").json()[0]
    assert before["validity"] == "unchecked" and before["decision_is_current"] is False
    detail = client.get(f"/api/monitoring-topics/{topic['id']}").json()
    assert detail["history_scan"]["status"] == "superseded"
    refreshed = client.post(f"/api/monitoring-topics/{topic['id']}/history-scan").json()
    new_id = refreshed["history_scan"]["job_id"]
    assert new_id != job_id
    assert execute(service, new_id)["state"] == "succeeded"
    after = client.get(f"/api/monitoring-topics/{topic['id']}/matches").json()[0]
    assert after["validity"] == "matching" and after["decision"] == "confirmed"
    assert after["review_evidence"]["evaluation_fingerprint"] is None
    assert after["decision_is_current"] is False


def test_live_reversion_enqueues_a_new_generation_and_health_is_not_a_nonmatch(harness):
    client, _, service, model = harness
    event_id = add_event(service)
    topic = create_topic(client)
    first_job, _ = enqueue(service, event_id)
    assert execute(service, first_job)["state"] == "succeeded"
    with service.db.session() as session:
        record = session.scalar(select(TopicEventMatch))
        record.decision_status = "confirmed"
        checked_at = record.evaluated_at
        original = deepcopy(session.get(RegulatoryEvent, event_id).evidence_json)
        session.get(RegulatoryEvent, event_id).connector_health = "error"
        session.commit()
    repeated, info = enqueue(service, event_id)
    assert repeated == first_job and info["reused"] == 1
    endpoint = f"/api/monitoring-topics/{topic['id']}/matches"
    assert client.get(endpoint).json()[0]["is_current"] is True  # Source health is separate coverage state.
    with service.db.session() as session:
        assert session.scalar(select(TopicEventMatch)).evaluated_at == checked_at
        session.get(RegulatoryEvent, event_id).evidence_json = {**original, "correction": "sport"}
        session.commit()
    second_job, _ = enqueue(service, event_id)
    assert execute(service, second_job)["state"] == "succeeded"
    assert client.get(endpoint).json()[0]["validity"] == "not_matching"
    with service.db.session() as session:
        session.get(RegulatoryEvent, event_id).evidence_json = original
        session.commit()
    third_job, info = enqueue(service, event_id)
    assert third_job not in {first_job, second_job} and info["queued"] == 1
    assert enqueue(service, event_id)[0] == third_job
    assert execute(service, third_job)["state"] == "succeeded"
    after = client.get(endpoint).json()[0]
    assert after["validity"] == "matching" and after["decision_is_current"] is True
    with service.db.session() as session:
        assert session.scalar(select(RegulatoryEventState)).topic_match_generation == 3
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 1
    assert model.calls == []


def check_validity_migration_roundtrip(service):
    """Populated SQLite/PostgreSQL migration check, only inside a test database."""
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    with service.db.session() as session:
        record = session.scalar(select(TopicEventMatch))
        record.decision_status = "confirmed"
        record_id, evidence = record.id, deepcopy(record.evidence_references_json)
        session.commit()
    with service.db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "f8b394a26d10")
        assert "match_status" not in {column["name"] for column in inspect(connection).get_columns("topic_event_matches")}
        assert connection.scalar(text("SELECT decision_status FROM topic_event_matches WHERE id=:id"), {"id": record_id}) == "confirmed"
        command.upgrade(config, "head")
    with service.db.session() as session:
        record = session.get(TopicEventMatch, record_id)
        assert record.evidence_references_json == evidence and record.decision_status == "confirmed"
        assert record.match_status == "unchecked"
        assert record.evaluation_fingerprint is None and record.review_snapshot_json is None
        assert session.scalar(select(RegulatoryEventState)).topic_match_generation == 0


def test_populated_validity_migration_preserves_legacy_evidence(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    topic = create_topic(client)
    evaluate(service, topic, event_id, "history")
    check_validity_migration_roundtrip(service)
