"""Bounded extractive questions over authorized native records, without inference.

Readers, not client prose or an assistant transcript, establish the evidence.
Only source-bearing fields are extracted; personal notes and work audit are not.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlencode

from sqlalchemy import select

from .config import DomainError
from .monitoring_subjects import _actor

Domain = Literal["pollen", "river", "air", "warnings", "commute", "traffic", "tenders", "ip", "auctions"]
DOMAINS = tuple(Domain.__args__)
VERSION = "monitoring-evidence-extract.v1"
LOCALES = {"en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"}
MAX_BYTES = 256_000
MAX_EXTRACTS = 1000
CONTEXT_FIELDS = ("station_id", "metric", "allergen", "period", "unit", "currency", "language", "valid_at", "observed_at")


@dataclass(frozen=True)
class Record:
    domain: str
    monitor_id: str
    item_id: str
    sequence: int | None = None


def fail(code="monitoring_evidence_unavailable", status=409):
    raise DomainError("Open this record's source evidence again.", status, code)


def _numeric(session, user_id, record):
    if record.domain == "air":
        from .air_models import AirChange as Change
        from .air_runtime import change_view, owned
    else:
        from .river_models import RiverChange as Change
        from .river_runtime import change_view, owned
    monitor = owned(session, user_id, record.monitor_id)
    row = session.scalar(select(Change).where(Change.id == record.item_id,
        Change.monitor_id == monitor.id, Change.organization_id == monitor.organization_id))
    if row is None:
        fail("monitoring_evidence_not_found", 404)
    newer = session.scalar(select(Change.id).where(Change.monitor_id == monitor.id,
        Change.development_id == row.development_id, Change.sequence > row.sequence).limit(1))
    return {"event": change_view(row), "current_configuration": row.revision == monitor.revision,
        "newer_available": newer is not None, "configuration_revision": monitor.revision}


def native(session, settings, user_id, record, *, now):
    """Read one record through its existing scope/rights/retention boundary."""
    organization = _actor(session, user_id)
    if record.domain not in DOMAINS:
        fail("monitoring_evidence_domain_invalid", 422)
    flags = {"river": "river_watch_enabled", "air": "air_watch_enabled",
        "warnings": "hazard_watch_enabled", "commute": "commute_watch_enabled",
        "traffic": "road_watch_enabled", "tenders": "tender_watch_enabled",
        "ip": "trademark_watch_enabled", "auctions": "auction_watch_enabled"}
    if record.domain in flags and not getattr(settings, flags[record.domain]):
        fail("monitoring_evidence_not_found", 404)
    if record.sequence is not None and (type(record.sequence) is not int or not 1 <= record.sequence <= 10000
            or record.domain not in {"warnings", "commute", "traffic"}):
        fail("monitoring_evidence_sequence_invalid", 422)
    if record.domain == "pollen":
        from . import monitoring_runtime as runtime
        runtime._require_live(settings, organization)
        result = runtime.exact_entry(session, settings=settings, user_id=user_id,
            subject_id=record.monitor_id, entry_id=record.item_id, now=now)
        if result["entry"].get("source_withheld"):
            fail()
        return result, {key: result["entry"].get(key) for key in ("current", "previous", "baseline", "provenance")}
    if record.domain in {"air", "river"}:
        result = _numeric(session, user_id, record)
        return result, {"evidence": result["event"]["evidence"]}
    if record.domain == "warnings":
        from .hazard_boundary_store import BoundaryStore
        from .hazard_events import read_event
        result = read_event(session, user_id, record.monitor_id, record.item_id,
            store=BoundaryStore(settings.storage_path), now=now, revision=record.sequence)
        if result["state"] == "unavailable":
            fail()
        return result, {"source": result["source"]}
    if record.domain in {"commute", "traffic"}:
        if record.domain == "commute":
            from .commute_today import detail
        else:
            from .road_today import detail
        result = detail(session, user_id, record.item_id, monitor_id=record.monitor_id,
            sequence=record.sequence, now=now)
        snapshot = result["snapshot"]
        if snapshot.get("availability") == "unavailable" or snapshot.get("state") == "unavailable":
            fail()
        return result, {"snapshot": snapshot}
    from .business_item_work import _target, _view, binding
    monitor, row = _target(session, user_id, record.domain, record.monitor_id, record.item_id)
    result = _view(session, user_id, record.domain, monitor, row, now)
    if result["state"] != "available":
        fail()
    result = {**result, "binding": binding(session, record.domain, row), "configuration_revision": monitor.revision}
    result["current_configuration"] = result["binding"]["profile_revision"] == monitor.revision
    keys = ("material", "changes") if record.domain == "tenders" else ("facts", "attribution")
    return result, {key: result.get(key) for key in keys}


def _json(value):
    # Native contracts may contain datetimes in metadata; their ISO spelling is
    # stable. Source extracts themselves below accept JSON primitives only.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _tokens(value):
    text = unicodedata.normalize("NFKC", value).casefold()
    return set(re.findall(r"[^\W_]+", text, flags=re.UNICODE))


def extracts(source):
    """Keep exact scalar spelling and pointer; never execute source instructions."""
    if len(_json(source).encode("utf-8")) > MAX_BYTES:
        fail("monitoring_evidence_too_large", 413)
    result = []

    def visit(value, path, depth, context):
        if depth > 16 or len(result) >= MAX_EXTRACTS:
            fail("monitoring_evidence_too_large", 413)
        if isinstance(value, dict):
            descriptors = {**(value.get("series") if isinstance(value.get("series"), dict) else {}), **value}
            context = {**context, **{key: str(descriptors[key]) for key in CONTEXT_FIELDS
                if isinstance(descriptors.get(key), (str, int, float)) and len(str(descriptors[key])) <= 240}}
            for key, child in value.items():
                # Identity/proof links remain in the binding, not in search results.
                if key == "id" or key.endswith(("_id", "_hash", "_sha256")) or key in {"proof", "fingerprint", "raw", "artifact_hashes"}:
                    continue
                visit(child, (*path, key), depth + 1, context)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)), depth + 1, context)
        elif isinstance(value, (str, int, float, bool, date, datetime)) and value != "":
            quote = value if isinstance(value, str) else value.isoformat() if isinstance(value, (date, datetime)) else _json(value)
            if len(quote) > 16000:
                fail("monitoring_evidence_too_large", 413)
            pointer = "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)
            result.append({"pointer": pointer, "quote": quote, "context": context})

    visit(source, (), 0, {})
    return result


def _binding(record, view, locale):
    return hashlib.sha256(_json({"version": VERSION, "locale": locale,
        "record": record.__dict__, "reader": view}).encode("utf-8")).hexdigest()


def reference(session, settings, user_id, record, *, now, locale, expected_binding):
    """A citation rechecks the same native reader before exposing normalized fields.

    These are existing display fields, never raw artifacts or a new export grant.
    A changed binding cannot silently redirect a citation to different evidence.
    """
    view, source = native(session, settings, user_id, record, now=now)
    if locale not in LOCALES or _binding(record, view, locale) != expected_binding:
        fail("monitoring_evidence_changed")
    extracts(source)  # Keep the same bounded display contract as the question.
    return {"record": record.__dict__, "binding": expected_binding, "source": source}


def answer(session, settings, user_id, record, *, now, locale, question="", expected_binding=None):
    if locale not in LOCALES or not isinstance(question, str) or len(question) > 2000:
        fail("monitoring_evidence_question_invalid", 422)
    view, source = native(session, settings, user_id, record, now=now)
    # Full reader output binds review/configuration/current-head changes as well
    # as source facts. Responses are ephemeral; no question or answer is stored.
    fingerprint = _binding(record, view, locale)
    if expected_binding is not None and expected_binding != fingerprint:
        fail("monitoring_evidence_changed")
    rows = extracts(source)
    tokens = _tokens(question)
    scored = [(len(tokens & _tokens(item["quote"] + " " + item["pointer"] + " " + " ".join(item["context"].values()))), index, item)
        for index, item in enumerate(rows)]
    selected = [item for score, _, item in sorted(scored, key=lambda value: (-value[0], value[1]))
        if score or not question.strip()]
    return {"mode": "extractive", "extractor_revision": VERSION, "binding": fingerprint,
        "reference_url": "/api/monitoring-centre/evidence/reference?" + urlencode({
            **{key: value for key, value in record.__dict__.items() if value is not None},
            "locale": locale, "expected_binding": fingerprint}),
        "locale": locale, "record": record.__dict__, "has_matches": bool(selected),
        "extracts": selected[:12], "more_matches": len(selected) > 12,
        "newer_available": bool(view.get("newer_available")),
        "current_configuration": view.get("current_configuration"),
        "checked_at": now.isoformat(), "ai_calls": 0, "mutations": 0}
