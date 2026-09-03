from datetime import UTC, datetime

import pytest
from conftest import add_law
from sqlalchemy import func, select

from helvetic_lens.config import DomainError
from helvetic_lens.models import (
    LegacyDocumentMapping,
    RegulatoryDate,
    RegulatoryEvent,
    RegulatoryExpression,
    RegulatoryRelation,
    RegulatoryWork,
)
from helvetic_lens.regulatory_corpus import (
    DateInput,
    DocumentInput,
    EventInput,
    ExpressionInput,
    IdentifierInput,
    RelationInput,
    VersionInput,
)


def federal_act(language="de", expression_key="fedlex:de:101", version_key="2026-01-01"):
    return DocumentInput(
        kind="act",
        authority="fedlex",
        identifiers=(
            IdentifierInput("eli_uri", "https://fedlex.data.admin.ch/eli/cc/1999/404"),
            IdentifierInput("sr_rs", "101"),
        ),
        title="Bundesverfassung",
        stable_official_url="https://fedlex.data.admin.ch/eli/cc/1999/404",
        expression=ExpressionInput(
            language=language,
            key=expression_key,
            title="Bundesverfassung" if language == "de" else "Constitution fédérale",
            official_url=f"https://fedlex.data.admin.ch/eli/cc/1999/404/{language}",
            version=VersionInput(
                key=version_key,
                content_hash=(language[0] * 64),
                source_url=f"https://fedlex.data.admin.ch/eli/cc/1999/404/{language}/pdf-a",
                fetched_at=datetime(2026, 9, 3, 8, tzinfo=UTC),
            ),
        ),
        dates=(
            DateInput(
                target="version",
                kind="version_date",
                value=version_key,
                precision="day",
                provenance="fedlex_jolux",
                source_url="https://fedlex.data.admin.ch/eli/cc/1999/404",
            ),
        ),
    )


def test_retry_and_second_language_merge_into_one_canonical_work(harness):
    client, _, service, _ = harness
    with service.db.session() as session:
        first = service.regulatory_corpus.merge_document(session, federal_act())
        retry = service.regulatory_corpus.merge_document(session, federal_act())
        french = service.regulatory_corpus.merge_document(
            session,
            federal_act(language="fr", expression_key="fedlex:fr:101", version_key="2026-01-01"),
        )
        session.commit()

        assert first.created_work is True
        assert retry.created_work is False
        assert retry.created_expression is False
        assert retry.created_version is False
        assert french.work.id == first.work.id
        assert french.created_expression is True
        assert session.scalar(select(func.count()).select_from(RegulatoryWork)) == 1
        assert session.scalar(select(func.count()).select_from(RegulatoryExpression)) == 2
        assert session.scalar(select(func.count()).select_from(RegulatoryDate)) == 2

    listing = client.get("/api/corpus/works")
    assert listing.status_code == 200
    assert listing.json()[0]["languages"] == ["de", "fr"]
    detail = client.get(f"/api/corpus/works/{first.work.id}")
    assert detail.status_code == 200
    assert len(detail.json()["versions"]) == 2


def test_events_require_evidence_and_connector_retry_is_idempotent(harness):
    _, _, service, _ = harness
    now = datetime(2026, 9, 3, 9, tzinfo=UTC)
    with service.db.session() as session:
        merged = service.regulatory_corpus.merge_document(session, federal_act())
        data = EventInput(
            work_id=merged.work.id,
            expression_id=merged.expression.id,
            document_version_id=merged.version.id,
            authority="fedlex",
            event_type="new_version",
            detected_at=now,
            provenance_method="official_metadata",
            source_url="https://fedlex.data.admin.ch/eli/cc/1999/404",
            evidence={"feed_entry": "entry-42", "version": "2026-01-01"},
            external_key="feed:entry-42:new-version",
        )
        first = service.regulatory_corpus.record_event(session, data)
        retry = service.regulatory_corpus.record_event(session, data)
        assert retry.id == first.id
        assert session.scalar(select(func.count()).select_from(RegulatoryEvent)) == 1

        with pytest.raises(DomainError) as error:
            service.regulatory_corpus.record_event(
                session,
                EventInput(
                    work_id=merged.work.id,
                    authority="fedlex",
                    event_type="repealed",
                    detected_at=now,
                    provenance_method="official_metadata",
                    source_url="https://fedlex.data.admin.ch/eli/cc/1999/404",
                    evidence={},
                ),
            )
        assert error.value.code == "regulatory_event_evidence_required"


def test_relations_are_evidence_backed_idempotent_and_versioned(harness):
    _, _, service, _ = harness
    with service.db.session() as session:
        source = service.regulatory_corpus.merge_document(session, federal_act())
        target = service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="ordinance",
                authority="fedlex",
                identifiers=(IdentifierInput("sr_rs", "101.1"),),
                title="Test ordinance",
                expression=ExpressionInput(language="de", key="fedlex:de:101.1"),
            ),
        )
        proposed_data = RelationInput(
            subject_work_id=source.work.id,
            object_work_id=target.work.id,
            source_version_id=source.version.id,
            authority="helvetic_lens",
            relation_type="potentially_impacts",
            state="proposed",
            provenance_method="model_proposal",
            evidence={"version_id": source.version.id, "passage_ids": ["art-1"]},
            confidence=0.71,
            rule_or_model_revision="apertus-v1:prompt-3",
        )
        proposed = service.regulatory_corpus.record_relation(session, proposed_data)
        retry = service.regulatory_corpus.record_relation(session, proposed_data)
        confirmed = service.regulatory_corpus.record_relation(
            session,
            RelationInput(
                **{
                    **proposed_data.__dict__,
                    "state": "confirmed",
                    "provenance_method": "human_review",
                    "supersedes_relation_id": proposed.id,
                }
            ),
        )
        session.commit()

        assert retry.id == proposed.id
        assert confirmed.id != proposed.id
        assert confirmed.supersedes_relation_id == proposed.id
        assert session.scalar(select(func.count()).select_from(RegulatoryRelation)) == 2


def test_legacy_url_law_remains_readable_with_explicit_provisional_mapping(harness):
    client, _, service, _ = harness
    law = add_law(client)
    detail_before = client.get(f"/api/laws/{law['id']}")
    assert detail_before.status_code == 200

    with service.db.session() as session:
        mapping = session.scalar(
            select(LegacyDocumentMapping).where(LegacyDocumentMapping.law_id == law["id"])
        )
        assert mapping is not None
        assert mapping.mapping_status == "provisional"
        work_id = mapping.work_id

    corpus = client.get(f"/api/corpus/works/{work_id}")
    assert corpus.status_code == 200
    assert corpus.json()["legacy_mappings"][0]["mapping_status"] == "provisional"
    assert client.get(f"/api/laws/{law['id']}").status_code == 200


def test_conflicting_authority_identifiers_do_not_silently_merge(harness):
    _, _, service, _ = harness
    with service.db.session() as session:
        service.regulatory_corpus.merge_document(session, federal_act())
        service.regulatory_corpus.merge_document(
            session,
            DocumentInput(
                kind="act",
                authority="fedlex",
                identifiers=(IdentifierInput("sr_rs", "999"),),
                expression=ExpressionInput(language="de", key="fedlex:de:999"),
            ),
        )
        with pytest.raises(DomainError) as error:
            service.regulatory_corpus.merge_document(
                session,
                DocumentInput(
                    kind="act",
                    authority="fedlex",
                    identifiers=(
                        IdentifierInput("eli_uri", "https://fedlex.data.admin.ch/eli/cc/1999/404"),
                        IdentifierInput("sr_rs", "999"),
                    ),
                    expression=ExpressionInput(language="it", key="fedlex:it:conflict"),
                ),
            )
        assert error.value.code == "regulatory_identity_conflict"
