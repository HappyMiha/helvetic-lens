from dataclasses import replace

import pytest
from bs4 import BeautifulSoup
from conftest import LAW_URL, add_law, policy, run_scan
from sqlalchemy import select

from helvetic_lens import service as service_module
from helvetic_lens.extraction import extract
from helvetic_lens.models import Observation, Version


def source(days=30):
    return policy(days).replace(b"<main>", b'<div id="lawcontent"><main>').replace(
        b"</main>", b"</main><p>Annex: keep an audit register of all retained records.</p></div>"
    )


def old_baseline(client, fetcher, monkeypatch):
    fetcher.values[LAW_URL] = source()

    def legacy_extract(body, content_type="", filename="document", provider="native"):
        main = str(BeautifulSoup(body, "html.parser").find("main")).encode()
        partial = extract(main, content_type, filename, provider)
        return replace(partial, body=body, extractor="native-v3")

    with monkeypatch.context() as patch:
        patch.setattr(service_module, "extract", legacy_extract)
        return add_law(client)


@pytest.mark.parametrize("days,expected", [(30, "unchanged"), (60, "changed")])
def test_parser_upgrade_compares_originals_and_keeps_old_evidence(harness, monkeypatch, days, expected):
    client, fetcher, service, model = harness
    law = old_baseline(client, fetcher, monkeypatch)
    old_id = law["current_version_id"]
    old_before = client.get(f"/api/versions/{old_id}").json()
    fetcher.values[LAW_URL] = source(days)
    item = run_scan(client, [law["id"]])["items"][0]
    assert item["result"] == expected
    comparison = client.get("/api/comparisons/" + item["comparison_id"]).json()
    assert comparison["old_version"]["extractor"] == "native-html-v5"
    assert comparison["new_version"]["extractor"] == "native-html-v5"
    old_full = client.get(comparison["old_version"]["artifact_url"])
    assert old_full.content == source()
    assert client.get(f"/api/versions/{old_id}").json() == old_before
    assert not model.calls
    with service.db.session() as session:
        derived = session.get(Version, comparison["old_version"]["id"])
        assert "Annex: keep an audit register" in derived.text
        assert derived.owner_organization_id == service.organization_id
        parent = next(row for row in session.scalars(select(Observation))
                      if row.metadata_json.get("reextracted_from_version_id") == old_id)
        assert parent.metadata_json["prior_extractor"] == "native-v3"
        assert parent.artifact_key == session.get(Version, old_id).artifact_key
    if days == 60:
        assert comparison["diff"]["counts"]["modified"] == 1
        assert comparison["diff"]["counts"]["added"] == 0
        assert comparison["old_version"]["origin"] == "reprocessed"
    assert run_scan(client, [law["id"]])["items"][0]["result"] == "unchanged"


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_unreadable_prior_original_stops_scan_and_retains_pointer(harness, monkeypatch, damage):
    client, fetcher, service, _ = harness
    law = old_baseline(client, fetcher, monkeypatch)
    with service.db.session() as session:
        previous = session.get(Version, law["current_version_id"])
        artifact = service.settings.storage_path / "artifacts" / previous.artifact_key
    if damage == "missing":
        artifact.unlink()
    else:
        artifact.write_bytes(b"damaged stored original")
    # Different current bytes must not silently replace the unavailable old original.
    fetcher.values[LAW_URL] = source(60)
    result = run_scan(client, [law["id"]])
    assert result["items"][0]["result"] == "failed"
    assert result["items"][0]["analysis_status"] == "not_run"
    detail = client.get("/api/laws/" + law["id"]).json()
    assert detail["current_version_id"] == law["current_version_id"]
    assert "original" in detail["last_error"]


def test_saved_version_comparison_reextracts_without_network_and_replays(harness, monkeypatch):
    client, fetcher, _, _ = harness
    law = old_baseline(client, fetcher, monkeypatch)
    new = client.post("/api/laws/" + law["id"] + "/import",
                      files={"file": ("changed.html", source(60), "text/html")}).json()["version"]
    calls = list(fetcher.calls)
    payload = {"old_version_id": law["current_version_id"], "new_version_id": new["id"]}
    first = client.post("/api/comparisons", json=payload)
    assert first.status_code == 201, first.text
    again = client.post("/api/comparisons", json=payload)
    assert again.json()["id"] == first.json()["id"]
    assert first.json()["diff"]["counts"]["modified"] == 1
    assert first.json()["diff"]["counts"]["added"] == 0
    assert fetcher.calls == calls
    assert client.get("/api/laws/" + law["id"]).json()["current_version_id"] == law["current_version_id"]
