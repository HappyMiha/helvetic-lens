"""Renewed conclusions preserve the full public context and descendant fences."""

import json
from copy import deepcopy

import pytest
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_episode_progress import extra_source
from test_product_investigations import tick
from test_product_iterative_research import complete
from test_product_question_assessment import assessment_adapters
from test_product_question_renewal import configured
from test_product_saved_check import command, url

from helvetic_lens import decision_search
from helvetic_lens.product_investigation_models import (
    ClaimEvidence,
    DossierClaim,
    Investigation,
    InvestigationBranch,
    InvestigationSource,
)
from helvetic_lens.product_investigations import scope


def change(service, identity, data, kind):
    if kind == "source":
        exclude(service, identity, data["sources"][0]["id"])
        return
    with service.db.session() as session:
        branch = session.get(InvestigationBranch, data["question_renewal_targets"][0]["branch_id"])
        run = session.get(Investigation, branch.investigation_id)
        if kind == "hash":
            session.get(InvestigationSource, data["sources"][0]["id"]).sha256 = "e" * 64
        elif kind in {"claim_status", "claim_text"}:
            claim = session.get(DossierClaim, data["claims"][0]["id"])
            if kind == "claim_status":
                claim.status = "SUPPORTED"
            else:
                claim.statement = "PRIVATE revised statement must not survive"
        elif kind == "mixed":
            source = extra_source(session, run, private=True)
            session.add(
                ClaimEvidence(
                    **scope(run),
                    claim_id=data["claims"][0]["id"],
                    source_id=source.id,
                    relation="SUPPORTS",
                    quote=source.snapshot["excerpts"][0]["text"],
                    locator="p1",
                )
            )
        elif kind == "question":
            state = deepcopy(run.research_state)
            next(
                q for q in state["questions"] if q["id"] == data["question_renewal_targets"][0]["question_id"]
            )["purpose"] = "A different purpose changed during final assessment."
            run.research_state = state
        session.commit()


@pytest.mark.parametrize("kind", ["source", "hash", "claim_status", "claim_text", "mixed", "question"])
def test_inflight_context_change_cannot_store_renewal(signed, monkeypatch, kind):
    client, service, identity, _ = signed
    root, run, _, observed, before = configured(
        signed, monkeypatch, callback=lambda data: change(service, identity, data, kind)
    )
    final = complete(client, service, root + "/investigations", run)
    assert observed and before and final["exploration"]["briefing"] is None
    assert final["exploration"]["next_check"] is None
    assert "PRIVATE" not in json.dumps(final["exploration"])
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        assert not any(q.get("branch_assessment_history") for q in saved.research_state["questions"])


@pytest.mark.parametrize("when", ["after", "queued", "during_search"])
def test_later_context_change_hides_renewal_and_fences_descendants(signed, monkeypatch, when):
    client, service, identity, model = signed
    root, run, trace, observed, _ = configured(signed, monkeypatch)
    old = complete(client, service, root + "/investigations", run)
    assert old["exploration"]["next_check"]
    body = command(old)
    if when != "after":
        assessment_adapters(monkeypatch, model, trace, old, "partial")
        child = post(client, url(root, old), body).json()
        if when == "during_search":
            search = decision_search.federated_retrieve

            async def changed_search(*args):
                result = await search(*args)
                change(service, identity, observed[0], "claim_status")
                return result

            monkeypatch.setattr(decision_search, "federated_retrieve", changed_search)
        else:
            change(service, identity, observed[0], "claim_status")
        final = complete(client, service, root + "/investigations", child)
        assert final["status"] == "paused" and not final["sources"]
        replay = post(client, url(root, old), body)
        assert replay.status_code == 202 and replay.json()["id"] == child["id"]
    else:
        change(service, identity, observed[0], "claim_status")
        assert post(client, url(root, old), body).status_code == 409
    final = client.get(root + "/investigations/" + run["id"]).json()
    assert final["exploration"]["status"] == "evidence_changed"
    assert final["exploration"]["briefing"] is None and final["exploration"]["next_check"] is None
    assert final["exploration"]["question_assessments"]["status"] == "evidence_changed"


def test_unrelated_private_source_never_enters_renewal_or_history(signed, monkeypatch):
    client, service, _, _ = signed
    root, run, _, observed, _ = configured(signed, monkeypatch)
    tick(service, run["id"])
    with service.db.session() as session:
        extra_source(session, session.get(Investigation, run["id"]), private=True)
        session.commit()
    final = complete(client, service, root + "/investigations", run)
    assert final["exploration"]["question_assessments"]["assessments"][0]["stage"] == "final_briefing"
    assert "PRIVATE CANARY" not in json.dumps(observed)
    assert "PRIVATE CANARY" not in json.dumps(final["exploration"])
