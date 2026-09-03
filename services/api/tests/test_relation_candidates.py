from datetime import UTC, datetime

import pytest
from conftest import add_law
from sqlalchemy import func, select

from helvetic_lens.models import (
    DocumentWatch,
    LegacyDocumentMapping,
    Organization,
    OrganizationRelationCandidate,
    RegulatoryIdentifier,
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
)
from helvetic_lens.relation_candidates import generate_for_events, score_candidate


@pytest.mark.parametrize(
    ("source", "target", "source_kind", "expected"),
    [
        ("Revision of the Data Protection Act", "Federal Data Protection Act", "bill", True),
        ("Repeal of the Epidemics Ordinance", "Epidemics Ordinance", "bill", True),
        ("Initiative for transparent procurement", "Public Procurement Act", "initiative", True),
        ("Decision on employee data retention", "Employee Data Retention Act", "court_decision", True),
        ("Notice concerning energy subsidies", "Energy Subsidies Act", "official_notice", True),
        ("Agricultural direct payments", "Telecommunications surveillance", "bill", False),
    ],
)
def test_labelled_candidate_recall_and_noise(source, target, source_kind, expected):
    score = score_candidate(
        source,
        target,
        source_authority="swiss_parliament",
        target_authority="fedlex",
        source_kind=source_kind,
        target_kind="act",
    )
    assert (score is not None) is expected


def test_candidates_are_shared_explainable_bounded_and_idempotent(harness):
    client, _, service, _ = harness
    law = add_law(client, name="Federal Data Protection Retention Act")
    now = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
    with service.db.session(include_all_organizations=True) as session:
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"])
        )
        target = session.get(RegulatoryWork, mapping.work_id)
        target.title = "Federal Data Protection Retention Act"
        target.metadata_json = {"norms": ["SR 235.1"], "articles": ["Art. 25"]}
        second_org = Organization(name="Second workspace", slug="second-candidates")
        session.add(second_org)
        session.flush()
        second_watch = DocumentWatch(
            organization_id=second_org.id,
            law_id=law["id"],
            display_name=target.title,
            active=True,
        )
        session.add(second_watch)

        source = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="bill",
                authority="swiss_parliament",
                identifiers=(IdentifierInput("parliament_affair_id", "20260099"),),
                title="Revision of the Data Protection Retention Act",
                stable_official_url="https://www.parlament.ch/example/20260099",
                expression=ExpressionInput("en", "affair:20260099"),
                metadata={"norms": ["SR 235.1"], "articles": ["Art. 25"]},
            ),
        )
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=source.work.id,
                authority="swiss_parliament",
                event_type="created",
                detected_at=now,
                provenance_method="official_metadata",
                source_url="https://www.parlament.ch/example/20260099",
                evidence={"source": "official affair catalogue"},
                connector="swiss-parliament",
            ),
        )
        session.flush()
        constrained = service.settings.model_copy(
            update={
                "relation_candidates_per_event": 5,
                "relation_candidates_per_organization": 1,
            }
        )
        first = generate_for_events(
            session, [event], service.regulatory_corpus, constrained
        )
        second = generate_for_events(
            session, [event], service.regulatory_corpus, constrained
        )
        session.commit()

        assert first == {"candidates": 1, "deliveries": 2, "expired": 0}
        assert second == {"candidates": 0, "deliveries": 0, "expired": 0}
        candidate = session.scalar(select(RelationCandidate))
        relation = session.get(RegulatoryRelation, candidate.relation_id)
        assert candidate.source_version_id is None
        assert candidate.target_version_id is not None
        assert candidate.score_components_json["title_overlap"] > 0
        assert candidate.score_components_json["norm_reference"] > 0
        assert candidate.why_json
        assert candidate.rule_revision == "relation-candidate-v1"
        assert candidate.expires_at.date() > now.date()
        assert relation.state == "proposed"
        assert relation.relation_type == "potentially_impacts"
        assert relation.evidence_json["candidate_only"] is True
        assert candidate.evidence_json["similarity_is_not_evidence"] is True
        assert session.scalar(
            select(func.count()).select_from(OrganizationRelationCandidate)
        ) == 2


def test_confirmed_exact_relation_is_reused_as_the_candidate_evidence(harness):
    client, _, service, _ = harness
    law = add_law(client, name="Epidemics Act")
    with service.db.session(include_all_organizations=True) as session:
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"])
        )
        target = session.get(RegulatoryWork, mapping.work_id)
        source = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="bill",
                authority="swiss_parliament",
                identifiers=(IdentifierInput("parliament_affair_id", "20260101"),),
                title="Epidemics Act amendment",
                expression=ExpressionInput("en", "affair:20260101"),
            ),
        )
        confirmed = service.regulatory_corpus.record_relation(
            session,
            RelationInput(
                subject_work_id=source.work.id,
                object_work_id=target.id,
                authority="swiss_parliament",
                relation_type="amends",
                state="confirmed",
                provenance_method="exact_identifier",
                evidence={"field": "official affected act", "identifier": target.canonical_key},
                rule_or_model_revision="official-field-v1",
            ),
        )
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=source.work.id,
                authority="swiss_parliament",
                event_type="created",
                detected_at=datetime.now(UTC),
                provenance_method="official_metadata",
                source_url="https://www.parlament.ch/example/20260101",
                evidence={"field": "updated"},
                connector="swiss-parliament",
            ),
        )
        generate_for_events(session, [event], service.regulatory_corpus, service.settings)
        session.commit()
        candidate = session.scalar(
            select(RelationCandidate).where(RelationCandidate.event_id == event.id)
        )
        assert candidate.relation_id == confirmed.id
        assert candidate.score == 1.0
        assert candidate.evidence_json["relation_state"] == "confirmed"
        assert candidate.evidence_json["similarity_is_not_evidence"] is False


def test_cross_language_exact_norm_reference_seeds_candidate_retrieval(harness):
    client, _, service, _ = harness
    law = add_law(client, name="Bundesgesetz über den Datenschutz")
    with service.db.session(include_all_organizations=True) as session:
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"])
        )
        target = session.get(RegulatoryWork, mapping.work_id)
        target.title = "Bundesgesetz über den Datenschutz"
        target.metadata_json = {"systematic_number": "SR 235.1"}
        session.add(
            RegulatoryIdentifier(
                work_id=target.id,
                authority=target.authority,
                scheme="sr_rs",
                value="235.1",
                normalized_value="235.1",
                source_url="https://fedlex.data.admin.ch/eli/cc/2022/491",
            )
        )
        source = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="bill",
                authority="swiss_parliament",
                identifiers=(IdentifierInput("parliament_affair_id", "20260123"),),
                title="Révision des obligations numériques",
                expression=ExpressionInput("fr", "affair:20260123"),
                metadata={"affected_norm": "RS 235.1"},
            ),
        )
        event = service.regulatory_corpus.record_event(
            session,
            EventInput(
                work_id=source.work.id,
                authority="swiss_parliament",
                event_type="created",
                detected_at=datetime.now(UTC),
                provenance_method="official_metadata",
                evidence={"affected_norm": "RS 235.1"},
                connector="swiss-parliament",
                source_url="https://www.parlament.ch/fr/20260123",
            ),
        )
        result = generate_for_events(session, [event], service.regulatory_corpus, service.settings)
        session.commit()
        candidate = session.scalar(
            select(RelationCandidate).where(RelationCandidate.event_id == event.id)
        )
        assert result["candidates"] == 1
        assert candidate.target_work_id == target.id
        assert candidate.score_components_json["norm_reference"] > 0
