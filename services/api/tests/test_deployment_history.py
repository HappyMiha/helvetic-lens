import json
import sqlite3

import pytest

from helvetic_lens.config import DomainError
from helvetic_lens.deployment_history import history_detail, history_page, redact


def record(index, status="succeeded"):
    return {"id": f"run-{index:05}", "kind": "release", "status": status,
            "started_at": "2026-09-08T08:00:00+00:00", "finished_at": "2026-09-08T08:05:00+00:00",
            "target_sha": str(index % 10) * 40, "previous_sha": "a" * 40,
            "activated_sha": str(index % 10) * 40 if status == "succeeded" else None,
            "steps": [{"name": "api_tests", "status": status, "error": None}], "changes": [],
            "rollback": {"status": "not_required"}, "error": None,
            "release_notes": {"kind": "commit_summary", "target_sha": str(index % 10) * 40,
                              "previous_sha": "a" * 40, "text": f"Deployment change {index}"}}


def journal(tmp_path, records):
    with sqlite3.connect(tmp_path / "history.sqlite3") as database:
        database.executescript("""CREATE TABLE runs(id TEXT PRIMARY KEY, started_at TEXT, status TEXT, summary TEXT, detail TEXT);
            CREATE INDEX runs_chronology ON runs(started_at DESC, id DESC);
            CREATE INDEX runs_status ON runs(status, started_at DESC, id DESC);
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO metadata VALUES('archive_started_at', '2026-09-08T08:00:00+00:00');
            INSERT INTO metadata VALUES('archive_id', 'archive-fixture');""")
        for row in records:
            database.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                             (row["id"], row["started_at"], row["status"], json.dumps(row), json.dumps(row)))


def test_all_equal_time_history_is_reachable_without_new_run_duplicates(tmp_path):
    journal(tmp_path, [record(i, "failed" if i % 2 else "succeeded") for i in range(135)])
    first = history_page(tmp_path)
    assert len(first["items"]) == 20 and first["mode"] == "journal"
    with sqlite3.connect(tmp_path / "history.sqlite3") as database:
        later = record(9)
        later["id"] = "run-00009-new"
        database.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                         (later["id"], later["started_at"], later["status"], json.dumps(later), json.dumps(later)))
    ids = [row["id"] for row in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        page = history_page(tmp_path, cursor=cursor)
        ids.extend(row["id"] for row in page["items"])
        cursor = page["next_cursor"]
    assert ids == [f"run-{i:05}" for i in reversed(range(135))]
    failed = history_page(tmp_path, status="failed", limit=50)
    assert len(failed["items"]) == 50 and all(row["status"] == "failed" for row in failed["items"])
    with pytest.raises(DomainError) as error:
        history_page(tmp_path, status="succeeded", cursor=failed["next_cursor"])
    assert error.value.code == "invalid_cursor"


def test_detail_preserves_error_phase_and_pinned_notes_without_executing_or_reading_paths(tmp_path):
    failed = record(1, "failed")
    failed.update(error_step="api_tests", error="Authorization: Bearer secret-token api_key=secret-key",
                  log_id="../../private.env", environment_values={"secret": "never display"})
    failed["steps"][0]["error"] = "password=secret-password database test failed"
    journal(tmp_path, [failed, record(2)])
    detail = history_detail(tmp_path, failed["id"])
    serialized = json.dumps(detail)
    assert "secret-token" not in serialized and "secret-key" not in serialized
    assert "secret-password" not in serialized and "never display" not in serialized
    assert "private.env" not in serialized
    assert detail["error_step"] == "api_tests" and detail["activated_sha"] is None
    assert detail["steps"][0]["error"].endswith("database test failed")
    (tmp_path / "status.json").write_text(json.dumps({"current": {"sha": "f" * 40}}))
    success = history_detail(tmp_path, "run-00002")
    assert success["activated_sha"] == "2" * 40
    assert success["release_notes"]["previous_sha"] == "a" * 40
    assert success["release_notes"]["text"] == "Deployment change 2"
    with pytest.raises(DomainError) as error:
        history_detail(tmp_path, "../../private.env")
    assert error.value.status == 404


def test_legacy_mode_has_honest_retention_and_complete_reachable_snapshot(tmp_path):
    (tmp_path / "history.json").write_text(json.dumps([record(i) for i in range(60)]))
    (tmp_path / "status.json").write_text(json.dumps({"last_run": record(61, "deploying")}))
    page = history_page(tmp_path, limit=50)
    assert page["mode"] == "legacy" and page["legacy_retention_unknown"]
    assert page["archive_started_at"] is None and len(page["items"]) == 50
    assert page["items"][0]["status"] == "deploying"
    next_page = history_page(tmp_path, cursor=page["next_cursor"], limit=50)
    assert len(next_page["items"]) == 11 and next_page["next_cursor"] is None
    assert history_detail(tmp_path, "run-00000")["id"] == "run-00000"


def test_unavailable_corrupt_and_replaced_archives_are_not_reported_as_empty_success(tmp_path):
    assert history_page(tmp_path)["items"] == []
    journal(tmp_path, [record(i) for i in range(25)])
    page = history_page(tmp_path)
    with sqlite3.connect(tmp_path / "history.sqlite3") as database:
        database.execute("UPDATE metadata SET value='replacement' WHERE key='archive_id'")
    with pytest.raises(DomainError) as error:
        history_page(tmp_path, cursor=page["next_cursor"])
    assert error.value.code == "invalid_cursor"
    (tmp_path / "history.sqlite3").write_text("not a database")
    with pytest.raises(DomainError) as error:
        history_page(tmp_path)
    assert error.value.status == 503


def test_truncation_is_explicit_and_missing_notes_are_not_invented(tmp_path):
    row = record(1)
    row["error"] = "x" * 9000
    row["release_notes"] = None
    row["steps"] = row["steps"] * 101
    journal(tmp_path, [row])
    result = history_detail(tmp_path, row["id"])
    assert result["details_truncated"] and len(result["error"]) == 8000 and len(result["steps"]) == 100
    assert result["release_notes"] is None


def test_http_history_is_platform_admin_only_and_read_only(tmp_path):
    from conftest import FakeFetcher, ScriptedModel
    from fastapi.testclient import TestClient
    from test_organization_access import register, settings

    from helvetic_lens.main import create_app
    from helvetic_lens.models import User
    app_settings = settings(tmp_path).model_copy(update={"deployment_state_dir": tmp_path})
    journal(tmp_path, [record(1), record(2, "failed")])
    model = ScriptedModel()
    app = create_app(app_settings, fetcher=FakeFetcher(), model_client=model)
    paths = ["/api/admin/deployments/history", "/api/admin/deployments/history/run-00001"]
    with TestClient(app) as client:
        for path in paths:
            assert client.get(path).status_code == 401
        user = register(client, "deployment-admin@example.ch").json()["user"]
        for path in paths:
            assert client.get(path).status_code == 403
        with app.state.service.db.session(include_all_organizations=True) as session:
            session.get(User, user["id"]).platform_admin = True
            session.commit()
        for path in paths:
            response = client.get(path)
            assert response.status_code == 200, response.text
        filtered = client.get(paths[0] + "?status=failed").json()
        assert len(filtered["items"]) == 1 and filtered["items"][0]["status"] == "failed"
        assert client.get(paths[0] + "?limit=500").status_code == 422
        assert client.get(paths[0] + "?cursor=not-base64").status_code == 422
        assert client.get(paths[1] + "-unknown").status_code == 404
        assert model.calls == []


def test_malformed_details_and_invalid_dates_are_explicit_not_ui_crashes(tmp_path):
    row = record(1)
    row["started_at"] = "invalid timestamp"
    row["steps"] = None
    journal(tmp_path, [row])
    assert history_page(tmp_path)["items"][0]["started_at"] is None
    with pytest.raises(DomainError) as error:
        history_detail(tmp_path, row["id"])
    assert error.value.status == 503


@pytest.mark.parametrize("value", ['password="quoted secret"', "token='quoted secret'", '"api_key": "quoted secret"', 'Authorization: Bearer quoted-secret'])
def test_quoted_and_header_credentials_are_redacted(value):
    assert "quoted" not in redact(value)
