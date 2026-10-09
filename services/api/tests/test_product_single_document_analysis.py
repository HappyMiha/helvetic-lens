"""A complete one-batch original needs one grounded analysis, with current rights."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_product_dossiers import signed as signed
from test_product_investigations import start, tick

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens.product_document_reading import projection
from helvetic_lens.product_exploration import sources as visible_sources
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigation_worker import settle
from helvetic_lens.product_investigations import scope
from helvetic_lens.product_models import DossierEntry

QUOTE = "The fictional foundation awarded a grant of 100 units."
CONDITION = "Payment remains conditional on the recipient submitting its receipt."
GAP = "The original does not say whether the receipt was submitted."


def seed(signed):
    client, service, _, _ = signed
    _, result, _ = start(client, "Was the fictional foundation grant actually paid?")
    with service.db.session() as session:
        run = session.get(Investigation, result["id"])
        run.status, run.plan_version = "running", 1
        source = InvestigationSource(**scope(run), source_key="a" * 64, kind="public_source",
            title="Fictional grant announcement", url="https://example.org/fictional-grant", sha256="a" * 64,
            snapshot={"allow_discovery": True, "document_index": "0", "page_count": None,
                "excerpts": [{"passage": "p1", "text": QUOTE}, {"passage": "p2", "text": CONDITION}],
                "reading": {"contract": "document-reading/v1", "cursor": {"page": 0, "offset": 0},
                    "next_cursor": None, "complete": True, "pages": None,
                    "characters_read": len(QUOTE) + len(CONDITION)}, "analysis_completed": True})
        session.add(source)
        session.flush()
        work = {"input": {"question": run.question, "source": {"id": source.id}}}
        analysis.prepare_section(work, source)
        review = analysis.SectionReview.model_validate({
            "coverage_fingerprint": work["input"]["document_section"]["coverage_fingerprint"],
            "summary": "A grant was awarded, but payment remains conditional.",
            "observations": [{"statement": "The award does not establish that payment occurred.",
                "role": "context", "quote": QUOTE, "locator": "p1", "context_anchors": [
                    {"kind": "condition", "quote": CONDITION, "locator": "p2"}]}],
            "cross_references": [], "limitations": [GAP]})
        source.snapshot = {**source.snapshot,
            "section_review": analysis.validate_section(source, work, SimpleNamespace(section_review=review))}
        state = {"source_ids": [source.id], "extract_index": 1, "read_index": 1, "analysed": 1,
            "items": [{"title": source.title, "url": source.url}], "steps": [],
            "document_reads": {"0": {"title": source.title, "url": source.url, "sha256": source.sha256,
                "source_ids": [source.id], "read_complete": True, "analysis_complete": False,
                "complete": False, "next_cursor": None, "warnings": [], "portions": 1,
                "characters_read": len(QUOTE) + len(CONDITION)}}}
        branch = InvestigationBranch(**scope(run), query=run.question, phase="extract", status="queued",
            reason="Read the complete original.", checkpoint=state)
        session.add(branch)
        session.commit()
        return service, run.id, branch.id, source.id


def records(session, identifiers):
    _, run_id, branch_id, source_id = identifiers
    return (session.get(Investigation, run_id), session.get(InvestigationBranch, branch_id),
        session.get(InvestigationSource, source_id))


@pytest.mark.parametrize("obsolete_failure", [False, True])
def test_one_complete_analysis_finishes_without_another_model_call(signed, obsolete_failure):
    identifiers = seed(signed)
    service, model = identifiers[0], signed[3]
    before = len(model.calls), len(service.fetcher.calls)
    with service.db.session() as session:
        run, branch, source = records(session, identifiers)
        state = deepcopy(branch.checkpoint)
        if obsolete_failure:
            state["document_reads"]["0"]["review_failed"] = True
        assert analysis.refresh_single_document_analysis(session, run, state)
        doc = state["document_reads"]["0"]
        assert doc["complete"] and doc["analysis_complete"] and doc["sections_analysed"] == 1
        assert not doc.get("review_failed") and not doc.get("unread_reason")
        assert doc["reconciliation"]["contract"] == analysis.SINGLE_DOCUMENT_CONTRACT
        assert doc["reconciliation"]["limitations"] == [GAP]
        assert doc["reconciliation"]["findings"][0]["source_id"] == source.id
        settle(branch, state)
        assert branch.status == "completed" and branch.phase != "document_review"
        assert not any(step["phase"] == "document_review" for step in state["steps"])
        assert not analysis.refresh_single_document_analysis(session, run, state)
    assert (len(model.calls), len(service.fetcher.calls)) == before


def test_one_pass_findings_keep_original_conditions_and_current_reading_context(signed, monkeypatch):
    identifiers = seed(signed)
    with identifiers[0].db.session() as session:
        run, branch, source = records(session, identifiers)
        state = deepcopy(branch.checkpoint)
        analysis.refresh_single_document_analysis(session, run, state)
        branch.checkpoint = state
        point = state["document_reads"]["0"]["reconciliation"]["findings"][0]
        assert point["quote"] == QUOTE and point["context_anchors"] == [
            {"source_id": source.id, "kind": "condition", "quote": CONDITION, "locator": "p2"}]
        assert analysis.current_document_reading(session, run, branch, "0", state["document_reads"]["0"],
            visible_sources(session, run))
        compact = analysis.compact_sources(session, run, [source])
        notes = compact[0]["reading_context"]["notes"]
        note = next(item for item in notes if item["level"] == "document")
        assert note["original"]["quote"] == QUOTE and note["original"]["source_id"] == source.id
        assert note["anchors"][0]["quote"] == CONDITION
        assert note["anchors"][0]["source_id"] == source.id
        # Saved reading already has this current authorization-filtered map.
        # Projecting each document must not reload the run's full originals.
        available = visible_sources(session, run)
        def no_reload(*args, **kwargs):
            raise AssertionError("Saved reading loaded all originals again")
        monkeypatch.setattr("helvetic_lens.product_exploration.sources", no_reload)
        assert projection(state, session, run, available=available)[0]["complete"]


def test_worker_recovers_obsolete_review_failure_using_the_saved_analysis(signed, monkeypatch):
    identifiers = seed(signed)
    service = identifiers[0]
    with service.db.session() as session:
        _, branch, _ = records(session, identifiers)
        state = deepcopy(branch.checkpoint)
        state["document_reads"]["0"]["review_failed"] = True
        branch.phase, branch.checkpoint = "document_review", state
        session.commit()

    async def unexpected_model_call(*args, **kwargs):
        raise AssertionError("The fully read and analysed original must not request another model call.")

    monkeypatch.setattr(signed[3], "complete", unexpected_model_call)
    before = len(service.fetcher.calls)
    tick(service, identifiers[1])
    with service.db.session() as session:
        run, branch, _ = records(session, identifiers)
        assert run.status == "completed" and branch.status == "completed"
        assert branch.checkpoint["document_reads"]["0"]["complete"]
        assert not branch.checkpoint["document_reads"]["0"].get("review_failed")
        assert not branch.checkpoint["steps"]
    assert len(service.fetcher.calls) == before


@pytest.mark.parametrize("change", ["question", "hash", "withdrawn", "excluded", "passages", "section"])
def test_stale_or_withdrawn_one_pass_completion_is_not_current_proof(signed, change):
    identifiers = seed(signed)
    with identifiers[0].db.session() as session:
        run, branch, source = records(session, identifiers)
        state = deepcopy(branch.checkpoint)
        analysis.refresh_single_document_analysis(session, run, state)
        branch.checkpoint = deepcopy(state)
        if change == "question":
            run.question = "Was the fictional grant approved for a different recipient?"
        elif change == "hash":
            source.sha256 = "b" * 64
        elif change == "withdrawn":
            source.snapshot = {**source.snapshot, "allow_discovery": False}
        elif change == "excluded":
            session.add(DossierEntry(dossier_id=run.dossier_id, kind="source_review", url=source.url,
                actor_user_id=run.created_by_user_id, request_key=str(uuid4()),
                data_json={"decision": "exclude", "revision": 1}))
        elif change == "passages":
            source.snapshot = {**source.snapshot, "excerpts": [{"passage": "p1", "text": "A corrected original."}]}
        else:
            value = deepcopy(source.snapshot)
            value["section_review"]["observations"][0]["statement"] = "An amended interpretation needs fresh proof."
            source.snapshot = value
        session.flush()
        assert not analysis.current_document_reading(session, run, branch, "0", state["document_reads"]["0"],
            visible_sources(session, run))
        projected = projection(state, session, run)[0]
        assert not projected["complete"] and not projected["analysis_complete"]
        assert state["document_reads"]["0"]["complete"]  # Reading freshness never mutates the saved receipt.


@pytest.mark.parametrize("obstacle", ["cross_reference", "multiple_batches", "incomplete", "warning", "buffer",
    "next_cursor", "later_cursor", "partial_capture", "failed_extract", "unbound_review", "unfinished_analysis"])
def test_partial_or_unverified_reading_does_not_gain_one_pass_completion(signed, obstacle):
    identifiers = seed(signed)
    with identifiers[0].db.session() as session:
        run, branch, source = records(session, identifiers)
        state = deepcopy(branch.checkpoint)
        doc = state["document_reads"]["0"]
        if obstacle == "cross_reference":
            value = deepcopy(source.snapshot)
            value["section_review"]["cross_references"] = [{"quote": QUOTE, "locator": "p1",
                "target": "The separate recipient receipt", "target_pages": []}]
            source.snapshot = value
        elif obstacle == "multiple_batches":
            doc["source_ids"].append(str(uuid4()))
        elif obstacle == "incomplete":
            doc["read_complete"] = False
        elif obstacle == "warning":
            doc["warnings"] = ["An original page was unreadable."]
        elif obstacle == "buffer":
            doc["buffer"] = {"excerpts": [{"passage": "p3", "text": "A pending original paragraph."}]}
        elif obstacle == "next_cursor":
            doc["next_cursor"] = {"page": 1, "offset": 0}
        elif obstacle in {"later_cursor", "partial_capture"}:
            value = deepcopy(source.snapshot)
            value["reading"].update({"cursor": {"page": 1, "offset": 0}} if obstacle == "later_cursor"
                else {"complete": False})
            source.snapshot = value
        elif obstacle == "failed_extract":
            state["failed_extract_indices"] = [0]
        elif obstacle == "unbound_review":
            value = deepcopy(source.snapshot)
            value["section_review"].pop("reading_binding")
            source.snapshot = value
        else:
            source.snapshot = {**source.snapshot, "analysis_completed": False}
        analysis.refresh_single_document_analysis(session, run, state)
        assert not doc["complete"] and not doc["analysis_complete"]
        assert "reconciliation" not in doc


def test_duplicate_reuses_current_one_pass_original_without_fabricating_review_execution(signed):
    identifiers = seed(signed)
    with identifiers[0].db.session() as session:
        run, canonical, source = records(session, identifiers)
        state = deepcopy(canonical.checkpoint)
        analysis.refresh_single_document_analysis(session, run, state)
        canonical.checkpoint = state
        before = deepcopy(state)
        duplicate = InvestigationSource(**scope(run), source_key="b" * 64, kind="public_source",
            title=source.title, url=source.url + "?alias=1", sha256=source.sha256,
            snapshot={**deepcopy(source.snapshot), "duplicate_of": source.id})
        duplicate.snapshot.pop("section_review")
        duplicate.snapshot.pop("analysis_completed")
        session.add(duplicate)
        session.flush()
        alias = {"source_ids": [], "extract_index": 0, "read_index": 1, "items": [{}], "unchanged": 1,
            "document_reads": {"0": {"sha256": source.sha256, "source_ids": [duplicate.id],
                "read_complete": True, "analysis_complete": False, "complete": False}}}
        assert analysis.refresh_duplicate_analysis(session, run, alias)
        doc = alias["document_reads"]["0"]
        assert doc["complete"] and doc["source_ids"] == [duplicate.id]
        assert doc["reconciliation"]["findings"][0]["source_id"] == source.id
        assert doc["reconciliation"] == state["document_reads"]["0"]["reconciliation"]
        assert canonical.checkpoint == before and not before["steps"]
        source.snapshot = {**source.snapshot, "allow_discovery": False}
        assert not projection(alias, session, run)[0]["complete"]
