from conftest import LAW_URL, add_law, policy, run_scan
from sqlalchemy import func, select

from helvetic_lens.diffing import compare_passages
from helvetic_lens.models import Analysis, AskRecord, Comparison, IdentityDecision, Version

NATURALIZATION_ELI = "https://fedlex.data.admin.ch/eli/oc/2017/259/de"
NATURALIZATION_TITLE = (
    "Bundesbeschluss über die erleichterte Einbürgerung von Personen "
    "der dritten Ausländergeneration"
)
DZV = """
<html><head><title>910.13</title></head><body><main>
<p>SR 910.13</p>
<h1>Verordnung über die Direktzahlungen an die Landwirtschaft
(Direktzahlungsverordnung, DZV)</h1>
<p>Diese Verordnung regelt landwirtschaftliche Direktzahlungen.</p>
</main></body></html>
""".encode()


def test_artifact_identity_is_persisted_with_official_metadata(harness):
    client, fetcher, _, _ = harness
    fetcher.values[NATURALIZATION_ELI] = policy()
    law = add_law(client, url=NATURALIZATION_ELI, name=NATURALIZATION_TITLE)
    version = client.get("/api/versions/" + law["current_version_id"]).json()
    identity = version["identity_json"]

    assert identity["revision"] == "artifact-identity-v2"
    assert identity["authority"] == "Swiss Confederation / Fedlex"
    assert identity["canonical_work_id"] == "/eli/oc/2017/259"
    assert identity["document_kind"] == "document"
    assert identity["title"]
    assert identity["language"] == "de"
    assert identity["source_url"] == NATURALIZATION_ELI
    assert identity["extractor"] and identity["content_type"] == "text/html"
    assert identity["evidence"] and identity["fingerprint"]


def test_naturalization_record_rejects_sr_910_13_before_comparison_or_ai(harness):
    client, fetcher, service, model = harness
    fetcher.values[NATURALIZATION_ELI] = policy()
    law = add_law(client, url=NATURALIZATION_ELI, name=NATURALIZATION_TITLE)

    preview = client.post(
        f"/api/laws/{law['id']}/import?preview=true",
        files={"file": ("dzv.html", DZV, "text/html")},
    )
    assert preview.status_code == 200
    assert preview.json()["identity"]["status"] == "mismatch"

    blocked_save = client.post(
        f"/api/laws/{law['id']}/import",
        files={"file": ("dzv.html", DZV, "text/html")},
    )
    assert blocked_save.status_code == 409

    saved = client.post(
        f"/api/laws/{law['id']}/import",
        files={"file": ("dzv.html", DZV, "text/html")},
        data={"allow_identity_mismatch": "true"},
    )
    assert saved.status_code == 200
    wrong_id = saved.json()["version"]["id"]
    assert saved.json()["identity"]["detected_identifier"] == "sr:910.13"

    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": wrong_id, "new_version_id": law["current_version_id"]},
    )
    assert comparison.status_code == 409
    assert comparison.json()["code"] == "document_identity_mismatch"

    with service.db.session() as session:
        legacy = Comparison(
            law_id=law["id"],
            old_version_id=wrong_id,
            new_version_id=law["current_version_id"],
            mode="saved_versions",
            diff=compare_passages(
                session.get(Version, wrong_id).passages,
                session.get(Version, law["current_version_id"]).passages,
            ),
        )
        session.add(legacy)
        session.commit()
        comparison_id = legacy.id

    assert client.post(f"/api/comparisons/{comparison_id}/analyse").status_code == 409
    assert client.post(
        f"/api/comparisons/{comparison_id}/ask", json={"question": "What changed?"}
    ).status_code == 409
    with service.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Analysis)) == 0
        assert session.scalar(select(func.count()).select_from(AskRecord)) == 0
        decision = session.scalar(
            select(IdentityDecision).where(IdentityDecision.version_id == wrong_id)
        )
        assert decision.action == "saved_for_inspection"
    assert model.calls == []


def test_unknown_assignment_requires_and_audits_explicit_confirmation(harness):
    client, _, service, _ = harness
    law = add_law(client)
    text = "3\n\nEarlier provision.\n\nRecords remain available."

    blocked = client.post(f"/api/laws/{law['id']}/import", data={"text": text})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "document_identity_unknown"

    saved = client.post(
        f"/api/laws/{law['id']}/import",
        data={"text": text, "confirm_identity": "true"},
    )
    assert saved.status_code == 200
    version_id = saved.json()["version"]["id"]
    with service.db.session() as session:
        decision = session.scalar(
            select(IdentityDecision).where(IdentityDecision.version_id == version_id)
        )
        assert decision.action == "confirm_assignment"
        assert decision.identity_fingerprint == session.get(Version, version_id).identity_json["fingerprint"]

    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": version_id, "new_version_id": law["current_version_id"]},
    )
    assert comparison.status_code == 201
    assert comparison.json()["identity"]["effective_status"] == "probable"


def test_scan_quarantines_wrong_artifact_without_moving_live_pointer(harness):
    client, fetcher, service, model = harness
    law = add_law(client)
    current_id = law["current_version_id"]
    fetcher.values[LAW_URL] = DZV

    scan = run_scan(client, [law["id"]])
    item = scan["items"][0]
    assert item["result"] == "failed"
    assert item["new_version_id"] and item["comparison_id"] is None
    assert client.get("/api/laws/" + law["id"]).json()["current_version_id"] == current_id
    with service.db.session() as session:
        assert session.get(Version, item["new_version_id"]).identity_json["canonical_work_id"] == "sr:910.13"
        assert session.scalar(select(func.count()).select_from(Comparison)) == 0
    assert model.calls == []


def test_mismatch_cannot_be_overridden_by_identity_confirmation(harness):
    client, fetcher, _, _ = harness
    fetcher.values[NATURALIZATION_ELI] = policy()
    law = add_law(client, url=NATURALIZATION_ELI, name=NATURALIZATION_TITLE)
    saved = client.post(
        f"/api/laws/{law['id']}/import",
        files={"file": ("dzv.html", DZV, "text/html")},
        data={"allow_identity_mismatch": "true"},
    ).json()
    result = client.post(
        f"/api/versions/{saved['version']['id']}/identity-decision",
        json={"note": "Trust this anyway"},
    )
    assert result.status_code == 409
    assert result.json()["code"] == "identity_decision_not_allowed"


def test_mistaken_import_can_be_removed_but_current_snapshot_cannot(harness):
    client, _, _, _ = harness
    law = add_law(client)
    imported = client.post(
        f"/api/laws/{law['id']}/import",
        data={
            "text": "3\n\nEarlier provision.\n\nRecords remain available.",
            "confirm_identity": "true",
        },
    ).json()["version"]
    assert client.delete("/api/versions/" + imported["id"]).status_code == 200
    assert client.get("/api/versions/" + imported["id"]).status_code == 404
    blocked = client.delete("/api/versions/" + law["current_version_id"])
    assert blocked.status_code == 409


def test_assignment_change_rechecks_gate_and_invalidates_previous_ai_result(harness):
    client, _, service, _ = harness
    service.settings.apertus_base_url = "https://model.example/v1"
    law = add_law(client)
    old = client.post(
        f"/api/laws/{law['id']}/import",
        files={"file": ("old.html", policy(10), "text/html")},
    ).json()["version"]
    comparison = client.post(
        "/api/comparisons",
        json={"old_version_id": old["id"], "new_version_id": law["current_version_id"]},
    ).json()
    assert client.post(f"/api/comparisons/{comparison['id']}/analyse").json()["status"] == "succeeded"

    client.patch(
        f"/api/laws/{law['id']}",
        json={"name": "Ordinanza sulla pesca marittima"},
    )
    detail = client.get(f"/api/comparisons/{comparison['id']}").json()
    assert detail["identity"]["effective_status"] in {"unknown", "mismatch"}
    assert detail["analysis"]["stale"] is True
