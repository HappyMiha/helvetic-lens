"""Real worker progress and durable compatibility for Monitoring isolation."""

import json
import subprocess
import sys
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from celery import Celery
from celery.contrib.testing.worker import start_worker
from sqlalchemy import select
from test_monitoring_compose import render

from helvetic_lens import jobs
from helvetic_lens import monitoring_queues as queues
from helvetic_lens.celery_app import celery_app
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job, OutboxMessage


@pytest.fixture(scope="module")
def composition(tmp_path_factory):
    return render(tmp_path_factory.mktemp("monitoring-queue-config"), {})


def test_periodic_routes_have_dedicated_consumers_and_retention_stays_separate(composition):
    consumers = {}
    for name, service in composition["services"].items():
        command = service.get("command") or []
        if "-Q" in command:
            for queue in command[command.index("-Q") + 1].split(","):
                consumers.setdefault(queue, []).append(name)
    config = composition["services"]["worker-cpu"]
    assert config["command"] == ["python", "-m", "helvetic_lens.worker_supervisor"]
    assert config["stop_grace_period"] == "2m30s"
    assert config["healthcheck"]["test"][-1] == "--healthcheck"
    for name, owned_queues, _ in queues.CPU_WORKERS:
        for queue in owned_queues.split(","):
            consumers.setdefault(queue, []).append(name)
    expected = {queues.CONTROL: "control", queues.SOURCES: "sources", queues.BULK: "bulk",
        queues.PROJECTION: "projection", queues.DELIVERY: "delivery"}
    for queue, service in expected.items():
        assert consumers[queue] == [service]
    assert "pollen-decode" in config["networks"]
    assert config["depends_on"]["pollen-decoder"]["condition"] == "service_healthy"
    assert queues.PERIODIC_QUEUES.keys() <= celery_app.tasks.keys()
    for entry in celery_app.conf.beat_schedule.values():
        name = entry["task"]
        assert entry["options"]["expires"] == entry["schedule"]
        route = celery_app.amqp.router.route(dict(entry.get("options", {})), name)["queue"].name
        assert route in consumers, (name, route)
        if "cleanup" in name or "sample_monitoring_source_history" in name:
            assert route == "maintenance"
        else:
            assert route == queues.PERIODIC_QUEUES[name]
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_acks_late and celery_app.conf.task_reject_on_worker_lost


def test_real_workers_progress_while_ingestion_and_source_slots_are_occupied(composition, tmp_path):
    # Celery's testing worker mutates process-global logging/default-app state.
    # Keep it out of the API test process and observe terminal child completion.
    path = tmp_path / "synthetic-compose.json"
    path.write_text(json.dumps(composition), encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), str(path)],
        capture_output=True, text=True, timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONTROL_PROJECTION_DELIVERY_PROGRESS_CONFIRMED" in result.stdout


def _worker_probe(composition):
    """No DB, Redis, source request, SMTP or production application task runs."""
    prefix = "isolated-" + uuid4().hex
    app = Celery(prefix, broker="memory://")
    app.conf.update(task_ignore_result=True, worker_prefetch_multiplier=1,
        task_acks_late=True, broker_transport_options={"polling_interval": 0.05})
    release = Event()
    occupied = [Event() for _ in range(5)]
    progressed = {queue: Event() for queue in (queues.CONTROL, queues.PROJECTION, queues.DELIVERY)}

    @app.task(name=prefix + ".block", shared=False)
    def block(index):
        occupied[index].set()
        assert release.wait(30), "The test must release every occupied slot"

    @app.task(name=prefix + ".progress", shared=False)
    def progress(queue):
        progressed[queue].set()

    try:
        with ExitStack() as stack:
            for _, owned_queues, concurrency in queues.CPU_WORKERS:
                stack.enter_context(start_worker(app, pool="threads", concurrency=concurrency,
                    queues=[prefix + "-" + queue for queue in owned_queues.split(",")], perform_ping_check=False,
                    shutdown_timeout=15))
            try:
                for index, queue in enumerate(("ingest", "ingest", queues.SOURCES, queues.SOURCES, queues.BULK)):
                    block.apply_async(args=[index], queue=prefix + "-" + queue)
                assert all(event.wait(8) for event in occupied), "Observe every blocked worker slot"
                for queue in progressed:
                    progress.apply_async(args=[queue], queue=prefix + "-" + queue)
                assert all(event.wait(8) for event in progressed.values())
                assert not release.is_set(), "All three classes progress before releasing source/ingestion"
            finally:
                release.set()
    finally:
        release.set()
        app.close()
    print("CONTROL_PROJECTION_DELIVERY_PROGRESS_CONFIRMED")


def test_new_native_jobs_dispatch_to_isolated_queues_and_preserve_idempotency(harness):
    service = harness[2]
    expected = {**dict.fromkeys(queues.SOURCE_JOBS, queues.SOURCES),
        **dict.fromkeys(queues.BULK_JOBS, queues.BULK),
        **dict.fromkeys(queues.PROJECTION_JOBS, queues.PROJECTION),
        **dict.fromkeys(queues.DELIVERY_JOBS, queues.DELIVERY),
        "scan": "ingest", "ask": "ai_interactive", "digest": "maintenance"}
    identities = {}
    with service.db.session() as session:
        for kind, queue in expected.items():
            original = "maintenance" if kind in queues.DELIVERY_JOBS else "ingest"
            if kind in {"ask", "digest"}:
                original = queue
            arguments = dict(job_type=kind, target_type="synthetic", target_id=kind,
                queue=original, idempotency_key="queue-test-" + kind)
            job, reused = jobs.enqueue(session, **arguments)
            assert not reused and job.queue == queue
            again, reused = jobs.enqueue(session, **arguments)
            assert reused and again.id == job.id
            identities[job.id] = queue
        session.commit()
        sent = []
        result = jobs.dispatch(session, lambda topic, queue, payload, priority: sent.append((payload["job_id"], queue)))
        session.commit()
        assert result == {"sent": len(identities), "failed": 0}
        assert dict(sent) == identities
        assert jobs.dispatch(session, lambda *args: pytest.fail("Already sent")) == {"sent": 0, "failed": 0}


def test_legacy_pending_monitoring_jobs_are_rerouted_without_replacing_identity_or_retry(harness):
    service = harness[2]
    with service.db.session() as session:
        job, _ = jobs.enqueue(session, job_type="road_refresh", target_type="synthetic", target_id="road",
            queue="ingest", idempotency_key="legacy-route", payload={"version": 7}, priority=9)
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == job.id))
        job.queue = message.queue = "ingest"  # Persisted pre-isolation release.
        identifier, message_id = job.id, message.id
        session.commit()
        def unavailable(*args):
            raise ConnectionError("synthetic broker outage")
        assert jobs.dispatch(session, unavailable) == {"sent": 0, "failed": 1}
        session.commit()
        assert job.state == "queued" and job.queue == queues.PROJECTION
        assert message.id == message_id and message.queue == queues.PROJECTION
        message.available_at = utcnow() - timedelta(seconds=1)
        session.commit()
        sent = []
        assert jobs.dispatch(session, lambda *args: sent.append(args)) == {"sent": 1, "failed": 0}
        session.commit()
        assert sent == [(message.topic, queues.PROJECTION, {"job_id": identifier}, 9)]
        assert session.get(Job, identifier).payload == {"version": 7}
        assert session.get(OutboxMessage, message_id).attempts == 2


def test_recovery_and_pinned_controller_quiesce_the_existing_worker_container(composition):
    from test_capacity_gate_runner import capacity
    from test_release_manager import release_manager
    assert "worker-cpu" in capacity.RECOVERY_SERVICES
    assert "worker-cpu" in release_manager.WRITER_SERVICES
    assert {name for name in composition["services"] if name.startswith("worker-")} == {"worker-cpu", "worker-ai"}


if __name__ == "__main__":
    _worker_probe(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
