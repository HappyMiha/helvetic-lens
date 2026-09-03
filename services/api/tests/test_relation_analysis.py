import asyncio
from datetime import UTC, datetime

from conftest import add_law
from sqlalchemy import select

from helvetic_lens.models import (
    Job,
    LegacyDocumentMapping,
    OrganizationRelationCandidate,
    RegulatoryRelation,
    RegulatoryWork,
    RelationCandidate,
)
from helvetic_lens.regulatory_corpus import (
    DocumentInput,
    EventInput,
    ExpressionInput,
    IdentifierInput,
    RelationInput,
    VersionInput,
)
from helvetic_lens.relation_candidates import generate_for_events


def relation_delivery(harness, *, confirmed: bool = False):
    client, _, service, _ = harness
    law = add_law(client, name="Federal Data Protection Retention Act")
    with service.db.session(include_all_organizations=True) as session:
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"])
        )
        target = session.get(RegulatoryWork, mapping.work_id)
        target.title = "Federal Data Protection Retention Act"
        target.lifecycle_status = "in_force"
        target.metadata_json = {"systematic_number": "SR 235.1", "articles": ["Art. 25"]}
        source = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="bill",
                authority="swiss_parliament",
                identifiers=(IdentifierInput("parliamentary_business_id", "20260099"),),
                title="Revision of the Data Protection Retention Act",
                stable_official_url=(
                    "https://www.parlament.ch/en/ratsbetrieb/suche-curia-vista/"
                    "geschaeft?AffairId=20260099"
                ),
                expression=ExpressionInput(
                    language="en",
                    key="affair:20260099:en",
                    version=VersionInput(
                        key="2026-09-03",
                        content_hash="a" * 64,
                        source_url=(
                            "https://www.parlament.ch/en/ratsbetrieb/suche-curia-vista/"
                            "geschaeft?AffairId=20260099"
                        ),
                        text=(
                            "The proposal introduces a documented retention review for personal data "
                            "and names Article 25 of SR 235.1."
                        ),
                        passages=(
                            {
                                "id": "bill-p1",
                                "position": 1,
                                "page": 1,
                                "text": (
                                    "Organizations processing personal data shall review retention "
                                    "periods under Article 25 of SR 235.1."
                                ),
                            },
                        ),
                        fetched_at=datetime(2026, 9, 3, 8, tzinfo=UTC),
                    ),
                ),
                metadata={"affected_norm": "SR 235.1", "articles": ["Art. 25"]},
            ),
        )
        if confirmed:
            service.regulatory_corpus.record_relation(
                session,
                RelationInput(
                    subject_work_id=source.work.id,
                    object_work_id=target.id,
                    authority="swiss_parliament",
                    relation_type="amends",
                    state="confirmed",
                    provenance_method="exact_identifier",
                    evidence={"field": "official affected act", "identifier": "SR 235.1"},
                    source_version_id=source.version.id,
                    rule_or_model_revision="official-field-v1",
                ),
            )
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=source.work.id,
                expression_id=source.expression.id,
                document_version_id=source.version.id,
                authority="swiss_parliament",
                event_type="created",
                detected_at=datetime(2026, 9, 3, 8, 5, tzinfo=UTC),
                provenance_method="official_metadata",
                source_url=source.work.stable_official_url,
                evidence={"affected_norm": "SR 235.1", "articles": ["Art. 25"]},
                connector="swiss-parliament",
            ),
        )
        generated = generate_for_events(
            session, [event], service.regulatory_corpus, service.settings
        )
        assert generated["candidates"] == 1
        candidate = session.scalar(
            select(RelationCandidate).where(RelationCandidate.event_id == event.id)
        )
        delivery = session.scalar(
            select(OrganizationRelationCandidate).where(
                OrganizationRelationCandidate.candidate_id == candidate.id,
                OrganizationRelationCandidate.organization_id == service.organization_id,
            )
        )
        relation_id = candidate.relation_id
        session.commit()
        return delivery.id, relation_id


def test_relation_impact_is_bounded_cited_cached_and_background_work(harness):
    client, _, service, model = harness
    delivery_id, relation_id = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"

    response = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs")
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["queue"] == "ai_background"
    assert job["priority"] < 8
    assert job["state"] == "succeeded"
    assert [step["state"] for step in job["steps"]] == ["succeeded"] * 3

    analysis = job["result"]["data"]
    report = analysis["result"]
    assert analysis["status"] == "succeeded"
    assert analysis["analysis_plan"]["limits"]["provider_call_budget"] == 5
    assert analysis["analysis_plan"]["estimates"]["planned_generation_calls"] == 1
    assert analysis["coverage"]["provider_calls"] <= 5
    assert report["supported"] is True
    assert report["proposed_relation_type"] == "potentially_impacts"
    assert report["potential_severity"] == "medium"
    assert report["evidence_grade"] == "possible"
    assert len(report["actions"]) == 1
    assert report["actions"][0]["owner_role"] == "Legal operations"
    assert report["actions"][0]["applicability_condition"]
    assert report["actions"][0]["due_basis"]
    assert report["actions"][0]["action_key"].startswith("act_")
    assert report["citations"]
    citation = report["citations"][0]
    evidence = client.get(citation["url"])
    assert evidence.status_code == 200
    assert evidence.json()["text"] == citation["quote"]
    assert len(model.calls) == 1

    repeated = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    assert repeated["id"] == job["id"]
    assert repeated["result"]["data"]["id"] == analysis["id"]
    assert len(model.calls) == 1

    history = client.get(f"/api/relation-candidates/{delivery_id}/analyses").json()
    assert history["total"] == 1
    assert history["current"]["id"] == analysis["id"]
    with service.db.session(include_all_organizations=True) as session:
        assert session.get(RegulatoryRelation, relation_id).state == "proposed"
        assert session.get(OrganizationRelationCandidate, delivery_id).status == "analysed"


def test_new_relation_deliveries_are_automatically_queued_without_blocking_ingestion(harness):
    _, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"

    result = asyncio.run(
        service.enqueue_pending_relation_analyses(
            [(service.organization_id, delivery_id)]
        )
    )

    assert result == {
        "candidates": 1,
        "queued": 1,
        "waiting_for_configuration": 0,
        "failed": 0,
    }
    assert model.calls == []
    with service.db.session() as session:
        job = session.scalar(
            select(Job).where(
                Job.type == "relation_impact_analysis",
                Job.target_id == delivery_id,
            )
        )
        assert job.queue == "ai_background" and job.state == "queued"


def test_relation_impact_cache_changes_with_profile_and_preserves_history(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"

    first = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    profile = client.get("/api/profile").json()
    updated = client.patch(
        "/api/profile",
        json={
            "name": profile["name"],
            "description": "Processes personal data and has a retention policy.",
            "business_areas": ["Operations"],
        },
    )
    assert updated.status_code == 200
    second = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()

    assert second["id"] != first["id"]
    assert second["result"]["data"]["id"] != first["result"]["data"]["id"]
    assert len(model.calls) == 2
    history = client.get(f"/api/relation-candidates/{delivery_id}/analyses").json()
    assert history["total"] == 2
    assert history["current"]["id"] == second["result"]["data"]["id"]


def test_relation_impact_keeps_confirmed_relation_separate_from_ai_proposal(harness):
    client, _, service, _ = harness
    delivery_id, relation_id = relation_delivery(harness, confirmed=True)
    service.settings.apertus_base_url = "https://model.example/v1"

    job = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    report = job["result"]["data"]["result"]
    assert report["official_relation"]["id"] == relation_id
    assert report["official_relation"]["type"] == "amends"
    assert report["official_relation"]["state"] == "confirmed"
    assert report["proposed_relation_type"] == "potentially_impacts"
    with service.db.session(include_all_organizations=True) as session:
        relation = session.get(RegulatoryRelation, relation_id)
        assert relation.state == "confirmed" and relation.relation_type == "amends"


def test_relation_impact_rejects_out_of_range_citations_and_keeps_evidence(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"
    model.invalid = True

    job = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    assert job["state"] == "retrying"
    history = client.get(f"/api/relation-candidates/{delivery_id}/analyses").json()
    failed = history["latest_attempt"]
    assert failed["status"] == "failed"
    assert failed["result"] is None
    assert failed["evidence_count"] > 0
    assert failed["analysis_plan"]["state"] == "failed"
    assert len(model.calls) == 2

    with service.db.session() as session:
        context = service._relation_analysis_context(session, delivery_id, "test-runtime")
    saved_evidence_id = context["evidence"][0]["evidence_id"]
    evidence = client.get(
        f"/api/relation-analyses/{failed['id']}/evidence/{saved_evidence_id}"
    )
    assert evidence.status_code == 200


def test_unsupported_relation_conclusion_is_saved_without_actions(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"
    model.unsupported = True

    job = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    report = job["result"]["data"]["result"]
    assert job["state"] == "succeeded"
    assert report["supported"] is False
    assert report["potential_severity"] == "none"
    assert report["proposed_relation_type"] is None
    assert report["actions"] == []
    assert report["citations"] == []


def test_small_local_model_shape_is_safely_completed_from_valid_action_rows(harness):
    client, _, service, model = harness
    delivery_id, _ = relation_delivery(harness)
    service.settings.apertus_base_url = "https://model.example/v1"
    model.relation_compact = True

    job = client.post(f"/api/relation-candidates/{delivery_id}/analyse-jobs").json()
    analysis = job["result"]["data"]
    report = analysis["result"]

    assert job["state"] == "succeeded"
    assert report["proposed_relation_type"] == "potentially_impacts"
    assert report["evidence_grade"] == "possible"
    assert report["citations"]
    assert report["actions"] == []
    assert "Revision of the Data Protection Retention Act" in report["explanation"]
    assert analysis["evidence_count"] >= 5
