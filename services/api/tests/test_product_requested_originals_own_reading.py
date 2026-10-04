"""A document's own current analysis survives mixed duplicate capture portions."""
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_requested_originals import URL, complete, seed
from test_product_requested_originals import signed as signed

from helvetic_lens import product_document_analysis as analysis
from helvetic_lens import product_exploration as exploration
from helvetic_lens import product_requested_originals as requested
from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
from helvetic_lens.product_models import DossierEntry


def mixed_document(signed):
    service, run_id, branch_id, source_ids, owner_id = seed(signed, portions=2)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branch_id)
        sources = [session.get(InvestigationSource, identifier) for identifier in source_ids]
        sources[1].snapshot = {**sources[1].snapshot, "duplicate_of": sources[0].id}
        # Ordinary whole-document reconciliation binds the actual current
        # section snapshots, including their existing duplicate metadata.
        complete(session, run, branch, sources)
        state = deepcopy(branch.checkpoint)
        state["steps"].append({"phase": "reflect", "status": "interrupted"})
        branch.status, branch.checkpoint = "failed", state
        session.commit()
    return service, run_id, branch_id, source_ids, owner_id


def test_own_bound_whole_reading_resolves_mixed_duplicate_original_without_widening_visibility(signed):
    service, run_id, branch_id, source_ids, owner_id = mixed_document(signed)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branch_id)
        sources = {identifier: session.get(InvestigationSource, identifier) for identifier in source_ids}
        doc = branch.checkpoint["document_reads"]["0"]
        before = deepcopy(branch.checkpoint), [deepcopy(s.snapshot) for s in sources.values()]
        assert analysis.current_document_reading(session, run, branch, "0", doc, sources)
        # No wholly visible canonical document can lend a receipt. Own reading
        # is what distinguishes this case from an unanalysed duplicate alias.
        assert analysis.duplicate_analysis(session, run, doc) is None
        assert source_ids[1] not in exploration.sources(session, run)
        values = requested.outcomes(session, run, owner_id)
        assert len(values) == 2
        assert all(v["status"] == "matched_read" and v["read_complete"] and v["analysis_complete"] for v in values)
        assert (branch.checkpoint, [s.snapshot for s in sources.values()]) == before
        assert source_ids[1] not in exploration.sources(session, run)
        assert not session.dirty and not session.new and not session.deleted


@pytest.mark.parametrize("fault", ["changed_hash", "changed_text", "excluded", "withdrawn", "warning",
    "unfinished", "changed_question", "changed_reconciliation"])
def test_own_duplicate_reading_requires_every_current_authorized_portion_and_bound_analysis(signed, fault):
    service, run_id, branch_id, source_ids, owner_id = mixed_document(signed)
    with service.db.session() as session:
        run = session.get(Investigation, run_id)
        branch = session.get(InvestigationBranch, branch_id)
        later = session.get(InvestigationSource, source_ids[1])
        state = deepcopy(branch.checkpoint)
        doc = state["document_reads"]["0"]
        if fault == "changed_hash":
            later.sha256 = "b" * 64
        elif fault == "changed_text":
            later.snapshot = {**later.snapshot, "excerpts": [{"passage": "p2", "text": "Revised conditions."}]}
        elif fault == "excluded":
            session.add(DossierEntry(dossier_id=run.dossier_id, kind="source_review", request_key=str(uuid4()),
                url=URL, body="Exclude this original.", data_json={"decision": "exclude", "revision": 1}))
        elif fault == "withdrawn":
            later.snapshot = {**later.snapshot, "allow_discovery": False}
        elif fault == "warning":
            doc["warnings"] = ["Some original pages could not be read."]
        elif fault == "unfinished":
            doc.update(complete=False, analysis_complete=False)
        elif fault == "changed_question":
            doc["reading_context_binding"]["question"] += " A different investigation."
        else:
            doc["reconciliation"]["limitations"] = ["A changed unvalidated review."]
        branch.checkpoint = state
        session.flush()
        values = requested.outcomes(session, run, owner_id)
        assert len(values) == 2
        assert all(v["status"] != "matched_read" and not v.get("analysis_complete") for v in values)
