import json

from helvetic_lens.deployments import deployment_snapshot


def test_missing_deployment_state_is_reported_as_not_configured(tmp_path):
    result = deployment_snapshot(tmp_path)

    assert result["service"]["state"] == "not_configured"
    assert result["history"] == []


def test_deployment_state_and_history_are_bounded(tmp_path):
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "service": {"enabled": True, "state": "idle"},
                "remote": {"branch": "main", "sha": "a" * 40},
                "current": {"sha": "a" * 40, "release": "git-aaaaaaaaaaaa"},
                "last_run": {"status": "succeeded", "error": None},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "history.json").write_text(
        json.dumps([{"id": str(index), "status": "succeeded"} for index in range(60)]),
        encoding="utf-8",
    )

    result = deployment_snapshot(tmp_path)

    assert result["service"] == {"enabled": True, "state": "idle"}
    assert result["current"]["release"] == "git-aaaaaaaaaaaa"
    assert len(result["history"]) == 30


def test_invalid_deployment_state_never_breaks_platform_admin(tmp_path):
    (tmp_path / "status.json").write_text("not-json", encoding="utf-8")

    result = deployment_snapshot(tmp_path)

    assert result["service"]["state"] == "status_unavailable"
    assert "error" in result["service"]
