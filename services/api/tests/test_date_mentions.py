import copy

import pytest
from conftest import LAW_URL, add_law, import_old, policy

from helvetic_lens.analysis import ImportantDateReport, answer_from_impact_report
from helvetic_lens.date_mentions import scan_date_mentions
from helvetic_lens.models import Analysis


def evidence(text, *, side="new", passage="p1"):
    return {
        "text": text,
        "side": side,
        "version_id": side,
        "passage_id": passage,
        "change_id": "c1",
        "page": 2,
    }


LANGUAGES = [
    ("de-CH", "1. Januar 2027", "30 Tagen"),
    ("fr-CH", "1er janvier 2027", "30 jours ouvrables"),
    ("it-CH", "1 gennaio 2027", "30 giorni lavorativi"),
    ("rm-CH", "1. da schaner 2027", "30 dis"),
    ("en-CH", "January 1, 2027", "30 business days"),
]


@pytest.mark.parametrize("locale,date,period", LANGUAGES)
def test_literal_dates_and_periods_keep_exact_provenance_without_calculating(locale, date, period):
    row = evidence(f"Art. 9 — {date}. {period}.")
    entries, review = scan_date_mentions([row], locale)
    assert [entry["mention"] for entry in entries] == [date, period]
    assert [entry["kind"] for entry in entries] == ["other", "relative_period"]
    for entry in entries:
        ImportantDateReport.model_validate(entry)
        assert entry["date"] is None and entry["status"] == "uncertain"
        assert entry["version_side"] == "new" and entry["change_id"] == "c1"
        citation = entry["citations"][0]
        assert entry["mention"] in citation["quote"] in row["text"]
        assert citation["page"] == 2 and citation["url"] == "/evidence/new?passage=p1"
    assert review["legal_meaning_status"] == "not_reviewed"
    assert review["detected_mentions"] == review["displayed_mentions"] == 2


@pytest.mark.parametrize("locale,date,period", LANGUAGES)
def test_no_match_never_establishes_no_deadlines(locale, date, period):
    entries, review = scan_date_mentions([evidence("Art. 9. See Annex B.")], locale)
    assert entries == []
    assert review["legal_meaning_status"] == "not_reviewed"
    assert review["scanned_passages"] == 1 and review["detected_mentions"] == 0


@pytest.mark.parametrize("mention", ["01/02/2027", "31.02.2027", "2027-02-31", "30–60 days"])
def test_ambiguous_invalid_and_relative_dates_remain_literal(mention):
    entries, _ = scan_date_mentions([evidence(f"Example: {mention}.")], "en-CH")
    assert len(entries) == 1
    assert entries[0]["mention"] == mention
    assert entries[0]["date"] is None and entries[0]["status"] == "uncertain"


@pytest.mark.parametrize("prefix", ["Proposal only:", "Repealed provision:", "Except for small firms:"])
def test_context_does_not_become_an_enacted_or_applicable_deadline(prefix):
    text = f"{prefix} 1 January 2027. The condition must be checked."
    entries, review = scan_date_mentions([evidence(text)], "en-CH")
    assert entries[0]["citations"][0]["quote"] == text
    assert entries[0]["kind"] == "other" and entries[0]["status"] != "found"
    assert review["legal_meaning_status"] == "not_reviewed"


def test_saved_full_passages_not_model_preview_or_model_prose_supply_dates():
    row = evidence("Introduction. " * 200 + "On 1 January 2027 the rule may apply.")
    row["_model_text"] = "Model preview: 1 January 2099."
    entries, _ = scan_date_mentions([row], "en-CH")
    assert [entry["mention"] for entry in entries] == ["1 January 2027"]
    assert entries[0]["citations"][0]["quote"] in row["text"]
    assert len(entries[0]["citations"][0]["quote"]) < 300


def test_identical_mentions_preserve_version_sides_and_distinct_occurrences():
    rows = [
        evidence("1 January 2027. Exception: 1 January 2027.", side="old"),
        evidence("1 January 2027.", side="new"),
    ]
    entries, review = scan_date_mentions([*rows, rows[0]], "en-CH")
    assert [entry["version_side"] for entry in entries] == ["old", "old", "new"]
    assert review["scanned_passages"] == 2 and review["detected_mentions"] == 3


def test_display_limit_does_not_silently_claim_complete_date_coverage():
    rows = [evidence(f"{day} January 2027.", passage=f"p{day}") for day in range(1, 13)]
    entries, review = scan_date_mentions(rows, "en-CH")
    assert len(entries) == review["displayed_mentions"] == 8
    assert review["detected_mentions"] == review["scanned_passages"] == 12
    assert review["display_limited"] is True
    assert review["scope"] == "selected_material_evidence"


@pytest.mark.parametrize("provider", ["custom", "docker"])
def test_report_dates_cached_and_historical_values_remain_immutable(harness, provider):
    client, fetcher, service, model = harness
    service.settings.apertus_provider = provider
    service.settings.apertus_base_url = "http://127.0.0.1:12435/v1"
    model.settings = service.settings
    fetcher.values[LAW_URL] = policy(60, "<p>Art. 9 Proposed start: 1 January 2027.</p>")
    law = add_law(client)
    old = import_old(client, law["id"], policy(30, "<p>Art. 9 Proposed start: 1 January 2026.</p>"))[
        "version"
    ]
    comparison = client.post(
        "/api/comparisons",
        json={
            "old_version_id": old["id"],
            "new_version_id": law["current_version_id"],
        },
    ).json()
    route = f"/api/comparisons/{comparison['id']}"
    first = client.post(route + "/analyse").json()
    assert first["status"] == "succeeded", first
    report = first["result"]
    assert report["schema_version"] == "impact-report-v4"
    assert {entry["mention"] for entry in report["important_dates"]} >= {
        "30 days",
        "60 days",
        "1 January 2026",
        "1 January 2027",
    }
    assert report["date_review"]["legal_meaning_status"] == "not_reviewed"
    for entry in report["important_dates"]:
        assert entry["status"] == "uncertain" and entry["date"] is None
        citation = entry["citations"][0]
        version = client.get(f"/api/versions/{citation['version_id']}").json()
        passage = next(p for p in version["passages"] if p["id"] == citation["passage_id"])
        assert entry["mention"] in citation["quote"] in passage["text"]
    calls = len(model.calls)
    assert calls <= 5
    cached = client.post(route + "/analyse").json()
    assert cached["cached"] and cached["result"] == report and len(model.calls) == calls
    history = client.get(route + "/ai-history").json()["items"]
    assert history[0]["result"]["date_review"] == report["date_review"]

    # Previous v3 date claims must not be repaired invisibly on read or reused.
    legacy = copy.deepcopy(report)
    legacy["schema_version"] = "impact-report-v3"
    del legacy["date_review"]
    legacy["important_dates"] = [
        {
            "kind": "deadline",
            "label": "Deadline",
            "date": None,
            "status": "not_found",
            "evidence_grade": "needs_review",
            "citations": [],
        }
    ]
    with service.db.session() as session:
        stored = session.get(Analysis, first["id"])
        stored.result = legacy
        stored.cache_key = "previous-schema-cache-key"
        session.commit()
    visible = client.get(route).json()["analysis"]
    assert visible["stale"] and visible["result"] == legacy
    assert answer_from_impact_report("actions", "en-CH", {"result": legacy}) is None
    replacement = client.post(route + "/analyse").json()
    assert replacement["id"] != first["id"]
    assert replacement["result"]["schema_version"] == "impact-report-v4"
    with service.db.session() as session:
        assert session.get(Analysis, first["id"]).result == legacy
