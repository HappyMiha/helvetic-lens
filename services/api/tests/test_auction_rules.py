from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from helvetic_lens.auction_contracts import AuctionFacts, AuctionProfile
from helvetic_lens.auction_rules import assessment, changes, ending_soon

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)


def profile(**updates):
    return AuctionProfile.model_validate({"name": "Vehicle interests", "categories": ["vehicles"],
        "maximum_price_chf_cents": 1200000, **updates})


def price(amount=850000, kind="current_bid", currency="CHF"):
    return {"kind": kind, "currency": currency, "amount_minor": amount, "locator": "auction.currentBid"}


def facts(**updates):
    return AuctionFacts.model_validate({"source_key": "fixture-ti", "canton": "TI", "auction_id": "auction-12",
        "lot_id": "lot-2", "authority": "Synthetic official office", "title": "BMW commercial vehicle",
        "description": "A used commercial vehicle", "brand": "BMW", "category": "vehicles",
        "asset_location": "Lugano", "prices": [price()], "bid_count": 3, "status": "open",
        "ends_at": NOW + timedelta(hours=20), "observed_at": NOW,
        "source_url": "https://auction.example.invalid/auction/12", "raw_sha256": "a" * 64, **updates})


def test_price_threshold_crossing_is_one_event_and_further_bids_are_quiet():
    p = profile()
    below, crossing, above = facts(), facts(prices=[price(1270000)]), facts(prices=[price(1350000)])
    event, = changes(p, below, crossing)
    assert event["code"] == "price_above_limit" and event["notify"]
    event, = changes(p, crossing, above)
    assert event["code"] == "price_changed" and not event["notify"]
    assert assessment(p, crossing)["status"] == "excluded"


def test_price_types_never_substitute_for_the_selected_budget_basis():
    f = facts(prices=[price(10000, "starting_price"), price(900000, "estimate")], bid_count=0)
    assert assessment(profile(), f)["status"] == "unknown"
    assert assessment(profile(budget_price_kind="estimate"), f)["status"] == "match"
    assert assessment(profile(budget_price_kind="minimum_price"), f)["status"] == "unknown"
    with pytest.raises(ValidationError):
        facts(bid_count=0)


@pytest.mark.parametrize("value", [-1, True, 8.5, "850000", 10**16])
def test_budget_uses_exact_nonnegative_integer_minor_units(value):
    with pytest.raises(ValidationError):
        profile(maximum_price_chf_cents=value)


def test_unknown_and_foreign_currency_are_not_zero_or_confirmed_crossings():
    for f in (facts(prices=[]), facts(prices=[price(1, currency="EUR")])):
        assert assessment(profile(), f)["status"] == "unknown"
        assert all(e["code"] != "price_above_limit" for e in changes(profile(), f, facts(prices=[price(1270000)])))
    assert assessment(profile(maximum_price_chf_cents=0), facts(prices=[price(0)]))["status"] == "match"


def test_filters_explain_known_exclusions_and_preserve_unknown_fields():
    p = profile(locations=["Lugano"], brands=["BMW"], keywords=["commercial vehicle"])
    matched = assessment(p, facts())
    assert matched["status"] == "match"
    assert {r["field"] for r in matched["reasons"]} == {"canton", "category", "asset_location", "brand", "title_description", "prices.current_bid"}
    assert assessment(p, facts(asset_location=None, brand=None))["status"] == "unknown"
    assert assessment(p, facts(asset_location="LuganoNord"))["status"] == "excluded"
    assert assessment(p, facts(canton="ZH", brand=None))["status"] == "excluded"
    assert assessment(p, facts(title="Other", description=None))["status"] == "unknown"
    assert assessment(p, facts(title="Other", description="No wanted words"))["status"] == "excluded"


@pytest.mark.parametrize("phrase", ["équipement industriel", "öffentliche maschine", "macchina industriale", "maschina industriala", "industrial equipment"])
def test_explicit_phrases_preserve_language_without_invented_translation(phrase):
    p = profile(keywords=[phrase])
    assert assessment(p, facts(title=phrase.upper()))["status"] == "match"
    assert assessment(p, facts(title="An unrelated asset"))["status"] == "excluded"


def test_lots_and_auctions_do_not_merge_and_out_of_order_data_is_rejected():
    p, f = profile(), facts()
    for other in (facts(lot_id="lot-3"), facts(lot_id=None), facts(source_key="other-ti")):
        assert other.identity() != f.identity()
        with pytest.raises(ValueError):
            changes(p, f, other)
    with pytest.raises(ValueError):
        changes(p, f, facts(observed_at=NOW - timedelta(seconds=1)))


def test_another_canton_adapter_uses_identical_domain_rules():
    outputs = []
    for canton, source in (("TI", "fixture-ti"), ("ZH", "fixture-zh")):
        p = profile(cantons=[canton])
        before = facts(canton=canton, source_key=source)
        after = facts(canton=canton, source_key=source, prices=[price(1270000)])
        outputs.append((assessment(p, before)["status"], changes(p, before, after)))
    assert outputs[0] == outputs[1]


def test_transport_refresh_and_reordering_do_not_change_state_but_keep_evidence_binding():
    p = profile()
    a = facts(prices=[price(), price(10000, "starting_price")])
    b = facts(prices=[price(10000, "starting_price"), price()], observed_at=NOW + timedelta(seconds=30), raw_sha256="b" * 64)
    assert a.state_hash() == b.state_hash() and changes(p, a, b) == []
    assert assessment(p, a)["assessment_hash"] != assessment(p, b)["assessment_hash"]


def document(identifier="terms", sha="a"):
    return {"official_id": identifier, "title": "Conditions", "sha256": sha * 64 if sha else None}


def test_partial_document_listing_never_proves_removal_and_recovery_is_not_false_addition():
    baseline = facts(documents={"state": "complete", "items": [document()]})
    missing = facts(documents={"state": "unavailable"})
    assert [e["code"] for e in changes(profile(), baseline, missing)] == ["document_coverage_changed"]
    assert "document_added" not in {e["code"] for e in changes(profile(), missing, baseline)}
    removed = facts(documents={"state": "complete"})
    assert [e["code"] for e in changes(profile(), baseline, removed)] == ["document_removed"]
    replaced = facts(documents={"state": "complete", "items": [document(sha="b")]})
    assert [e["code"] for e in changes(profile(), baseline, replaced)] == ["document_changed"]


def test_conditions_and_cancellation_are_material_and_deadlines_recalculate():
    p = profile(notify={"ending_soon_hours": 24})
    before = facts(conditions_sha256="a" * 64)
    after = facts(conditions_sha256="b" * 64, ends_at=NOW + timedelta(days=3))
    assert {e["code"] for e in changes(p, before, after)} == {"conditions_changed", "deadline_changed"}
    assert ending_soon(p, before, now=NOW, max_age_seconds=900, following=True)["eligible"]
    assert ending_soon(p, after, now=NOW, max_age_seconds=900, following=True)["reason"] == "outside_window"
    cancelled = facts(status="cancelled")
    assert changes(p, facts(), cancelled)[0]["code"] == "cancelled"
    assert not ending_soon(p, cancelled, now=NOW, max_age_seconds=900, following=True)["eligible"]


@pytest.mark.parametrize("updates,reason", [({"status": "unknown"}, "auction_not_open"),
    ({"status": "postponed"}, "auction_not_open"), ({"ends_at": None}, "deadline_unknown"),
    ({"observed_at": NOW - timedelta(minutes=16)}, "source_not_current"),
    ({"observed_at": NOW + timedelta(seconds=1)}, "source_not_current"),
    ({"ends_at": NOW}, "outside_window")])
def test_reminder_suppresses_unknown_stale_cancelled_or_elapsed_states(updates, reason):
    result = ending_soon(profile(notify={"ending_soon_hours": 24}), facts(**updates), now=NOW, max_age_seconds=900, following=True)
    assert result == {**result, "eligible": False, "reason": reason}


def test_opted_in_bid_changes_and_stop_following_are_explicit():
    p = profile(notify={"price_above_limit": False, "every_bid_change": True, "ending_soon_hours": 24})
    assert changes(p, facts(), facts(prices=[price(1270000)]))[0]["notify"]
    assert not ending_soon(p, facts(), now=NOW, max_age_seconds=900, following=False)["eligible"]


@pytest.mark.parametrize("updates", [{"ends_at": "2026-09-14T12:00:00"}, {"source_url": "http://example.org/x"},
    {"source_url": "https://user:pass@example.org/x"}, {"source_url": "https://example.org/x?token=secret"},
    {"prices": [price(), price(900000)]}, {"canton": "XX"}, {"lot_id": " "}])
def test_invalid_or_ambiguous_source_facts_fail_closed(updates):
    with pytest.raises(ValidationError):
        facts(**updates)
