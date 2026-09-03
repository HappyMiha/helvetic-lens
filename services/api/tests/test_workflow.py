import asyncio

from conftest import LAW_URL, LIST_URL, add_law, import_old, policy, run_scan
from fastapi.testclient import TestClient
from sqlalchemy import select

from helvetic_lens.config import DomainError
from helvetic_lens.main import create_app
from helvetic_lens.models import Version


def test_connect_discover_preview_and_add_without_code_changes(harness):
    client, fetcher, _, _ = harness
    source = client.post("/api/sources", json={"url": LIST_URL, "section": "/laws"}).json()
    result = client.post("/api/sources/" + source["id"] + "/discover").json()
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["url"] == LAW_URL
    assert result["candidates"][0]["verified"] is True
    assert result["inspected_count"] == result["verified_count"] == 1
    assert "30 days" in result["candidates"][0]["preview"]["excerpt"]
    assert any(url == LAW_URL for url, _ in fetcher.calls)
    assert client.get("/api/laws").json() == []
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
    duplicate = import_old(client, law["id"], declared_date="2025-02-01")
    assert duplicate["reused"] is True
    assert duplicate["version"]["id"] == first["version"]["id"]
    assert duplicate["version"]["declared_date"] == "2025-01-01"
    observations = client.get("/api/laws/" + law["id"]).json()["observations"]
    assert any(
        observation["version_id"] == first["version"]["id"]
        and observation["declared_date"] == "2025-02-01"
        and observation["origin"] == "uploaded"
        for observation in observations
    )
    text = (
        "Synthetic earlier wording.\n\nThe original retention period was five days in this fictional example."
    )
    preview = client.post("/api/laws/" + law["id"] + "/import?preview=true", data={"text": text})
    assert preview.status_code == 200
    assert len(client.get("/api/laws/" + law["id"]).json()["versions"]) == 2
    pasted = client.post(
        "/api/laws/" + law["id"] + "/import",
        data={"text": text, "confirm_identity": "true"},
    ).json()["version"]
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
    assert recovered["status"] == "queued"
    assert recovered["items"][0]["stage"] == "queued"
    asyncio.run(service.execute_job(recovered["job"]["id"], worker="restarted-worker"))
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
    from helvetic_lens.analysis import ModelClient

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
    from helvetic_lens.models import Law

    client, _, service, _ = harness
    with service.db.session() as session:
        law = Law(name="Synthetic retention policy", url=LAW_URL)
        session.add(law)
        session.commit()
        law_id = law.id
    result = run_scan(client, [law_id])
    assert result["items"][0]["result"] == "baseline_created"
    assert client.get("/api/laws/" + law_id).json()["current_version_id"]


def test_source_edits_are_persisted_and_conflicts_leave_original_configuration(harness):
    client, fetcher, _, _ = harness
    source = client.post("/api/sources", json={"url": LIST_URL}).json()
    edited = client.patch(
        "/api/sources/" + source["id"],
        json={"url": LIST_URL, "name": "Selected regulations", "section": "/laws"},
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "Selected regulations"
    assert edited.json()["section"] == "/laws"
    other_url = LIST_URL + "?page=2"
    fetcher.values[other_url] = fetcher.values[LIST_URL]
    other = client.post("/api/sources", json={"url": other_url}).json()
    conflict = client.patch("/api/sources/" + other["id"], json={"url": LIST_URL})
    assert conflict.status_code == 409 and conflict.json()["code"] == "duplicate_source"
    sources = {item["id"]: item for item in client.get("/api/sources").json()}
    assert sources[other["id"]]["url"] == other_url
    assert sources[source["id"]]["name"] == "Selected regulations"


def test_sources_and_monitored_documents_can_be_deleted_with_their_history(harness):
    client, _, service, _ = harness
    source = client.post("/api/sources", json={"url": LIST_URL}).json()
    law = add_law(client, source_id=source["id"])
    old = import_old(client, law["id"])["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    scan = run_scan(client, [law["id"]])
    with service.db.session() as session:
        artifacts = [
            service.settings.storage_path / "artifacts" / key
            for key in session.scalars(
                select(Version.artifact_key).where(Version.law_id == law["id"])
            )
        ]
    assert artifacts and all(path.is_file() for path in artifacts)

    removed_source = client.delete("/api/sources/" + source["id"])
    assert removed_source.status_code == 200
    assert removed_source.json()["detached_documents"] == 1
    assert client.get("/api/laws/" + law["id"]).json()["source_id"] is None

    removed_law = client.delete("/api/laws/" + law["id"])
    assert removed_law.status_code == 200
    assert removed_law.json()["versions"] == 2
    assert client.get("/api/laws/" + law["id"]).status_code == 404
    assert client.get("/api/versions/" + old["id"]).status_code == 404
    assert client.get("/api/comparisons/" + comparison["id"]).status_code == 404
    assert client.get("/api/scans/" + scan["id"]).status_code == 404
    assert all(not path.exists() for path in artifacts)


def test_document_deletion_waits_for_an_active_scan(harness):
    client, _, service, _ = harness
    law = add_law(client)
    scan_id = service.start_scan([law["id"]], None)
    blocked = client.delete("/api/laws/" + law["id"])
    assert blocked.status_code == 409 and blocked.json()["code"] == "scan_in_progress"
    service.initialize()
    recovered = client.get("/api/scans/" + scan_id).json()
    assert recovered["status"] == "queued" and recovered["job"]["state"] == "queued"
    assert client.post("/api/jobs/" + recovered["job"]["id"] + "/cancel").status_code == 200
    assert client.delete("/api/laws/" + law["id"]).status_code == 200


def test_discovery_inspects_at_most_fifty_pages_preserves_errors_and_never_crawls_deeper(harness):
    client, fetcher, _, _ = harness
    links = "".join(f'<a href="candidate-{number}.html">Linked document</a>' for number in range(55))
    fetcher.values[LIST_URL] = (
        "<main><h1>Synthetic regulator index</h1><p>Choose a document to inspect.</p>" + links + "</main>"
    ).encode()
    for number in range(55):
        fetcher.values[LIST_URL + f"candidate-{number}.html"] = policy(
            30, '<p><a href="deeper.html">This deeper link must not be followed.</a></p>'
        )
    fetcher.values[LIST_URL + "candidate-1.html"] = b"<main></main>"
    fetcher.values[LIST_URL + "candidate-2.html"] = DomainError(
        "This source is unavailable.", 422, "source_unavailable"
    )
    source = client.post("/api/sources", json={"url": LIST_URL, "section": "/laws"}).json()
    result = client.post("/api/sources/" + source["id"] + "/discover").json()
    assert result["candidate_count"] == 55 and result["inspected_count"] == 50
    assert result["verified_count"] == 48 and result["error_count"] == 2
    assert result["uninspected_count"] == 0 and result["limit_reached"]
    assert result["candidates"][1]["error_code"] == "empty_extraction"
    assert result["candidates"][2]["error_code"] == "source_unavailable"
    assert all(
        candidate["preview"]["content_type"] == "text/html"
        for candidate in result["candidates"]
        if candidate["verified"]
    )
    assert not any("deeper.html" in url or "candidate-50.html" in url for url, _ in fetcher.calls)
    saved = client.get("/api/sources").json()[0]["discovery"]
    assert saved["candidates"] == result["candidates"]
    assert client.get("/api/laws").json() == []


def test_discovery_time_budget_returns_partial_results_instead_of_hanging(harness, monkeypatch):
    import asyncio

    import helvetic_lens.service

    client, fetcher, _, _ = harness
    fetcher.values[LIST_URL] = (
        "<main><h1>Synthetic listing with slow documents</h1><p>Inspect these documents without adding any to the watchlist.</p>"
        + "".join(f'<a href="slow-{number}.html">Document {number}</a>' for number in range(5))
        + "</main>"
    ).encode()
    original_fetch = fetcher.fetch

    async def delayed_fetch(url, provider="native", *, boundary=None):
        if url != LIST_URL:
            await asyncio.sleep(0.2)
        return await original_fetch(url, provider, boundary=boundary)

    monkeypatch.setattr(fetcher, "fetch", delayed_fetch)
    monkeypatch.setattr(helvetic_lens.service, "DISCOVERY_TIMEOUT_SECONDS", 0.03)
    source = client.post("/api/sources", json={"url": LIST_URL, "section": "/laws"}).json()
    response = client.post("/api/sources/" + source["id"] + "/discover")
    assert response.status_code == 200
    result = response.json()
    assert result["time_limit_reached"] and result["verified_count"] == 0
    assert result["inspected_count"] == result["error_count"] == 3
    assert result["uninspected_count"] == 2
    assert all(c["error_code"] == "discovery_time_limit" for c in result["candidates"])
    assert client.get("/api/laws").json() == []
