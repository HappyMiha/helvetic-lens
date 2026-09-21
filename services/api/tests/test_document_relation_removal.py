"""Explicit document deletion clears only its own related-history dependencies."""
import pytest
from sqlalchemy import select
from test_relation_profile_freshness import analyse

from helvetic_lens import jobs
from helvetic_lens.models import (
    DocumentWatch,
    Law,
    Organization,
    OrganizationRelationCandidate,
    OrganizationRelationReview,
    RegulatoryWork,
    RelationCandidate,
    RelationImpactAnalysis,
    Version,
)


@pytest.mark.parametrize("shared", [False, True])
def test_remove_document_with_related_history_preserves_other_workspace(harness, shared):
    client, _, service, model = harness
    delivery_id, saved = analyse(harness)
    other_watch_id = other_delivery_id = other_review_id = None
    with service.db.session(include_all_organizations=True) as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        watch = session.get(DocumentWatch, delivery.watch_id)
        law = session.get(Law, watch.law_id)
        law_id, watch_id = law.id, watch.id
        version_id = law.current_version_id
        own_review = OrganizationRelationReview(organization_id=service.organization_id,
            organization_candidate_id=delivery_id, decision="annotated", note="Synthetic local review")
        session.add(own_review)
        if shared:
            law.owner_organization_id = None
            session.get(Version, version_id).owner_organization_id = None
            session.get(RegulatoryWork, saved["target_work_id"]).owner_organization_id = None
            other = Organization(name="Other synthetic workspace", slug="other-removal-test")
            session.add(other)
            session.flush()
            other_watch = DocumentWatch(organization_id=other.id, law_id=law_id, display_name="Other watch")
            session.add(other_watch)
            session.flush()
            other_delivery = OrganizationRelationCandidate(organization_id=other.id,
                candidate_id=delivery.candidate_id, watch_id=other_watch.id)
            session.add(other_delivery)
            session.flush()
            other_review = OrganizationRelationReview(organization_id=other.id,
                organization_candidate_id=other_delivery.id, decision="annotated", note="Keep this other review")
            session.add(other_review)
            session.flush()
            other_watch_id, other_delivery_id, other_review_id = other_watch.id, other_delivery.id, other_review.id
        session.flush()
        own_review_id = own_review.id
        session.commit()
    response = client.delete(f"/api/laws/{law_id}")
    assert response.status_code == 200, response.text
    assert response.json()["relation_deliveries"] == 1
    assert client.get(f"/api/laws/{law_id}").status_code == 404
    with service.db.session(include_all_organizations=True) as session:
        assert session.get(DocumentWatch, watch_id) is None
        assert session.get(OrganizationRelationCandidate, delivery_id) is None
        assert session.get(OrganizationRelationReview, own_review_id) is None
        assert session.get(RelationImpactAnalysis, saved["id"]) is None
        assert session.get(RelationCandidate, saved["candidate_id"]) is not None
        if shared:
            assert response.json()["shared_corpus_retained"]
            assert session.get(Law, law_id) is not None and session.get(Version, version_id) is not None
            assert session.get(DocumentWatch, other_watch_id) is not None
            assert session.get(OrganizationRelationCandidate, other_delivery_id) is not None
            assert session.get(OrganizationRelationReview, other_review_id).note == "Keep this other review"
        else:
            assert session.get(Law, law_id) is None
    assert len(model.calls) == 1


@pytest.mark.parametrize("state", ["queued", "running"])
def test_active_related_analysis_blocks_removal_without_losing_history(harness, state):
    client, _, service, _ = harness
    delivery_id, saved = analyse(harness)
    with service.db.session() as session:
        delivery = session.get(OrganizationRelationCandidate, delivery_id)
        watch = session.get(DocumentWatch, delivery.watch_id)
        law_id = watch.law_id
        job, _ = jobs.enqueue(session, job_type="relation_impact_analysis",
            target_type="organization_relation_candidate", target_id=delivery_id,
            queue="ai_background", idempotency_key="synthetic-active-removal-test")
        job.state = state
        session.commit()
    response = client.delete(f"/api/laws/{law_id}")
    assert response.status_code == 409 and response.json()["code"] == "job_in_progress"
    assert client.get(f"/api/laws/{law_id}").status_code == 200
    with service.db.session() as session:
        assert session.get(RelationImpactAnalysis, saved["id"]).result == saved["result"]
        assert session.scalar(select(OrganizationRelationCandidate.id).where(
            OrganizationRelationCandidate.id == delivery_id)) == delivery_id
