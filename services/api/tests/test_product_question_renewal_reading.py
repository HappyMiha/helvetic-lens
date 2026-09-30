"""Unquoted reading limits remain dependencies, including absent optional renewal."""

from copy import deepcopy

import pytest
from test_product_dossiers import signed as signed
from test_product_iterative_research import complete
from test_product_question_renewal import configured

from helvetic_lens.product_investigation_models import Investigation, InvestigationSource


@pytest.mark.parametrize("when", ["during", "after", "after_without_renewal"])
def test_read_context_is_checked_without_a_source_hash_change(signed, monkeypatch, when):
    client, service, _, _ = signed

    def changed(data):
        with service.db.session() as session:
            source = session.get(InvestigationSource, data["sources"][0]["id"])
            snapshot = deepcopy(source.snapshot)
            snapshot["text_truncated"] = True
            source.snapshot = snapshot
            session.commit()

    root, run, _, observed, _ = configured(
        signed,
        monkeypatch,
        invalid="missing" if when == "after_without_renewal" else None,
        callback=changed if when == "during" else None,
    )
    final = complete(client, service, root + "/investigations", run)
    assert observed
    if when != "during":
        assert final["exploration"]["status"] == "ready"
        changed(observed[0])
        final = client.get(root + "/investigations/" + run["id"]).json()
        assert final["exploration"]["status"] == "evidence_changed"
    assert final["exploration"]["briefing"] is None and final["exploration"]["next_check"] is None
    if when == "during":
        with service.db.session() as session:
            saved = session.get(Investigation, run["id"])
            assert not any(q.get("branch_assessment_history") for q in saved.research_state["questions"])
