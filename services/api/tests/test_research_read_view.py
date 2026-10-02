"""Fresh rights and human-review decisions between read-only projections."""
from copy import deepcopy

import pytest
from test_product_claim_review import body, item, seed
from test_product_dossiers import post
from test_product_dossiers import signed as signed

from helvetic_lens import product_claim_review as reviews
from helvetic_lens.product_investigation_models import DossierClaim, InvestigationSource
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
