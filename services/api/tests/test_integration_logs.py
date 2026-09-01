def test_integration_logs_are_redacted_sortable_inspectable_and_clearable(harness):
    client, _, service, _ = harness
    secret = "test-secret-that-must-never-leak"
    service.integration_logger.record(
        provider="infomaniak",
        operation="chat_completion",
        method="POST",
        url="https://provider.example/v1/chat/completions?access_token=" + secret,
        status="success",
        duration_ms=245,
        request_headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"},
        request_body={"model": "test-model", "max_tokens": 200, "prompt": "safe"},
        response_status=200,
        response_headers={"Content-Type": "application/json", "Set-Cookie": "session=" + secret},
        response_body={"answer": "safe", "echo": secret},
    )
    service.integration_logger.record(
        provider="fedlex",
        operation="resolve_eli",
        method="GET",
        url="https://fedlex.example/sparql",
        status="error",
        duration_ms=12,
        response_status=503,
        error="Temporary upstream error",
    )

    listed = client.get(
        "/api/integration-logs?sort_by=provider&sort_dir=asc&limit=10"
    )
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 2
    assert [item["provider"] for item in payload["items"]] == ["fedlex", "infomaniak"]
    assert "request_body" not in payload["items"][0]

    infomaniak = next(item for item in payload["items"] if item["provider"] == "infomaniak")
    detail = client.get("/api/integration-logs/" + infomaniak["id"])
    assert detail.status_code == 200
    assert secret not in detail.text
    assert detail.json()["request_headers"]["Authorization"] == "[REDACTED]"
    assert detail.json()["response_headers"]["Set-Cookie"] == "[REDACTED]"
    assert detail.json()["response_body"]["echo"] == "[REDACTED]"
    assert "access_token=%5BREDACTED%5D" in detail.json()["url"]

    errors = client.get("/api/integration-logs?status=error").json()
    assert errors["total"] == 1 and errors["items"][0]["provider"] == "fedlex"
    cleared = client.delete("/api/integration-logs")
    assert cleared.status_code == 200 and cleared.json()["deleted"] == 2
    assert client.get("/api/integration-logs").json()["total"] == 0
