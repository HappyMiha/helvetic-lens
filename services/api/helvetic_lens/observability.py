"""Bounded request metrics and safe correlation context for operational diagnostics."""

from __future__ import annotations

import math
import re
import threading
from collections import Counter, deque
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_CORRELATION_KEYS = frozenset(
    {
        "request_id",
        "organization_id",
        "job_id",
        "connector_run_id",
        "document_id",
        "event_id",
        "comparison_id",
        "analysis_id",
        "ask_record_id",
        "target_type",
        "target_id",
    }
)
_correlation: ContextVar[dict[str, str]] = ContextVar("helvetic_lens_correlation", default={})
_uuid_segment = re.compile(
    r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _safe_values(values: dict[str, object]) -> dict[str, str]:
    return {
        key: str(value)[:200]
        for key, value in values.items()
        if key in _CORRELATION_KEYS and value is not None and str(value).strip()
    }


def current_correlation() -> dict[str, str]:
    """Return a copy so callers cannot mutate another request's context."""

    return dict(_correlation.get())


def enrich_correlation(**values: object) -> dict[str, str]:
    """Add identifiers discovered during the current bounded request or job."""

    merged = {**current_correlation(), **_safe_values(values)}
    _correlation.set(merged)
    return dict(merged)


@contextmanager
def correlation_context(**values: object) -> Iterator[dict[str, str]]:
    merged = {**current_correlation(), **_safe_values(values)}
    token = _correlation.set(merged)
    try:
        yield merged
    finally:
        _correlation.reset(token)


def normalized_route(path: str) -> str:
    """Remove dynamic identifiers before using a path as a metric label."""

    parts = []
    for part in path.split("/"):
        if part.isdigit() or _uuid_segment.fullmatch(part):
            parts.append("{id}")
        else:
            parts.append(part[:80])
    return "/".join(parts)[:300] or "/"


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


@dataclass(frozen=True)
class ApiObservation:
    method: str
    route: str
    status: int
    duration_ms: int


class ApiMetrics:
    """Process-local rolling API metrics with bounded memory and labels."""

    def __init__(self, max_samples: int = 2_000):
        self._samples: deque[ApiObservation] = deque(maxlen=max(100, max_samples))
        self._lock = threading.Lock()
        self._in_flight = 0

    def started(self) -> None:
        with self._lock:
            self._in_flight += 1

    def finished(self, method: str, route: str, status: int, duration_ms: int) -> None:
        observation = ApiObservation(
            method=method.upper()[:10],
            route=normalized_route(route),
            status=max(100, min(599, status)),
            duration_ms=max(0, duration_ms),
        )
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._samples.append(observation)

    def snapshot(self) -> dict:
        with self._lock:
            samples = list(self._samples)
            in_flight = self._in_flight
        durations = [item.duration_ms for item in samples]
        server_errors = sum(item.status >= 500 for item in samples)
        status_classes = Counter(f"{item.status // 100}xx" for item in samples)
        routes = Counter(f"{item.method} {item.route}" for item in samples)
        return {
            "window_samples": len(samples),
            "in_flight": in_flight,
            "server_errors": server_errors,
            "server_error_rate": round(server_errors / len(samples), 4) if samples else 0.0,
            "latency_ms": {
                "p50": _percentile(durations, 0.50),
                "p95": _percentile(durations, 0.95),
                "max": max(durations) if durations else None,
            },
            "status_classes": dict(sorted(status_classes.items())),
            "top_routes": [
                {"route": route, "requests": count}
                for route, count in routes.most_common(12)
            ],
        }
