import hashlib
import json
import logging
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import IntegrationLog
from .observability import current_correlation

logger = logging.getLogger(__name__)
MAX_LOG_BODY_CHARS = 160_000
REDACTED = "[REDACTED]"


def _sensitive_key(value: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return normalized in {
        "authorization",
        "proxy_authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "secret",
        "password",
        "cookie",
        "set_cookie",
    } or normalized.endswith(("_api_key", "_access_token", "_refresh_token", "_password", "_secret"))


def _collect_secrets(value: Any, secrets: set[str], key: object = "") -> None:
    if _sensitive_key(key) and isinstance(value, str):
        candidate = value.strip()
        if candidate:
            secrets.add(candidate)
            if candidate.lower().startswith("bearer "):
                secrets.add(candidate[7:].strip())
        return
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            _collect_secrets(child, secrets, child_key)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_secrets(child, secrets)


def _sanitize_string(value: str, secrets: set[str]) -> str:
    cleaned = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer " + REDACTED, value)
    for secret in sorted((item for item in secrets if len(item) >= 4), key=len, reverse=True):
        cleaned = cleaned.replace(secret, REDACTED)
    return cleaned


def _sanitize(value: Any, secrets: set[str], key: object = "") -> Any:
    if _sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(child_key): _sanitize(child, secrets, child_key) for child_key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(child, secrets) for child in value]
    if isinstance(value, bytes):
        return binary_snapshot(value, "application/octet-stream")
    if isinstance(value, str):
        return _sanitize_string(value, secrets)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize_string(str(value), secrets)


def _safe_url(value: str, secrets: set[str]) -> str:
    try:
        parsed = urlsplit(value)
        query = urlencode(
            [
                (key, REDACTED if _sensitive_key(key) else _sanitize_string(item, secrets))
                for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        )
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
    except ValueError:
        return _sanitize_string(value, secrets)


def _bounded(value: Any, secrets: set[str]) -> tuple[Any, int]:
    if value is None:
        return None, 0
    cleaned = _sanitize(value, secrets)
    serialized = json.dumps(cleaned, ensure_ascii=False, default=str)
    size = len(serialized.encode("utf-8"))
    if len(serialized) <= MAX_LOG_BODY_CHARS:
        return cleaned, size
    return {
        "truncated": True,
        "original_characters": len(serialized),
        "preview": serialized[:MAX_LOG_BODY_CHARS],
    }, size


def binary_snapshot(body: bytes, content_type: str) -> dict:
    return {
        "binary": True,
        "content_type": content_type,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def response_snapshot(body: bytes, content_type: str) -> dict | list | str | None:
    if not body:
        return None
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime == "application/json" or mime.endswith("+json"):
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return body.decode("utf-8", errors="replace")
    if mime.startswith("text/") or mime in {"application/xml", "application/xhtml+xml"}:
        return body.decode("utf-8", errors="replace")
    return binary_snapshot(body, content_type or "application/octet-stream")


class IntegrationLogger:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def record(
        self,
        *,
        provider: str,
        operation: str,
        method: str,
        url: str,
        status: str,
        duration_ms: int,
        request_headers: Mapping | None = None,
        request_body: Any = None,
        response_status: int | None = None,
        response_headers: Mapping | None = None,
        response_body: Any = None,
        error: str | None = None,
    ) -> None:
        try:
            request_headers = dict(request_headers or {})
            response_headers = dict(response_headers or {})
            secrets: set[str] = set()
            _collect_secrets(request_headers, secrets)
            _collect_secrets(request_body, secrets)
            safe_request, request_size = _bounded(request_body, secrets)
            safe_response, response_size = _bounded(response_body, secrets)
            correlation = current_correlation()
            record = IntegrationLog(
                request_id=correlation.get("request_id"),
                correlation=correlation,
                provider=provider[:40],
                operation=operation[:60],
                method=method.upper()[:10],
                url=_safe_url(url, secrets),
                status=status[:20],
                response_status=response_status,
                duration_ms=max(0, round(duration_ms)),
                request_headers=_sanitize(request_headers, secrets),
                request_body=safe_request,
                response_headers=_sanitize(response_headers, secrets),
                response_body=safe_response,
                request_size=request_size,
                response_size=response_size,
                error=_sanitize_string(error, secrets) if error else None,
            )
            with self.session_factory() as session:
                session.add(record)
                session.commit()
        except Exception:
            # Diagnostics must never make monitoring or model requests fail.
            logger.exception("Could not persist an integration log")
