from pathlib import Path

from helvetic_lens.triage_regression import load_corpus, run_gate

CORPUS = Path(__file__).resolve().parents[3] / "demo" / "ai-triage-regression.json"


def test_labelled_corpus_covers_every_required_case_and_locale():
    corpus = load_corpus(CORPUS)
    kinds = {case["kind"] for case in corpus["cases"]}
    case_ids = {case["id"] for case in corpus["cases"]}

    assert set(corpus["supported_locales"]) == {"de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"}
    assert {case["locale"] for case in corpus["cases"]} == set(corpus["supported_locales"])
    assert kinds == {"identity_mismatch", "diff", "official_relation", "generated_rewrite"}
    assert {
        "different-law-identity",
        "page-wrap-noise",
        "insertion-and-renumbering",
        "moved-unchanged-section",
        "true-deadline-change",
        "official-repeal-replacement",
        "large-complete-rewrite",
    } <= case_ids
    rewrite = next(case for case in corpus["cases"] if case["id"] == "large-complete-rewrite")
    assert rewrite["generator"]["full_passages_per_side"] >= 1400


def test_quick_gate_preserves_material_and_structural_classification():
    result = run_gate(CORPUS)
    by_id = {case["id"]: case for case in result["cases"]}

    assert result["passed"] == 7
    assert by_id["different-law-identity"]["status"] == "mismatch"
    assert by_id["page-wrap-noise"]["material_count"] == 0
    assert by_id["insertion-and-renumbering"]["material_count"] == 1
    assert by_id["insertion-and-renumbering"]["semantic_counts"]["renumbered"] == 2
    assert by_id["moved-unchanged-section"]["material_count"] == 0
    assert by_id["true-deadline-change"]["material_count"] == 1
    assert by_id["official-repeal-replacement"]["authoritative"] is True
    assert by_id["large-complete-rewrite"]["complete"] is True
    assert by_id["large-complete-rewrite"]["passages_per_side"] == 220
