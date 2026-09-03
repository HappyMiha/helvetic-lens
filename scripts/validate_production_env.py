"""Fail closed before rendering or starting the public production stack."""

from __future__ import annotations

import argparse
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
PLACEHOLDER_MARKERS = ("change_me", "changeme", "example", "placeholder")
LOCALES = {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"line {number}: expected NAME=value")
        name, value = line.split("=", 1)
        name = name.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError(f"line {number}: invalid variable name")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[name] = value
    return values


def _placeholder(value: str) -> bool:
    lowered = value.lower()
    return not value or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []

    def require(name: str) -> str:
        value = values.get(name, "").strip()
        if not value:
            errors.append(f"{name}: required")
        return value

    def require_bool(name: str, expected: bool) -> None:
        raw = require(name).lower()
        accepted = TRUE_VALUES if expected else FALSE_VALUES
        if raw and raw not in accepted:
            errors.append(f"{name}: must be {'true' if expected else 'false'}")

    if require("APP_ENVIRONMENT") != "production":
        errors.append("APP_ENVIRONMENT: must be production")
    require_bool("ALLOW_ANONYMOUS_DEV", False)
    require_bool("SESSION_COOKIE_SECURE", True)
    require_bool("ALLOW_PRIVATE_SOURCES", False)

    domain = require("HELVETIC_LENS_DOMAIN").lower()
    if domain and ("://" in domain or "/" in domain or "." not in domain or domain == "localhost"):
        errors.append("HELVETIC_LENS_DOMAIN: use a public hostname without scheme or path")

    public_url = require("PUBLIC_BASE_URL")
    parsed = urlsplit(public_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"}:
        errors.append("PUBLIC_BASE_URL: must be an HTTPS origin without a path")
    elif domain and parsed.hostname.lower() != domain:
        errors.append("PUBLIC_BASE_URL: hostname must match HELVETIC_LENS_DOMAIN")

    release = require("HELVETIC_LENS_RELEASE")
    if _placeholder(release) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{6,79}", release):
        errors.append("HELVETIC_LENS_RELEASE: use an immutable commit or release identifier")

    email = require("CADDY_ACME_EMAIL")
    if "@" not in email or _placeholder(email):
        errors.append("CADDY_ACME_EMAIL: use the real certificate contact address")

    password = require("HELVETIC_LENS_DB_PASSWORD")
    if len(password) < 24 or _placeholder(password) or password == "helvetic_lens":
        errors.append("HELVETIC_LENS_DB_PASSWORD: use at least 24 random non-placeholder characters")
    elif not re.fullmatch(r"[A-Za-z0-9._~-]+", password):
        errors.append("HELVETIC_LENS_DB_PASSWORD: use URL-safe characters")

    credential_key = require("HELVETIC_LENS_CREDENTIAL_KEY")
    if len(credential_key) < 32 or _placeholder(credential_key):
        errors.append("HELVETIC_LENS_CREDENTIAL_KEY: use at least 32 random non-placeholder characters")

    if require("AUTH_EMAIL_MODE") != "smtp":
        errors.append("AUTH_EMAIL_MODE: public registration requires smtp")
    require("AUTH_EMAIL_FROM")
    require("AUTH_SMTP_HOST")
    smtp_user = values.get("AUTH_SMTP_USERNAME", "").strip()
    smtp_password = values.get("AUTH_SMTP_PASSWORD", "").strip()
    if bool(smtp_user) != bool(smtp_password):
        errors.append("AUTH_SMTP_USERNAME/AUTH_SMTP_PASSWORD: set both or neither")
    if smtp_user and (_placeholder(smtp_user) or _placeholder(smtp_password)):
        errors.append("AUTH_SMTP_USERNAME/AUTH_SMTP_PASSWORD: replace placeholder credentials")

    if values.get("APERTUS_PROVIDER", "docker").strip() != "docker":
        errors.append("APERTUS_PROVIDER: the production baseline must default to docker")
    if require("JOB_EXECUTION_MODE") != "celery":
        errors.append("JOB_EXECUTION_MODE: production requires celery")
    if values.get("DEFAULT_LOCALE", "de-CH") not in LOCALES:
        errors.append("DEFAULT_LOCALE: unsupported locale")

    try:
        upload_limit = int(require("MAX_DOCUMENT_BYTES"))
        if not 1024 <= upload_limit <= 20 * 1024 * 1024:
            errors.append("MAX_DOCUMENT_BYTES: must be between 1 KiB and the 20 MiB proxy limit")
    except ValueError:
        errors.append("MAX_DOCUMENT_BYTES: must be an integer")

    backup_dir = require("HELVETIC_LENS_BACKUP_DIR")
    if backup_dir and not PurePosixPath(backup_dir).is_absolute():
        errors.append("HELVETIC_LENS_BACKUP_DIR: must be an absolute separate host path")

    return sorted(set(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    args = parser.parse_args()
    try:
        values = load_env(args.env_file)
        errors = validate(values)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Production configuration is invalid: {exc}") from exc
    if errors:
        print("Production configuration is invalid:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Production configuration is valid ({len(values)} fields checked; values not displayed).")


if __name__ == "__main__":
    main()
