"""Auditable Swiss opposition date arithmetic over explicitly reviewed inputs.

No production rule/calendar is installed here. Registry mutations are internal;
all readers take a shared registry lock before calibration and source locks.
"""

from calendar import monthrange
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select

from .config import DomainError
from .trademark_contracts import fingerprint
from .trademark_deadline_contracts import ENGINE, DeadlineCalendar, DeadlineRule
from .trademark_deadline_models import (
    TrademarkDeadlineCalendar,
    TrademarkDeadlineCalendarSelection,
    TrademarkDeadlineRegistry,
    TrademarkDeadlineRule,
    TrademarkDeadlineRuleSelection,
)
from .trademark_sources import _clock

ZONE = ZoneInfo("Europe/Zurich")
MODELS = {"rule": (TrademarkDeadlineRule, DeadlineRule), "calendar": (TrademarkDeadlineCalendar, DeadlineCalendar)}


def _fail(code):
    raise DomainError("The reviewed deadline evidence is unavailable.", 409, code)


def guard(session, *, write=False):
    row = session.scalar(select(TrademarkDeadlineRegistry).where(TrademarkDeadlineRegistry.id == "main")
        .with_for_update(read=not write).execution_options(populate_existing=True))
    if row is None:
        _fail("deadline_registry_unavailable")
    return row


def retain(session, kind, configuration):
    registry = guard(session, write=True)
    model, contract = MODELS[kind]
    value = contract.model_validate(configuration)
    payload = value.model_dump(mode="json")
    identifier = fingerprint(payload)
    if session.get(model, identifier) is None:
        session.add(model(id=identifier, configuration=payload))
        registry.revision += 1
        session.flush()
    return identifier


def _read(session, kind, identifier, *, now, reviewed_at=None):
    model, contract = MODELS[kind]
    row = session.get(model, identifier, populate_existing=True)
    if row is None or row.revoked_at is not None:
        _fail("deadline_" + kind + "_unavailable")
    try:
        value = contract.model_validate(row.configuration)
    except ValidationError:
        _fail("deadline_" + kind + "_invalid")
    if fingerprint(value.model_dump(mode="json")) != identifier:
        _fail("deadline_" + kind + "_invalid")
    instant = _clock(reviewed_at or now)
    if not value.reviewed_at <= instant < value.review_expires_at:
        _fail("deadline_" + kind + "_unavailable")
    return value


def select_current(session, kind, identifier, *, expected_id, now):
    now, registry = _clock(now), guard(session, write=True)
    value = _read(session, kind, identifier, now=now)
    if kind == "rule":
        model, key, field = TrademarkDeadlineRuleSelection, (value.source_key, value.origin), "rule_id"
        attributes = {"source_key": value.source_key, "origin": value.origin}
    else:
        model, key, field = TrademarkDeadlineCalendarSelection, value.key, "calendar_id"
        attributes = {"key": value.key}
    row = session.get(model, key, populate_existing=True)
    if (getattr(row, field) if row else None) != expected_id:
        _fail("deadline_registry_conflict")
    if row:
        setattr(row, field, identifier)
    else:
        session.add(model(**attributes, **{field: identifier}))
    registry.revision += 1
    session.flush()


def revoke(session, kind, identifier, *, now):
    registry = guard(session, write=True)
    row = session.get(MODELS[kind][0], identifier, populate_existing=True)
    if row is None:
        _fail("deadline_" + kind + "_unavailable")
    row.revoked_at = row.revoked_at or _clock(now)
    registry.revision += 1
    session.flush()


def calendars(session, *, now):
    guard(session)
    rows = list(session.scalars(select(TrademarkDeadlineCalendarSelection)
        .order_by(TrademarkDeadlineCalendarSelection.key).limit(101)))
    if len(rows) > 100:
        _fail("deadline_calendar_capacity")
    result = []
    for row in rows:
        try:
            value = _read(session, "calendar", row.calendar_id, now=now)
            result.append({"key": value.key, "name": value.name, "jurisdiction": value.jurisdiction,
                "version": row.calendar_id, "covers_from": value.covers_from.isoformat(), "covers_until": value.covers_until.isoformat()})
        except DomainError:
            continue
    return result


def _months(day, amount):
    year, month = divmod(day.year * 12 + day.month - 1 + amount, 12)
    return day.replace(year=year, month=month + 1, day=min(day.day, monthrange(year, month + 1)[1]))


def _empty(facts, now):
    return {"state": "unavailable", "reason": None,
        "official_publication_date": facts.publication_date.isoformat() if facts.publication_date else None,
        "applicable_deadline_rule": None, "calendar": None, "calculated_review_deadline": None,
        "exclusive_end": None, "days_remaining": None, "as_of_date": now.astimezone(ZONE).date().isoformat(),
        "timezone": "Europe/Zurich", "verification_required": True, "calculation_trace": [],
        "publication_evidence": None}


def evaluate(session, source_key, facts, preference, *, now, binding=None, historical_at=None):
    """Return current visible context and a licensed-content-free audit binding.

    A historical binding pins the exact reviewed inputs. Revoked inputs are
    unavailable even in history; source permission checks remain with the caller.
    """
    now = _clock(now)
    guard(session)
    result, rule_id, calendar_id = _empty(facts, now), None, None
    if preference is None:
        result["reason"] = "deadline_context_required"
        return result, None
    basis = None
    try:
        if binding is None:
            selected = session.get(TrademarkDeadlineRuleSelection, (source_key, facts.origin), populate_existing=True)
            calendar = session.get(TrademarkDeadlineCalendarSelection, preference.calendar_key, populate_existing=True)
            rule_id, calendar_id = (selected.rule_id if selected else None), (calendar.calendar_id if calendar else None)
        else:
            if binding.get("engine") != ENGINE:
                _fail("deadline_binding_unavailable")
            rule_id, calendar_id = binding.get("rule_id"), binding.get("calendar_id")
        if not rule_id:
            _fail("deadline_rule_unavailable")
        rule = _read(session, "rule", rule_id, now=now, reviewed_at=historical_at)
        if rule.source_key != source_key or rule.origin != facts.origin:
            _fail("deadline_rule_not_applicable")
        result["applicable_deadline_rule"] = {"id": rule_id, "engine": rule.engine, "basis": rule.basis,
            "mapping_reference": rule.mapping_reference, "citations": [c.model_dump(mode="json") for c in rule.citations]}
        matches = [p for p in facts.publications if p.category == rule.publication_category and p.office_code == rule.publication_office]
        if len(matches) != 1 or matches[0].publication_date is None:
            _fail("deadline_publication_unavailable")
        publication = matches[0]
        day = publication.publication_date
        basis = publication.model_dump(mode="json")
        if not rule.publication_from <= day < rule.publication_until or day > now.astimezone(ZONE).date():
            _fail("deadline_rule_not_applicable")
        result["official_publication_date"] = day.isoformat()
        result["publication_evidence"] = {"identifier": publication.identifier, "date": day.isoformat(),
            "category": publication.category, "office_code": publication.office_code,
            "source_key": source_key, "source_sha256": facts.source_sha256,
            "source_document_sha256": facts.source_document_sha256}
        if not calendar_id:
            _fail("deadline_calendar_unavailable")
        calendar = _read(session, "calendar", calendar_id, now=now, reviewed_at=historical_at)
        if calendar.key != preference.calendar_key:
            _fail("deadline_calendar_not_applicable")
        result["calendar"] = {"id": calendar_id, "key": calendar.key, "name": calendar.name,
            "jurisdiction": calendar.jurisdiction, "domicile_basis": preference.domicile_basis,
            "citations": [c.model_dump(mode="json") for c in calendar.citations]}
        anchor = day if rule.basis == "swissreg_registration_publication" else _months(day.replace(day=1), 1)
        due = _months(anchor, 3)
        trace = [{"step": "publication", "date": day.isoformat()},
            {"step": rule.basis, "date": anchor.isoformat()},
            {"step": "calendar_months", "months": 3, "date": due.isoformat()}]
        holidays = set(calendar.recognized_holidays)
        for _ in range(32):
            if not calendar.covers_from <= due <= calendar.covers_until:
                _fail("deadline_calendar_coverage_unavailable")
            if due.weekday() < 5 and due not in holidays:
                break
            trace.append({"step": "non_working_day", "date": due.isoformat(),
                "reason": "recognized_holiday" if due in holidays else "weekend"})
            due += timedelta(days=1)
        else:
            _fail("deadline_calendar_coverage_unavailable")
        end = datetime.combine(due + timedelta(days=1), time.min, tzinfo=ZONE)
        result.update(state="available", reason=None, calculated_review_deadline=due.isoformat(),
            exclusive_end=end.isoformat(), days_remaining=(due - now.astimezone(ZONE).date()).days,
            calculation_trace=trace + [{"step": "deadline", "date": due.isoformat(), "exclusive_end": end.isoformat()}])
    except DomainError as error:
        result["reason"] = error.code
    except (ValueError, OverflowError):
        result["reason"] = "deadline_date_out_of_range"
    stable = {"engine": ENGINE, "state": result["state"], "reason": result["reason"],
        "rule_id": rule_id, "calendar_id": calendar_id, "preference": preference.model_dump(mode="json"),
        "basis": basis, "deadline": result["calculated_review_deadline"], "trace": result["calculation_trace"]}
    retained = {"engine": ENGINE, "rule_id": rule_id, "calendar_id": calendar_id, "calculation_hash": fingerprint(stable)}
    result["calculation_hash"] = retained["calculation_hash"]
    if binding is not None and binding.get("calculation_hash") != retained["calculation_hash"]:
        result.update(state="unavailable", reason="deadline_historical_calculation_unavailable",
            calculated_review_deadline=None, exclusive_end=None, days_remaining=None, calculation_trace=[])
    return result, retained


def evaluation_hash(name_hash, binding):
    return fingerprint({"name_evaluation": name_hash, "deadline": binding}) if binding else name_hash
