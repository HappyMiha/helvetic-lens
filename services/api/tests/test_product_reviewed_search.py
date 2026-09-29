"""Current human decisions beside fictional search evidence, never model truth."""
import json
from uuid import uuid4

import pytest
from test_product_claim_review import body, item, link, seed
from test_product_corpus_search import complete, encoder
from test_product_dossiers import post
from test_product_dossiers import signed as signed
from test_product_evidence_search import local, search

from helvetic_lens.product_investigation_models import ClaimChange, DossierClaim, InvestigationSource
from helvetic_lens.product_models import DossierEntry


def results(client, root, mode="literal"):
    if mode == "corpus":
        return complete(client, root, query="Fictional")[0]
    response = search(client, root, query="Fictional", mode=mode)
    assert response.status_code == 200, response.text
    return response.json()


def check(client, root, page, **changes):
    return search(client, root, query=page["query"], mode=page["mode"], check_only=True,
        as_of=page["as_of"], offset=page["offset"], fingerprint=page["fingerprint"],
        **{**{key: page[key] for key in ("review_claim_ids", "review_fingerprint")}, **changes})


def finding(page, identifier):
    return next(row for row in page["items"] if row["claim_id"] == identifier)


@pytest.mark.parametrize("product", ["pharma", "loyer"])
@pytest.mark.parametrize("mode", ["literal", "semantic", "corpus"])
def test_search_keeps_separate_current_review_and_every_original_citation(signed, monkeypatch, product, mode):
    client, service, _, root, ids, _, _, _, _ = seed(signed, product=product)
    calls = local(monkeypatch, service)
    vectors = encoder(monkeypatch, service)
    page = results(client, root, mode)
    assert finding(page, ids[0])["human_review"]["human_status"] == "PROPOSED"
    original = {row["id"]: row["quote"] for row in page["items"]}
    for decision, status in [("accepted", "ACCEPTED"), ("dismissed", "REJECTED"), ("needs_more_evidence", "UNRESOLVED")]:
        saved = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]),
            decision=decision, reason="Private explanation is never used for search inference."))
        assert saved.status_code == 200, saved.text
        before = len(calls), len(vectors)
        assert check(client, root, page).status_code == 409
        assert (len(calls), len(vectors)) == before, "Freshness checks never invoke models"
        updated = results(client, root, mode)
        review = finding(updated, ids[0])["human_review"]
        assert review["human_status"] == status and not review["stale"]
        assert review["revision"] == saved.json()["revision"] and review["has_conflicting_evidence"]
        assert finding(updated, ids[0])["claim_status"] == "CONTESTED"
        assert {r["citation_relation"] for r in updated["items"] if r["claim_id"] == ids[0]} == {"SUPPORTS", "CONTRADICTS"}
        assert {row["id"]: row["quote"] for row in updated["items"]} == original
        assert updated["fingerprint"] == page["fingerprint"] and updated["review_fingerprint"] != page["review_fingerprint"]
        assert check(client, root, updated).json() == {"current": True}
        if mode == "corpus":
            assert len(vectors) == before[1] + 1 and vectors[-1] == ["query: Fictional"], "Text vectors remain reusable, no cached human decision"
        assert "Private explanation" not in json.dumps(updated)
        page = updated
    assert "human_review" not in json.dumps(calls) and "Private explanation" not in json.dumps(calls + vectors)
    assert signed[3].calls == []


@pytest.mark.parametrize("change", ["comparison", "comparison_review", "capture_metadata", "hidden_dependency", "claim_revision"])
def test_search_review_fence_tracks_evidence_not_only_reviewer_revision(signed, change):
    client, service, doc, root, ids, sources, runs, _, evidence = seed(signed)
    if change in {"comparison_review", "hidden_dependency"}:
        with service.db.session() as session:
            change_id = link(session, runs, ids, evidence)
    saved = post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]), reason="Private related-source interpretation."))
    assert saved.status_code == 200
    page = results(client, root)
    with service.db.session() as session:
        if change == "comparison":
            link(session, runs, ids, evidence)
        elif change == "comparison_review":
            row = session.get(ClaimChange, change_id)
            row.status, row.revision = "dismissed", 2
        elif change == "capture_metadata":
            source = session.get(InvestigationSource, sources[0])
            source.snapshot = {**source.snapshot, "correction": "Additional recorded context"}
        elif change == "claim_revision":
            session.get(DossierClaim, ids[0]).revision += 1
        else:
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()),
                url=session.get(InvestigationSource, sources[1]).url, data_json={"decision": "exclude", "revision": 1}))
        session.commit()
    assert check(client, root, page).status_code == 409
    current = results(client, root)
    review = finding(current, ids[0])["human_review"]
    assert review["stale"] and review["human_status"] == "UNRESOLVED" and review["revision"] == 1
    assert review["stale"] == item(client, root, ids[0])["stale"]
    assert "Private related-source" not in json.dumps(current)
    assert check(client, root, current).status_code == 200


def test_projection_cannot_read_foreign_public_or_unavailable_claims_and_bounds(signed):
    client, service, doc, root, ids, _, _, _, _ = seed(signed)
    page = results(client, root)
    _, _, _, _, foreign, _, _, _, _ = seed(signed)
    _, _, _, _, public, _, _, _, _ = seed(signed, public=True)
    for identifier in [foreign[0], public[0], str(uuid4())]:
        response = check(client, root, page, review_claim_ids=[identifier])
        assert response.status_code == 409 and "statement" not in response.text
    assert check(client, root, page, review_claim_ids=[str(uuid4()) for _ in range(13)]).status_code == 422
    assert check(client, root, page, review_claim_ids=["invalid"]).status_code == 422
    assert check(client, root, page, review_fingerprint=None).status_code == 422
    assert search(client, root, query="Fictional", mode="literal", review_fingerprint=page["review_fingerprint"]).status_code == 422
    # Existing clients retain the original check contract, without human state.
    assert search(client, root, query=page["query"], mode=page["mode"], check_only=True,
        as_of=page["as_of"], fingerprint=page["fingerprint"]).json() == {"current": True}
    client.cookies.clear()
    assert client.post(root + "/evidence-search", json={"query": "Fictional", "mode": "literal"}).status_code == 401


def test_latest_review_after_local_ranking_does_not_reuse_old_acceptance(signed, monkeypatch):
    from helvetic_lens.product_claim_review import context
    from helvetic_lens.product_investigation_models import ClaimReview

    client, service, _, root, ids, _, _, _, _ = seed(signed)
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]))).status_code == 200
    def change(count):
        if count == 1:
            # Simulate a committed concurrent editor transaction; TestClient
            # cannot recursively call its own running event-loop portal.
            with service.db.session() as session:
                claim = session.get(DossierClaim, ids[0])
                current = context(session, claim)
                session.add(ClaimReview(investigation_id=claim.investigation_id, dossier_id=claim.dossier_id,
                    organization_id=claim.organization_id, claim_id=claim.id, decision="dismissed", revision=2,
                    reason="Concurrent fictional review", evidence_fingerprint=current["evidence_fingerprint"],
                    basis=current["basis"], reviewed_by_user_id=signed[2]["user"]["id"],
                    request_key=str(uuid4()), request_fingerprint="c" * 64))
                session.commit()
    local(monkeypatch, service, hook=change)
    page = results(client, root, "semantic")
    review = finding(page, ids[0])["human_review"]
    assert review["human_status"] == "REJECTED" and review["revision"] == 2
    assert check(client, root, page).status_code == 200


def test_unreviewable_or_partial_context_is_not_presented_as_accepted(signed):
    from sqlalchemy import select

    from helvetic_lens.product_investigation_models import ClaimEvidence

    client, service, _, root, ids, _, _, _, evidence = seed(signed)
    assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[0]))).status_code == 200
    page = results(client, root)
    with service.db.session() as session:
        citation = session.get(ClaimEvidence, evidence[0])
        for _ in range(100):
            session.add(ClaimEvidence(investigation_id=citation.investigation_id, dossier_id=citation.dossier_id,
                organization_id=citation.organization_id, claim_id=ids[0], source_id=citation.source_id,
                relation="CONTEXT", quote=citation.quote, locator=citation.locator))
        session.commit()
    assert check(client, root, page).status_code == 409
    current = results(client, root)
    review = finding(current, ids[0])["human_review"]
    assert not review["complete"] and not review["reviewable"] and review["stale"]
    assert review["human_status"] == "UNRESOLVED"
    with service.db.session() as session:
        assert session.scalar(select(DossierClaim).where(DossierClaim.id == ids[0])).status == "CONTESTED"


def test_native_page_correction_invalidates_search_review_without_rewriting_quote(signed, monkeypatch):
    from test_product_contributions import no_discovery
    from test_product_document_history import setup
    from test_product_investigations import complete as finish
    from test_product_monitoring_research import due, enable, model
    from test_product_page_research import changed, last_run

    from helvetic_lens.models import Version

    client, service, _, target = signed
    _, root, law_id, _, _ = setup(client)
    enable(client, root, include_page_changes=True)
    model(monkeypatch, target)
    external = no_discovery(monkeypatch)
    version_id = changed(client, service, law_id, "Fictional demonstration registry now lists six example entries.")
    assert due(service)["started"] == 1
    run = finish(client, service, root + "/investigations", last_run(client, root))
    claim_id = run["claims"][0]["id"]
    assert post(client, root + "/claim-reviews/review", body(item(client, root, claim_id))).status_code == 200
    page = results(client, root)
    quote = finding(page, claim_id)["quote"]
    with service.db.session() as session:
        session.get(Version, version_id).evidence_revision += 1
        session.commit()
    assert check(client, root, page).status_code == 409
    current = finding(results(client, root), claim_id)
    assert current["human_review"]["stale"] and not current["human_review"]["reviewable"]
    assert current["human_review"]["human_status"] == "UNRESOLVED" and current["quote"] == quote
    assert external == []


def test_review_read_timeout_never_returns_an_old_or_partly_decorated_result(signed, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from helvetic_lens import product_search_review

    client, _, _, root, _, _, _, _, _ = seed(signed)
    page = results(client, root)
    failure = RuntimeError("private database diagnostics")
    failure.sqlstate = "57014"
    def unavailable(*args):
        raise OperationalError("sensitive query", {}, failure)
    for operation in ("decorate", "read"):
        with monkeypatch.context() as patch:
            patch.setattr(product_search_review, operation, unavailable)
            response = check(client, root, page) if operation == "read" else search(client, root, query="Fictional", mode="literal")
            assert response.status_code == 503
            assert "time limit" in response.text
            assert "private database" not in response.text and "items" not in response.json()
    assert signed[3].calls == []
