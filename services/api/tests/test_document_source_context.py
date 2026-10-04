"""Source qualifications survive real reading/apply/compaction boundaries.

Scripted observations test provenance and transport, not semantic model accuracy.
"""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens import product_document_reconciliation as tree
from helvetic_lens import research_source_context as context
from helvetic_lens.config import DomainError
from helvetic_lens.product_investigation_models import InvestigationBranch
from helvetic_lens.product_operations import fingerprint

OBSERVATION = "The study reported improved response among the enrolled participants."
ANCHORS = {
    "scope": "The enrolled population consisted of adults with the specified condition.",
    "condition": "The improvement is expected only if the treatment continues without interruption.",
    "time": "These observations cover the period from January to December 2021.",
    "category": "Clinical response is distinct from the laboratory surrogate measurement.",
}


def note(quote, locator, *, anchors=()):
    return {"statement": "A fallible reading observation, not original quoted evidence.",
        "quote": quote, "locator": locator, "role": "context", "context_anchors": list(anchors)}


def original(run, passages, observations):
    excerpts = [{"passage": locator, "text": text} for locator, text in passages]
    source = SimpleNamespace(id=str(uuid4()), investigation_id=run.id, sha256="a" * 64,
        url="https://example.test/study.pdf", title="Retained study", snapshot={
            "excerpts": excerpts, "reading": {"pages": [1, 9]}, "page_count": 9, "document_index": "0"})
    source.snapshot["section_review"] = {"contract": analysis.CONTRACT, "sha256": source.sha256,
        "coverage_fingerprint": fingerprint({"sha256": source.sha256, "excerpts": excerpts}),
        "summary": "Fallible section summary.", "observations": observations,
        "cross_references": [], "limitations": []}
    return source


def reading(monkeypatch, *, tree_review=False):
    run = SimpleNamespace(id=str(uuid4()), question="What improved, for whom and during which period?")
    first = original(run, [("page-1-text-1", OBSERVATION)], [note(OBSERVATION, "page-1-text-1")])
    anchors = [{"kind": kind, "locator": f"page-{page}-text-1", "quote": quote}
        for page, (kind, quote) in enumerate(ANCHORS.items(), 5)]
    second = original(run, [(a["locator"], a["quote"]) for a in anchors] + [
        ("page-9-text-1", "Unrelated appendix information. " * 400)],
        [note(anchors[0]["quote"], anchors[0]["locator"], anchors=anchors[1:])])
    sources = [first, second]
    available = {s.id: s for s in sources}
    session = SimpleNamespace(get=lambda model, identifier: available.get(identifier))
    state = {"source_ids": list(available), "document_reads": {"0": {
        "sha256": first.sha256, "source_ids": list(available), "read_complete": True}}}
    branch = SimpleNamespace(checkpoint=state)
    monkeypatch.setattr(analysis, "rows", lambda session, model, run: [branch] if model is InvestigationBranch else [])
    # compact_reviews imports rows independently; the same durable branch is used.
    monkeypatch.setattr("helvetic_lens.product_investigations.rows",
        lambda session, model, run: [branch] if model is InvestigationBranch else [])
    work = {}
    analysis.prepare(session, run, state, work)
    if tree_review:
        pack = {key: deepcopy(value) for key, value in work["input"].items()
            if key not in {"question", "coverage_fingerprint"}}
        work["document_review_pack"] = pack
        tree.prepare(state["document_reads"]["0"], pack, work)
        state["document_reads"]["0"]["review_tree"]["source_dependencies"] = deepcopy(work["document_dependencies"])
    point = note(OBSERVATION, "page-1-text-1",
        anchors=[{**anchor, "source_id": second.id} for anchor in anchors])
    point["source_id"] = first.id
    payload = {"coverage_fingerprint": work["input"]["coverage_fingerprint"], "findings": [point],
        "cross_reference_checks": [], "limitations": []}
    if tree_review:
        payload["synopsis"] = "A source-bound observation and its original qualifications."
    result = (tree.ReviewNode if tree_review else analysis.DocumentReview).model_validate(payload)
    return run, sources, session, state, work, result


def test_section_anchors_are_literal_and_legacy_observations_remain_unannotated(monkeypatch):
    run = SimpleNamespace(id=str(uuid4()), question="What does this source say?")
    anchors = [{"kind": kind, "locator": f"page-{i}-text-1", "quote": quote}
        for i, (kind, quote) in enumerate(ANCHORS.items(), 2)]
    row = original(run, [("page-1-text-1", OBSERVATION), *[(a["locator"], a["quote"]) for a in anchors]],
        [note(OBSERVATION, "page-1-text-1", anchors=anchors)])
    work = {"input": {"source": {}}}
    analysis.prepare_section(work, row)
    review = analysis.SectionReview.model_validate({key: row.snapshot["section_review"][key]
        for key in ("coverage_fingerprint", "summary", "observations", "cross_references", "limitations")})
    result = SimpleNamespace(section_review=review)
    saved = analysis.validate_section(row, work, result)
    assert saved["observations"][0]["context_anchors"] == anchors
    result.section_review.observations[0].context_anchors[0].quote = "This invented population was never present."
    with pytest.raises(DomainError) as error:
        analysis.validate_section(row, work, result)
    assert error.value.code == "invalid_evidence"
    assert context.validated_context(analysis.source_views([row]).values()) == {}
    assert analysis.Observation.model_validate({key: value for key, value in note(OBSERVATION, "page-1-text-1").items()
        if key != "context_anchors"}).context_anchors == []


@pytest.mark.parametrize("tree_review", [False, True], ids=["whole-original", "review-tree"])
def test_review_and_compaction_preserve_cross_portion_context_and_reject_withdrawal(monkeypatch, tree_review):
    run, sources, session, state, work, result = reading(monkeypatch, tree_review=tree_review)
    before = deepcopy([s.snapshot for s in sources])
    analysis.apply(session, run, state, work, result)
    if tree_review:
        # A one-leaf tree finishes on the next ordinary prepare, without a model call.
        tree.prepare(state["document_reads"]["0"], work["document_review_pack"], work)
    compacted = analysis.compact_sources(session, run, sources)
    bound = compacted[0]["source_context"][0]
    assert bound["observation"] == {"source_id": sources[0].id, "sha256": sources[0].sha256,
        "locator": "page-1-text-1", "quote": OBSERVATION}
    assert {anchor["kind"]: anchor["quote"] for anchor in bound["anchors"]} == ANCHORS
    assert all(anchor["source_id"] == sources[1].id and anchor["sha256"] == sources[1].sha256
        for anchor in bound["anchors"])
    assert {p["text"] for p in compacted[1]["excerpts"]} == set(ANCHORS.values())
    assert "statement" not in str(bound) and "summary" not in str(bound)
    assert context.validated_context(compacted)[sources[0].id] == [bound]
    assert [s.snapshot for s in sources] == before
    withdrawn = analysis.compact_sources(session, run, sources[:1])
    assert "source_context" not in withdrawn[0]
    assert all(text not in str(withdrawn) for text in ANCHORS.values())
    # Replacing only the source identity cannot bless a previously recorded association.
    sources[1].sha256 = "b" * 64
    changed = analysis.compact_sources(session, run, sources)
    assert not changed[0].get("source_context")


@pytest.mark.parametrize("failure", ["fabricated", "unsupplied", "different_original", "changed", "withdrawn"])
def test_document_context_rejects_unavailable_or_unbound_originals_before_commit(monkeypatch, failure):
    run, sources, session, state, work, result = reading(monkeypatch)
    if failure == "fabricated":
        result.findings[0].context_anchors[0].quote = "An invented qualification is not a source quotation."
    elif failure == "unsupplied":
        result.findings[0].context_anchors[0].locator = "page-9-text-1"
        result.findings[0].context_anchors[0].quote = "Unrelated appendix information."
    elif failure == "different_original":
        sources[1].url = "https://example.test/another-study.pdf"
    elif failure == "changed":
        sources[1].sha256 = "b" * 64
    else:
        session.get = lambda model, identifier: sources[0] if identifier == sources[0].id else None
    before = deepcopy(state)
    with pytest.raises(DomainError) as error:
        analysis.apply(session, run, state, work, result)
    assert error.value.code == "invalid_evidence"
    assert state == before


def test_normalizer_never_rebinds_a_saved_anchor_to_a_new_sha(monkeypatch):
    run, sources, session, state, work, result = reading(monkeypatch)
    analysis.apply(session, run, state, work, result)
    values = analysis.compact_sources(session, run, sources)
    values[1]["sha256"] = "c" * 64
    with pytest.raises(ValueError, match="current original citation") as error:
        context.validated_context(values)
    assert ANCHORS["condition"] not in str(error.value)
