"""Fresh rights and human-review decisions between read-only projections."""
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_claim_review import body, item, link, seed
from test_product_dossiers import post
from test_product_dossiers import signed as signed

from helvetic_lens import product_claim_review as reviews
from helvetic_lens.product_investigation_models import DossierClaim, InvestigationSource
from helvetic_lens.product_models import DossierEntry, ProductPublication
from helvetic_lens.research_read_view import read_view


def test_read_views_keep_current_reviews_and_evidence_after_mutation_or_failure(signed):
    client, service, _, root, ids, sources, _, _, _ = seed(signed)

    @read_view
    def render(session, claim, *, fail=False):
        first = reviews.projection(session, claim)
        first["human_status"] = "LOCAL PRESENTATION CHANGE"
        current = reviews.context(session, claim)
        unavailable = {**deepcopy(current), "reviewable": False}
        assert not reviews.projection(session, claim, current=unavailable)["reviewable"]
        result = reviews.projection(session, claim)
        assert result["human_status"] != first["human_status"]
        if fail:
            raise ValueError("Rendering interrupted")
        return result

    with service.db.session() as session:
        claim = session.get(DossierClaim, ids[1])
        revision = claim.revision
        assert render(session, claim)["human_status"] == "PROPOSED"
        assert post(client, root + "/claim-reviews/review", body(item(client, root, ids[1]))).status_code == 200
        session.rollback()
        assert claim.revision == revision  # Human review changes without a claim revision.
        assert render(session, claim)["human_status"] == "ACCEPTED"
        with pytest.raises(ValueError, match="Rendering interrupted"):
            render(session, claim, fail=True)
        source = session.get(InvestigationSource, sources[1])
        source.snapshot = {**source.snapshot, "excerpts": []}
        session.commit()
        outside = reviews.projection(session, claim)
        assert not outside["reviewable"] and outside["human_status"] == "UNRESOLVED"
        assert render(session, claim) == outside


@pytest.mark.parametrize("public", [False, True])
def test_shared_comparison_query_keeps_claim_bindings_and_fresh_visibility(signed, public):
    _, service, doc, _, ids, sources, runs, publication, evidence = seed(signed, public=public)

    def contexts(session, claims, publication):
        return [reviews.context(session, claim, publication) for claim in claims]

    render = read_view(contexts)
    with service.db.session() as session:
        change_id = link(session, runs, ids, evidence)
        claims = [session.get(DossierClaim, key) for key in ids]
        publication = session.get(ProductPublication, publication["id"]) if public else None
        plain = contexts(session, claims, publication)
        assert render(session, claims, publication) == plain
        assert [row["claim"]["id"] for row in plain] == ids
        assert [row["comparisons"][0]["id"] for row in plain] == [change_id, change_id]
        assert [row["comparisons"][0]["direction"] for row in plain] == ["later", "earlier"]
        if public:
            publication.revision += 1
        else:
            source = session.get(InvestigationSource, sources[1])
            session.add(DossierEntry(dossier_id=doc["id"], kind="source_review", request_key=str(uuid4()),
                url=source.url, body="Exclude fictional source", data_json={"decision": "exclude", "revision": 1}))
        session.commit()
        current = render(session, claims, publication)
        assert current == contexts(session, claims, publication)
        assert all(row["comparisons"] == [] for row in current)
