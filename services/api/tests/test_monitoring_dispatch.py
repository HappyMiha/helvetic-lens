"""Host handoff fairness uses real storage; broker and work payloads are synthetic."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from helvetic_lens import jobs
from helvetic_lens.db import Database, utcnow
from helvetic_lens.models import Job, OutboxMessage
from helvetic_lens.monitoring_queues import DELIVERY, PROJECTION, SOURCES


def enqueue(service, kind, queue, *, count=1, age=0, priority=5, now):
    ids = []
    with service.db.session(include_all_organizations=True) as session:
        for _ in range(count):
            job, _ = jobs.enqueue(session, job_type=kind, queue=queue, target_type="synthetic",
                target_id=str(uuid4()), idempotency_key=str(uuid4()), priority=priority,
                organization_id=service.organization_id)
            message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == job.id))
            job.available_at = message.available_at = now - timedelta(seconds=age)
            job.created_at = message.created_at = now - timedelta(seconds=age)
            ids.append(job.id)
        session.commit()
    return ids


def dispatch(service, now, *, limit=100, sender=None):
    sent = []
    def send(topic, queue, body, priority):
        if sender:
            sender(topic, queue, body, priority)
        sent.append((body["job_id"], queue, priority))
    with patch.object(jobs, "utcnow", return_value=now), service.db.session(include_all_organizations=True) as session:
        result = jobs.dispatch(session, send, limit=limit)
        session.commit()
    return result, sent


def test_old_ingestion_backlog_does_not_hide_new_monitoring_handoff(harness):
    service, now = harness[2], utcnow()
    old = enqueue(service, "scan", "ingest", count=110, age=120, now=now)
    pollen, = enqueue(service, "pollen_refresh", "ingest", now=now)
    road, = enqueue(service, "road_refresh", "ingest", now=now)
    email, = enqueue(service, "auction_email", "maintenance", now=now)
    # Emulate persisted rows from before queue isolation; enqueue itself already
    # routes new work correctly, so force the old transport names in storage.
    with service.db.session() as session:
        for identity, queue in ((pollen, "ingest"), (road, "ingest"), (email, "maintenance")):
            session.get(Job, identity).queue = queue
            session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == identity)).queue = queue
        session.commit()
    result, sent = dispatch(service, now)
    assert result == {"sent": 100, "failed": 0}
    ids = {identity for identity, _, _ in sent}
    assert {pollen, road, email} <= ids
    assert ids & set(old)
    assert {queue for identity, queue, _ in sent if identity in {pollen, road, email}} == {SOURCES, PROJECTION, DELIVERY}


def test_one_busy_queue_keeps_full_batch_throughput(harness):
    service, now = harness[2], utcnow()
    ids = enqueue(service, "scan", "ingest", count=110, now=now)
    assert dispatch(service, now)[0] == {"sent": 100, "failed": 0}
    assert dispatch(service, now)[0] == {"sent": 10, "failed": 0}
    with service.db.session() as session:
        assert all(session.get(Job, identity).dispatch_sequence for identity in ids)
        assert jobs.serialize(session, session.get(Job, ids[0]))["queue_position"] is None


def test_small_batches_rotate_after_restart_with_equal_clocks(harness):
    service, now = harness[2], utcnow()
    groups = [enqueue(service, kind, queue, count=6, now=now) for kind, queue in (
        ("scan", "ingest"), ("pollen_refresh", "ingest"), ("road_refresh", "ingest"),
        ("auction_email", "maintenance"), ("tender_refresh", "ingest"), ("synthetic", "ai_background"))]
    sent = []
    for _ in range(12):
        restarted = Database(service.settings)
        try:
            with patch.object(jobs, "utcnow", return_value=now), restarted.session(include_all_organizations=True) as session:
                assert jobs.dispatch(session, lambda _t, _q, body, _p: sent.append(body["job_id"]), limit=1) == {"sent": 1, "failed": 0}
                assert jobs.claim(session, sent[-1], "synthetic-worker") is not None
                session.commit()
        finally:
            restarted.engine.dispose()
    for offset in (0, 6):
        assert all(len(set(sent[offset:offset + 6]) & set(group)) == 1 for group in groups)


def test_priority_ages_only_after_both_job_and_outbox_are_ready(harness):
    service, now = harness[2], utcnow()
    aged, = enqueue(service, "scan", "ingest", age=600, priority=1, now=now)
    delayed, = enqueue(service, "scan", "ingest", age=600, priority=1, now=now)
    fresh, = enqueue(service, "scan", "ingest", priority=8, now=now)
    with service.db.session() as session:
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == delayed))
        message.available_at = now + timedelta(seconds=1)
        session.commit()
    assert dispatch(service, now, limit=1)[1] == [(aged, "ingest", 9)]
    assert dispatch(service, now + timedelta(seconds=1), limit=1)[1] == [(fresh, "ingest", 8)]
    assert dispatch(service, now + timedelta(seconds=1))[1] == [(delayed, "ingest", 1)]
    with service.db.session() as session:
        assert session.get(Job, aged).priority == 1


@pytest.mark.parametrize("state", ["succeeded", "running", "dispatched", "future"])
def test_ineligible_old_prefix_cannot_hide_ready_work(harness, state):
    service, now = harness[2], utcnow()
    old = enqueue(service, "scan", "ingest", count=110, age=600, now=now)
    ready, = enqueue(service, "scan", "ingest", now=now)
    with service.db.session() as session:
        for identity in old:
            job = session.get(Job, identity)
            if state == "future":
                job.available_at = now + timedelta(minutes=1)
            else:
                job.state = state
        session.commit()
    assert dispatch(service, now, limit=1)[1] == [(ready, "ingest", 5)]
    assert dispatch(service, now)[1] == []


def test_broker_failure_retries_same_job_without_consuming_queue_turn(harness):
    service, now = harness[2], utcnow()
    identity, = enqueue(service, "pollen_refresh", "ingest", now=now)
    with service.db.session() as session:
        message_id = session.scalar(select(OutboxMessage.id).where(OutboxMessage.job_id == identity))
    def fail(*_args):
        raise ConnectionError("synthetic broker unavailable")
    assert dispatch(service, now, sender=fail) == ({"sent": 0, "failed": 1}, [])
    with service.db.session() as session:
        assert session.get(Job, identity).dispatch_sequence is None
        assert session.get(Job, identity).state == "queued"
    assert dispatch(service, now)[1] == []
    assert dispatch(service, now + timedelta(seconds=3))[1] == [(identity, SOURCES, 5)]
    with service.db.session() as session:
        messages = list(session.scalars(select(OutboxMessage).where(OutboxMessage.job_id == identity)))
        assert len(messages) == 1 and messages[0].id == message_id and messages[0].attempts == 2


def test_scoped_non_ai_dispatch_never_hands_off_foreign_jobs(harness):
    from test_ai_dispatch import enqueue as enqueue_ai
    from test_ai_dispatch import organizations
    service, now = harness[2], utcnow()
    foreign = enqueue_ai(service, organizations(service, 1)[0], now, queue="ingest", count=110, age=600)
    own, = enqueue(service, "scan", "ingest", now=now)
    with patch.object(jobs, "utcnow", return_value=now), service.db.session() as session:
        sent = []
        jobs.dispatch(session, lambda _t, _q, body, _p: sent.append(body["job_id"]))
        session.commit()
        assert sent == [own] and not set(sent) & set(foreign)


def test_full_ai_window_does_not_reduce_non_ai_throughput(harness):
    from test_ai_dispatch import enqueue as enqueue_ai
    from test_ai_dispatch import organizations
    service, now = harness[2], utcnow()
    for org in organizations(service, 4):
        enqueue_ai(service, org, now)
    enqueue(service, "scan", "ingest", count=210, now=now)
    first = dispatch(service, now)[1]
    assert len(first) == 100 and sum(queue == "ai_interactive" for _, queue, _ in first) == 1
    second = dispatch(service, now)[1]
    assert len(second) == 100 and all(queue == "ingest" for _, queue, _ in second)


def test_postgres_locked_queue_head_leaves_outbox_available_to_owner(harness):
    service, now = harness[2], utcnow()
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    locked, = enqueue(service, "pollen_refresh", "ingest", now=now)
    other, = enqueue(service, "road_refresh", "ingest", now=now)
    with service.db.session() as session:
        session.scalar(select(Job).where(Job.id == locked).with_for_update())
        with ThreadPoolExecutor(max_workers=1) as pool:
            result, sent = pool.submit(dispatch, service, now).result(timeout=5)
        assert result == {"sent": 1, "failed": 0} and sent == [(other, PROJECTION, 5)]
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == locked).with_for_update(nowait=True))
        assert message.state == "pending"
        session.commit()
    assert dispatch(service, now)[1] == [(locked, SOURCES, 5)]
