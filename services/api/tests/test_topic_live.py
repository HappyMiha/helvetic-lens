"""Live fan-out must not silently drop an organization, topic or matching row."""

import asyncio

import pytest
from sqlalchemy import func, select
from test_topic_history import dispatch, execute
from test_topic_matching import add_event, create_topic, plan

from helvetic_lens import jobs, topic_matching
from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    Job,
    JobStep,
    MonitoringTopic,
    MonitoringTopicRevision,
    Organization,
    OutboxMessage,
    RegulatoryEvent,
    RegulatoryEventState,
    RegulatoryWork,
    TopicEventMatch,
)


def seed_topics(session, organization_id, count, **overrides):
    values = plan(**overrides)
    ids = []
    for index in range(count):
        topic = MonitoringTopic(organization_id=organization_id, idempotency_key=f"live-topic-{index}")
        session.add(topic)
        session.flush()
        revision = MonitoringTopicRevision(
            organization_id=organization_id, topic_id=topic.id, revision=1, status="active",
            name=values["name"], goal=values["goal"], importance_floor=values["importance_floor"],
            **{f"{key}_json": values[key] for key in (
                "concepts", "synonyms", "exclusions", "jurisdictions", "languages",
                "source_pack_ids", "document_kinds", "event_kinds",
            )},
        )
        session.add(revision)
        ids.append(topic.id)
    session.flush()
    return ids


def enqueue(service, event_id):
    with service.db.session() as session:
        result = topic_matching.enqueue_live_events(session, [session.get(RegulatoryEvent, event_id)], service.settings)
        session.commit()
        job = session.scalar(select(Job).where(Job.type == "topic_match_event").order_by(Job.created_at.desc()))
        return job.id, result


def test_live_spooling_includes_101_organizations_and_owns_all_child_records(harness):
    client, _, service, model = harness
    event_id = add_event(service)
    with service.db.session(include_all_organizations=True) as session:
        for index in range(100):
            org = Organization(name=f"Live organization {index}", slug=f"live-org-{index}")
            session.add(org)
            session.flush()
            session.add(RegulatoryEventState(organization_id=org.id, event_id=event_id))
            seed_topics(session, org.id, 1)
        event = session.get(RegulatoryEvent, event_id)
        first = topic_matching.enqueue_live_events(session, [event], service.settings)
        repeated = topic_matching.enqueue_live_events(session, [event], service.settings)
        session.commit()
        assert first["queued"] == first["organizations_considered"] == 101
        assert repeated["queued"] == 0 and repeated["reused"] == 101
        records = list(session.scalars(select(Job).where(Job.type == "topic_match_event").order_by(Job.organization_id)))
        assert len(records) == 101
        for record in records:
            assert session.scalar(select(JobStep.organization_id).where(JobStep.job_id == record.id)) == record.organization_id
            assert session.scalar(select(OutboxMessage.organization_id).where(OutboxMessage.job_id == record.id)) == record.organization_id
        last = records[-1]
    # This organization would have been completely omitted by the old live cap.
    with service.db.organization_context(last.organization_id):
        completed = asyncio.run(service.execute_job(last.id))
        assert completed["state"] == "succeeded" and completed["result"]["data"]["matched"] == 1
        with service.db.session() as session:
            assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 1
    assert client.get(f"/api/jobs/{last.id}").status_code == 404
    assert model.calls == []


def test_51_matching_topics_resume_after_write_limit_and_retain_metadata_matches(harness):
    _, _, service, model = harness
    event_id = add_event(service, title="Federal publication")
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        work = session.get(RegulatoryWork, event.work_id)
        # Only metadata mentions this interest. A title-only shortlist loses it.
        work.metadata_json = {**work.metadata_json, "subject": "rare citizenship subject"}
        topics = seed_topics(session, service.db.current_organization_id, 51,
                             concepts=["rare citizenship subject"], synonyms=[])
        session.commit()
    job_id, _ = enqueue(service, event_id)
    assert dispatch(service) == [job_id]
    first = execute(service, job_id)
    assert first["state"] == "queued" and first["progress"] == {"current": 20, "total": 51}
    assert first["result"]["data"]["remaining"] == 31
    assert dispatch(service) == [job_id]
    assert execute(service, job_id)["progress"]["current"] == 40
    assert dispatch(service) == [job_id]
    last = execute(service, job_id)
    assert last["state"] == "succeeded" and last["result"]["data"]["matched"] == 51
    assert last["result"]["data"]["batches"] == 3
    assert execute(service, job_id)["result"] == last["result"]
    with service.db.session() as session:
        assert set(session.scalars(select(TopicEventMatch.topic_id))) == set(topics)
    assert enqueue(service, event_id)[1]["reused"] == 1
    assert model.calls == []


def test_live_failure_cancel_and_retry_preserve_cursor_and_committed_matches(harness, monkeypatch):
    _, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_matches_per_organization_event": 1})
    event_id = add_event(service)
    with service.db.session() as session:
        seed_topics(session, service.db.current_organization_id, 5)
        session.commit()
    job_id, _ = enqueue(service, event_id)
    first = execute(service, job_id)
    original = topic_matching._persist_match

    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        args[0].flush()
        raise RuntimeError("Synthetic live worker failure after writing a match")

    monkeypatch.setattr(topic_matching, "_persist_match", fail_after_write)
    failed = execute(service, job_id)
    assert failed["state"] == "retrying" and failed["progress"]["current"] == 1
    assert failed["result"] == first["result"]
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 1
        jobs.cancel(session, job_id)
        session.commit()
        jobs.retry(session, job_id)
        session.commit()
        assert session.get(Job, job_id).progress_current == 1
    monkeypatch.setattr(topic_matching, "_persist_match", original)
    for _ in range(4):
        finished = execute(service, job_id)
    assert finished["state"] == "succeeded" and finished["result"]["data"]["matched"] == 5
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 5


def test_large_organization_yields_to_another_organizations_waiting_event(harness):
    _, _, service, _ = harness
    event_id = add_event(service)
    with service.db.session(include_all_organizations=True) as session:
        seed_topics(session, service.db.current_organization_id, 21)
        other = Organization(name="Waiting organization", slug="waiting-live-org")
        session.add(other)
        session.flush()
        seed_topics(session, other.id, 1)
        session.add(RegulatoryEventState(organization_id=other.id, event_id=event_id))
        topic_matching.enqueue_live_events(session, [session.get(RegulatoryEvent, event_id)], service.settings)
        session.commit()

    def next_job():
        sent = []
        with service.db.session(include_all_organizations=True) as session:
            jobs.dispatch(session, lambda _topic, _queue, payload, _priority: sent.append(payload["job_id"]), limit=1)
            session.commit()
            assert len(sent) == 1
            record = session.get(Job, sent[0])
            return record.id, record.organization_id

    first_id, owner = next_job()
    assert owner == service.db.current_organization_id
    assert execute(service, first_id)["state"] == "queued"
    second_id, owner = next_job()
    assert second_id != first_id and owner == other.id
    with service.db.organization_context(owner):
        assert execute(service, second_id)["state"] == "succeeded"
    assert next_job()[0] == first_id
    assert execute(service, first_id)["result"]["data"]["matched"] == 21


def test_changed_event_supersedes_old_live_checkpoint_and_queues_fresh_evidence(harness):
    _, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_matches_per_organization_event": 1})
    event_id = add_event(service)
    with service.db.session() as session:
        seed_topics(session, service.db.current_organization_id, 2)
        session.commit()
    old_id, _ = enqueue(service, event_id)
    assert execute(service, old_id)["state"] == "queued"
    with service.db.session() as session:
        event = session.get(RegulatoryEvent, event_id)
        event.evidence_json = {**event.evidence_json, "updated_source_evidence": "New official detail"}
        session.commit()
    superseded = execute(service, old_id)["result"]["data"]
    assert superseded["status"] == "superseded" and superseded["exclusion_reason"] == "evidence_changed"
    new_id, result = enqueue(service, event_id)
    assert new_id != old_id and result["reused"] == 1
    assert execute(service, new_id)["state"] == "queued"
    finished = execute(service, new_id)["result"]["data"]
    assert finished["matched"] == finished["updated"] == 1
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 2


def test_revoked_admission_and_foreign_checkpoint_cannot_match(harness):
    _, _, service, _ = harness
    event_id = add_event(service)
    with service.db.session() as session:
        seed_topics(session, service.db.current_organization_id, 1)
        session.commit()
    job_id, _ = enqueue(service, event_id)
    with service.db.session() as session:
        job = session.get(Job, job_id)
        with pytest.raises(DomainError) as exc:
            topic_matching.run_live_batch(session, event_id, service.settings,
                                          **{key: job.payload[key] for key in ("admission_id", "evidence_fingerprint")},
                                          checkpoint={"version": topic_matching.LIVE_REVISION,
                                                      "organization_id": "another-organization"})
        assert exc.value.code == "topic_checkpoint_invalid"
        session.delete(session.get(RegulatoryEventState, job.payload["admission_id"]))
        session.commit()
    result = execute(service, job_id)["result"]["data"]
    assert result["status"] == "superseded" and result["exclusion_reason"] == "event_not_visible"
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(TopicEventMatch)) == 0


def test_topics_created_between_spool_and_start_are_not_missed(harness):
    client, _, service, _ = harness
    event_id = add_event(service)
    job_id, _ = enqueue(service, event_id)
    topic = create_topic(client)
    result = execute(service, job_id)["result"]["data"]
    assert result["matched"] == 1
    # The independent history path reuses that same saved evidence.
    history = execute(service, topic["backfill_job"]["id"])["result"]["data"]
    assert history["reused"] == 1 and history["matched"] == 0


def test_spooling_failure_rolls_back_jobs_steps_and_outbox_together(harness, monkeypatch):
    _, _, service, _ = harness
    event_id = add_event(service)
    original = jobs.enqueue

    def fail_after_enqueue(*args, **kwargs):
        original(*args, **kwargs)
        args[0].flush()
        raise RuntimeError("Synthetic connector interruption after spooling")

    monkeypatch.setattr(jobs, "enqueue", fail_after_enqueue)
    with pytest.raises(RuntimeError):
        enqueue(service, event_id)
    with service.db.session() as session:
        for model in (Job, JobStep, OutboxMessage):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(func.count()).select_from(RegulatoryEventState)) == 1
    monkeypatch.setattr(jobs, "enqueue", original)
    job_id, result = enqueue(service, event_id)
    assert result["queued"] == 1
    assert execute(service, job_id)["result"]["data"]["processed"] == 0


def test_plan_edited_between_batches_uses_its_new_history_not_stale_live_rules(harness):
    client, _, service, _ = harness
    service.settings = service.settings.model_copy(update={"topic_matches_per_organization_event": 1})
    topics = [create_topic(client, key=f"live-edit-{index}") for index in range(2)]
    topics.sort(key=lambda item: item["id"])
    event_id = add_event(service)
    job_id, _ = enqueue(service, event_id)
    assert execute(service, job_id)["state"] == "queued"
    revised = client.put(f"/api/monitoring-topics/{topics[1]['id']}",
                         json={**plan(exclusions=["naturalisation"]), "expected_revision": 1})
    assert revised.status_code == 200
    completed = execute(service, job_id)["result"]["data"]
    assert completed["processed"] == completed["matched"] == 1
    assert completed["removed_since_capture"] == 1 and completed["remaining"] == 0
    history_id = revised.json()["backfill_job"]["id"]
    history = execute(service, history_id)["result"]["data"]
    assert history["excluded"] == 1 and history["matched"] == 0
