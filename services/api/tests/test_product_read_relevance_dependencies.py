"""In-flight extraction version and current-access fences."""

import json

import pytest
from test_product_dossiers import signed as signed
from test_product_early_orientation import exclude
from test_product_exploration import start
from test_product_iterative_research import complete
from test_product_read_relevance import relevance, setup

from helvetic_lens.product_investigation_models import InvestigationSource


@pytest.mark.parametrize("mode", ["exclude_during", "change_during"])
def test_relevance_result_cannot_outlive_its_actual_model_input(signed, monkeypatch, mode):
    client, service, identity, model = signed
    changed = []

    def revoke(data):
        if changed:
            return
        source_id = data["source"]["id"]
        changed.append(source_id)
        if mode == "exclude_during":
            exclude(service, identity, source_id)
        else:
            with service.db.session() as session:
                session.get(InvestigationSource, source_id).sha256 = "changed-during-model"
                session.commit()

    trace = setup(monkeypatch, service, model, during=revoke)
    root, run, _ = start(client)
    value = complete(client, service, root + "/investigations", run)
    with service.db.session() as session:
        from helvetic_lens.product_investigation_models import Investigation, InvestigationBranch
        from helvetic_lens.product_investigations import rows

        saved = session.get(Investigation, run["id"])
        assessments = [
            a
            for b in rows(session, InvestigationBranch, saved)
            for a in b.checkpoint.get("read_relevance", {}).get("assessments", [])
        ]
        assert changed[0] not in {a["source_id"] for a in assessments}
    assert sum(d["source"]["id"] == changed[0] for d in trace["assessed_inputs"]) == 1
    if value["exploration"]["research_scope"]["status"] == "ready":
        assert changed[0] not in json.dumps(relevance(value))


def test_mixed_private_public_claim_context_is_not_sent_for_read_assessment(signed, monkeypatch):
    from uuid import uuid4

    from test_product_investigations import tick

    from helvetic_lens.product_investigation_models import ClaimEvidence, DossierClaim, Investigation
    from helvetic_lens.product_investigations import scope

    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    _, run, _ = start(client)
    with service.db.session() as session:
        saved = session.get(Investigation, run["id"])
        sources = []
        for kind in ("public_source", "uploaded_file"):
            source = InvestigationSource(
                **scope(saved),
                kind=kind,
                title="Context fixture",
                url="",
                source_key=str(uuid4()),
                sha256=kind,
                snapshot={
                    "allow_discovery": kind == "public_source",
                    "excerpts": [{"passage": "p1", "text": "A neutral context statement."}],
                },
            )
            session.add(source)
            sources.append(source)
        claim = DossierClaim(
            **scope(saved),
            statement="PRIVATE MIXED CLAIM CANARY",
            status="UNVERIFIED",
            revision=0,
            history=[],
        )
        session.add(claim)
        session.flush()
        for source in sources:
            session.add(
                ClaimEvidence(
                    **scope(saved),
                    source_id=source.id,
                    claim_id=claim.id,
                    relation="CONTEXT",
                    quote="A neutral context statement.",
                    locator="p1",
                )
            )
        session.commit()
    for _ in range(15):
        tick(service, run["id"])
        if trace["assessed_inputs"]:
            break
    assert trace["assessed_inputs"]
    assert "PRIVATE MIXED CLAIM CANARY" not in json.dumps(trace["assessed_inputs"])


def test_known_truncated_read_cannot_open_replacement_when_model_omits_limit(signed, monkeypatch):
    from helvetic_lens import decision_sources

    client, service, _, model = signed
    trace = setup(monkeypatch, service, model)
    inspect = decision_sources.safe_inspect

    async def truncated(*args, **kwargs):
        result = await inspect(*args, **kwargs)
        if "misleading" in args[2]["url"]:
            result["text_truncated"] = True
        return result

    monkeypatch.setattr(decision_sources, "safe_inspect", truncated)
    root, run, _ = start(client)
    value = complete(client, service, root + "/investigations", run)
    assert "https://example.org/identity" not in trace["attempts"]
    assessed = relevance(value)
    assert assessed["alternative_reads"] == 0
    assert all(
        "incomplete" in a["limitations"] for a in assessed["assessments"] if a["category"] == "unrelated"
    )
    assert any(d["source"]["text_truncated"] is True for d in trace["assessed_inputs"])
