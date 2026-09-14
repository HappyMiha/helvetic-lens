"""Synthetic reviewed rules and calendars; these never authorize production legal dates."""

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_trademark_matching import facts, portfolio
from test_trademark_sources import NOW
from test_trademark_sources import db as _database_fixture
from test_trademark_sources import template as _template_fixture

from helvetic_lens import trademark_deadlines as deadlines
from helvetic_lens.config import DomainError
from helvetic_lens.trademark_contracts import TrademarkPortfolio, fingerprint
from helvetic_lens.trademark_deadline_contracts import DeadlineCalendar, DeadlinePreference, DeadlineRule

db, template = _database_fixture, _template_fixture
PREFERENCE = DeadlinePreference(calendar_key="synthetic-basel", domicile_basis="party")


def review_fields():
    return {"reviewed_at": datetime(2020, 1, 1, tzinfo=UTC), "review_expires_at": datetime(2030, 1, 1, tzinfo=UTC),
        "reviewer_reference": "SYNTHETIC fixture, not a reviewed legal rule",
        "citations": ({"url": "https://example.invalid/synthetic-reference", "sha256": "a" * 64, "section": "Synthetic rule"},)}


def rule(**changes):
    return DeadlineRule(**{**review_fields(), "engine": deadlines.ENGINE, "source_key": "synthetic-ipi",
        "origin": "national_ch", "basis": "swissreg_registration_publication", "publication_category": "New registration",
        "publication_office": "CH", "publication_from": date(2020, 1, 1), "publication_until": date(2030, 1, 1),
        "mapping_reference": "Synthetic source-category mapping, not production approval", **changes})


def calendar(**changes):
    return DeadlineCalendar(**{**review_fields(), "key": PREFERENCE.calendar_key, "name": "Synthetic Basel calendar",
        "jurisdiction": "Synthetic party/representative domicile", "covers_from": date(2020, 1, 1),
        "covers_until": date(2029, 12, 31), "recognized_holidays": (), "coverage_confirmed": True, **changes})


def install(db, *, rule_value=None, calendar_value=None, previous_rule=None, previous_calendar=None):
    with db.session() as session:
        r = deadlines.retain(session, "rule", rule_value or rule())
        c = deadlines.retain(session, "calendar", calendar_value or calendar())
        deadlines.select_current(session, "rule", r, expected_id=previous_rule, now=NOW)
        deadlines.select_current(session, "calendar", c, expected_id=previous_calendar, now=NOW)
        session.commit()
        return r, c


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_calendar_requires_explicit_boolean_review_confirmation(value):
    with pytest.raises(ValidationError):
        calendar(coverage_confirmed=value)


def published(day, *, international=False, **changes):
    return facts(**{"origin": "international_designating_ch" if international else "national_ch",
        "publication_date": day, "publications": ({"identifier": "synthetic-publication-1",
        "office_code": "WO" if international else "CH", "category": "New registration", "publication_date": day},), **changes})


def calculate(db, evidence, *, now=NOW, preference=PREFERENCE, **kwargs):
    with db.session() as session:
        return deadlines.evaluate(session, "synthetic-ipi", evidence, preference, now=now, **kwargs)


@pytest.mark.parametrize("international,expected", [(False, "2022-10-19"), (True, "2022-11-01")])
def test_documented_anchor_examples_require_distinct_reviewed_source_mappings(db, international, expected):
    changes = {"origin": "international_designating_ch", "publication_office": "WO", "basis": "wipo_ch_extension_publication"} if international else {}
    install(db, rule_value=rule(**changes))
    result, binding = calculate(db, published(date(2022, 7, 19), international=international))
    assert result["calculated_review_deadline"] == expected
    assert result["verification_required"] and result["calculation_trace"][-1]["date"] == expected
    assert binding["calculation_hash"] == result["calculation_hash"]
    assert "publication_date" not in binding and "ALMORA" not in str(binding)


@pytest.mark.parametrize("publication,expected", [
    (date(2023, 11, 30), "2024-02-29"), (date(2024, 11, 30), "2025-02-28"),
    (date(2026, 1, 31), "2026-04-30"),
])
def test_calendar_month_arithmetic_preserves_end_of_month_and_leap_years(db, publication, expected):
    install(db)
    result, _ = calculate(db, published(publication))
    assert result["calculated_review_deadline"] == expected


def test_consecutive_recognized_holidays_weekends_and_local_day_counts(db):
    install(db, calendar_value=calendar(recognized_holidays=(date(2026, 9, 11), date(2026, 9, 14))))
    result, first = calculate(db, published(date(2026, 6, 11)))
    assert result["calculated_review_deadline"] == "2026-09-15" and result["days_remaining"] == 2
    skipped = [step["date"] for step in result["calculation_trace"] if step["step"] == "non_working_day"]
    assert skipped == ["2026-09-11", "2026-09-12", "2026-09-13", "2026-09-14"]
    tomorrow, second = calculate(db, published(date(2026, 6, 11)), now=NOW + timedelta(days=1))
    assert tomorrow["days_remaining"] == 1 and first == second


def test_dst_and_midnight_use_zurich_dates_without_a_24_hour_rounding_error(db):
    install(db)
    evidence = published(date(2025, 12, 30))
    before, a = calculate(db, evidence, now=datetime(2026, 3, 28, 23, 30, tzinfo=UTC))
    after, b = calculate(db, evidence, now=datetime(2026, 3, 29, 22, 30, tzinfo=UTC))
    assert before["days_remaining"] == 1 and after["days_remaining"] == 0
    assert after["exclusive_end"] == "2026-03-31T00:00:00+02:00" and a == b
    elapsed, _ = calculate(db, evidence, now=datetime(2026, 3, 30, 22, 0, tzinfo=UTC))
    assert elapsed["days_remaining"] == -1


def test_no_calendar_coverage_means_no_weekend_only_guess(db):
    install(db, calendar_value=calendar(covers_until=date(2026, 9, 13)))
    result, _ = calculate(db, published(date(2026, 6, 13)))
    assert result["state"] == "unavailable" and result["reason"] == "deadline_calendar_coverage_unavailable"
    assert result["calculated_review_deadline"] is result["days_remaining"] is None


@pytest.mark.parametrize("case", ["none", "wrong_office", "multiple", "missing_date", "future"])
def test_ambiguous_or_inapplicable_publication_is_never_replaced_by_registration_date(db, case):
    install(db)
    value = published(date(2026, 8, 12))
    publications = list(value.publications)
    if case == "none":
        publications = []
    if case == "wrong_office":
        publications = [publications[0].model_copy(update={"office_code": "WO"})]
    if case == "multiple":
        publications.append(publications[0].model_copy(update={"identifier": "another-publication"}))
    if case == "missing_date":
        publications = [publications[0].model_copy(update={"publication_date": None})]
    if case == "future":
        publications = [publications[0].model_copy(update={"publication_date": date(2027, 1, 1)})]
    result, _ = calculate(db, value.model_copy(update={"publications": tuple(publications)}))
    assert result["state"] == "unavailable" and result["calculated_review_deadline"] is None


def test_rule_and_calendar_revocation_invalidate_historical_calculation(db):
    r, c = install(db)
    value = published(date(2026, 8, 12))
    _, binding = calculate(db, value)
    with db.session() as session:
        deadlines.revoke(session, "calendar", c, now=NOW)
        session.commit()
    result, _ = calculate(db, value, binding=binding, historical_at=NOW)
    assert result["state"] == "unavailable" and result["days_remaining"] is None
    assert result["calculated_review_deadline"] is None
    with db.session() as session:
        with pytest.raises(DomainError):
            deadlines.select_current(session, "rule", r, expected_id="unknown", now=NOW)


def test_changed_rule_version_changes_binding_but_raw_transport_hash_does_not(db):
    r, c = install(db)
    value = published(date(2026, 8, 12))
    _, first = calculate(db, value)
    _, transport = calculate(db, value.model_copy(update={"source_sha256": "b" * 64, "source_document_sha256": "c" * 64}))
    assert first == transport
    install(db, rule_value=rule(mapping_reference="Synthetic corrected mapping review"), previous_rule=r, previous_calendar=c)
    _, second = calculate(db, value)
    assert first["calculation_hash"] != second["calculation_hash"]


def test_legacy_portfolio_serialization_and_fingerprints_do_not_change():
    original = portfolio().model_dump(mode="json")
    assert "deadline_context" not in original
    parsed = TrademarkPortfolio.model_validate({**original, "deadline_context": None})
    assert parsed.model_dump(mode="json") == original and parsed.fingerprint() == fingerprint(original)
    changed = TrademarkPortfolio.model_validate({**original, "deadline_context": PREFERENCE.model_dump(mode="json")})
    assert changed.fingerprint() != parsed.fingerprint()


def test_unreviewed_calendar_and_mismatched_origin_rule_are_rejected():
    with pytest.raises(ValidationError):
        calendar(coverage_confirmed=False)
    with pytest.raises(ValidationError):
        rule(origin="international_designating_ch")
