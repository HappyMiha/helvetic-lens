import uuid

from helvetic_lens import jobs
from helvetic_lens.models import IntegrationLog
from helvetic_lens.observability import ApiMetrics, correlation_context, normalized_route


def test_api_metrics_are_bounded_and_remove_high_cardinality_ids():
    metrics = ApiMetrics(max_samples=100)
    document_id = "a706a68c-36ff-4f84-8291-e68ef1ed410e"
    metrics.started()
    metrics.finished("get", f"/api/documents/{document_id}", 200, 10)
    metrics.started()
    metrics.finished("POST", "/api/scans/814", 503, 90)

    snapshot = metrics.snapshot()
    assert snapshot["window_samples"] == 2
    assert snapshot["in_flight"] == 0
    assert snapshot["server_errors"] == 1
    assert snapshot["server_error_rate"] == 0.5
    assert snapshot["latency_ms"] == {"p50": 10, "p95": 90, "max": 90}
    labels = [item["route"] for item in snapshot["top_routes"]]
    assert "GET /api/documents/{id}" in labels
    assert "POST /api/scans/{id}" in labels
    assert document_id not in str(snapshot)
    assert normalized_route("/api/documents/42/evidence") == "/api/documents/{id}/evidence"


def test_request_id_is_returned_and_platform_metrics_include_completed_requests(harness):
    client, _, _, _ = harness
    health = client.get("/api/health")
    request_id = health.headers["X-Request-ID"]
    assert str(uuid.UUID(request_id)) == request_id

    status = client.get("/api/admin/status")
    assert status.status_code == 200
    metrics = status.json()["api_metrics"]
    assert metrics["window_samples"] >= 1
    assert any(item["route"] == "GET /api/health" for item in metrics["top_routes"])


def test_request_correlation_survives_job_and_integration_log_boundaries(harness):
    _, _, service, _ = harness
    request_id = "d6dd7c60-e4b1-4053-ac2b-1b79341ea61c"
    target_id = "0276cd83-e45a-41a9-a903-3f01fd2d6faa"
    with correlation_context(
        request_id=request_id,
        organization_id=service.default_organization_id,
        comparison_id=target_id,
        api_token="must-not-be-stored",
    ):
        with service.db.session() as session:
            job, reused = jobs.enqueue(
                session,
                job_type="test_correlation",
                target_type="comparison",
                target_id=target_id,
                queue="maintenance",
                idempotency_key="test-correlation",
            )
            session.commit()
            job_id = job.id

    with service.db.session() as session:
        saved_job = session.get(type(job), job_id)
        assert saved_job is not None and not reused
        assert saved_job.request_id == request_id
        assert saved_job.correlation["job_id"] == job_id
        assert saved_job.correlation["comparison_id"] == target_id
        assert "api_token" not in saved_job.correlation
        worker_correlation = dict(saved_job.correlation)

    with correlation_context(**worker_correlation):
        service.integration_logger.record(
            provider="docker",
            operation="chat_completion",
            method="POST",
            url="http://model-gateway/v1/chat/completions",
            status="success",
            duration_ms=4,
            response_status=200,
        )

    with service.db.session() as session:
        log = session.query(IntegrationLog).filter_by(request_id=request_id).one()
        assert log.correlation["job_id"] == job_id
        assert log.correlation["target_type"] == "comparison"
        assert log.correlation["target_id"] == target_id
    matching = service.integration_logs(query=request_id)
    assert matching["total"] == 1 and matching["items"][0]["request_id"] == request_id
