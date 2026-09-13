"""Render production configuration without a daemon, deployment or real secrets."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from helvetic_lens.commute_static_collector import collect
from helvetic_lens.config import Settings
from helvetic_lens.monitoring_centre import capabilities
from helvetic_lens.road_acquisition import collect as collect_road

ROOT = Path(__file__).resolve().parents[3]
SERVICES = ("api", "worker-cpu", "worker-ai", "scheduler", "migrate")
FLAGS = ("COMMUTE_WATCH_ENABLED", "COMMUTE_SOURCE_ENABLED", "COMMUTE_STATIC_ENABLED",
         "ROAD_WATCH_ENABLED", "ROAD_SOURCE_ENABLED", "TRADEMARK_WATCH_ENABLED",
         "HAZARD_WATCH_ENABLED", "HAZARD_SOURCE_ENABLED", "TENDER_WATCH_ENABLED", "SIMAP_PUBLIC_SOURCE_ENABLED")


def render(tmp_path, overrides):
    executable = shutil.which("docker")
    if executable is None:
        pytest.skip("Docker CLI is needed for read-only Compose rendering")
    # Do not inherit deployment credentials or a real application environment.
    env = {name: value for name, value in os.environ.items() if name.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA",
        "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES"}}
    env.update(HELVETIC_LENS_RELEASE="monitoring-config-test", PUBLIC_BASE_URL="https://lens.example.invalid",
        AUTH_EMAIL_MODE="smtp", AUTH_EMAIL_FROM="lens@example.invalid", AUTH_SMTP_HOST="smtp.example.invalid",
        HELVETIC_LENS_DB_PASSWORD="synthetic-database-only", HELVETIC_LENS_CREDENTIAL_KEY="synthetic-encryption-only",
        HELVETIC_LENS_DOMAIN="lens.example.invalid", CADDY_ACME_EMAIL="ops@example.invalid",
        HELVETIC_LENS_BACKUP_DIR=str(tmp_path / "backup"), **overrides)
    result = subprocess.run([executable, "compose", "--env-file", os.devnull, "-p", "monitoring-config-test",
        "-f", str(ROOT / "compose.production.yaml"), "config", "--format", "json"], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, "Production Compose failed to render with synthetic configuration"
    return json.loads(result.stdout)


def settings(monkeypatch, values):
    for name, value in values.items():
        if name.startswith(("COMMUTE_", "TENDER_", "SIMAP_", "AIR_WATCH_", "RIVER_WATCH_", "ROAD_", "TRADEMARK_", "HAZARD_")):
            monkeypatch.setenv(name, str(value))
    return Settings(_env_file=None, app_environment="test")


def test_default_render_opens_all_implemented_sections_without_inventing_source_access(tmp_path, monkeypatch):
    document = render(tmp_path, {})
    for service in SERVICES:
        values = document["services"][service]["environment"]
        assert all(values[name] == "true" for name in FLAGS)
        assert values["TENDER_WATCH_ENABLED"] == values["SIMAP_PUBLIC_SOURCE_ENABLED"] == "true"
        assert values["COMMUTE_GTFS_RT_KEY"] == values["COMMUTE_GTFS_SA_KEY"] == ""
        assert values["COMMUTE_STATIC_DATASET_ID"] == ""
        assert values["ROAD_SOURCE_KEY"] == values["ROAD_SOURCE_PERMISSION_ID"] == ""
        config = settings(monkeypatch, values)
        assert config.air_watch_enabled and config.river_watch_enabled
        assert config.trademark_watch_enabled and config.hazard_watch_enabled
        choices = {item["id"]: item for item in capabilities(config, "release-test-organization")}
        assert len(choices) == 9
        for domain in ("warnings", "commute", "traffic", "tenders", "ip", "river", "air"):
            assert choices[domain]["href"]
        assert choices["tenders"]["availability"] == "available"
        for domain in ("warnings", "commute", "traffic", "ip"):
            assert choices[domain]["availability"] == "preview_only"
        assert config.commute_feed_redirect_origins == config.commute_static_redirect_origins == ()
        assert config.commute_static_cache_max_bytes == 2 * 1024**3
        assert collect(object(), config) == {"state": "unconfigured"}
        assert collect_road(object(), config) == {"state": "unconfigured"}


def test_operator_values_reach_every_backend_and_source_kill_switch_is_effective(tmp_path, monkeypatch):
    overrides = {name: "true" for name in FLAGS}
    overrides.update(TENDER_WATCH_ENABLED="true", SIMAP_PUBLIC_SOURCE_ENABLED="true", COMMUTE_SOURCE_ENABLED="false", AIR_WATCH_ENABLED="false", RIVER_WATCH_ENABLED="false",
        ROAD_SOURCE_ENABLED="false", ROAD_SOURCE_KEY="synthetic-road-key-only",
        ROAD_SOURCE_PERMISSION_ID="00000000-0000-4000-8000-000000000004",
        COMMUTE_GTFS_RT_KEY="synthetic-rt-only", COMMUTE_GTFS_SA_KEY="synthetic-sa-only",
        COMMUTE_GTFS_RT_PERMISSION_ID="00000000-0000-4000-8000-000000000001",
        COMMUTE_GTFS_SA_PERMISSION_ID="00000000-0000-4000-8000-000000000002",
        COMMUTE_STATIC_DATASET_ID="00000000-0000-4000-8000-000000000003",
        COMMUTE_FEED_REDIRECT_ORIGINS='["https://feeds.example.invalid"]',
        COMMUTE_STATIC_REDIRECT_ORIGINS='["https://archives.example.invalid"]',
        COMMUTE_STATIC_CACHE_MAX_BYTES="1073741824", TENDER_PUBLIC_STORAGE_MAX_BYTES="1073741824",
        TENDER_MONITOR_MAX_VERSIONS="2000")
    document = render(tmp_path, overrides)
    for service in SERVICES:
        values = document["services"][service]["environment"]
        assert {name: values[name] for name in overrides} == overrides
        config = settings(monkeypatch, values)
        assert config.commute_watch_enabled and config.commute_static_enabled and not config.commute_source_enabled
        assert config.tender_watch_enabled and config.simap_public_source_enabled
        assert not config.air_watch_enabled and not config.river_watch_enabled
        assert config.commute_gtfs_rt_key.get_secret_value() == "synthetic-rt-only"
        assert config.commute_gtfs_sa_key.get_secret_value() == "synthetic-sa-only"
        assert "synthetic-rt-only" not in repr(config)
        assert config.road_watch_enabled and not config.road_source_enabled
        assert config.road_source_key.get_secret_value() == "synthetic-road-key-only"
        assert "synthetic-road-key-only" not in repr(config)
        assert collect_road(object(), config) == {"state": "disabled"}
        assert config.commute_feed_redirect_origins == ("https://feeds.example.invalid",)
        assert config.commute_static_redirect_origins == ("https://archives.example.invalid",)
        assert config.commute_static_cache_max_bytes == config.tender_public_storage_max_bytes == 1024**3
        assert config.tender_monitor_max_versions == 2000
        assert collect(object(), config) == {"state": "disabled"}  # No DB or network despite installed keys.
    for service, spec in document["services"].items():
        if service not in SERVICES:
            assert not any(name.startswith(("COMMUTE_", "ROAD_")) for name in spec.get("environment", {}))
