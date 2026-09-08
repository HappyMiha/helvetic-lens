"""Durable fairness uses real SQL/transactions; clocks and broker sends are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import timedelta
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from helvetic_lens import jobs
from helvetic_lens.db import Database, utcnow
from helvetic_lens.models import Job, Organization, OutboxMessage


def organizations(service, count=2):
    with service.db.session(include_all_organizations=True) as session:
        rows = [Organization(name="Synthetic private tenant", slug=str(uuid4())) for _ in range(count)]
        session.add_all(rows)
        session.commit()
        return [row.id for row in rows]


def enqueue(service, org, now, *, count=1, priority=8, age=0, delay=0, queue="ai_interactive"):
    with service.db.session(include_all_organizations=True) as session:
        identities = []
        for _ in range(count):
            job, _ = jobs.enqueue(session, organization_id=org, job_type="synthetic-dispatch",
                target_type="synthetic", target_id=str(uuid4()), queue=queue,
                priority=priority, idempotency_key=str(uuid4()))
            job.available_at = now - timedelta(seconds=age) + timedelta(seconds=delay)
            message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == job.id))
            message.available_at = job.available_at
            identities.append(job.id)
        session.commit()
        return identities


def dispatch(service, now, *, window=1, limit=100):
    sent = []
    clock = patch.object(jobs, "utcnow", return_value=now) if now is not None else nullcontext()
    with clock, service.db.session(include_all_organizations=True) as session:
        result = jobs.dispatch(session, lambda topic, queue, body, priority: sent.append((body["job_id"], priority)),
                               limit=limit, ai_window=window)
        session.commit()
        assert result == {"sent": len(sent), "failed": 0}
    return sent


def claim(service, identity):
    with service.db.session(include_all_organizations=True) as session:
        row = jobs.claim(session, identity, "synthetic-worker")
        assert row is not None
        session.commit()


def test_tenant_turns_survive_restart_equal_clock_and_large_noisy_prefix(harness):
    service, now = harness[2], utcnow()
    a, b = organizations(service)
    noisy = enqueue(service, a, now, count=110)
    first = dispatch(service, now, limit=1)
    assert first[0][0] in noisy
    claim(service, first[0][0])
    quiet = enqueue(service, b, now)
    # New Database/Session, same wall clock: no in-process cursor or time tie.
    restarted = Database(service.settings)
    try:
        with patch.object(jobs, "utcnow", return_value=now), restarted.session(include_all_organizations=True) as session:
            sent = []
            jobs.dispatch(session, lambda _t, _q, body, _p: sent.append(body["job_id"]), limit=1)
            session.commit()
            assert sent == quiet
            assert session.get(Job, quiet[0]).dispatch_sequence == 2
            assert session.get(Job, first[0][0]).dispatch_sequence == 1
    finally:
        restarted.engine.dispose()
    claim(service, quiet[0])
    assert dispatch(service, now, limit=1)[0][0] in noisy


def test_unclaimed_window_keeps_background_in_db_and_does_not_block_cpu(harness):
    service, now = harness[2], utcnow()
    a, b = organizations(service)
    background = enqueue(service, a, now, priority=2, queue="ai_background", count=3)
    first = dispatch(service, now)[0][0]
    assert first in background
    question = enqueue(service, b, now)
    cpu = enqueue(service, a, now, queue="ingest")
    assert [row[0] for row in dispatch(service, now)] == cpu
    claim(service, first)
    assert dispatch(service, now) == [(question[0], 8)]
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(Job).where(
            Job.queue.in_(("ai_interactive", "ai_background")), Job.state == "dispatched")) == 1
        assert sum(session.get(Job, identity).state == "queued" for identity in background) == 2
        assert jobs.serialize(session, session.get(Job, question[0]))["queue_position"] is None


def test_aged_background_eventually_precedes_continuously_fresh_questions(harness):
    service, start = harness[2], utcnow()
    a, b = organizations(service)
    background = enqueue(service, b, start, priority=2, queue="ai_background")[0]
    chosen_at = None
    for minute in range(9):
        now = start + timedelta(minutes=minute)
        question = enqueue(service, a, now)[0]
        selected = dispatch(service, now)
        assert len(selected) == 1
        identity, wire_priority = selected[0]
        claim(service, identity)
        if identity == background:
            chosen_at = minute
            assert wire_priority >= 8
            break
        assert identity == question
    assert chosen_at is not None and chosen_at <= 7
    with service.db.session(include_all_organizations=True) as session:
        assert session.get(Job, background).priority == 2  # Immutable requested priority.


def test_future_retry_does_not_age_before_it_is_eligible(harness):
    service, start = harness[2], utcnow()
    a, b = organizations(service)
    delayed = enqueue(service, a, start, priority=2, queue="ai_background", delay=600)[0]
    assert dispatch(service, start) == []
    now = start + timedelta(minutes=10)
    question = enqueue(service, b, now)[0]
    assert dispatch(service, now) == [(question, 8)]
    claim(service, question)
    assert dispatch(service, now) == [(delayed, 2)]


def test_larger_window_selects_distinct_tenants_and_respects_total_limit(harness):
    service, now = harness[2], utcnow()
    orgs = organizations(service, 3)
    identities = [enqueue(service, org, now, count=4) for org in orgs]
    sent = dispatch(service, now, window=3, limit=2)
    assert len(sent) == 2
    assert len({index for identity, _ in sent for index, group in enumerate(identities) if identity in group}) == 2
    assert len(dispatch(service, now, window=3)) == 1
    assert dispatch(service, now, window=3) == []


def test_broker_failure_does_not_consume_turn_or_window(harness):
    service, now = harness[2], utcnow()
    a, b = organizations(service)
    first = enqueue(service, a, now, age=1)[0]
    second = enqueue(service, b, now)[0]
    with patch.object(jobs, "utcnow", return_value=now), service.db.session(include_all_organizations=True) as session:
        def sender(_topic, _queue, body, _priority):
            if body["job_id"] == first:
                raise ConnectionError("synthetic broker outage")
        assert jobs.dispatch(session, sender) == {"sent": 1, "failed": 1}
        session.commit()
        assert session.get(Job, first).dispatch_sequence is None
        assert session.get(Job, second).dispatch_sequence == 1
        assert session.get(Job, first).state == "queued"
    claim(service, second)
    assert dispatch(service, now) == []  # Broker backoff is retained.
    assert dispatch(service, now + timedelta(seconds=3)) == [(first, 8)]


def test_concurrent_dispatchers_cannot_fill_same_window_twice(harness):
    service, now = harness[2], utcnow()
    for org in organizations(service, 4):
        enqueue(service, org, now)
    barrier = Barrier(4)
    def run(_):
        barrier.wait(timeout=15)
        return dispatch(service, None)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, range(4)))
    assert sum(map(len, results)) == 1
    with service.db.session(include_all_organizations=True) as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.state == "dispatched")) == 1


def test_scoped_dispatch_does_not_select_another_tenant_head(harness):
    service, now = harness[2], utcnow()
    other = organizations(service, 1)[0]
    foreign = enqueue(service, other, now, priority=9, age=600)[0]
    own = enqueue(service, service.organization_id, now, priority=2)[0]
    with patch.object(jobs, "utcnow", return_value=now), service.db.session() as session:
        sent = []
        jobs.dispatch(session, lambda _t, _q, body, _p: sent.append(body["job_id"]))
        session.commit()
        assert sent == [own] and foreign not in sent
        assert session.scalar(select(Job).where(Job.id == foreign)) is None


def test_postgres_busy_dispatcher_does_not_wait_on_its_lock(harness):
    service = harness[2]
    if service.db.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL advisory lock semantics")
    from helvetic_lens.ai_dispatch import begin_turn
    ready = Event()
    with service.db.session(include_all_organizations=True) as session:
        assert begin_turn(session)
        def contender():
            ready.set()
            return dispatch(service, utcnow())
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(contender).result(timeout=3) == []
        assert ready.is_set()


def test_sequence_migration_preserves_existing_jobs_and_outbox(harness):
    from pathlib import Path

    from alembic.config import Config
    from sqlalchemy import inspect, text

    from alembic import command
    service, now = harness[2], utcnow()
    identity = enqueue(service, service.organization_id, now)[0]
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    with service.db.engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "d9fb034a6dc7")
        assert "dispatch_sequence" not in {row["name"] for row in inspect(connection).get_columns("jobs")}
        assert connection.scalar(text("SELECT count(*) FROM jobs WHERE id=:id"), {"id": identity}) == 1
        command.upgrade(cfg, "head")
    with service.db.session() as session:
        assert session.get(Job, identity).dispatch_sequence is None
        assert session.scalar(select(func.count()).select_from(OutboxMessage).where(OutboxMessage.job_id == identity)) == 1
    assert dispatch(service, now) == [(identity, 8)]
