from conftest import add_law, import_old


def comparison_for(client, law):
    old = import_old(client, law["id"])["version"]
    return client.post(
        "/api/comparisons",
        json={
            "old_version_id": old["id"],
            "new_version_id": law["current_version_id"],
        },
    ).json()


def test_matrix_uses_saved_current_report_without_calling_model(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    comparison = comparison_for(client, law)

    empty = client.get("/api/impact-matrix", params={"output_locale": "en-CH"})
    assert empty.status_code == 200
    assert empty.json()["summary"]["unanalysed_documents"] == 1
    assert {cell["state"] for cell in empty.json()["rows"][0]["cells"]} == {
        "unanalysed"
    }
    assert model.calls == []

    report = client.post(
        f"/api/comparisons/{comparison['id']}/analyse",
        json={"output_locale": "en-CH"},
    ).json()
    calls_after_analysis = len(model.calls)
    matrix = client.get(
        "/api/impact-matrix", params={"output_locale": "en-CH"}
    ).json()

    assert len(model.calls) == calls_after_analysis
    assert matrix["summary"] == {
        "documents": 1,
        "current_reports": 1,
        "stale_reports": 0,
        "failed_reports": 0,
        "unanalysed_documents": 0,
        "assessed_cells": 1,
        "unknown_cells": 2,
    }
    row = matrix["rows"][0]
    assert row["analysis_id"] == report["id"]
    assert row["comparison_url"] == f"/compare/{comparison['id']}"
    assert row["overall_impact"] == "medium"
    cells = {cell["area"]: cell for cell in row["cells"]}
    assert cells["Operations"]["state"] == "assessed"
    assert cells["Operations"]["impact"] == "medium"
    assert cells["Operations"]["reason"]
    assert cells["Legal"] == {
        "area": "Legal",
        "state": "unknown",
        "impact": None,
        "previous_impact": None,
        "reason": None,
    }
    assert cells["IT"]["impact"] is None


def test_profile_revision_invalidates_matrix_values_but_retains_history_link(harness):
    client, _, service, _ = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    comparison = comparison_for(client, law)
    report = client.post(
        f"/api/comparisons/{comparison['id']}/analyse",
        json={"output_locale": "en-CH"},
    ).json()
    profile = client.get("/api/profile").json()
    client.patch(
        "/api/profile",
        json={
            "name": "Revised profile",
            "description": profile["description"],
            "business_areas": profile["business_areas"],
        },
    )

    matrix = client.get(
        "/api/impact-matrix", params={"output_locale": "en-CH"}
    ).json()

    row = matrix["rows"][0]
    assert row["report_state"] == "stale"
    assert row["analysis_id"] == report["id"]
    assert row["overall_impact"] is None
    assert row["previous_overall_impact"] == "medium"
    assert row["comparison_url"] == f"/compare/{comparison['id']}"
    operations = next(cell for cell in row["cells"] if cell["area"] == "Operations")
    assert operations["state"] == "stale"
    assert operations["impact"] is None
    assert operations["previous_impact"] == "medium"


def test_failed_analysis_and_inactive_watch_are_not_mislabelled_low(harness):
    client, _, service, model = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    comparison = comparison_for(client, law)
    model.fail = True
    failed = client.post(
        f"/api/comparisons/{comparison['id']}/analyse",
        json={"output_locale": "en-CH"},
    )
    assert failed.json()["status"] == "failed"

    matrix = client.get(
        "/api/impact-matrix", params={"output_locale": "en-CH"}
    ).json()
    assert matrix["summary"]["failed_reports"] == 1
    assert {cell["state"] for cell in matrix["rows"][0]["cells"]} == {"failed"}
    assert all(cell["impact"] is None for cell in matrix["rows"][0]["cells"])

    client.patch(f"/api/laws/{law['id']}", json={"active": False})
    hidden = client.get("/api/impact-matrix", params={"output_locale": "en-CH"}).json()
    assert hidden["summary"]["documents"] == 0
    assert hidden["rows"] == []
