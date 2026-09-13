import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from helvetic_lens.simap_sources import PublicationEmbargo, parse_cpv_ancestry, parse_publication
from helvetic_lens.simap_tender_facts import facts_from_publication
from helvetic_lens.tender_contracts import TenderLotFacts, TenderProfile, match_lot, phrase_in

NOW = datetime(2026, 9, 12, 6, tzinfo=UTC)
PROJECT, PUBLICATION, LOT_A, LOT_B = (str(uuid4()) for _ in range(4))


def profile(**changes):
    return TenderProfile.model_validate(
        {
            "name": "Basel software",
            "company_name": "Example GmbH",
            "capabilities": [{"name": "Software", "phrases": ["software development"]}],
            **changes,
        }
    )


def facts(**changes):
    return TenderLotFacts.model_validate(
        {
            "project_id": PROJECT,
            "publication_id": PUBLICATION,
            "evidence_sha256": "a" * 64,
            "phase": "open",
            "text": [
                {
                    "locator": "/procurement/orderDescription/en",
                    "language": "en",
                    "text": "We require software development and support.",
                }
            ],
            "qualification_coverage": "complete",
            **changes,
        }
    )


def codes(result, key):
    return {r["code"] for r in result[key]}


def taxonomy():
    # Provider /codes/v1/cpv/search tree shape, verified against the official API.
    return {
        "codes": [
            {
                "code": "72000000",
                "codes": [
                    {
                        "code": "72200000",
                        "codes": [{"code": "72210000", "codes": [{"code": "72212000", "codes": []}]}],
                    }
                ],
            }
        ]
    }


def test_description_match_is_explained_and_never_promises_eligibility_or_ai_score():
    selected = profile(minimum_semantic_score=82)
    result = match_lot(selected, facts(), now=NOW)
    assert result["verdict"] == "match"
    assert result["matches"] == [
        {
            "code": "capability_phrase",
            "capability": "Software",
            "phrase": "software development",
            "locator": "/procurement/orderDescription/en",
            "language": "en",
        }
    ]
    assert result["eligibility"] == "not_determined"
    assert result["semantic_status"] == "disabled" and result["semantic_score"] is None
    assert result["profile_sha256"] == selected.fingerprint()
    assert profile().minimum_semantic_score is None


@pytest.mark.parametrize(
    "phrase,text,expected",
    [
        ("C++", "Experience with C#", False),
        ("C#", "Experience with C++", False),
        ("C++", "C++ development", True),
        (".NET", ".NET development", True),
        (".NET", "Internet services", False),
        ("software", "softwareentwicklung", False),
        ("software development", "SOFTWARE—development", True),
        ("développement", "DÉVELOPPEMENT de logiciels", True),
    ],
)
def test_phrase_matching_preserves_languages_technical_identifiers_and_word_boundaries(
    phrase, text, expected
):
    assert phrase_in(phrase, text) is expected


def test_cpv_ancestry_uses_official_edges_and_binds_the_taxonomy_evidence():
    ancestry = parse_cpv_ancestry(taxonomy(), requested_code="72212000")
    result = match_lot(
        profile(capabilities=[], cpv_codes=["72000000"]),
        facts(cpv_codes=["72212000"], cpv_ancestry=[ancestry]),
        now=NOW,
    )
    assert result["verdict"] == "match"
    assert result["matches"] == [
        {
            "code": "cpv_descendant",
            "value": "72212000",
            "selected_code": "72000000",
            "taxonomy_sha256": ancestry.source_sha256,
        }
    ]
    exact = match_lot(
        profile(capabilities=[], cpv_codes=["72000000"], cpv_include_descendants=False),
        facts(cpv_codes=["72212000"], cpv_ancestry=[ancestry]),
        now=NOW,
    )
    assert exact["verdict"] == "no_match"


def test_missing_taxonomy_never_infers_numeric_prefixes_and_cannot_bypass_an_exclusion():
    result = match_lot(
        profile(capabilities=[], cpv_codes=["72000000"]), facts(cpv_codes=["72212000"]), now=NOW
    )
    assert result["verdict"] == "unknown" and "cpv_hierarchy_unknown" in codes(result, "unknowns")
    result = match_lot(profile(excluded_cpv_codes=["72000000"]), facts(cpv_codes=["72212000"]), now=NOW)
    assert result["verdict"] == "unknown" and result["matches"]
    result = match_lot(
        profile(excluded_cpv_codes=["72000000"]),
        facts(
            cpv_codes=["72212000"], cpv_ancestry=[parse_cpv_ancestry(taxonomy(), requested_code="72212000")]
        ),
        now=NOW,
    )
    assert result["verdict"] == "excluded"
    assert result["exclusions"][0]["taxonomy_sha256"]


@pytest.mark.parametrize(
    "raw,code",
    [
        (None, "72212000"),
        ({"codes": None}, "72212000"),
        ({"codes": {}}, "72212000"),
        (taxonomy(), None),
        (taxonomy(), "79999999"),
        ({"codes": [{"code": "72000000", "codes": None}]}, "72000000"),
    ],
)
def test_invalid_taxonomy_is_rejected_without_guessing(raw, code):
    with pytest.raises(ValueError):
        parse_cpv_ancestry(raw, requested_code=code)


def test_ambiguous_taxonomy_is_not_silently_deduplicated():
    raw = taxonomy()
    raw["codes"].append({"code": "72212000", "codes": []})
    with pytest.raises(ValueError, match="Ambiguous"):
        parse_cpv_ancestry(raw, requested_code="72212000")


@pytest.mark.parametrize(
    "options,source,expected",
    [
        ({"excluded_phrases": ["support"]}, {}, "excluded_phrase"),
        ({"contract_cantons": ["BS"]}, {"contract_country": "DE"}, "contract_outside_switzerland"),
        ({"contract_cantons": ["BS"]}, {"contract_canton": "ZH"}, "contract_canton_excluded"),
        ({"offer_languages": ["de"]}, {"offer_languages": ["fr"]}, "offer_languages_excluded"),
        ({"authority_levels": ["municipal"]}, {"authority_level": "federal"}, "authority_level_excluded"),
        (
            {"excluded_contract_types": ["construction"]},
            {"contract_type": "construction"},
            "excluded_contract_type",
        ),
        ({}, {"offer_deadline": NOW}, "offer_deadline_passed"),
        ({}, {"phase": "awarded"}, "discovery_phase_closed"),
    ],
)
def test_hard_exclusions_win_over_positive_capability(options, source, expected):
    result = match_lot(profile(**options), facts(**source), now=NOW)
    assert result["matches"] and result["verdict"] == "excluded"
    assert expected in codes(result, "exclusions")


def test_unknown_hard_exclusion_and_missing_filter_facts_are_visible():
    result = match_lot(profile(excluded_contract_types=["construction"]), facts(), now=NOW)
    assert result["verdict"] == "unknown"
    assert "contract_type_exclusions_unverified" in codes(result, "unknowns")
    result = match_lot(
        profile(contract_cantons=["BS"], offer_languages=["de"], authority_levels=["municipal"]),
        facts(),
        now=NOW,
    )
    assert result["verdict"] == "needs_review"
    assert codes(result, "unknowns") == {
        "contract_location_unknown",
        "offer_languages_unknown",
        "authority_level_unknown",
    }


@pytest.mark.parametrize(
    "source,verdict,reason",
    [
        ({}, "needs_review", "contract_maximum_not_established"),
        (
            {"estimated_min_chf": "10000", "estimated_max_chf": "90000"},
            "needs_review",
            "contract_maximum_not_established",
        ),
        ({"estimated_min_chf": "60000"}, "excluded", "contract_value_above_maximum"),
        ({"estimated_min_chf": "10000", "estimated_max_chf": "40000"}, "match", None),
    ],
)
def test_unknown_and_overlapping_budget_ranges_do_not_claim_within_budget(source, verdict, reason):
    result = match_lot(profile(maximum_contract_chf="50000"), facts(**source), now=NOW)
    assert result["verdict"] == verdict
    if reason:
        assert reason in codes(result, "unknowns") | codes(result, "exclusions")


def test_unstated_company_qualifications_are_unknown_and_declared_gaps_are_not_legal_disqualification():
    required = facts(
        required_reference_count=3,
        references_locator="/terms/criteria/1",
        required_certificates=["ISO 9001"],
        certificates_locator="/terms/criteria/2",
    )
    result = match_lot(profile(), required, now=NOW)
    assert result["verdict"] == "needs_review" and result["qualification_gaps"] == []
    assert codes(result, "unknowns") == {"company_references_unknown", "company_certificates_unknown"}
    result = match_lot(profile(available_reference_count=2, certificates=[]), required, now=NOW)
    assert result["verdict"] == "needs_review" and result["eligibility"] == "not_determined"
    assert codes(result, "qualification_gaps") == {"declared_reference_gap", "declared_certificate_gap"}
    assert (
        match_lot(profile(available_reference_count=3, certificates=["ISO 9001"]), required, now=NOW)[
            "verdict"
        ]
        == "match"
    )
    assert match_lot(profile(), facts(qualification_coverage="partial"), now=NOW)["verdict"] == "needs_review"


@pytest.mark.parametrize(
    "changes",
    [
        {"capabilities": []},
        {"name": "  "},
        {"contract_cantons": ["Basel"]},
        {"cpv_codes": ["72000000-5"]},
        {"cpv_include_descendants": "true"},
        {"minimum_contract_chf": 200, "maximum_contract_chf": 100},
        {"available_reference_count": True},
        {"minimum_semantic_score": 101},
        {"certificates": [" "]},
        {"cpv_codes": ["72000000"], "excluded_cpv_codes": ["72000000"]},
    ],
)
def test_profile_rejects_ambiguous_configuration(changes):
    with pytest.raises(ValidationError):
        profile(**changes)


def source(*, lots=False):
    return {
        "id": PUBLICATION,
        "type": "tender",
        "hasProjectDocuments": True,
        "base": {
            "id": PUBLICATION,
            "projectId": PROJECT,
            "type": "tender",
            "publicationDate": "2026-09-12",
            "lotsType": "with" if lots else "without",
            "procOfficeId": "official-office",
        },
        "dates": {"offerDeadline": "2026-10-16T15:00:00+02:00"},
        "project-info": {
            "title": {"en": "Umbrella software development project"},
            "orderType": "service",
            "offerLanguages": ["de"],
            "procOfficeAddress": {"countryId": "CH", "cantonId": "BS"},
        },
        "procurement": {
            "orderDescription": {"en": "<p>software development</p><script>secret phrase</script>"}
        },
        **(
            {
                "lots": [
                    {"id": LOT_A, "title": {"en": "Software development"}, "projectSubType": "service"},
                    {"id": LOT_B, "title": {"en": "Catering"}, "projectSubType": "service"},
                ]
            }
            if lots
            else {}
        ),
    }


def record(raw):
    return parse_publication(raw, project_id=PROJECT, publication_id=PUBLICATION, now=NOW)


def test_lot_projection_never_borrows_umbrella_title_or_other_lot_text():
    lot_a, lot_b = facts_from_publication(record(source(lots=True)), now=NOW)
    assert lot_a.lot_id == LOT_A and lot_b.lot_id == LOT_B
    assert match_lot(profile(), lot_a, now=NOW)["verdict"] == "needs_review"
    assert match_lot(profile(), lot_b, now=NOW)["verdict"] == "no_match"
    assert all(t.locator.startswith("/lots/1/") for t in lot_b.text)


def test_project_cpv_keeps_unclassified_lots_visible_without_claiming_lot_relevance():
    raw = source(lots=True)
    raw["procurement"]["cpvCode"] = {"code": "72212000"}
    ancestry = parse_cpv_ancestry(taxonomy(), requested_code="72212000")
    selected = profile(capabilities=[], cpv_codes=["72000000"])
    lot_a, lot_b = facts_from_publication(record(raw), now=NOW, cpv_ancestry=[ancestry])
    for lot in (lot_a, lot_b):
        result = match_lot(selected, lot, now=NOW)
        assert result["verdict"] == "needs_review" and result["matches"] == []
        assert result["project_context"] == [
            {
                "code": "project_cpv_context",
                "value": "72212000",
                "selected_code": "72000000",
                "locator": "/procurement",
                "lot_relevance": "not_verified",
                "taxonomy_sha256": ancestry.source_sha256,
            }
        ]
    no_taxonomy = facts_from_publication(record(raw), now=NOW)[0]
    assert match_lot(selected, no_taxonomy, now=NOW)["project_context"] == []
    # An explicit incompatible lot classification defeats the umbrella hint.
    classified = lot_b.model_copy(update={"cpv_codes": ("55500000",), "cpv_ancestry": ()})
    assert match_lot(selected, classified, now=NOW)["project_context"] == []
    excluded = profile(capabilities=[], cpv_codes=["72000000"], excluded_phrases=["catering"])
    assert match_lot(excluded, lot_b, now=NOW)["verdict"] == "excluded"
    unverified_exclusion = profile(capabilities=[], cpv_codes=["72000000"], excluded_cpv_codes=["55500000"])
    assert match_lot(unverified_exclusion, lot_a, now=NOW)["verdict"] == "unknown"
    assert (
        match_lot(selected, lot_a.model_copy(update={"phase": "awarded"}), now=NOW)["verdict"] == "excluded"
    )
    assert match_lot(selected, lot_a.model_copy(update={"phase": "unknown"}), now=NOW)["verdict"] == "unknown"


def test_authority_headquarters_and_unstructured_contract_address_do_not_set_contract_location():
    raw = source()
    raw["procurement"].update(
        orderAddressOnlyDescription="yes", orderAddress={"countryId": "CH", "cantonId": "BS"}
    )
    (item,) = facts_from_publication(record(raw), now=NOW)
    assert item.contract_country is None and item.contract_canton is None and item.authority_level is None
    assert "contract_location_unknown" in codes(
        match_lot(profile(contract_cantons=["BS"]), item, now=NOW), "unknowns"
    )
    raw["procurement"]["orderAddressOnlyDescription"] = "no"
    (item,) = facts_from_publication(record(raw), now=NOW, authority_levels={"official-office": "cantonal"})
    assert item.contract_canton == "BS" and item.authority_level == "cantonal"


def test_source_text_projection_keeps_evidence_links_originals_and_unambiguous_deadline():
    raw = source()
    original = copy.deepcopy(raw)
    (item,) = facts_from_publication(record(raw), now=NOW)
    assert raw == original
    assert item.offer_deadline == datetime(2026, 10, 16, 13, tzinfo=UTC)
    assert not any("secret phrase" in t.text for t in item.text)
    assert item.qualification_coverage == "unknown" and item.estimated_max_chf is None


def test_award_referencing_one_lot_does_not_close_every_lot_in_the_project():
    raw = source(lots=True)
    raw["type"] = raw["base"]["type"] = "award"
    raw["lot"] = raw.pop("lots")[0]
    (item,) = facts_from_publication(record(raw), now=NOW)
    assert item.lot_id == LOT_A and item.phase == "awarded" and item.cpv_codes is None


def test_projection_rechecks_embargo_and_exact_original_binding():
    saved = record(source())
    with pytest.raises(PublicationEmbargo):
        facts_from_publication(saved, now=NOW - timedelta(seconds=1))
    saved["original"]["project-info"]["title"]["en"] = "Mutated original"
    with pytest.raises(ValueError, match="fingerprint"):
        facts_from_publication(saved, now=NOW)


def test_duplicate_lots_and_unproven_invitation_access_do_not_become_public_opportunities():
    raw = source(lots=True)
    raw["lots"][1]["id"] = LOT_A
    with pytest.raises(ValueError, match="Duplicate lot"):
        facts_from_publication(record(raw), now=NOW)
    raw = source()
    raw["project-info"]["processType"] = "invitation"
    (item,) = facts_from_publication(record(raw), now=NOW)
    assert item.phase == "unknown"
