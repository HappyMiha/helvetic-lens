"""Dense neutral originals, real worker resumption, and original-quote fences."""
import json
from uuid import uuid4

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_investigations import start, tick

from helvetic_lens.config import DomainError
from helvetic_lens.product_document_analysis import CONTRACT
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_operations import fingerprint

EARLY = "The fictional foundation reported a grant of 100 units."
LATE = "The fictional recipient reported receiving 80 units; the discrepancy remains unresolved."


def test_dense_original_reconciles_all_sections_and_targets_and_resumes_failed_merge(signed, monkeypatch):
    client, service, _, model = signed
    root, run, _ = start(client, "Explain the fictional foundation grant discrepancy.")
    seen_sections, seen_targets, calls, rejected = set(), set(), [], [False]
    source_ids = []
    original_hash = "a" * 64
    with service.db.session() as session:
        row = session.get(Investigation, run["id"])
        row.status, row.plan_version = "running", 1
        row.research_state = {"admission": row.research_state["admission"]}
        for index in range(24):
            identifier = str(uuid4())
            source_ids.append(identifier)
            text = EARLY if index == 0 else LATE if index == 23 else "The fictional appendix provides administrative background."
            excerpts = [{"passage": f"page-{index + 1}-text-1", "text": text}]
            if index == 23:
                excerpts += [{"passage": f"page-24-text-{j + 2}", "text": "Fictional target-page background. " * 36} for j in range(180)]
                excerpts.append({"passage": "page-24-text-183", "text": LATE})
            review = {"contract": CONTRACT, "sha256": original_hash,
                "coverage_fingerprint": fingerprint({"sha256": original_hash, "excerpts": excerpts}),
                "summary": "A section of the fictional original. " * 35,
                "observations": [{"statement": "Fictional administrative detail. " * 20,
                    "role": "support" if index == 0 else "counterevidence" if index == 23 else "context",
                    "quote": text, "locator": excerpts[0]["passage"]} for _ in range(16)],
                "limitations": ["The original does not identify the missing receipt."] if index == 7 else [], "cross_references": []}
            if index == 0:
                review["cross_references"] = [{"target": "recipient statement", "target_pages": [24],
                    "quote": EARLY, "locator": excerpts[0]["passage"]}]
            source = InvestigationSource(**scope(row), id=identifier, source_key=f"{index:064x}",
                kind="public_source", title="Fictional original", url="https://example.org/fictional-original.pdf",
                sha256=original_hash, snapshot={"excerpts": excerpts, "allow_discovery": True,
                    "reading": {"pages": [index + 1, index + 1]}, "page_count": 24,
                    "section_review": review, "document_index": "0"})
            session.add(source)
        session.flush()
        state = {"source_ids": source_ids, "extract_index": len(source_ids), "read_index": 1,
            "items": [{"url": "https://example.org/fictional-original.pdf", "title": "Fictional original"}], "analysed": len(source_ids),
            "document_reads": {"0": {"sha256": original_hash, "source_ids": source_ids, "read_complete": True,
                "analysis_complete": False, "complete": False, "page_count": 24, "pages_read": 24}}}
        branch = InvestigationBranch(**scope(row), query="Review the complete fictional original", phase="document_review",
            status="queued", reason="All retained sections need whole-document reconciliation.", checkpoint=state)
        session.add(branch)
        session.commit()
        branch_id = branch.id

    async def model_response(system, user, **kwargs):
        data = json.loads(user)
        assert kwargs["response_schema"]["title"] == "ReviewNode"
        assert len(user) < 40000
        calls.append(data["coverage_fingerprint"])
        findings, checks = [], []
        for section in data.get("sections", []):
            seen_sections.add(section["source_id"])
            for point in section["observations"]:
                if point["role"] != "context":
                    value = {"source_id": section["source_id"], **point}
                    if value not in findings:
                        findings.append(value)
        for ref in data.get("cross_references", []):
            for target in ref["target_passages"]:
                seen_targets.add(target["passage"])
            target = next((p for p in ref["target_passages"] if p["text"] == LATE), None)
            point = None if not target else {"source_id": target["source_id"], "statement": "The recipient reports a different amount.",
                "quote": LATE, "locator": target["passage"], "role": "counterevidence"}
            checks.append({"id": ref["id"], "status": "verified" if target else "unresolved",
                "explanation": "The target states the discrepancy." if target else "The recipient amount is absent from this target portion.",
                "evidence": point})
        for node in data.get("nodes", []):
            for point in node["findings"]:
                if point not in findings:
                    findings.append(point)
        if data["kind"] == "merge" and not rejected[0]:
            rejected[0] = True
            findings = [{"source_id": source_ids[0], "statement": "An unsupported invented conclusion.",
                "quote": "This original never said this invented sentence.", "locator": "page-1-text-1", "role": "support"}]
        return json.dumps({"coverage_fingerprint": data["coverage_fingerprint"],
            "synopsis": "The foundation and recipient report different amounts; the reason remains unknown.",
            "findings": findings, "cross_reference_checks": checks, "limitations": ["The reason for the discrepancy is unknown."]})

    monkeypatch.setattr(model, "complete", model_response)
    for _ in range(65):
        tick(service, run["id"])
        result = client.get(root + "/" + run["id"]).json()
        if result["status"] not in {"queued", "running"}:
            break
    assert result["status"] == "failed" and rejected[0], result["stop_reason"]
    completed_before = calls[:-1]
    retry = post(client, root + "/" + run["id"] + "/control", {"action": "retry", "expected_revision": result["revision"]})
    assert retry.status_code == 200, retry.text
    for _ in range(65):
        tick(service, run["id"])
        result = client.get(root + "/" + run["id"]).json()
        if result["status"] not in {"queued", "running"}:
            break
    assert result["status"] == "completed", result["stop_reason"]
    assert all(calls.count(value) == 1 for value in completed_before)
    assert seen_sections == set(source_ids)
    assert len(seen_targets) == 182
    with service.db.session() as session:
        saved = session.get(InvestigationBranch, branch_id).checkpoint["document_reads"]["0"]
        assert saved["complete"] and saved["sections_analysed"] == 24
        assert saved["review_progress"]["complete"]
        review = saved["reconciliation"]
        assert review["review_nodes"] > 10
        assert {p["quote"] for p in review["findings"]} == {EARLY, LATE}
        assert review["cross_reference_checks"][0]["status"] == "verified"
        assert review["cross_reference_checks"][0]["portions_checked"] > 1
        assert "The original does not identify the missing receipt." in review["limitations"]

        from helvetic_lens.product_document_analysis import compact_sources
        from helvetic_lens.product_document_reading import model_projection, projection
        sources = [session.get(InvestigationSource, key) for key in source_ids]
        inputs = compact_sources(session, session.get(Investigation, run["id"]), sources)
        assert len(json.dumps(inputs)) < 20000
        assert {s["id"] for s in inputs} == set(source_ids)  # Every dependency remains pinned.
        # Compact originals retain neighbouring context even when only selected
        # observations survive the whole-document synopsis.
        assert {p["text"] for s in inputs for p in s["excerpts"]} == {
            EARLY, LATE, "The fictional appendix provides administrative background."}
        assert any("whole_document_review" in s for s in inputs)
        public = projection(session.get(InvestigationBranch, branch_id).checkpoint)[0]
        assert "review_tree" not in public
        assert "cross_reference_checks" not in model_projection(public)["reconciliation"]
        # Withdrawing even an uncited section invalidates the composite synopsis.
        withdrawn = compact_sources(session, session.get(Investigation, run["id"]), sources[1:])
        assert all("whole_document_review" not in s for s in withdrawn)


@pytest.mark.parametrize("status", ["verified", "unresolved"])
def test_reference_status_never_allows_an_invented_quote_into_saved_findings(status):
    from helvetic_lens.product_document_reconciliation import ReviewNode, apply

    key, source_id = "a" * 64, str(uuid4())
    doc = {"review_tree": {"basis": key, "nodes": {}}}
    work = {"review_tree_node": {"basis": key}, "input": {
        "coverage_fingerprint": key, "cross_references": [{"id": key, "target_passages": [
            {"source_id": source_id, "passage": "page-24-text-1", "text": LATE}]}]}}
    result = ReviewNode(coverage_fingerprint=key, synopsis="The reference remains uncertain.",
        cross_reference_checks=[{"id": key, "status": status, "explanation": "The wording needs interpretation.",
            "evidence": {"source_id": source_id, "locator": "page-24-text-1", "quote": "An invented sentence absent from the original.",
                "statement": "An unsupported claim.", "role": "context"}}])
    with pytest.raises(DomainError) as error:
        apply(None, None, doc, {}, work, result)
    assert error.value.status == 422
    assert doc["review_tree"]["nodes"] == {}
