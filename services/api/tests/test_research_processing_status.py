"""Saved technical work stays visible without masquerading as a research gap."""
from copy import deepcopy

from helvetic_lens.product_research_mission import separate_processing


def test_saved_technical_limitation_is_separate_and_real_evidence_gap_survives():
    technical = "Original: reading or whole-document analysis is incomplete. Section analysis and whole-document review are pending."
    gap = "The original does not establish which rule applies to the exception."
    answer = {"status": "partial", "limitations": [technical, gap]}
    state = {"checkpoints": [{"answer": deepcopy(answer)}], "answer": deepcopy(answer)}
    documents = [{"title": "Original", "url": "https://example.org/original", "read_complete": True,
        "complete": False, "review_failed": True}]
    original = deepcopy(documents)

    separate_processing(state, documents)

    assert state["answer"]["limitations"] == [gap]
    assert state["checkpoints"][0]["answer"]["limitations"] == [gap]
    assert state["processing_issues"] == [{"title": "Original", "url": "https://example.org/original",
        "kind": "analysis", "status": "failed",
        "reason": "The source text is saved. Its analysis needs to be retried."}]
    assert documents == original
    # Completion removes an obsolete processing warning, never upgrades the
    # research conclusion or removes a substantive uncertainty.
    documents[0]["complete"] = True
    state["stop"] = "documents_incomplete"
    separate_processing(state, documents)
    assert state["processing_issues"] == []
    assert state["stop"] is None
    assert state["answer"] == {"status": "partial", "limitations": [gap]}


def test_processing_projection_keeps_pending_reads_and_analysis_distinct():
    state = {"answer": {"status": "partial", "limitations": ["An unrelated original is missing."]}}
    separate_processing(state, [
        {"title": "Unread", "read_complete": False, "complete": False},
        {"title": "Read", "read_complete": True, "complete": False},
        {"title": "Finished", "read_complete": True, "complete": True}])
    assert [(issue["title"], issue["kind"], issue["status"]) for issue in state["processing_issues"]] == [
        ("Unread", "reading", "pending"), ("Read", "analysis", "pending")]
    assert state["answer"]["limitations"] == ["An unrelated original is missing."]
