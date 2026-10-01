"""A failed original cannot starve ready siblings or erase completed review work."""
import json
from types import SimpleNamespace
from uuid import uuid4

from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import complete, start

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens import product_iterative_research as research
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigation_worker import advance, settle
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_operations import fingerprint


def test_native_review_isolates_failed_originals_and_retry_keeps_completed_siblings(signed, monkeypatch):
    client, service, _, model = signed
    root, run, _ = start(client, "Explain the fictional foundation's available records and remaining gaps.")
    identifiers, hashes, review_calls, extraction_calls = [], [], [], []
    gap = "A proposed finding lacked an exact source quotation and remains unresolved."
    with service.db.session() as session:
        row = session.get(Investigation, run["id"])
        row.status, row.plan_version = "running", 1
        row.research_state = {**research.initial(research.Limits()), "admission": row.research_state["admission"]}
        documents = {}
        for index in range(3):
            identifier, sha = str(uuid4()), str(index + 1) * 64
            identifiers.append(identifier)
            hashes.append(sha)
            text = f"The fictional original {index + 1} describes a foundation record without resolving the discrepancy."
            excerpts = [{"passage": "p1", "text": text}]
            snapshot = {"excerpts": excerpts, "allow_discovery": True, "document_index": str(index),
                "reading": {"pages": None}, "page_count": None}
            if index:
                snapshot["section_review"] = {"contract": analysis.CONTRACT, "sha256": sha,
                    "coverage_fingerprint": fingerprint({"sha256": sha, "excerpts": excerpts}),
                    "summary": "The record leaves the discrepancy unresolved.", "observations": [],
                    "cross_references": [], "limitations": [gap]}
                snapshot["analysis_gaps"] = {"claims": 1}
            session.add(InvestigationSource(**scope(row), id=identifier, source_key=sha,
                kind="public_source", title=f"Fictional original {index + 1}",
                url=f"https://example.org/original-{index + 1}", sha256=sha, snapshot=snapshot))
            documents[str(index)] = {"sha256": sha, "source_ids": [identifier], "read_complete": True,
                "analysis_complete": False, "complete": False, "title": f"Fictional original {index + 1}"}
        state = {"source_ids": identifiers, "extract_index": 3, "read_index": 3,
            "items": [{"url": f"https://example.org/original-{i + 1}", "title": f"Fictional original {i + 1}"} for i in range(3)],
            "failed_extract_indices": [0], "analysed": 2, "iterative": True, "document_reads": documents}
        branch = InvestigationBranch(**scope(row), query="Review the retained fictional originals", phase="extract",
            status="queued", reason="Reconcile the available originals independently.", checkpoint=state)
        session.add(branch)
        session.commit()
        branch_id = branch.id

    async def model_response(system, user, **kwargs):
        data = json.loads(user)
        title = kwargs["response_schema"]["title"]
        if title == "DocumentReview":
            identifier = data["sections"][0]["source_id"]
            review_calls.append(identifier)
            if identifier == identifiers[1] and review_calls.count(identifier) == 1:
                raise RuntimeError("The fictional model cannot currently review this original.")
            return json.dumps({"coverage_fingerprint": data["coverage_fingerprint"], "findings": [],
                "cross_reference_checks": [], "limitations": []})
        if title == "Reflection":
            return json.dumps({"gaps": [], "outcome": "Available records were considered; named discrepancies remain unresolved."})
        assert data.get("document_section"), title
        extraction_calls.append(data["source"]["id"])
        return json.dumps({"claims": [], "entities": [], "relationships": [],
            "section_review": {"coverage_fingerprint": data["document_section"]["coverage_fingerprint"],
                "summary": "This original leaves the discrepancy unresolved.", "observations": [],
                "cross_references": [], "limitations": []}})

    monkeypatch.setattr(model, "complete", model_response)
    failed = complete(client, service, root, run)
    assert failed["status"] == "failed" and "2 were read" in failed["stop_reason"]
    assert review_calls == identifiers[1:] and extraction_calls == []
    with service.db.session() as session:
        saved = session.get(InvestigationBranch, branch_id)
        docs = saved.checkpoint["document_reads"]
        assert saved.phase == "reflect" and saved.status == "failed"
        assert not docs["0"]["analysis_complete"] and docs["1"]["review_failed"]
        assert docs["2"]["complete"] and gap in docs["2"]["reconciliation"]["limitations"]
        before = docs["2"]["reconciliation"]
        steps = saved.checkpoint["steps"]
        failed_review = next(s for s in steps if s["phase"] == "document_review" and s["document_index"] == "1")
        assert failed_review["status"] == "unavailable" and not failed_review.get("recovered_by")
    retry = post(client, root + "/" + run["id"] + "/control", {"action": "retry", "expected_revision": failed["revision"]})
    assert retry.status_code == 200, retry.text
    result = complete(client, service, root, retry.json())
    assert result["status"] == "completed", result["stop_reason"]
    assert extraction_calls == [identifiers[0]]
    assert review_calls == [identifiers[1], identifiers[2], identifiers[0], identifiers[1]]
    with service.db.session() as session:
        saved = session.get(InvestigationBranch, branch_id).checkpoint
        assert all(doc["complete"] for doc in saved["document_reads"].values())
        assert saved["document_reads"]["2"]["reconciliation"] == before
        assert gap in saved["document_reads"]["1"]["reconciliation"]["limitations"]
        recovered = next(s for s in saved["steps"] if s["id"] == failed_review["id"])
        matching = next(s for s in saved["steps"] if s["id"] == recovered["recovered_by"])
        assert matching["document_index"] == "1" and matching["status"] == "completed"


def test_interrupted_review_only_marks_its_persisted_original():
    state = {"review_document_index": "1", "source_ids": ["a", "b", "c"], "extract_index": 3,
        "read_index": 3, "items": [{}, {}, {}], "failed_extract_indices": [0], "analysed": 2,
        "document_reads": {str(i): {"source_ids": [identifier], "read_complete": True, "complete": False}
            for i, identifier in enumerate(["a", "b", "c"])}}
    branch = SimpleNamespace(phase="document_review", status="running", checkpoint=state)
    advance(branch, state, interrupted=True)
    settle(branch, state)
    assert state["document_reads"]["1"]["review_failed"]
    assert not state["document_reads"]["0"].get("review_failed")
    assert not state["document_reads"]["2"].get("review_failed")
    assert state["failed_extract_indices"] == [0]
    assert branch.status == "running" and branch.phase == "document_review"
    assert analysis.next_document(state)[0] == "2"


def test_unreadable_pages_cannot_be_hidden_by_a_completed_sibling():
    state = {"source_ids": ["a", "b"], "extract_index": 2, "read_index": 2, "items": [{}, {}],
        "analysed": 2, "document_reads": {
            "0": {"source_ids": ["a"], "read_complete": False, "complete": False,
                "warnings": ["A fictional scanned page could not be read."]},
            "1": {"source_ids": ["b"], "read_complete": True, "analysis_complete": True, "complete": True}}}
    branch = SimpleNamespace(phase="extract", status="running", checkpoint=state)
    settle(branch, state)
    assert branch.status == "failed"
    assert not state["document_reads"]["0"]["complete"] and state["document_reads"]["1"]["complete"]
    assert not analysis.ready_to_review(state)


def test_resumed_earlier_read_skips_completed_siblings_without_resetting_them():
    completed = {"source_ids": ["b"], "read_complete": True, "analysis_complete": True,
        "complete": True, "next_cursor": None, "reconciliation": {"limitations": ["Unresolved discrepancy."]}}
    state = {"source_ids": ["a", "b"], "extract_index": 2, "read_index": 1, "items": [{}, {}],
        "analysed": 2, "document_reads": {
            "0": {"source_ids": ["a"], "read_complete": True, "analysis_complete": False, "complete": False},
            "1": completed}}
    branch = SimpleNamespace(phase="read", status="running", checkpoint=state)
    settle(branch, state)
    assert state["read_index"] == 2 and branch.phase == "document_review"
    assert analysis.next_document(state)[0] == "0"
    assert completed["complete"] and completed["analysis_complete"]
    assert completed["reconciliation"]["limitations"] == ["Unresolved discrepancy."]
