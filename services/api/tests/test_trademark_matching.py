"""Synthetic candidates/calibrations: engineering checks, not measured IP quality."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from helvetic_lens.trademark_contracts import (
    NORMALIZATION_VERSION,
    Brand,
    SimilarityCalibration,
    TrademarkFacts,
    TrademarkPortfolio,
    exact,
)
from helvetic_lens.trademark_matching import assess, soundex

NOW = datetime(2026, 9, 13, 19, tzinfo=UTC)


def portfolio(**changes):
    brand = {"key": "almora", "name": "ALMORA", "language": "en", "relevant_classes": [9, 42],
        "goods_services": [{"name": "Software", "phrases": [{"language": "en", "text": "computer software"}]}], **changes}
    return TrademarkPortfolio(name="Brand portfolio", brands=[brand])


def facts(**changes):
    return TrademarkFacts(**{"official_id": "synthetic-ch-1", "origin": "national_ch",
        "source_url": "https://example.invalid/trademark/1", "source_sha256": "1" * 64,
        "mark": "ALMORA", "mark_type": "word", "owners": ["Synthetic Owner AG"], "classes": [9],
        "goods_services": [{"language": "en", "text": "Computer software and related services.", "class_number": 9}],
        "application_date": "2026-07-01", "publication_date": "2026-08-12", "registration_date": "2026-08-09", **changes})


def calibration(**changes):
    return SimilarityCalibration(**{"version": "synthetic-english-v1", "normalization_version": NORMALIZATION_VERSION,
        "language": "en", "lexical_minimum": 70, "word_extension_minimum": 70, "phonetic_method": "soundex-en-v1",
        "phonetic_lexical_floor": 60, "training_sha256": "a" * 64, "validation_sha256": "b" * 64,
        "review_reference": "Synthetic engineering fixture, not human calibration",
        "reviewed_at": NOW - timedelta(days=1), "valid_until": NOW + timedelta(days=1), **changes})


def result(profile=None, record=None, **kw):
    return assess(profile or portfolio(), record or facts(), now=kw.pop("now", NOW), **kw)


def test_exact_is_an_explained_candidate_never_infringement():
    assessment = result()
    item, = assessment["results"]
    assert item["classification"] == "candidate_for_ip_review" and item["priority"] == "high"
    assert item["methods"] == [{"kind": "exact", "brand_variant": "ALMORA", "source_mark": "ALMORA"}]
    assert not assessment["legal_conflict_confirmed"] and not assessment["coverage_verified"]
    assert item["goods_services"]["state"] == "direct_phrases"
    assert assessment["normalization_version"] == NORMALIZATION_VERSION


@pytest.mark.parametrize("name", ["ALMORE", "ALMORIA", "ALMORA AI", "ALMROA"])
def test_calibrated_lexical_candidates_preserve_source_text_and_basis(name):
    item, = result(record=facts(mark=name), calibrations=[calibration()])["results"]
    assert item["state"] == "candidate"
    lexical, = [method for method in item["methods"] if method["kind"] == "lexical"]
    assert lexical["source_mark"] == name and lexical["distance"] >= 1 and lexical["score"] >= 70
    assert item["calibration_sha256"] == calibration().fingerprint()


def test_phonetic_candidate_uses_language_scoped_method_and_lexical_floor():
    item, = result(record=facts(mark="ALMORE"), calibrations=[calibration(lexical_minimum=99)])["results"]
    assert [m["kind"] for m in item["methods"]] == ["phonetic"]
    assert item["methods"][0]["key"] == "A456"
    assert result(record=facts(mark="ALMORE"), calibrations=[calibration(lexical_minimum=99, phonetic_lexical_floor=99)])["results"][0]["state"] == "not_selected"


@pytest.mark.parametrize("value,key", [("robert", "R163"), ("rupert", "R163"), ("ashcraft", "A261"), ("tymczak", "T522"), ("pfister", "P236"), ("école", None), ("foo bar", None), ("", None)])
def test_english_soundex_reference_vectors_and_unsupported_forms(value, key):
    assert soundex(value) == key


@pytest.mark.parametrize("calibrations", [[], [calibration(valid_until=NOW)], [calibration(normalization_version="older-unicode")]])
def test_missing_expired_or_wrong_normalization_calibration_does_not_promote(calibrations):
    item, = result(record=facts(mark="ALMORIA"), calibrations=calibrations)["results"]
    assert item["state"] == "unavailable" and item["methods"] == []
    assert item["unavailable"] == ["similarity_calibration_unavailable"]


def test_short_names_and_cross_script_confusables_never_claim_exact():
    assert exact(" A  B ") == "a b"
    assert exact("A-B") != exact("AB") and exact("café") != exact("cafe")
    assert exact("ＡＬＭＯＲＡ") == exact("almora")
    item, = result(record=facts(mark="АLMORA"), calibrations=[calibration()])["results"]
    assert item["state"] == "unavailable" and item["unavailable"] == ["cross_script_similarity_unavailable"]
    assert not any(m["kind"] == "exact" for m in result(record=facts(mark="ALMORÁ"), calibrations=[calibration()])["results"][0]["methods"])


@pytest.mark.parametrize("language,phrase", [("de", "Computerprogramme"), ("fr", "logiciels informatiques"), ("it", "programmi informatici"), ("rm", "programs da computer"), ("en", "computer software")])
def test_goods_evidence_is_language_bound_and_original_statement_is_addressable(language, phrase):
    profile = portfolio(language=language, goods_services=[{"name": "Software", "phrases": [{"language": language, "text": phrase}]}])
    record = facts(goods_services=[{"language": language + "-CH", "text": phrase + "; other material", "class_number": 9}])
    item, = result(profile, record)["results"]
    evidence, = item["goods_services"]["matches"]
    assert evidence["statement_index"] == 0 and evidence["phrase"] == phrase and item["priority"] == "high"
    foreign = record.model_copy(update={"goods_services": facts(goods_services=[{"language": "ja", "text": phrase}]).goods_services})
    assert result(profile, foreign)["results"][0]["goods_services"]["state"] == "not_established"


def test_class_alone_cannot_prove_overlap_and_missing_goods_stay_unknown():
    same_class = result(record=facts(goods_services=[{"language": "en", "text": "Magnetic compasses."}]))["results"][0]
    assert same_class["priority"] == "review" and same_class["goods_services"]["state"] == "not_established"
    assert same_class["goods_services"]["class_overlap"] == [9]
    assert not same_class["goods_services"]["classes_prove_goods_similarity"]
    missing = result(record=facts(classes=None, goods_services=None))["results"][0]
    assert missing["goods_services"]["state"] == "unknown" and missing["goods_services"]["class_overlap"] is None
    # Class boundaries alone do not negate directly evidenced relevant goods.
    different_class = result(record=facts(classes=[35]))["results"][0]
    assert different_class["priority"] == "high" and different_class["goods_services"]["class_overlap"] == []


def test_phrase_boundaries_and_partial_goods_relevance():
    profile = portfolio(goods_services=[{"name": "Software", "phrases": [{"language": "en", "text": "software"}]},
        {"name": "Hosting", "phrases": [{"language": "en", "text": "hosting"}]}])
    assert result(profile, facts(goods_services=[{"language": "en", "text": "softwarehouse"}]))["results"][0]["goods_services"]["state"] == "not_established"
    assert result(profile)["results"][0]["goods_services"]["state"] == "partial"


def test_multiple_brands_variants_owner_interest_and_missing_verbal_mark():
    original = portfolio()
    profile = original.model_copy(update={"brands": (*original.brands, Brand(key="owner", name="Other Brand", language="en",
        exact_name=False, similar_names=False, owners_of_interest=["Synthetic Owner AG"]))})
    items = result(profile)["results"]
    assert [i["brand_key"] for i in items] == ["almora", "owner"]
    assert items[1]["methods"][0]["kind"] == "owner_interest"
    assert result(record=facts(mark=None, mark_type="figurative"))["results"][0]["state"] == "unavailable"
    variant = portfolio(word_variants=["ALMORA AI"])
    assert any(m["kind"] == "exact" and m["brand_variant"] == "ALMORA AI" for m in result(variant, facts(mark="almora ai"))["results"][0]["methods"])
    assert result(portfolio(exact_name=False), facts(), calibrations=[calibration()])["results"][0]["state"] == "not_selected"


def test_budget_exhaustion_is_not_a_negative_and_preserves_other_exact_brands():
    profile = TrademarkPortfolio(name="Multiple", brands=[{"key": "near", "name": "ALMORIA", "language": "en"},
        {"key": "exact", "name": "ALMORA", "language": "en"}])
    items = result(profile, calibrations=[calibration()], max_distance_cells=0)["results"]
    assert items[0]["state"] == "unavailable" and "comparison_budget_exhausted" in items[0]["unavailable"]
    assert items[1]["state"] == "candidate"


def test_material_dates_status_owner_and_goods_separate_from_transport_refresh():
    first = facts()
    assert first.application_date != first.publication_date != first.registration_date
    for update in ({"publication_date": "2026-08-13"}, {"owners": ["Changed AG"]}, {"status": "cancelled"}, {"goods_services": None}):
        changed = facts(**update)
        assert changed.material_fingerprint() != first.material_fingerprint()
        assert result(record=changed)["decision_sha256"] != result(record=first)["decision_sha256"]
    refreshed = facts(source_sha256="2" * 64, source_url="https://example.invalid/trademark/1/revision")
    assert refreshed.material_fingerprint() == first.material_fingerprint()
    assert result(record=refreshed)["decision_sha256"] == result(record=first)["decision_sha256"]
    missing = facts(application_date=None, publication_date=None, registration_date=None)
    assert missing.publication_date is None and missing.registration_date is None


@pytest.mark.parametrize("changes", [{"name": "\u202eALMORA"}, {"relevant_classes": [0]}, {"relevant_classes": [46]},
    {"relevant_classes": [True]}, {"word_variants": ["almora"]}, {"similar_names": "yes"},
    {"owners_of_interest": ["  "]}, {"name": "A" * 257}])
def test_profile_rejects_ambiguous_duplicate_unbounded_or_forged_values(changes):
    with pytest.raises(ValidationError):
        portfolio(**changes)


def test_calibration_rejects_shared_splits_unknown_engine_and_unscoped_phonetics():
    for change in ({"training_sha256": "b" * 64}, {"language": "de"}, {"matcher_version": "unknown"}, {"held_out_sha256": "c" * 64}):
        with pytest.raises(ValidationError):
            calibration(**change)
    with pytest.raises(ValueError):
        result(calibrations=[calibration(), calibration()])
    with pytest.raises(ValueError):
        result(now=NOW.replace(tzinfo=None))
