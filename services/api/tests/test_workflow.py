from conftest import LAW_URL, LIST_URL, add_law, import_old, policy, run_scan
from fastapi.testclient import TestClient

from regwatch.config import DomainError
from regwatch.main import create_app


def test_connect_discover_preview_and_add_without_code_changes(harness):
    client, fetcher, _, _ = harness
    source = client.post("/api/sources", json={"url": LIST_URL, "section": "/laws"}).json()
    result = client.post("/api/sources/" + source["id"] + "/discover").json()
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["url"] == LAW_URL
    assert result["candidates"][0]["verified"] is False
    assert not any(url == LAW_URL for url, _ in fetcher.calls)
    preview = client.post("/api/preview", json={"url": LAW_URL}).json()
    assert preview["passage_count"] == 3
    law = add_law(client, source_id=source["id"])
    assert law["source_id"] == source["id"]
    assert law["last_result"] == "baseline_created"
    assert law["current_version"]["synthetic"] is True
    assert client.post("/api/laws", json={"url": LAW_URL + "#same"}).status_code == 409
    assert client.post("/api/sources", json={"url": LIST_URL}).status_code == 409
    assert client.post("/api/sources/" + source["id"] + "/discover").json()["candidates"][0]["tracked"]


def test_historical_import_repeat_and_current_pointer(harness):
    client, _, _, _ = harness
    law = add_law(client)
    current_id = law["current_version_id"]
    old = import_old(client, law["id"])["version"]
    assert old["origin"] == "uploaded" and old["date_provenance"] == "user_supplied"
    assert old["declared_date"] == "2025-01-01"
    assert old["synthetic"] is True
    comparison_ids = []
    for _ in range(2):
        result = run_scan(client, [law["id"]], old["id"])
        item = result["items"][0]
        assert result["status"] == "complete"
        assert item["result"] == "historical_comparison"
        assert item["live_result"] == "unchanged"
        assert item["analysis_status"] == "not_configured"
        assert item["monitoring_comparison_id"] != item["comparison_id"]
        comparison_ids.append(item["comparison_id"])
        comparison = client.get("/api/comparisons/" + item["comparison_id"]).json()
        assert comparison["old_version"]["id"] == old["id"]
        assert comparison["new_version"]["id"] == current_id
        assert comparison["diff"]["counts"]["modified"] == 1
    assert comparison_ids[0] == comparison_ids[1]
    detail = client.get("/api/laws/" + law["id"]).json()
    assert detail["current_version_id"] == current_id
    assert detail["last_result"] == "unchanged"
    assert len(detail["versions"]) == 2
    assert len(detail["observations"]) == 4


def test_unchanged_and_a_b_a_reuses_content_preserves_observations(harness):
    client, fetcher, _, _ = harness
    law = add_law(client)
    assert run_scan(client, [law["id"]])["items"][0]["result"] == "unchanged"
    fetcher.values[LAW_URL] = policy(60)
    forward = run_scan(client, [law["id"]])["items"][0]
    assert forward["result"] == "changed"
    assert forward["new_version_id"] != law["current_version_id"]
    diff = client.get("/api/comparisons/" + forward["comparison_id"]).json()["diff"]
    modified = next(item for item in diff["items"] if item["kind"] == "modified")
    assert any(part == {"text": "30", "kind": "removed"} for part in modified["old_parts"])
    assert any(part == {"text": "60", "kind": "added"} for part in modified["new_parts"])
    fetcher.values[LAW_URL] = policy(30)
    reverse = run_scan(client, [law["id"]])["items"][0]
    assert reverse["result"] == "changed"
    assert reverse["new_version_id"] == law["current_version_id"]
    detail = client.get("/api/laws/" + law["id"]).json()
    assert len(detail["versions"]) == 2
    assert len(detail["observations"]) == 4


def test_duplicate_import_preview_pasted_text_and_historical_url(harness):
    client, fetcher, _, _ = harness
    law = add_law(client)
    original = law["current_version_id"]
    first = import_old(client, law["id"])
    duplicate = import_old(client, law["id"])
    assert duplicate["reused"] is True
    assert duplicate["version"]["id"] == first["version"]["id"]
    text = (
        "Synthetic earlier wording.\n\nThe original retention period was five days in this fictional example."
    )
    preview = client.post("/api/laws/" + law["id"] + "/import?preview=true", data={"text": text})
    assert preview.status_code == 200
    assert len(client.get("/api/laws/" + law["id"]).json()["versions"]) == 2
    pasted = client.post("/api/laws/" + law["id"] + "/import", data={"text": text}).json()["version"]
    assert pasted["origin"] == "pasted" and pasted["declared_date"] is None
    archive_url = "https://regulator.example/archive/retention.html"
    fetcher.values[archive_url] = policy(5)
    archive = client.post("/api/laws/" + law["id"] + "/import", data={"url": archive_url}).json()["version"]
    assert archive["origin"] == "historical_url" and archive["source_url"] == archive_url
    assert client.get("/api/laws/" + law["id"]).json()["current_version_id"] == original


def test_saved_comparison_never_fetches_or_changes_live_state(harness):
    client, fetcher, _, _ = harness
    law = add_law(client)
    old = import_old(client, law["id"])["version"]
    calls_before = len(fetcher.calls)
    fetcher.values[LAW_URL] = DomainError("Network is offline.")
    response = client.post(
        "/api/comparisons", json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]}
    )
    assert response.status_code == 201
    assert response.json()["mode"] == "saved_versions"
    assert len(fetcher.calls) == calls_before
    detail = client.get("/api/laws/" + law["id"]).json()
    assert detail["last_result"] == "baseline_created"
    assert len(detail["observations"]) == 2
    saved = client.get("/api/versions/" + old["id"])
    assert saved.status_code == 200
    assert "10 days" in saved.json()["passages"][1]["text"]
    artifact = client.get(saved.json()["artifact_url"])
    assert artifact.content == policy(10)
    assert artifact.headers["content-type"].startswith("text/plain")
    assert "attachment" in artifact.headers["content-disposition"]
    assert client.get("/api/versions/nonexistent").status_code == 404


def test_failed_fetch_and_extraction_preserve_last_good_version(harness):
    client, fetcher, _, _ = harness
    law = add_law(client)
    for invalid in [DomainError("Document unavailable.", 422), b"<html><main></main></html>"]:
        fetcher.values[LAW_URL] = invalid
        scan = run_scan(client, [law["id"]])
        assert scan["status"] == "partial"
        assert scan["items"][0]["result"] == "failed"
        detail = client.get("/api/laws/" + law["id"]).json()
        assert detail["current_version_id"] == law["current_version_id"]
        assert len(detail["versions"]) == 1
        assert len(detail["observations"]) == 1
    fetcher.values[LAW_URL] = policy(60)
    assert run_scan(client, [law["id"]])["items"][0]["result"] == "changed"


def test_partial_batch_empty_selection_pause_and_cross_law_guard(harness):
    client, fetcher, _, _ = harness
    a = add_law(client)
    second_url = LAW_URL + "?document=2"
    fetcher.values[second_url] = policy(90)
    b = add_law(client, url=second_url)
    fetcher.values[LAW_URL] = DomainError("Offline")
    result = run_scan(client, [a["id"], b["id"]])
    assert result["status"] == "partial" and result["completed"] == 2
    assert {item["result"] for item in result["items"]} == {"failed", "unchanged"}
    assert client.post("/api/scans", json={"law_ids": []}).status_code == 422
    assert (
        client.post(
            "/api/scans", json={"law_ids": [b["id"]], "baseline_version_id": a["current_version_id"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/comparisons",
            json={"old_version_id": a["current_version_id"], "new_version_id": b["current_version_id"]},
        ).status_code
        == 422
    )
    assert client.patch("/api/laws/" + b["id"], json={"active": False}).status_code == 200
    assert client.post("/api/scans", json={"law_ids": [b["id"]]}).status_code == 422
    assert client.patch("/api/laws/" + b["id"], json={"active": True}).status_code == 200
    assert run_scan(client, [b["id"]])["items"][0]["result"] == "unchanged"


def test_concurrent_scan_guard_and_restart_recovery(harness):
    client, _, service, _ = harness
    law = add_law(client)
    scan_id = service.start_scan([law["id"]], None)
    conflict = client.post("/api/scans", json={"law_ids": [law["id"]]})
    assert conflict.status_code == 409 and conflict.json()["code"] == "scan_in_progress"
    service.initialize()
    recovered = client.get("/api/scans/" + scan_id).json()
    assert recovered["status"] == "interrupted"
    assert recovered["items"][0]["stage"] == "interrupted"
    assert client.get("/api/laws/" + law["id"]).json()["current_version_id"] == law["current_version_id"]
    assert run_scan(client, [law["id"]])["status"] == "complete"


def test_sources_versions_paused_state_and_results_survive_new_app(harness):
    client, fetcher, service, model = harness
    source = client.post("/api/sources", json={"url": LIST_URL}).json()
    law = add_law(client, source_id=source["id"])
    old = import_old(client, law["id"])["version"]
    scan = run_scan(client, [law["id"]], old["id"])
    client.patch("/api/laws/" + law["id"], json={"active": False})
    restarted = create_app(service.settings, fetcher, model)
    with TestClient(restarted) as restored:
        detail = restored.get("/api/laws/" + law["id"]).json()
        assert detail["active"] is False
        assert len(detail["versions"]) == 2
        assert restored.get("/api/sources").json()[0]["id"] == source["id"]
        assert restored.get("/api/scans/" + scan["id"]).json()["status"] == "complete"
        assert restored.get("/api/versions/" + old["id"]).status_code == 200


def test_import_validation_and_model_unavailable_are_explicit(harness):
    from regwatch.analysis import ModelClient

    client, _, service, _ = harness
    service.model_client = ModelClient(service.settings)
    law = add_law(client)
    route = "/api/laws/" + law["id"] + "/import"
    assert client.post(route, data={}).status_code == 422
    assert client.post(route, data={"text": "Too short"}).status_code == 422
    assert client.post(route, files={"file": ("empty.pdf", b"", "application/pdf")}).status_code == 422
    assert (
        client.post(
            route, files={"file": ("v.html", policy(), "text/html")}, data={"text": "Duplicate input"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            route, files={"file": ("v.html", policy(), "text/html")}, data={"declared_date": "2025-02-31"}
        ).status_code
        == 422
    )
    assert client.post("/api/model/test").status_code == 503
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons", json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]}
    ).json()
    assert client.post("/api/comparisons/" + comparison["id"] + "/analyse").status_code == 503
    assert (
        client.post(
            "/api/comparisons/" + comparison["id"] + "/ask", json={"question": "What changed?"}
        ).status_code
        == 503
    )


def test_first_fetch_without_a_live_pointer_creates_baseline(harness):
    from regwatch.models import Law

    client, _, service, _ = harness
    with service.db.session() as session:
        law = Law(name="Deferred first baseline", url=LAW_URL)
        session.add(law)
        session.commit()
        law_id = law.id
    result = run_scan(client, [law_id])
    assert result["items"][0]["result"] == "baseline_created"
    assert client.get("/api/laws/" + law_id).json()["current_version_id"]
