import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens import research_reference_metadata as metadata
from helvetic_lens.product_document_reconciliation import ReviewNode
from helvetic_lens.product_operations import fingerprint

FIRST = "Adams, A., B. Baker, and C. Clark, A new method detects a recovery, Journal of Testing, 12, 10–20, doi:10.1234/test-one, 2021."
SECOND = "Baker, B., C. Clark, and D. Davis, No recovery under alternate conditions, Journal of Testing, 13, 20–30, doi:10.1234/test-two, 2022."
NARRATIVE = "Adams et al. (2021) found no improvement in this group. Art. 25 DSG applies; the exception remains in force."


def source(passages, *, identifier=None, sha="a" * 64):
    return {"id": identifier or str(uuid4()), "sha256": sha, "url": "https://example.org/report.pdf",
        "excerpts": [{"passage": locator, "text": text} for locator, text in passages]}


def bibliography():
    return source([("page-8-text-1-char-1", "REFERENCES"),
        ("page-8-text-2-char-1", FIRST), ("page-8-text-3-char-1", SECOND)])


def row(view):
    snapshot = {"excerpts": deepcopy(view["excerpts"]), "reading": {"pages": [1, 8]}, "document_index": "0"}
    first = snapshot["excerpts"][-1]
    snapshot["section_review"] = {"contract": analysis.CONTRACT, "sha256": view["sha256"],
        "coverage_fingerprint": fingerprint({"sha256": view["sha256"], "excerpts": snapshot["excerpts"]}),
        "summary": "The study proves a substantive recovery in a different later period.",
        "observations": [{"quote": first["text"], "locator": first["passage"],
            "statement": first["text"], "role": "support"}], "cross_references": [],
        "limitations": ["All unrelated outcomes still need investigation."]}
    return SimpleNamespace(id=view["id"], sha256=view["sha256"], url=view["url"], title="Original report",
        investigation_id="run", snapshot=snapshot)


def test_real_list_not_toc_preserves_body_and_reassembles_cross_portion_entry():
    early = source([("page-1-text-1-char-1", "REFERENCES"), ("page-1-text-2-char-1", "247\n248\n262"),
        ("page-2-text-1-char-1", NARRATIVE), ("page-8-text-1-char-1", "REFERENCES"),
        ("page-8-text-2-char-1", FIRST), ("page-8-text-3-char-1", SECOND[:70])])
    late = source([("page-8-text-3-char-71", SECOND[70:])])
    original = deepcopy([early, late])
    views = metadata.annotate_sources([early, late])
    assert [early, late] == original
    assert [metadata.passage_use(views[0], p) for p in views[0]["excerpts"][:3]] == ["original"] * 3
    assert metadata.passage_use(views[0], views[0]["excerpts"][-1]) == "reference_metadata"
    assert metadata.pure_metadata(views[1])
    assert metadata.citation_use(views[1], "page-8-text-3-char-71", SECOND[70:]) == "reference_metadata"
    assert metadata.citation_use(views[1], "page-8-text-3-char-71", "invented text") == "original"
    # Identical positions in another document cannot complete this fragment.
    late["sha256"] = "b" * 64
    assert not metadata.pure_metadata(metadata.annotate_sources([early, late])[1])


@pytest.mark.parametrize("heading,body", [
    ("References", "Art. 25 DSG; SR 235.1. Das Gericht prüft den Auskunftsanspruch."),
    ("Références", "L'art. 97 CO et RS 220 sont cités dans le raisonnement."),
    ("References", "Proceedings of the 17th CGPM (1983), published in 1984, p. 97."),
    ("REFERENCES", "A substantive annotated discussion cites doi:10.1234/a and explains why its conclusions do not apply."),
])
def test_legal_holdings_publication_evidence_and_mixed_notes_are_not_blanket_filtered(heading, body):
    view = metadata.annotate_sources([source([("p1", heading), ("p2", body), ("p3", SECOND)])])[0]
    assert all(metadata.passage_use(view, p) == "original" for p in view["excerpts"])


def test_mixed_prose_after_bibliography_is_preserved_and_labels_are_content_bound():
    original = bibliography()
    original["excerpts"].extend([{"passage": "page-9-text-1-char-1", "text": NARRATIVE},
        {"passage": "page-9-text-2-char-1", "text": FIRST},
        {"passage": "page-9-text-3-char-1", "text": SECOND}])
    view = metadata.annotate_sources([original])[0]
    assert metadata.passage_use(view, view["excerpts"][3]) == "original"
    assert metadata.passage_use(view, view["excerpts"][4]) == "reference_metadata"
    view["excerpts"][1]["text"] += " This additional observation changes the result."
    assert metadata.passage_use(view, view["excerpts"][1]) == "original"
    assert not metadata.pure_metadata(view)
    forged = source([("p1", NARRATIVE)])
    forged["excerpts"][0].update(source_use="reference_metadata", source_use_basis={"policy": metadata.POLICY})
    assert "source_use" not in metadata.annotate_sources([forged])[0]["excerpts"][0]

    # Repeated short legal rules are not running headers or page numbers.
    repeated = bibliography()
    repeated["excerpts"].extend({"passage": f"page-9-text-{i}-char-1", "text": "Art. 25 DSG applies."} for i in (1, 2))
    safe = metadata.annotate_sources([repeated])[0]
    assert all(metadata.passage_use(safe, p) == "original" for p in safe["excerpts"][-2:])


def test_legacy_bibliography_notes_become_metadata_not_inherited_empirical_summary():
    original = row(bibliography())
    before = deepcopy(original.snapshot)
    view = analysis.source_views([original])[original.id]
    review = analysis.section(original, view)
    assert review["observations"] == [] and review["limitations"] == []
    assert review["source_use"] == "reference_metadata"
    assert "different later period" not in review["summary"]
    assert review["coverage_fingerprint"] == before["section_review"]["coverage_fingerprint"]
    assert original.snapshot == before


def test_pure_metadata_review_completes_exact_coverage_without_provider_but_mixed_does_not(monkeypatch):
    work = {"input": {"coverage_fingerprint": "a" * 64,
        "sections": [{"source_use": "reference_metadata", "summary": "Untrusted old empirical conclusion"}],
        "cross_references": []}, "review_tree_node": {"id": "node"}}
    result = asyncio.run(analysis.execute(object(), work, 0))
    assert isinstance(result, ReviewNode)
    assert result.coverage_fingerprint == "a" * 64 and result.findings == []
    assert "empirical conclusion" not in result.synopsis
    assert work["model_route"]["model_requests"] == 0

    async def needs_provider(*args, **kwargs):
        raise RuntimeError("Mixed material still requires evidence review")

    monkeypatch.setattr("helvetic_lens.research_gateway.complete", needs_provider)
    work["input"]["sections"].append({"observations": [], "summary": NARRATIVE})
    with pytest.raises(RuntimeError, match="Mixed material"):
        asyncio.run(analysis.execute(object(), work, 1))


def test_legacy_completion_invalidates_only_affected_review_not_retained_reading():
    original = row(bibliography())
    session = SimpleNamespace(get=lambda model, key: original if key == original.id else None)
    doc = {"source_ids": [original.id], "sha256": original.sha256, "read_complete": True,
        "analysis_complete": True, "complete": True, "characters_read": 1000,
        "review_tree": {"nodes": {"old": "title-backed finding"}}, "reconciliation": {"findings": ["old"]}}
    state = {"document_reads": {"0": doc}, "extract_index": 1}
    assert analysis.invalidate_reference_reviews(session, SimpleNamespace(id="run"), state)
    assert doc["read_complete"] and doc["characters_read"] == 1000 and state["extract_index"] == 1
    assert not doc["analysis_complete"] and not doc["complete"] and "review_tree" not in doc
    doc["review_tree"] = {"nodes": {"current": "new progress"}}
    assert not analysis.invalidate_reference_reviews(session, SimpleNamespace(id="run"), state)
    assert "current" in doc["review_tree"]["nodes"]


def test_metadata_remains_searchable_with_original_leads_after_observations_removed(monkeypatch):
    original = row(bibliography())
    monkeypatch.setattr(analysis, "rows", lambda *args: [])
    monkeypatch.setattr("helvetic_lens.product_document_reconciliation.compact_reviews", lambda *args: {})
    values = analysis.compact_sources(None, None, [original])
    assert [p["text"] for p in values[0]["excerpts"]] == [p["text"] for p in original.snapshot["excerpts"]]
    assert values[0]["section_review"]["observations"] == []
    assert metadata.citation_use(values[0], "page-8-text-2-char-1", FIRST) == "reference_metadata"
    assert {p["url"] for p in values[0]["discovery_links"]} == {
        "https://doi.org/10.1234/test-one", "https://doi.org/10.1234/test-two"}
