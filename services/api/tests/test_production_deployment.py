import shlex
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from scripts.validate_production_env import load_env, validate

from helvetic_lens.config import Settings
from helvetic_lens.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def valid_environment() -> dict[str, str]:
    return {
        "APP_ENVIRONMENT": "production",
        "ALLOW_ANONYMOUS_DEV": "false",
        "SESSION_COOKIE_SECURE": "true",
        "ALLOW_PRIVATE_SOURCES": "false",
        "HELVETIC_LENS_DOMAIN": "lens.example.net",
        "PUBLIC_BASE_URL": "https://lens.example.net",
        "HELVETIC_LENS_RELEASE": "faff3c012345",
        "CADDY_ACME_EMAIL": "ops@real-domain.ch",
        "HELVETIC_LENS_DB_PASSWORD": "random_database_password_42",
        "HELVETIC_LENS_CREDENTIAL_KEY": "random-credential-key-with-entropy-42",
        "AUTH_EMAIL_MODE": "smtp",
        "AUTH_EMAIL_FROM": "Helvetic Lens <lens@real-domain.ch>",
        "AUTH_SMTP_HOST": "smtp.real-domain.ch",
        "AUTH_SMTP_USERNAME": "",
        "AUTH_SMTP_PASSWORD": "",
        "APERTUS_PROVIDER": "docker",
        "JOB_EXECUTION_MODE": "celery",
        "DEFAULT_LOCALE": "de-CH",
        "MAX_DOCUMENT_BYTES": "8388608",
        "HELVETIC_LENS_BACKUP_DIR": "/srv/helvetic-lens-backups",
        "BACKUP_RETENTION_DAYS": "30",
        "BACKUP_INTERVAL_SECONDS": "86400",
    }


def test_production_example_is_deliberately_rejected_until_placeholders_are_replaced():
    values = load_env(ROOT / "deploy" / "production.env.example")

    errors = validate(values)

    assert any(error.startswith("HELVETIC_LENS_RELEASE:") for error in errors)
    assert any(error.startswith("HELVETIC_LENS_DB_PASSWORD:") for error in errors)
    assert any(error.startswith("HELVETIC_LENS_CREDENTIAL_KEY:") for error in errors)


def test_valid_production_environment_passes_without_cloud_credentials():
    assert validate(valid_environment()) == []


def test_deployment_status_mount_is_read_only_and_docker_socket_is_never_exposed():
    compose = (ROOT / "compose.production.yaml").read_text(encoding="utf-8")

    assert ":/operations/deployments:ro" in compose
    assert "/var/run/docker.sock" not in compose


def test_web_build_includes_all_node_checks_and_shared_fixtures():
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")
    build_stage, runtime_stage = dockerfile.split("\nFROM ", maxsplit=1)
    copied_scripts = set()
    for line in build_stage.splitlines():
        if line.startswith("COPY "):
            parts = shlex.split(line)
            if parts[-1] == "scripts/":
                for source in parts[1:-1]:
                    copied_scripts.update(ROOT.glob(source))

    required_scripts = set((ROOT / "scripts").glob("*.mjs"))
    assert required_scripts
    assert not required_scripts - copied_scripts, "Node checks/fixtures missing from web builder"
    assert not any(line.startswith("COPY ") and "scripts/" in line for line in runtime_stage.splitlines()), (
        "Build checks must not be copied into the runtime image"
    )


def test_production_environment_rejects_public_data_paths_and_insecure_auth():
    values = valid_environment()
    values.update(
        ALLOW_ANONYMOUS_DEV="true",
        SESSION_COOKIE_SECURE="false",
        ALLOW_PRIVATE_SOURCES="true",
        PUBLIC_BASE_URL="http://localhost:3000",
        AUTH_EMAIL_MODE="development",
        APERTUS_PROVIDER="infomaniak",
        JOB_EXECUTION_MODE="inline",
        MAX_DOCUMENT_BYTES=str(21 * 1024 * 1024),
        HELVETIC_LENS_BACKUP_DIR="./backups",
        BACKUP_RETENTION_DAYS="2",
        BACKUP_INTERVAL_SECONDS="60",
    )

    errors = validate(values)

    rejected = "\n".join(errors)
    assert "ALLOW_ANONYMOUS_DEV" in rejected
    assert "SESSION_COOKIE_SECURE" in rejected
    assert "ALLOW_PRIVATE_SOURCES" in rejected
    assert "PUBLIC_BASE_URL" in rejected
    assert "AUTH_EMAIL_MODE" in rejected
    assert "APERTUS_PROVIDER" in rejected
    assert "JOB_EXECUTION_MODE" in rejected
    assert "MAX_DOCUMENT_BYTES" in rejected
    assert "HELVETIC_LENS_BACKUP_DIR" in rejected
    assert "BACKUP_RETENTION_DAYS" in rejected
    assert "BACKUP_INTERVAL_SECONDS" in rejected


def test_application_accepts_only_the_validated_production_security_boundary(tmp_path):
    settings = Settings(
        _env_file=None,
        app_environment="production",
        allow_anonymous_dev=False,
        session_cookie_secure=True,
        public_base_url="https://lens.real-domain.ch",
        auth_email_mode="smtp",
        auth_email_from="lens@real-domain.ch",
        auth_smtp_host="smtp.real-domain.ch",
        credential_encryption_key="random-credential-key-with-entropy-42",
        database_url="postgresql+psycopg://helvetic_lens:random_database_password_42@db/helvetic_lens",
        job_execution_mode="celery",
        allow_private_sources=False,
        data_dir=tmp_path,
    )

    assert settings.app_environment == "production"

    with pytest.raises(ValidationError, match="HTTPS public base URL"):
        Settings(
            _env_file=None,
            app_environment="production",
            allow_anonymous_dev=False,
            session_cookie_secure=True,
            public_base_url="http://lens.real-domain.ch",
            auth_email_mode="smtp",
            auth_email_from="lens@real-domain.ch",
            auth_smtp_host="smtp.real-domain.ch",
            credential_encryption_key="random-credential-key-with-entropy-42",
            database_url="postgresql+psycopg://helvetic_lens:random_database_password_42@db/helvetic_lens",
            job_execution_mode="celery",
            data_dir=tmp_path,
        )


def test_readiness_requires_both_database_and_redis(monkeypatch, tmp_path):
    class ReadyRedis:
        def ping(self):
            return True

        def close(self):
            pass

    monkeypatch.setattr("helvetic_lens.main.Redis.from_url", lambda *_args, **_kwargs: ReadyRedis())
    app = create_app(
        Settings(
            _env_file=None,
            app_environment="test",
            data_dir=tmp_path,
            job_execution_mode="inline",
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": True, "redis": True}}
