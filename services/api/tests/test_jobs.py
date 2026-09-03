from datetime import timedelta

from conftest import add_law, import_old
from sqlalchemy import select

from helvetic_lens import jobs
from helvetic_lens.db import utcnow
from helvetic_lens.models import Job, OutboxMessage


def test_scan_runs_as_a_persisted_job_with_inspectable_steps(harness):
    client, _, _, _ = harness
    law = add_law(client)

    response = client.post("/api/scans", json={"law_ids": [law["id"]]})

    assert response.status_code == 202
    scan = response.json()
    assert scan["status"] == "complete"
    assert scan["job"]["state"] == "succeeded"
    assert scan["job"]["progress"] == {"current": 1, "total": 1}
    assert scan["job"]["steps"][0]["state"] == "succeeded"
    assert client.get("/api/jobs/" + scan["job"]["id"]).json()["result"]["id"] == scan["id"]


def test_celery_mode_returns_before_scan_work_and_restart_preserves_it(harness):
    client, fetcher, service, _ = harness
    law = add_law(client)
    service.settings.job_execution_mode = "celery"
    calls_before = len(fetcher.calls)

    response = client.post("/api/scans", json={"law_ids": [law["id"]]})

    assert response.status_code == 202
    scan = response.json()
    assert scan["status"] == "queued" and scan["job"]["state"] == "queued"
    assert len(fetcher.calls) == calls_before

    service.initialize()
    recovered = client.get("/api/jobs/" + scan["job"]["id"]).json()
    assert recovered["state"] == "queued" and recovered["steps"][0]["state"] == "pending"

    assert client.post("/api/jobs/" + recovered["id"] + "/cancel").json()["state"] == "cancelled"


def test_outbox_dispatch_and_worker_claim_are_idempotent(harness):
    _, _, service, _ = harness
    with service.db.session() as session:
        first, reused = jobs.enqueue(
            session,
            job_type="scan",
            target_type="scan",
            target_id="target",
            queue="ingest",
            idempotency_key="same-command",
        )
        duplicate, duplicate_reused = jobs.enqueue(
            session,
            job_type="scan",
            target_type="scan",
            target_id="target",
            queue="ingest",
            idempotency_key="same-command",
        )
        session.commit()
        job_id = first.id
    assert not reused and duplicate_reused and duplicate.id == job_id

    sent = []
    with service.db.session() as session:
        outcome = jobs.dispatch(
            session,
            lambda topic, queue, payload, priority: sent.append(
                (topic, queue, payload, priority)
            ),
        )
        session.commit()
    assert outcome == {"sent": 1, "failed": 0}
    assert sent[0][1:3] == ("ingest", {"job_id": job_id})

    with service.db.session() as session:
        assert jobs.claim(session, job_id, "worker-one") is not None
        session.commit()
    with service.db.session() as session:
        assert jobs.claim(session, job_id, "worker-two") is None


def test_broker_failure_and_stale_worker_are_recoverable_from_postgres(harness):
    _, _, service, _ = harness
    with service.db.session() as session:
        job, _ = jobs.enqueue(
            session,
            job_type="scan",
            target_type="scan",
            target_id="recover-me",
            queue="ingest",
            idempotency_key="recover-me",
        )
        session.commit()
        job_id = job.id
    with service.db.session() as session:
        outcome = jobs.dispatch(
            session,
            lambda *_: (_ for _ in ()).throw(ConnectionError("broker unavailable")),
        )
        session.commit()
        message = session.scalar(select(OutboxMessage).where(OutboxMessage.job_id == job_id))
        assert message.state == "pending" and message.attempts == 1
    assert outcome == {"sent": 0, "failed": 1}

    with service.db.session() as session:
        record = session.get(Job, job_id)
        record.state = "running"
        record.attempts = 1
        record.lease_owner = "lost-worker"
        record.heartbeat_at = utcnow() - timedelta(minutes=10)
        session.commit()
    with service.db.session() as session:
        assert jobs.reconcile(session, lease_seconds=60)["recovered"] == 1
        session.commit()
        record = session.get(Job, job_id)
        assert record.state == "retrying" and record.lease_owner is None


def test_cancelled_and_failed_jobs_can_be_safely_retried(harness):
    client, _, service, _ = harness
    with service.db.session() as session:
        job, _ = jobs.enqueue(
            session,
            job_type="unknown",
            target_type="test",
            target_id="one",
            queue="maintenance",
            idempotency_key="retryable-command",
            max_attempts=1,
        )
        session.commit()
        job_id = job.id

    failed = client.post("/api/jobs/" + job_id + "/retry").json()
    assert failed["state"] == "failed"
    assert failed["error"]["code"] == "job_type_unknown"

    retried = client.post("/api/jobs/" + job_id + "/retry").json()
    assert retried["attempts"] == 1 and retried["state"] == "failed"

    with service.db.session() as session:
        record = session.get(Job, job_id)
        record.state = "queued"
        record.attempts = 0
        session.commit()
    cancelled = client.post("/api/jobs/" + job_id + "/cancel").json()
    assert cancelled["state"] == "cancelled" and cancelled["cancel_requested"] is True


def test_running_job_finishes_cancellation_at_a_safe_boundary(harness):
    _, _, service, _ = harness
    with service.db.session() as session:
        job, _ = jobs.enqueue(
            session,
            job_type="scan",
            target_type="scan",
            target_id="running-target",
            queue="ingest",
            idempotency_key="cancel-running",
            steps=[("Started work", {})],
        )
        session.commit()
        job_id = job.id
    with service.db.session() as session:
        assert jobs.claim(session, job_id, "worker") is not None
        jobs.progress(session, job_id, current=0, step_position=1, step_state="running")
        jobs.request_cancel(session, job_id)
        session.commit()
    with service.db.session() as session:
        assert jobs.heartbeat(session, job_id, "worker") is False
        cancelled = jobs.cancel(session, job_id)
        session.commit()
        assert cancelled.state == "cancelled" and cancelled.lease_owner is None
        assert jobs.serialize(session, cancelled)["steps"][0]["state"] == "cancelled"


def test_impact_and_ask_use_durable_ai_queues_and_return_saved_results(harness):
    client, _, service, model = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={
            "old_version_id": old["id"],
            "new_version_id": law["current_version_id"],
        },
    ).json()
    service.settings.apertus_base_url = "https://model.example/v1"

    impact = client.post(f"/api/comparisons/{comparison['id']}/analyse-jobs")
    assert impact.status_code == 202
    impact_job = impact.json()
    assert impact_job["queue"] == "ai_background" and impact_job["state"] == "succeeded"
    assert impact_job["result"]["type"] == "analysis"
    assert impact_job["result"]["data"]["status"] == "succeeded"
    assert impact_job["steps"][1]["name"] == "Analyse evidence groups"
    assert impact_job["steps"][1]["progress"]["current"] == impact_job["steps"][1]["progress"]["total"]
    assert impact_job["steps"][2]["details"]["stage"] == "validating"
    reopened = client.get(f"/api/comparisons/{comparison['id']}").json()["analysis_job"]
    assert reopened["id"] == impact_job["id"] and reopened["state"] == "succeeded"

    answer = client.post(
        f"/api/comparisons/{comparison['id']}/ask-jobs",
        json={"question": "What changed?", "history": []},
    )
    assert answer.status_code == 202
    answer_job = answer.json()
    assert answer_job["queue"] == "ai_interactive" and answer_job["priority"] == 8
    assert answer_job["state"] == "succeeded"
    assert answer_job["result"]["data"]["record_id"]
    assert answer_job["result"]["data"]["context_mode"] == "impact_report"
    assert answer_job["result"]["data"]["coverage"]["provider_calls"] == 0
    assert len(model.calls) == 1


def test_resubmitting_cancelled_impact_job_requeues_same_persisted_work(harness):
    client, _, service, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    service.settings.apertus_base_url = "https://model.example/v1"
    service.settings.job_execution_mode = "celery"

    first = client.post(f"/api/comparisons/{comparison['id']}/analyse-jobs").json()
    assert first["state"] == "queued"
    assert client.post(f"/api/jobs/{first['id']}/cancel").json()["state"] == "cancelled"
    retried = client.post(f"/api/comparisons/{comparison['id']}/analyse-jobs").json()
    assert retried["id"] == first["id"] and retried["state"] == "queued"
    assert client.get(f"/api/comparisons/{comparison['id']}").json()["analysis_job"]["id"] == first["id"]


def test_waiting_for_local_model_does_not_consume_job_attempt(harness):
    _, _, service, _ = harness
    with service.db.session() as session:
        job, _ = jobs.enqueue(
            session,
            job_type="impact_analysis",
            target_type="comparison",
            target_id="waiting-target",
            queue="ai_background",
            idempotency_key="wait-for-model",
            steps=[("Run local inference", {})],
        )
        session.commit()
        job_id = job.id
    with service.db.session() as session:
        claimed = jobs.claim(session, job_id, "worker")
        assert claimed is not None and claimed.attempts == 1
        jobs.progress(session, job_id, current=0, step_position=1, step_state="running")
        waiting = jobs.defer_for_model(session, job_id, "Warming up.", delay=2)
        session.commit()
        assert waiting.state == "waiting_for_model" and waiting.attempts == 0
        assert waiting.lease_owner is None
        assert jobs.serialize(session, waiting)["steps"][0]["state"] == "pending"
