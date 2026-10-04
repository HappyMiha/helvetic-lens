"""Literal source identity never substitutes for current whole-reading proof."""
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_product_dossiers import signed as signed
from test_product_investigations import start

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens import product_requested_originals as requested
from helvetic_lens import product_source_requirements as ledger
from helvetic_lens import research_knowledge as knowledge
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_investigations import scope, snapshot
from helvetic_lens.product_models import DossierEntry
from helvetic_lens.product_operations import fingerprint

QUESTION = "Which rules apply? Read the Archive terms and the Archive access policy."
SPAN = "the Archive terms"
SECOND = "the Archive access policy"
URL = "https://example.org/archive-terms"
IDENTITY = "Archive terms and access policy, issued by the Archive Board for its deposits."


def match(run, source, requirement, *, locator="p1", quote=IDENTITY):
    return {"contract": requested.MATCH_CONTRACT, "question_fingerprint": fingerprint(run.question),
        "requirement_id": requirement["id"], "requested_source": requirement["requested_source"],
        "identity": {"source_id": source.id, "sha256": source.sha256, "locator": locator, "quote": quote}}


def complete(session, run, branch, sources):
    state = deepcopy(branch.checkpoint)
    state["document_reads"] = {"0": {"sha256": sources[0].sha256, "source_ids": [s.id for s in sources],
        "url": URL, "read_complete": True, "analysis_complete": False, "complete": False, "next_cursor": None}}
    work = {"query": branch.query}
    analysis.prepare(session, run, state, work)
    analysis.apply(session, run, state, work, analysis.DocumentReview.model_validate({
        "coverage_fingerprint": work["input"]["coverage_fingerprint"],
        "findings": [], "cross_reference_checks": [], "limitations": []}))
    state["steps"] = [{"phase": "document_review", "document_index": "0", "status": "completed",
        "execution": {"input_fingerprint": fingerprint({"input": work["input"], "query": work["query"]})}}]
    branch.checkpoint = state


def seed(signed, *, portions=1, direct=False):
    client, service, _, _ = signed
    question = f"Which rules apply? Read {URL}." if direct else QUESTION
    _, result, _ = start(client, question)
    with service.db.session() as session:
        run = session.get(Investigation, result["id"])
        owner_id, reading_id = str(uuid4()), str(uuid4())
        branch = InvestigationBranch(**scope(run), query="Archive original", phase="reflect", status="completed",
            reason="Read the complete original.", checkpoint={"question_id": reading_id})
        session.add(branch)
        session.flush()
        run.research_state = {**run.research_state, "questions": [
            {"id": owner_id, "branch_id": None}, {"id": reading_id, "branch_id": branch.id}]}
        ledger.attach(run, owner_id, [URL] if direct else [SPAN, SECOND])
        sources = []
        for index in range(portions):
            quote = IDENTITY if not index else "Later operative text qualifies the complete archive rule."
            excerpts = [{"passage": f"p{index + 1}", "text": quote}]
            value = {"status": "complete", "url": URL, "title": "Archive terms", "sha256": "a" * 64,
                "excerpts": excerpts, "allow_discovery": True, "document_index": "0", "branch_id": branch.id,
                "reading": {"contract": "document-reading/v1", "cursor": {"page": index, "offset": 0},
                    "next_cursor": {"page": index + 1, "offset": 0} if index + 1 < portions else None,
                    "complete": index + 1 == portions, "pages": None, "characters_read": len(quote)}}
            source, _ = snapshot(session, run, value, public=True)
            source.snapshot = {**source.snapshot, "section_review": {"contract": analysis.CONTRACT,
                "sha256": source.sha256, "coverage_fingerprint": fingerprint({"sha256": source.sha256, "excerpts": excerpts}),
                "summary": "The supplied section was read.", "observations": [],
                "cross_references": [], "limitations": []}}
            sources.append(source)
        if not direct:
            sources[0].snapshot = {**sources[0].snapshot, "requested_source_matches": [
                match(run, sources[0], requirement) for requirement in ledger.requirements(run)]}
        complete(session, run, branch, sources)
        if direct:
            state = deepcopy(branch.checkpoint)
            state["items"] = [{"url": URL, "provider": "Search engine", "submitted_public_source": True}]
            state["steps"] += [{"phase": "read", "source_url": URL, "source_id": sources[0].id, "status": "completed"}]
            branch.checkpoint = state
        session.commit()
        return service, run.id, branch.id, [s.id for s in sources], owner_id


def test_plural_requirements_resolve_complete_original_from_another_branch_without_mutation(signed):
    service, run_id, branch_id, source_ids, owner_id = seed(signed, portions=2)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branch_id)
        sources = [session.get(InvestigationSource, identifier) for identifier in source_ids]
        before = deepcopy(run.research_state), deepcopy(branch.checkpoint), [deepcopy(s.snapshot) for s in sources]
        values = requested.outcomes(session, run, owner_id)
        assert [v["requested_source"] for v in values] == [SPAN, SECOND]
        assert all(v["status"] == "matched_read" and v["identity_basis"] == "quoted_match" for v in values)
        assert all(v["read_complete"] and v["analysis_complete"] for v in values)
        assert requested.outcomes(session, run, "unowned") == []
        serial = json.dumps(values)
        assert all(value not in serial for value in [IDENTITY, "a" * 64, *source_ids, "snapshot_fingerprint"])
        assert (run.research_state, branch.checkpoint, [s.snapshot for s in sources]) == before
        assert not session.dirty and not session.new and not session.deleted


@pytest.mark.parametrize("fault,expected", [
    ("no_ledger", None), ("no_match", "not_identified"), ("old_source_class", "not_identified"),
    ("changed_question", None), ("stale_match", "not_identified"), ("fabricated_quote", "not_identified"),
    ("wrong_requirement", "not_identified"), ("wrong_contract", "not_identified"),
    ("withdrawn", "not_identified"), ("private", "not_identified"), ("excluded", "not_identified"),
    ("foreign_org", "not_identified"), ("foreign_dossier", "not_identified"),
    ("missing_document", "reading_incomplete"), ("partial", "reading_incomplete"),
    ("changed_other_portion", "analysis_incomplete"), ("analysis_failed", "analysis_incomplete"),
])
def test_match_and_execution_failures_remain_distinct_and_revocable(signed, fault, expected):
    service, run_id, branch_id, source_ids, _ = seed(signed, portions=2)
    with service.db.session() as session, session.no_autoflush:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branch_id)
        first, later = [session.get(InvestigationSource, identifier) for identifier in source_ids]
        if fault == "no_ledger":
            run.research_state = {**run.research_state, "questions": []}
        elif fault == "changed_question":
            run.question += " Address the revised scope."
        elif fault in {"no_match", "old_source_class"}:
            first.snapshot = {**first.snapshot, "requested_source_matches": []}
            if fault == "old_source_class":
                first.snapshot["source_class"] = {"category": "primary", "requested_source": SPAN,
                    "original_question": run.question, "source_id": first.id, "sha256": first.sha256,
                    "locator": "p1", "quote": IDENTITY}
        elif fault in {"stale_match", "fabricated_quote", "wrong_requirement", "wrong_contract"}:
            data = deepcopy(first.snapshot)
            for value in data["requested_source_matches"]:
                if fault == "fabricated_quote":
                    value["identity"]["quote"] = "An invented identity."
                else:
                    value[{"stale_match": "question_fingerprint", "wrong_requirement": "requirement_id",
                        "wrong_contract": "contract"}[fault]] = "not-current"
            first.snapshot = data
        elif fault == "withdrawn":
            first.snapshot = {**first.snapshot, "allow_discovery": False}
        elif fault == "private":
            first.kind = "uploaded_file"
        elif fault in {"foreign_org", "foreign_dossier"}:
            setattr(first, "organization_id" if fault == "foreign_org" else "dossier_id", str(uuid4()))
        elif fault == "excluded":
            session.add(DossierEntry(dossier_id=run.dossier_id, kind="source_review", request_key=str(uuid4()),
                url=URL, body="Exclude this original.", data_json={"decision": "exclude", "revision": 1}))
            session.flush()
        else:
            state = deepcopy(branch.checkpoint)
            if fault == "missing_document":
                state.pop("document_reads")
            elif fault == "partial":
                state["document_reads"]["0"].update(read_complete=False, complete=False)
            elif fault == "changed_other_portion":
                later.snapshot = {**later.snapshot, "excerpts": [{"passage": "p2", "text": "Changed original."}]}
            else:
                state["document_reads"]["0"].update(analysis_complete=False, complete=False, review_failed=True)
            branch.checkpoint = state
        values = requested.outcomes(session, run)
        assert [v["status"] for v in values] == ([] if expected is None else [expected, expected])


@pytest.mark.parametrize("fault", [None, "not_submitted", "not_read", "failed", "skipped", "excluded"])
def test_direct_url_requires_actual_admitted_read_provenance(signed, fault):
    service, run_id, branch_id, source_ids, _ = seed(signed, direct=True)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branch_id)
        state = deepcopy(branch.checkpoint)
        if fault == "not_submitted":
            state["items"][0].pop("submitted_public_source")
        elif fault == "not_read":
            state["steps"].pop()
        elif fault in {"failed", "skipped"}:
            state["steps"][-1].update(status="unavailable", source_id=None)
            if fault == "skipped":
                state["steps"][-1]["skipped"] = True
        elif fault == "excluded":
            session.add(DossierEntry(dossier_id=run.dossier_id, kind="source_review", request_key=str(uuid4()),
                url=URL, body="Exclude this original.", data_json={"decision": "exclude", "revision": 1}))
        branch.checkpoint = state
        session.flush()
        value = requested.outcomes(session, run)[0]
        assert value["status"] == ("matched_read" if fault is None else
            "acquisition_unavailable" if fault == "failed" else "not_identified")
        assert source_ids[0] not in json.dumps(value)


@pytest.mark.parametrize("fault", [None, "missing_portion", "origin_withdrawn", "changed_pin", "changed_question", "no_old_analysis"])
def test_recalled_identity_requires_exact_lineage_and_every_current_original_portion(signed, fault):
    service, origin_run_id, branch_id, source_ids, _ = seed(signed, portions=2)
    with service.db.session() as session:
        previous = session.get(Investigation, origin_run_id)
        previous.status = "completed"
        run = Investigation(organization_id=previous.organization_id, dossier_id=previous.dossier_id,
            request_key=str(uuid4()), question=previous.question, status="queued", research_state={
                "questions": [{"id": "current-owner", "branch_id": None}]})
        session.add(run)
        session.flush()
        ledger.attach(run, "current-owner", [SPAN, SECOND])
        origins = [session.get(InvestigationSource, identifier) for identifier in source_ids]
        if fault == "no_old_analysis":
            branch = session.get(InvestigationBranch, branch_id)
            state = deepcopy(branch.checkpoint)
            state["document_reads"]["0"].update(complete=False, analysis_complete=False)
            branch.checkpoint = state
        copies = []
        for origin in origins[:1] if fault == "missing_portion" else origins:
            copy, _ = snapshot(session, run, {**deepcopy(origin.snapshot), "url": origin.url, "title": origin.title,
                "sha256": origin.sha256, "key": "retained:" + origin.id,
                "retained_origin": knowledge.origin_pin(origin)}, public=True)
            copies.append(copy)
        if fault == "origin_withdrawn":
            origins[0].snapshot = {**origins[0].snapshot, "allow_discovery": False}
        elif fault == "changed_pin":
            copies[0].snapshot = {**copies[0].snapshot, "retained_origin": {"source_id": origins[0].id}}
        elif fault == "changed_question":
            previous.question += " A different old analysis question."
        session.commit()
        before = [deepcopy(s.snapshot) for s in [*origins, *copies]]
        values = requested.outcomes(session, run)
        expected = ("matched_read" if fault is None else "not_identified" if fault in {
            "origin_withdrawn", "changed_pin"} else "analysis_incomplete" if fault == "no_old_analysis" else "reading_incomplete")
        assert [v["status"] for v in values] == [expected, expected]
        assert [s.snapshot for s in [*origins, *copies]] == before
        assert not session.dirty and not session.new and not session.deleted


@pytest.mark.parametrize("fault", [None, "cycle", "unavailable_canonical"])
def test_direct_duplicate_uses_current_canonical_analysis_not_equal_hash(signed, fault):
    service, run_id, branch_id, source_ids, _ = seed(signed, direct=True)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        canonical = session.get(InvestigationSource, source_ids[0])
        branch = session.get(InvestigationBranch, branch_id)
        alias, _ = snapshot(session, run, {**deepcopy(canonical.snapshot), "url": URL,
            "sha256": canonical.sha256, "key": "duplicate", "duplicate_of": canonical.id}, public=True)
        alias_branch = InvestigationBranch(**scope(run), query="Another route to the original", phase="extract",
            reason="Read the submitted URL.", status="completed", checkpoint={"question_id": "alias-owner",
                "items": [{"url": URL, "submitted_public_source": True}],
                "steps": [{"phase": "read", "source_url": URL, "source_id": alias.id, "status": "completed"}],
                "document_reads": {"0": {"source_ids": [alias.id], "sha256": alias.sha256, "read_complete": True}}})
        session.add(alias_branch)
        session.flush()
        run.research_state = {**run.research_state, "questions": [*run.research_state["questions"],
            {"id": "alias-owner", "branch_id": alias_branch.id}]}
        # Only the actual submitted alias read supplies direct acquisition provenance.
        state = deepcopy(branch.checkpoint)
        state.pop("items")
        branch.checkpoint = state
        if fault == "cycle":
            canonical.snapshot = {**canonical.snapshot, "duplicate_of": alias.id}
        elif fault == "unavailable_canonical":
            canonical.snapshot = {**canonical.snapshot, "allow_discovery": False}
        session.commit()
        value = requested.outcomes(session, run)[0]
        assert value["status"] == ("matched_read" if fault is None else "reading_incomplete")


def test_fresh_retained_capture_discards_old_identity_notes_before_current_analysis(signed):
    service, run_id, _, source_ids, _ = seed(signed)
    with service.db.session() as session:
        previous = session.get(Investigation, run_id)
        previous.status = "completed"
        run = Investigation(organization_id=previous.organization_id, dossier_id=previous.dossier_id,
            request_key=str(uuid4()), question=previous.question, status="queued", research_state={
                "questions": [], "core": {"recall": {"origin_pins": []}}})
        session.add(run)
        session.flush()
        source = session.get(InvestigationSource, source_ids[0])
        before = deepcopy(source.snapshot)
        work = {"research": True, "document_cursor": {"page": 0, "offset": 0},
            "item": {"url": URL, "title": "Archive terms"}}
        knowledge.prepare_capture(session, run, {"question_id": "current-owner"}, work)
        assert work["retained_capture"]["excerpts"] == before["excerpts"]
        assert "requested_source_matches" not in work["retained_capture"]
        assert "section_review" not in work["retained_capture"]
        assert work["retained_capture"]["retained_origin"] == knowledge.origin_pin(source)
        assert source.snapshot == before and before["requested_source_matches"]


def test_bibliography_quote_cannot_identify_the_current_document():
    source = SimpleNamespace(id=str(uuid4()), sha256="a" * 64, url=URL, snapshot={"excerpts": [
        {"passage": "page-9-text-1", "text": "References"},
        {"passage": "page-9-text-2", "text": "Smith, A., Archive terms, Journal of Archives, 4, 12–19, 2021."},
        {"passage": "page-9-text-3", "text": "Jones, B., Archive standards, Journal of Archives, 3, 10–19, 2020."}]})
    requirement = {"id": ledger.identifier(QUESTION, SPAN), "requested_source": SPAN}
    value = match(SimpleNamespace(question=QUESTION), source, requirement,
        locator="page-9-text-2", quote=source.snapshot["excerpts"][1]["text"])
    assert not requested.valid_match(value, source, requirement, QUESTION)


def test_retained_direct_url_reuses_actual_submitted_read_without_creating_identity_notes(signed):
    service, run_id, branch_id, source_ids, _ = seed(signed, direct=True)
    with service.db.session() as session:
        previous = session.get(Investigation, run_id)
        previous.status = "completed"
        run = Investigation(organization_id=previous.organization_id, dossier_id=previous.dossier_id,
            request_key=str(uuid4()), question=previous.question, status="queued", research_state={
                "questions": [{"id": "current-owner", "branch_id": None}]})
        session.add(run)
        session.flush()
        ledger.attach(run, "current-owner", [URL])
        origin = session.get(InvestigationSource, source_ids[0])
        copy, _ = snapshot(session, run, {**deepcopy(origin.snapshot), "url": origin.url,
            "sha256": origin.sha256, "key": "retained:" + origin.id,
            "retained_origin": knowledge.origin_pin(origin)}, public=True)
        session.commit()
        assert not copy.snapshot.get("requested_source_matches")
        value = requested.outcomes(session, run)[0]
        assert value["status"] == "matched_read" and value["identity_basis"] == "submitted_url"
        branch = session.get(InvestigationBranch, branch_id)
        state = deepcopy(branch.checkpoint)
        state.pop("items")
        branch.checkpoint = state
        assert requested.outcomes(session, run)[0]["status"] == "not_identified"
